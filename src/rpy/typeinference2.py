"""The type inference algorithms manipulate the following data structure:

ElementType: a graph node that represent the type of: a global/local variable, function parameter/return value, class attribute or temporary value.
Constraint: constraints are attached to an ElementType. Example: ElementType is an instance with an attribute named 'x'
SourceLocation: a constraint is associated to a source location (py_code object, and bytecode index)


Common variable prefix used in this module:

py_: refer to python object, such as callable, constant or code object
tit_: ElementType refined_type (for Type Inference Type)
_elements: refer to ElementType sequence

"""

from rpy.opcodedecoder import make_opcode_functions_map, opname, make_opcode_functions_map, opcode_decoder, determine_branch_targets
import sys
import rpy.rtypes as rtypes
import bisect



class FunctionLocationHelper(object):
    """Helpers that provides the location (source, line) of an opcode of a code object.
    """
    def __init__( self, py_code ):
        import dis
        self.function_name = py_code.co_name
        self.filename = py_code.co_filename
        sorted_offset_lineno = list( dis.findlinestarts( py_code ) )
        self._sorted_offsets = [ ol[0] for ol in sorted_offset_lineno ]
        self._sorted_lines = [ ol[1] for ol in sorted_offset_lineno ]

    def get_source_range( self ):
        return (self._sorted_lines[0]-1, self._sorted_lines[-1])

    def get_source( self ):
        with open( self.filename, 'rt', encoding='utf-8' ) as f:
            source = f.readlines()
        start_line, end_line = self.get_source_range()
        while 'def' not in source[start_line] and start_line > 0:
            start_line -= 1
        fn_lines = [l.rstrip() for l in source[start_line:end_line]]
        return '\n'.join( fn_lines )

    def get_location( self, opcode_index ):
        """Returns a tuple (function_name, filename, line).
        """
        offset_index = bisect.bisect_right( self._sorted_offsets,
                                            opcode_index )
        assert offset_index > 0 and offset_index <= len(self._sorted_lines)
        assert self._sorted_offsets[offset_index - 1] <= opcode_index
        line = self._sorted_lines[offset_index - 1]
        return rtypes.SourceLocation(self.function_name, self.filename, line, '')


# Primitive Type Inference Types:
TIT_UNKNOWN = 'unknown'
TIT_INTEGER = 'int'
TIT_BOOLEAN = 'boolean'
TIT_FLOAT = 'float'
TIT_COMPLEX = 'complex'
TIT_LIST = 'list'
TIT_TUPLE = 'tuple'
TIT_INSTANCE = 'instance'

# ElementType nature
FN_PARAM_NATURE = 'fn_param'
FN_RETURN_NATURE = 'fn_return'
FN_LOCAL_NATURE = 'local_var'
GLOBAL_NATURE = 'global_var'
CONSTANT_NATURE = 'constant'
ATTRIBUTE_NATURE = 'attribute'
EXPR_BINOP_NATURE = 'expr_binop'

_ALL_NATURES = (FN_PARAM_NATURE, FN_RETURN_NATURE, FN_LOCAL_NATURE,
                GLOBAL_NATURE, CONSTANT_NATURE, ATTRIBUTE_NATURE,
                EXPR_BINOP_NATURE)

_REFINERS_BY_NATURE = {}

class ElementType(object):
##    __slots__ = ('maybe_none', 'refined_type', 'name', 'index',
##                 'ti_related_fn', 'nature', 'related_element')
##    __slots__ = ('location', 'model', 'incoming_elements',
##                 '_outgoing_element', '_outgoing_elements', 'name')
    def __init__( self, nature, initial_type = TIT_UNKNOWN,
                  maybe_none = False, name=None, index=-1, ti_related_fn=None,
                  incoming=None, incomings=None,
                  outgoing=None, outgoings=None):
        """Parameters:
        maybe_none: Indicates that the element may take the value None
        initial_type: Initial type. 
        nature: *_NATURE indicating the nature of the element the type
                relate to. This value indicates how to interpret
                index, name and ti_related_fn.
        """
        self.maybe_none = maybe_none # Probably a constraint...
        self.refined_type = initial_type
        # Graph
        if incomings:
            self._incoming_elements = tuple(incomings)
        elif incoming:
            self._incoming_elements = (incoming,)
        else:
            self._incoming_elements = ()
        if outgoings:
            self._outgoing_elements = tuple(outgoings)
        elif outgoing:
            self._outgoing_elements = (outgoing,)
        else:
            self._outgoing_elements = ()
        # Validates
        for element in self.incoming_elements:
            assert element is not None
        for element in self.outgoing_elements:
            assert element is not None
        # Related element info
        self.nature = nature # Nature of the related element
        self.name = name # Name of the local variable, function parameter or attribute.
        self.index = index  # Index of the function parameter or local variable
        self.ti_related_fn = ti_related_fn # Related function for local variable or parameter, return type.
        for element in self.incoming_elements:
            element.add_outgoing_element( self )

    def short_repr( self ):
        return 'ElementType(nature=%s, function=%s, name=%s)' % (
            self.nature,
            self.ti_related_fn and self.ti_related_fn.short_repr() or '?',
            self.name )

    def type_repr( self ):
        """Returns a string that represent the type of the element."""
        t = self.refined_type
        if self.maybe_none:
            t = '(%s+None)' % t
        return t

    def __repr__( self ):
        incomings = ''.join( '- %s\n' % e.short_repr() for e in self.incoming_elements )
        outgoings = ''.join( '- %s\n' % e.short_repr() for e in self.outgoing_elements )
        return 'ElementType(nature=%s, function=%s, name=%s, incomings=[\n%s], outgoings=[\n%s])' % (
            self.nature,
            self.ti_related_fn and self.ti_related_fn.short_repr() or '?',
            self.name, incomings, outgoings )

    @property
    def incoming_elements( self ):
        return self._incoming_elements

    @property
    def outgoing_elements( self ):
        return self._outgoing_elements

    def add_outgoing_element( self, outgoing_element ):
        self._outgoing_elements += (outgoing_element,)

    def add_incoming_element( self, incoming_element ):
        self._incoming_elements += (incoming_element,)
        incoming_element.add_outgoing_element( self )

    def add_store_source( self, element_value ):
        """Adds a incoming element used to derive the type of this element.
        Parameters:
        element_value : The value of element_value ElementType is "assigned" to this ElementType.
        """
        self.add_incoming_element( element_value )
    
    def can_refine( self ):
        for element in self.incoming_elements:
            if element.refined_type == TIT_UNKNOWN:
                return False
        return True

    def refine( self, refiners=_REFINERS_BY_NATURE ):
        return refiners[self.nature](self)

    def refine_comon_incoming_types( self ):
        incoming_elements = self.incoming_elements
        if len(incoming_elements) == 1:
            self.refined_type = incoming_elements[0].refined_type
        else:
            promoted_tit = incoming_elements[0].refined_type
            for index in range(1, len(incoming_elements)):
                promoted_tit = _promote_type( promoted_tit, incoming_elements[index].refined_type )
            self.refined_type = promoted_tit

    refine_fn_return = refine_comon_incoming_types
    refine_fn_param = refine_comon_incoming_types
    refine_local_var = refine_comon_incoming_types
    refine_global_var = refine_comon_incoming_types
    refine_constant = refine_comon_incoming_types
    refine_attribute = refine_comon_incoming_types

    def refine_expr_binop( self ):
        incoming_elements = self.incoming_elements
        promoted_tit = _promote_type( incoming_elements[0].refined_type,
                                      incoming_elements[1].refined_type )
        self.refined_type = promoted_tit

_TYPE_PROMOTIONS = {
    (TIT_BOOLEAN, TIT_BOOLEAN): TIT_BOOLEAN,
    (TIT_BOOLEAN, TIT_INTEGER): TIT_INTEGER,
    (TIT_BOOLEAN, TIT_FLOAT): TIT_FLOAT,
    (TIT_BOOLEAN, TIT_COMPLEX): TIT_COMPLEX,
    (TIT_INTEGER, TIT_BOOLEAN): TIT_INTEGER,
    (TIT_INTEGER, TIT_INTEGER): TIT_INTEGER,
    (TIT_INTEGER, TIT_FLOAT): TIT_FLOAT,
    (TIT_INTEGER, TIT_COMPLEX): TIT_COMPLEX,
    (TIT_FLOAT, TIT_BOOLEAN): TIT_FLOAT,
    (TIT_FLOAT, TIT_INTEGER): TIT_FLOAT,
    (TIT_FLOAT, TIT_FLOAT): TIT_FLOAT,
    (TIT_FLOAT, TIT_COMPLEX): TIT_COMPLEX,
    (TIT_COMPLEX, TIT_BOOLEAN): TIT_COMPLEX,
    (TIT_COMPLEX, TIT_INTEGER): TIT_COMPLEX,
    (TIT_COMPLEX, TIT_FLOAT): TIT_COMPLEX,
    (TIT_COMPLEX, TIT_COMPLEX): TIT_COMPLEX
    }

def _promote_type( tit_lhs, tit_rhs ):
    key = (tit_lhs, tit_rhs)
    return _TYPE_PROMOTIONS[key]
        
def set_element_functions_map( functions_by_model ):
    """Returns a dict { opcode : function(self, oparg) }.
    """
    if not functions_by_model:
        for name in _ALL_NATURES:
            function = getattr( ElementType, 'refine_' + name )
            functions_by_model[name] = function
set_element_functions_map( _REFINERS_BY_NATURE )

class Constraint(object):
    # DEAD CODE. NEED COMPLETE REVISION
    __slots__ = ('location', 'model', 'incoming_elements',
                 '_outgoing_element', '_outgoing_elements', 'name')
    def __init__( self, location, model, incomings=(), outgoing=None, outgoings=None, name=None ):
        """Parameters:
        location: a tuple (ti_function, opcode_index)
        """
        self.location = location
        self.model = model
        self.incoming_elements = tuple(incomings)
        if outgoings:
            self._outgoing_elements = tuple(outgoings)
            self._outgoing_element = None
        else:
            self._outgoing_elements = None
            self._outgoing_element = outgoing
        self.name = name


class Function(object):
    def __init__( self, py_callable, type_manager, signature_only=False ):
        """Parameters:
        py_callable: a Python callable object.
        type_manager: TypeManager
        signature_only: if True, indicates that no element are generated
            for local variables. If False, an ElementType is generated for
            each local variable. This is typically used to declare library
            functions with known signature.
        """
        self._py_func = py_callable
        py_code = py_callable.__code__
        nb_args = py_code.co_argcount
        elements = [ ElementType( FN_PARAM_NATURE if index < nb_args else FN_LOCAL_NATURE,
                                  name=py_code.co_varnames[index],
                                  index=index,
                                  ti_related_fn=self )
                        for index in range(0,nb_args) ]
        self._arg_elements = tuple( elements[:nb_args] )
        self._local_elements = tuple( elements[nb_args:] )
        self._return_element = ElementType( FN_RETURN_NATURE, ti_related_fn=self )
        elements.append( self._return_element )
        type_manager._new_elements( elements )

    def short_repr( self ):
        return self._py_func.__name__

    @property
    def py_callable( self ):
        return self._py_func

    @property
    def return_element( self ):
        return self._return_element

    @property
    def nb_args( self ):
        return len( self._arg_elements )

    def arg_element( self, index ):
        return self._arg_elements[index]

    @property
    def nb_local_vars( self ):
        return len( self._local_elements )

    def local_var_element( self, index ):
        return self._local_elements[index]

    @property
    def co_code( self ):
        return self._py_func.__code__.co_code

    def dis_dump( self ):
        import dis
        dis.dis( self._py_func )

    def __repr__( self ):
        return repr(self._py_func)

class TypeManager(object):
    """Keeps tracks of all known functions and constant.
    TypeManager analysis results are:
    - the list of py_callable referenced by the code (directly or indirectly)
    - the type of function parameters, local variables and return value.
    - the list of referenced classes
    - for each class, the type of the parameter taken by the constructor
    - for each class, the list of its attributes and their types.
    """
    def __init__( self ):
        self.ti_functions_to_scan = []
        self.ti_functions_by_py_callable = {}
        self.scanned_py_callables = []
        #self._refined_elements = set()
        self._elements_to_refine = set()
        self._iteration_no = 0

    def all_ti_functions( self ):
        return self.ti_functions_by_py_callable.values()

    def add_function( self, py_callable ):
        """Register a Python callable object for analysis.
        """
        ti_function = self.ti_functions_by_py_callable.get(py_callable)
        if ti_function is not None:
            return ti_function
        ti_function = Function(py_callable, self )
        self.ti_functions_by_py_callable[ py_callable ] = ti_function
        self.ti_functions_to_scan.append( ti_function )
        return ti_function

    def add_typed_function( self, py_callable, tit_arg_types ):
        """Register a Python callable object with known parameter types for analysis .
        """
        ti_function = self.add_function( py_callable )
        if len(tit_arg_types) != ti_function.nb_args:
            raise ValueError( ti_function,
                              '%d argument types provided, but %d argument types required' % (
                                  ti_function.nb_args, len(tit_arg_types) ) )
        for index, tit_arg_type in enumerate( tit_arg_types ):
            self._set_element_type( ti_function.arg_element(index), tit_arg_type )

    def infer_types( self ):
        """Infer types for registered Python callable, and discover other callable with their 
        """
        while True:
            self._scan_callables()
            refined_elements = self._refine_elements()
            if not refined_elements:
                break
        print( '\nType Inference complemented: %d remaining constraint.\n' %
               len(self._elements_to_refine) )

    def _set_element_type( self, element, tit ):
        element.refined_type = tit
        self._elements_to_refine.remove( element )

    def _new_elements( self, elements ):
        self._elements_to_refine.update( elements )

    def _modified_elements( self, elements ):
        self._elements_to_refine.update( elements )

    def _scan_callables( self ):
        while self.ti_functions_to_scan:
            ti_function = self.ti_functions_to_scan.pop(0)
            print( '\nScanning function: %s\n%s' % (ti_function, '='*60) )
            ti_function.dis_dump()
            scanner = FunctionScanner( ti_function, self )
            scanner.scan_function_code()

    def _refine_elements( self ):
        """Traverse all constraints and propagate all those with resolved incoming.
        """
        self._iteration_no += 1
        print( 'Refine iteration #%d, %d callables' % (
            self._iteration_no, len(self.scanned_py_callables) ) )
        refined_elements = set()
        for element in self._elements_to_refine:
            print( 'Checking if element %s can be refined...' % element.short_repr() )
            try:
                if element.can_refine():
                    element.refine()
                    refined_elements.add( element )
            except (BaseException) as e:
                print( 'Exception while working with element:\n%s' % repr( element ) )
                raise e
        self._elements_to_refine -= refined_elements
        return refined_elements

ACTION_PROCESS_NEXT_OPCODE = 0
# Used by opcode handler to indicate that the instruction was a terminator
# instruction and that a new branch target must be used to find the
# next instruction to process.
ACTION_BRANCH = 1

INVALID_OPCODE_INDEX = -1


class FunctionScannerBranch(object):
    def __init__( self, opcode_index ):
        self.opcode_index = opcode_index
        self.incomings = []
        self.outgoings = []

class FunctionScanner(object):
    def __init__( self, ti_function, type_manager ):
        self._ti_function = ti_function
        self._type_manager = type_manager
        self._branches_by_opcode_index = {} # dict { opcode_index: FunctionScannerBranch }
        self._elements_stack = []
        self.last_opcode_index = 0

    def scan_function_code( self ):
        """Scan the function codes.
        Returns: list of constraint created while scanning the code.
        """
        block_indexes = sorted( determine_branch_targets( self._ti_function.co_code ) )# read-only
        next_instr = 0
        co_code = self._ti_function.co_code
        print( repr(co_code) )
        print( 'Prescan branch indexes: %r' % block_indexes )
        if block_indexes and block_indexes[0] == 0:
            del block_indexes[0]
        self._switch_to_entry_branch()
        while True:
            last_instr = next_instr
            next_instr, opcode, oparg = opcode_decoder( co_code, next_instr )
            try:
                self.last_opcode_index = last_instr
                opcode_handler = FUNCTION_SCANNER_OPCODE_FUNCTIONS[ opcode ]
            except KeyError:
                self.warning( "Skipped opcode %s @ %d" % (opname[opcode], last_instr) )
                action = ACTION_PROCESS_NEXT_OPCODE
            else:
                print( "Processing @%d: opcode %s, %d" % (last_instr, opname[opcode], oparg) )
                self.next_instr_index = next_instr
                action = opcode_handler( self, oparg )
                assert action is not None
            if action == ACTION_PROCESS_NEXT_OPCODE:
                if next_instr in block_indexes: # Notes: some code similar to ACTION_BRANCH
                    # We are falling through into a new block
                    print( 'Switched via fall through to new branch @%d' % next_instr )
                    block_indexes.remove( next_instr )
                    self._switch_branch( next_instr, 'fall through' )
                else:
                    # next_instr has already been initialized, checks that last instruction
                    # was a terminator
                    if next_instr >= len(co_code):
                        raise ValueError( 'Attempting to process instruction beyond end of code block.' )
            elif action == ACTION_BRANCH:
                if block_indexes:
                    next_instr = block_indexes.pop(0)
                    # Set branch basic block as builder target
                    print( 'Switched to new branch @%d' % next_instr )
                    self._switch_branch( next_instr, 'some_branch')
                else: # Done, nothing to interpret
                    break
            else:
                raise ValueError( 'Invalid action: %d' % action )

    def _switch_to_entry_branch( self ):
        entry_branch = FunctionScannerBranch( 0 )
        self._branches_by_opcode_index[0] = entry_branch
        self._current_branch = entry_branch

    def _switch_branch( self, branch_opcode_index, cause ):
        """Switch from the current branch to the specified branch.
        """
        branch = FunctionScannerBranch( branch_opcode_index )
        branch.incomings.append( self._current_branch )
        self._current_branch.outgoings.append( branch )
        self._current_branch = branch

    def warning( self, message ):
        print( message, file=sys.stderr )

    def new_element( self, nature, name=None, incoming=None, incomings=None ):
        """Creates a new ElementType corresponding to a temporary expression
           value type.
        """
        element = ElementType( nature, name=name,
                               ti_related_fn=self._ti_function,
                               incoming=incoming, incomings=incomings )
        self._type_manager._new_elements( (element,) )
        return element

    def push_element( self, element ):
        self._elements_stack.append( element )

    def pop_element( self ):
        return self._elements_stack.pop()

##    def new_constraint( self, model, incomings=(), outgoing=None, outgoings=None, name=None ):
##        location=(self._ti_function, self.last_opcode_index)
##        constraint = Constraint( location, model,
##                                 incomings=incomings, outgoings=outgoings, outgoing=outgoing,
##                                 name=name)
##        self._new_constraints.append( constraint )
##        return constraint

    def modified_element_notification( self, element ):
        """Called when an element is modified."""
        self._type_manager._modified_elements( (element,) )

    def opcode_load_fast( self, oparg ):
        local_var_index = oparg
        nb_args = self._ti_function.nb_args
        if local_var_index < nb_args:
            element = self._ti_function.arg_element( local_var_index )
        else:
            element = self._ti_function.local_var_element( local_var_index - nb_args )
        self.push_element( element )
        return ACTION_PROCESS_NEXT_OPCODE

    def opcode_binary_add( self, oparg ):
        return self.generic_binary_op( 'add' )

    def opcode_binary_subtract( self, oparg ):
        return self.generic_binary_op( 'sub' )

    def opcode_binary_multiply( self, oparg ):
        return self.generic_binary_op( 'mul' )

    def opcode_binary_floor_divide( self, oparg ):
        return self.generic_binary_op( 'div' )

    def opcode_binary_modulo( self, oparg ):
        return self.generic_binary_op( 'mod' )

    opcode_inplace_add = opcode_binary_add
    opcode_inplace_subtract = opcode_binary_subtract
    opcode_inplace_multiply = opcode_binary_multiply
    opcode_inplace_floor_divide = opcode_binary_floor_divide
    opcode_inplace_modulo = opcode_binary_modulo

    def generic_binary_op( self, name ):
        rhs_element = self.pop_element()
        lhs_element = self.pop_element()
        result_element = self.new_element( EXPR_BINOP_NATURE, name=name,
                                           incomings=(lhs_element,rhs_element) )
        self.push_element( result_element )
        return ACTION_PROCESS_NEXT_OPCODE


    def opcode_return_value( self, oparg ):
        element = self.pop_element()
        return_element = self._ti_function.return_element
        return_element.add_store_source( element )
        self.modified_element_notification( return_element )
        return ACTION_BRANCH



class TypeAnnotator(object):
    def __init__( self, r_func_type, type_registry ):
        py_func = r_func_type.get_function_object()
        self.py_func = py_func
        self.location_helper = FunctionLocationHelper( py_func.__code__ )
        self.current_opcode_index = 0
        self.type_registry = type_registry
        self.r_func_type = r_func_type
        self.func_code = py_func.__code__
        self.visited_indexes = set()
        self.branch_indexes = []
        self.type_stack = [] # List of rtypes.Type
        self.local_vars = {} # Dict {local_var_index : [ rtypes.Type ] }
        self.global_types = {} # Dict {global_index: rtypes.Type}
        self.constant_types = {} # Dict {constant_index: rtypes.Type}
        # Function parameters are the first local variables. Initialize their types
        for index, arg_type in enumerate( self.r_func_type.get_arg_types() ):
            self.local_vars[index] = arg_type

    def get_function_source( self ):
        return self.location_helper.get_source()

    def get_opcode_location( self ):
        return self.location_helper.get_location( self.current_opcode_index )

    def get_local_var_type( self, local_var_index ):
        return self.local_vars[local_var_index]

    def get_constant_type( self, constant_index ):
        return self.constant_types[constant_index]

    def get_global_type( self, global_index ):
        return self.global_types[global_index]

    def report( self ):
        print( 'Type for function', self.py_func )
        for index in range(0,self.func_code.co_nlocals):
            var_type = self.local_vars[index]
            print( 'Local %d (%s): %r' % (index, self.func_code.co_varnames[index], var_type) )
        print( 'Return type:', self.r_func_type.get_return_type() )

    def explore_function_opcodes( self ):
        next_instr = 0
        co_code = self.func_code.co_code
        print( repr(co_code) )
        while True:
            if next_instr < 0:
                if self.branch_indexes:
                    next_instr = self.branch_indexes.pop()
                else: # Done, nothing to interpret
                    break
            self.visited_indexes.add( next_instr )
            last_instr = next_instr
            self.current_opcode_index = last_instr # Used to get current opcode source location
            next_instr, opcode, oparg = opcode_decoder( co_code, next_instr )
            try:
                opcode_handler = TYPE_ANNOTATOR_OPCODE_FUNCTIONS[ opcode ]
            except KeyError:
                self.warning( "Skipped opcode %s @ %d" % (opname[opcode], last_instr) )
                new_next_instr = -1
            else:
                print( "Processing @%d: opcode %s, %d" % (last_instr, opname[opcode], oparg) )
                new_next_instr = opcode_handler( self, oparg )
                assert new_next_instr is not None
            if new_next_instr >= 0:
                next_instr = new_next_instr
            elif next_instr >= len(co_code):
                next_instr = -1
    def warning( self, message ):
        print( message, file=sys.stderr )

    def push_type( self, r_value_type ):
        self.type_stack.append( (r_value_type,None) )

    def push_constant_type( self, r_value_type, py_value ):
        self.type_stack.append( (r_value_type, py_value) )

    def pop_constant_value( self ): # for parameter name in keywords
        _, py_value = self.type_stack.pop()
        return py_value

    def pop_type( self ):
        r_value_type, _ = self.type_stack.pop()
        return r_value_type

    def pop_types( self, n ):
        if n == 0:
            return []
        r_value_types = self.type_stack[-n:]
        self.type_stack = self.type_stack[:-n]
        return [t for t, v in r_value_types]

    def get_global_var_type( self, global_index ):
        """Get a global variable type.
           If the global varuable is not found in the func_globals dictionnary
        then it is a built-in variable.
           Returns: rpy.types.Type
        """
        if global_index in self.global_types:
            return self.global_types[global_index]
        global_var_name = self.func_code.co_names[global_index]
        opcode_location = self.get_opcode_location()
        if global_var_name in self.py_func.__globals__:
            global_var_value = self.py_func.__globals__[ global_var_name ]
            r_type = self.type_registry.from_python_object( global_var_value,
                                                            opcode_location )
        else:
            r_type = self.type_registry.get_builtin_type( global_var_name )
        self.global_types[global_index] = r_type
        return r_type

    def record_local_var_type( self, local_var_index, var_type ):
        opcode_location = self.get_opcode_location()
        if local_var_index not in self.local_vars:
            unknown_type = rtypes.UnknownType( location=opcode_location )
            self.local_vars[local_var_index] = unknown_type
        else:
            unknown_type = self.local_vars[local_var_index]
        unknown_type.add_candidate_type( var_type )

    def opcode_load_global( self, oparg ):
        var_type = self.get_global_var_type( oparg )
        self.push_type( var_type )
        return -1

    def opcode_load_const( self, oparg ):
        constant_index = oparg
        py_const_value = self.func_code.co_consts[constant_index]
        if constant_index in self.constant_types:
            # Adds possible location?
            r_const_type = self.constant_types[constant_index]
        else:
            opcode_location = self.get_opcode_location()
            r_const_type = self.type_registry.from_python_object(
                py_const_value,
                opcode_location )
            self.constant_types[constant_index] = r_const_type
        self.push_constant_type( r_const_type, py_const_value )
        return -1

    def opcode_call_function( self, oparg ):
        nb_arg = oparg & 0xff
        nb_kw = (oparg >> 8) & 0xff
        kw_args = {}
        for kw_index in range(0,nb_kw):
            parameter_type = self.pop_type()
            parameter_name = self.pop_constant_value()
            kw_args[parameter_name] = parameter_type
        arg_types = self.pop_types( nb_arg )
        print( '#'*10, 'Calling function with', arg_types )
        func_type = self.pop_type()
        for index, arg_type in enumerate(arg_types):
            func_type.record_arg_type( index, arg_type )
        for parameter_name, parameter_type in kw_args.items():
            func_type.record_keyword_arg_type( parameter_name, parameter_type )
        self.push_type( func_type.get_return_type() )
        return -1

    def opcode_store_fast( self, oparg ):
        var_type = self.pop_type()
        self.record_local_var_type( oparg, var_type )
        return -1

    def opcode_load_fast( self, oparg ):
        local_var_index = oparg
        self.push_type( self.local_vars[local_var_index] )
        return -1

    def opcode_load_attr( self, oparg ):
        attribute_name = self.func_code.co_names[oparg]
        self_type = self.pop_type()
        attribute_type = self_type.get_instance_attribute_type(
            self.type_registry, attribute_name )
        self.push_type( attribute_type )
        return -1

    def opcode_store_attr( self, oparg ):
        attribute_name = self.func_code.co_names[oparg]
        self_type = self.pop_type()
        attribute_type = self.pop_type()
        print( 'Storing attribute %s of type %r' % (attribute_name, attribute_type) )
        self_type.record_attribute_type( attribute_name, attribute_type )
        return -1

    def opcode_pop_top( self, oparg ):
        self.pop_type()
        return -1

    def opcode_return_value( self, oparg ):
        return_type = self.pop_type()
        self.r_func_type.record_return_type( return_type )
        return -1

    def opcode_compare_op( self, oparg ):
        cmp_types = self.pop_types( 2 )
        opcode_location = self.get_opcode_location()
        self.push_type( rtypes.BoolType( location=opcode_location ) )
        return -1

    def opcode_pop_jump_if_false( self, oparg ):
        return -1

    def opcode_dup_top( self, oparg ):
        # Duplicate the top value on the stack
        r_type = self.pop_type()
        self.push_type( r_type )
        self.push_type( r_type )
        return -1

    def opcode_rot_two( self, oparg ):
        # Swap the two top value on the stack
        r_type_v = self.pop_type()
        r_type_w = self.pop_type()
        self.push_type( r_type_v )
        self.push_type( r_type_w )
        return -1
        

                
FUNCTION_SCANNER_OPCODE_FUNCTIONS = make_opcode_functions_map( FunctionScanner )
            
            
if __name__ == '__main__':
    pass
