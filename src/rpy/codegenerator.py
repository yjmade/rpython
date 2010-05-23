from rpy.opcodedecoder import make_opcode_functions_map, opname, make_opcode_functions_map, opcode_decoder, determine_branch_targets
from rpy.opcodedecoder import CMP_LT, CMP_LE, CMP_EQ, CMP_NE, CMP_GE, CMP_GT, CMP_IN, CMP_NOT_IN, CMP_IS, CMP_IS_NOT, CMP_EXCEPTION_MATCH
import sys
import rpy.rtypes as rtypes
import llvm.core as lcore
from rpy.typeinference import FunctionLocationHelper

# Maps Python comparison to LLVM comparison predicate
_PY_CMP_AS_LLVM = {
    CMP_LT: lcore.IPRED_SLT,
    CMP_LE: lcore.IPRED_SLE,
    CMP_EQ: lcore.IPRED_EQ,
    CMP_NE: lcore.IPRED_NE,
    CMP_GE: lcore.IPRED_SGE,
    CMP_GT: lcore.IPRED_SGT,
    }

_FN_ALLOC = 'alloc'

# rtype -> LLVM primitive types
L_INT_TYPE = lcore.Type.int(32)
L_DOUBLE_TYPE = lcore.Type.double()
L_BOOL_TYPE = lcore.Type.int(1)
L_VOID_TYPE = lcore.Type.void()

L_CONSTANT_0 = lcore.Constant.int( L_INT_TYPE, 0 )


class LLVMTypeProvider(object):
    """Converts a rtype into an llvm type.
    """
    def __init__( self, l_module, type_registry ):
        self.l_module = l_module
        self.type_registry = type_registry
        self._converters = {
            rtypes.IntType: lambda rtype: (L_INT_TYPE, None),
            rtypes.NoneType: lambda rtype: (lcore.Type.void(), None),
            rtypes.UnknownType: self._rtype_unknown_to_llvm,
            rtypes.CallableType: self._rtype_callable_to_llvm,
            rtypes.FunctionType: self._rtype_callable_to_llvm,
            rtypes.FloatType: lambda rtype: (L_DOUBLE_TYPE, None),
            rtypes.BoolType: lambda rtype: (L_BOOL_TYPE, 'bool'),
            rtypes.ClassType: self._rtype_class_to_llvm,
            rtypes.InstanceType: self._rtype_instance_to_llvm
            }
        self._l_type_by_rtype = {} # dict{ r_type : l_type }
        self._l_type_by_rtype_callable = {} # dict{ r_type_callable : l_type }
        self._r_class_attributes = {} # dict { r_type_class: dict { attribute_name : l_constant_index } }

    def from_rtype( self, rtype ):
        """Returns the LLVM type corresponding to rtype.
           An LLVM type alias corresponding to the type name is automatically
           added to the LLVM module.
           If the rtype is a class, then the corresponding LLVM structure type is returned.
        """
        l_type = self._l_type_by_rtype.get( rtype )
        if l_type is None:
            l_type, name = self._converters[rtype.__class__]( rtype )
            self._l_type_by_rtype[ rtype ] = l_type
            self._declare_named_l_type( l_type, name )
        return l_type

    def from_rtype_callable( self, rtype ):    
        """Returns the LLVM function type corresponding to rtype.
           An LLVM type alias corresponding to the type name is automatically
           added to the LLVM module.
           If the rtype is a class, then the type of the constructor function is returned.
        """
        l_type = self._l_type_by_rtype_callable.get( rtype )
        if l_type is None:
            if isinstance( rtype, rtypes.UnknownType ):
                l_type, name = self._rtype_unknown_callable_to_llvm( rtype )
            elif isinstance( rtype, rtypes.CallableType ):
                l_type, name = self._rtype_callable_to_llvm( rtype )
            else:
                raise ValueError( 'RType is not a CallableType:' + str(rtype) )
            self._l_type_by_rtype_callable[ rtype ] = l_type
            self._declare_named_l_type( l_type, name )
        return l_type

    def get_attribute_index( self, r_type, attribute_name ):
        """Returns a integer constant corresponding to the index of the attribute
        'attribute_name' in r_type. r_type must be either an instance or a class.
        """
        # This dictionnary is set the first time the rtype class is converted to an llvm type
        r_type_class = r_type.get_resolved_type( self.type_registry )
        if isinstance( r_type_class, rtypes.InstanceType ):
            r_type_class = r_type_class.class_type
        l_attribute_indexes_by_name = self._r_class_attributes[r_type_class]
        return l_attribute_indexes_by_name[attribute_name]

    def _declare_named_l_type( self, l_type, name ):
        """Declares a type alias for l_type in the module with the specified
           name prefixed by 'rtype_'.
        """
        if name:
            self.l_module.add_type_name( 'rtype_' + name, l_type )

    def _rtype_class_to_llvm( self, rtype_class ):
        print( '#' * 80 )
        l_attribute_types = []
        r_instance_type = rtype_class.instance_type
        r_instance_type.flush_pending_records( self.type_registry )
        l_attribute_indexes_by_name = {}
        for name, r_attribute_type in r_instance_type.attribute_types.items():
            print( 'Found attribute:', name, r_attribute_type )
            l_attribute_type = self.from_rtype( r_attribute_type )
            l_attribute_indexes_by_name[name] = lcore.Constant.int( L_INT_TYPE, len(l_attribute_types) )
            l_attribute_types.append( l_attribute_type )
        l_struct_type = lcore.Type.struct( l_attribute_types )
        self._r_class_attributes[rtype_class] = l_attribute_indexes_by_name
        return l_struct_type, rtype_class.get_qualified_type_name()

    def _rtype_instance_to_llvm( self, rtype_instance ):
        l_class_type = self.from_rtype( rtype_instance.class_type )
        return lcore.Type.pointer( l_class_type ), None
    
    def _rtype_unknown_to_llvm( self, rtype ):
        return self.from_rtype( rtype.get_resolved_type( self.type_registry ) ), None

    def _rtype_unknown_callable_to_llvm( self, rtype ):
        return self.from_rtype_callable( rtype.get_resolved_type( self.type_registry ) ), None

    def _rtype_callable_to_llvm( self, rtype_callable ):
        if isinstance( rtype_callable, rtypes.ClassType ):
            # Notes: ClassType callable type (a constructor) indicates that it return an instance of that type.
            # This is usefull for type inferance, but the generated LLVM pass the allocated instance to the function.
            # So the constructor function is modified to just return void.
            l_return_type = L_VOID_TYPE
        else:
            l_return_type = self.from_rtype( rtype_callable.get_return_type() )
        l_arg_types = []
        for r_arg_type in rtype_callable.get_arg_types():
            l_arg_types.append( self.from_rtype(r_arg_type) )
        # Calling convention: lcore.CC_FASTCALL or lcore.CC_X86_FASTCALL
        return lcore.Type.function( l_return_type, l_arg_types ), None

class ModuleGenerator(object):
    def __init__( self, type_registry ):
        self.l_module = lcore.Module.new('main_module')
        self._type_provider = LLVMTypeProvider( self.l_module, type_registry )
        self.l_functions = {} # dict { py_func: l_func }
        #self.l_sys_functions[_FN_ALLOC] = 

    def llvm_type_from_rtype( self, rtype ):
        """Returns the LLVM type corresponding to rtype.
           An LLVM type alias corresponding to the type name is automatically
           added to the LLVM module.
           If the rtype is a class, then the corresponding LLVM structure type is returned.
        """
        return self._type_provider.from_rtype( rtype )

    def llvm_function_type_from_rtype( self, rtype ):    
        """Returns the LLVM function type corresponding to rtype.
           An LLVM type alias corresponding to the type name is automatically
           added to the LLVM module.
           If the rtype is a class, then the type of the constructor function is returned.
        """
        return self._type_provider.from_rtype_callable( rtype )

    def get_attribute_index( self, r_type_class, attribute_name ):
        """Returns a integer constant corresponding to the index of the attribute
        'attribute_name' in r_type_class.
        """
        return self._type_provider.get_attribute_index( r_type_class, attribute_name )

    def add_function( self, py_func, r_func_type ):
        # Notes: some rtypes are both a type and a callable (constructor). We hardwire that we want the callable aspect as llvm type.
        l_func_type = self.llvm_function_type_from_rtype( r_func_type )
        l_func_name = py_func.__module__ + '__' + py_func.__name__
        l_function = self.l_module.add_function( l_func_type, l_func_name )
        print( 'ModuleGenerator.add_function( %s -> %s )' % (py_func, str(l_function).replace('\n','')) )
        code = py_func.__code__
        for index, arg_name in enumerate( code.co_varnames[:code.co_argcount] ): # function parameter names
            l_function.args[index].name = arg_name
        assert py_func not in self.l_functions
        self.l_functions[ py_func ] = l_function
        if r_func_type.is_constructor():
            self.l_functions[ r_func_type.py_class ] = l_function
        return l_function, l_func_type

    def get_function( self, py_func ):
        """Returns the LLVM function declaration corresponding to the
           specified python function.
        """
        return self.l_functions[ py_func ]
        


ACTION_PROCESS_NEXT_OPCODE = 0
# Used by opcode handler to indicate that the instruction was a terminator
# instruction and that a new branch target must be used to find the
# next instruction to process.
ACTION_BRANCH = 1

INVALID_OPCODE_INDEX = -1

class BasicBlock(object):
    """Local variables and related basic block."""
    def __init__( self, l_func, name, opcode_index ):
        # prefix name with opcode index to make it easier to match
        # llvm code to python bytecode
        self.opcode_index = opcode_index
        name = self._make_name( name )
        self.l_basic_block = l_func.append_basic_block( name )
        self.incoming_blocks = [] # The list of blocks that branch to this block
        #self.outgoing_blocks = []
        self.locals_value = {} # values of local variable by index
        self.loop_break_index = INVALID_OPCODE_INDEX
        self.has_final_break_jump = False
        self.is_loop_end = False
        self.related_loop_setup_block = None # Resolved block that setup the loop for block with break statement

    def set_block_name( self, name ):
        self.l_basic_block.name = self._make_name( name )

    @property
    def name( self ):
        return self.l_basic_block.name

    def _make_name( self, name ):
        """Returns a name prefixed with the opcode index.
           This ease the analysis when comparing python bytecode and LLVM IR.
        """
        return 'l%d_%s' % (self.opcode_index, name) 

    def set_local_var( self, index, l_value ):
        self.locals_value[index] = l_value

    def get_local_var( self, index ):
        return self.locals_value[index]

    def get_modified_local_vars( self ):
        """Return the list of modified local variables in the block."""
        return self.locals_value.keys()

    def setup_loop_break_target( self, branch_index ):
        # A block can only setup one loop
        assert self.loop_break_index == INVALID_OPCODE_INDEX
        self.loop_break_index = branch_index

    def ends_with_loop_break( self ):
        assert not self.has_final_break_jump # a block can not break multiple loop
        self.has_final_break_jump = True

    def ends_loop( self ):
        assert not self.is_loop_end # a block can only ends a single loop
        self.is_loop_end = True

    def find_break_branch_target( self ):
        """Locates the setup_loop branch target matching this block break statement.
        This is done by looking at incoming blocks that setup a loop.
        """
        if not self.has_final_break_jump:
            raise ValueError( 'Logic error: attempting to add break to jump to block without break opcode.' )
        blocks_to_visit = [(block, 0) for block in self.incoming_blocks]
        visited_blocks = set() # cycle detector
        while blocks_to_visit:
            block, nesting_level = blocks_to_visit.pop(0)
            if block.is_loop_end:
                nesting_level -= 1
            if block.loop_break_index != INVALID_OPCODE_INDEX:
                nesting_level += 1
                if nesting_level == 1:
                    self.related_loop_setup_block = block
                    return block.loop_break_index
            visited_blocks.add( block )
            blocks_to_visit += [ (b, nesting_level)
                                 for b in block.incoming_blocks
                                 if b not in visited_blocks ]
        raise ValueError( 'Could not locate block that setup the loop for block %r' % self )

    def __repr__( self ):
        if self.related_loop_setup_block:
            loop_info = ', loop_start=%s' % self.related_loop_setup_block.name
        else:
            loop_info = ''
        return '<BasicBlock %s: locals=%s, incoming=%s%s>' % (self.name,
            list(self.locals_value),
            list(block.name for block in self.incoming_blocks),
            loop_info )

class FunctionCodeGenerator(object):
    """The function code generator acts mostly as a python bytecode to LLVM translator.

       General notes:
       Local variables are allocated on the stack via llvm.alloca.
       Parameters are allocated on the stack via llvm.alloca, and the initial value
       passed to the function is copied. This allow parameters to be assigned to.
       Load and store operations are used to load/store local variable/parameter values.
       LLVM optimization pass handle the convertion into register via the
       insertion of phi nodes. Not having to handle phi nodes drastically
       simply the code generation.

       When generating code for "constructor" function, then return statement is forced to
       return void (ignoring the python generated return None).
    """
    def __init__( self, py_func, module_generator, annotator ):
        self.py_func = py_func
        self.module_generator = module_generator
        self.annotator = annotator
        self.annotation = self.annotator.get_function_annotation( self.py_func )
        self.l_func, self.l_func_type = module_generator.add_function(
            py_func, self.annotation.r_func_type )
        self.arg_count = self.l_func_type.arg_count
        self.is_constructor = self.annotation.r_func_type.is_constructor()
        self.blocks_by_target = {} # dict{opcode_index: basic_block}
        self.branch_indexes = determine_branch_targets( self.py_func.__code__.co_code ) # read-only
        self.global_var_values = {} # dict{global_index: l_value}
        self._next_id_by_prefix = {}
        self.value_stack = []
        self.pending_break_jump_blocks = [] # List of blocks that need a final "break" jump
        # self.locals_ptr: dict{local_var_index: l_value}
        #   This dictionary contains pointer to local variable memory
        #   allocated via alloca(), and pointer directly to parameters
        #   for parameters.
        self.builder, self.current_block, self.locals_ptr = \
                      self.make_entry_basic_block_builder()

    def make_entry_basic_block_builder( self ):
        """Creates the entry block and reserve space on stack for local variables.
           This follows the recommandation of the "mutable variable" tutorial:
           http://llvm.org/docs/tutorial/LangImpl7.html#kalvars

           The mem2reg optimization pass will convert alloca memory access into
           register, avoiding the asle of creating phi node in the front-end.
        """
        entry_block = BasicBlock( self.l_func, 'entry', 0 )
        self.blocks_by_target[0] = entry_block
        builder = lcore.Builder.new( entry_block.l_basic_block )
        py_code = self.py_func.__code__
        locals_ptr = {}
        for local_var_index in range(0, py_code.co_nlocals ):
            local_var_name = py_code.co_varnames[local_var_index]
            r_type = self.annotation.get_local_var_type( local_var_index )
            l_type = self.module_generator.llvm_type_from_rtype( r_type )
            if local_var_index < self.arg_count: # function parameter
                l_param_value = self.l_func.args[local_var_index]
                l_value = builder.alloca( l_type, local_var_name + ".param" )
                builder.store( l_param_value, l_value )
            else:
                l_value = builder.alloca( l_type, local_var_name )
            locals_ptr[local_var_index] = l_value
        return (builder, entry_block, locals_ptr)

    def report( self ):
        print( '* Code for function', self.l_func )
        self.dump_block_flow()

    def generate_llvm_code( self ):
        self.explore_function_opcodes()
        self.process_pending_break_jumps()

    def explore_function_opcodes( self ):
        next_instr = 0
        co_code = self.py_func.__code__.co_code
        print( repr(co_code) )
        block_indexes = sorted( self.branch_indexes ) # start indexes of basic blocks
        print( 'Prescan branch indexes: %r' % block_indexes )
        if block_indexes and block_indexes[0] == 0:
            del block_indexes[0]
        while True:
            last_instr = next_instr
            next_instr, opcode, oparg = opcode_decoder( co_code, next_instr )
            try:
                opcode_handler = CODE_GENERATOR_OPCODE_FUNCTIONS[ opcode ]
            except KeyError:
                self.warning( "Skipped opcode %s @ %d" % (opname[opcode], last_instr) )
                action = ACTION_PROCESS_NEXT_OPCODE
            else:
                print( "Processing @%d: opcode %s, %d" % (last_instr, opname[opcode], oparg) )
                self.next_instr_index = next_instr
                action = opcode_handler( self, oparg )
                assert action is not None
            if action == ACTION_PROCESS_NEXT_OPCODE:
                if next_instr in self.branch_indexes: # Notes: some code similar to ACTION_BRANCH
                    # We are falling through into a new block
                    # We need to inject branch code.
                    print( 'Switched via fall through to new block @%d' % next_instr )
                    block_indexes.remove( next_instr )
                    branch_block = self.obtain_block_at(next_instr, 'fall_through')
                    branch_block.incoming_blocks.append( self.current_block )
                    self.builder.branch( branch_block.l_basic_block )
                    # Set branch basic block as builder target
                    self.builder.position_at_end( branch_block.l_basic_block )
                    self.current_block = branch_block
                else:
                    # next_instr has already been initialized, checks that last instruction
                    # was a terminator
                    if next_instr >= len(co_code):
                        raise ValueError( 'Attempting to process instruction beyond end of code block.' )
            elif action == ACTION_BRANCH:
                if block_indexes:
                    next_instr = block_indexes.pop(0)
                    # Set branch basic block as builder target
                    print( 'Switched to new block @%d' % next_instr )
                    #branch_block = self.blocks_by_target[next_instr]
                    branch_block = self.obtain_block_at(next_instr, 'some_branch')
                    self.builder.position_at_end( branch_block.l_basic_block )
                    self.current_block = branch_block
                else: # Done, nothing to interpret
                    break
            else:
                raise ValueError( 'Invalid action: %d' % action )

    def process_pending_break_jumps( self ):
        # Notes: should probably have a better algo that avoid scanning the flow graph
        # multiple times.
        for block in self.pending_break_jump_blocks:
            branch_index = block.find_break_branch_target()
            # Setup context to emit branch instruction
            self.builder.position_at_end( block.l_basic_block )
            self.current_block = block
            # Emit branch instruction
            self.generic_jump_absolute( branch_index )

    def dump_block_flow( self ):
        opcode_indexes = self.branch_indexes
        opcode_indexes.add( 0 )
        print( '* Block flow (%d blocks):' % len(opcode_indexes) )
        for opcode_index in sorted( opcode_indexes ):
            print( '@%d = %r' % (opcode_index,
                                 self.blocks_by_target[opcode_index]) )

    def obtain_block_at( self, branch_index, name ):
        """Obtains a block at the specified opcode index.
           If the block does not exist, it is created with the specified name.
           Parameters:
           branch_index: index of the opcode of the first instruction
                         corresponding to the basic block.
           name: name of the block, only used if the block does not exist.
        """
        if branch_index in self.blocks_by_target:
            return self.blocks_by_target[branch_index]
        if branch_index not in self.branch_indexes:
            raise ValueError( 'Logic error: no target was found at index %d '
                              'during initial scan' % branch_index )
        print('Created block for index %d' % branch_index )
        target_block = BasicBlock( self.l_func, name, branch_index )
        self.blocks_by_target[branch_index] = target_block
        return target_block

    def reset_block_name( self, branch_index, name ):
        block = self.obtain_block_at( branch_index, name )
        block.set_block_name( name )

    def new_id( self, prefix ):
        next_id = self._next_id_by_prefix.get( prefix, 0 ) + 1
        self._next_id_by_prefix[prefix] = next_id
        return '%s.%d' % (prefix, next_id)

    def push_value( self, l_value, r_type ):
        self.value_stack.append( (l_value, r_type) )

    def pop_value( self ):
        """Returns the last pushed l_value."""
        return self.value_stack.pop()[0]

    def pop_value_with_rtype( self ):
        """Returns the last pushed tuple (l_value, r_type)."""
        return self.value_stack.pop()

    def warning( self, message ):
        print( message, file=sys.stderr )

    def get_constant_type( self, constant_index ):
        return self.annotation.get_constant_type( constant_index )

    def get_global_var_type( self, global_index ):
        return self.annotation.get_global_type( global_index )

    def py_value_as_llvm_value( self, py_value, r_value_type ):
        """Returns a tuple (l_value, l_type) for the specified python object.
        """
        l_value_type = self.module_generator.llvm_type_from_rtype( r_value_type )
        if l_value_type == L_INT_TYPE:
            l_value = lcore.Constant.int( L_INT_TYPE, py_value )
        elif isinstance( l_value_type, lcore.FunctionType ):
            l_value = self.module_generator.get_function( py_value )
        elif py_value is None:
            l_value = lcore.Constant.int( L_INT_TYPE, 0 ) # @todo Use more distinct type to generate error
        elif isinstance( py_value, type ):
            # Notes: this assumes we want the constructor function corresponding to the type
            l_value = self.module_generator.get_function( py_value )
        else:
            raise NotImplementedError( 'Can not manage code generation for constant: %r' % py_value )
        return (l_value, l_value_type)

    def opcode_load_global( self, oparg ):
        global_index = oparg
        if global_index in self.global_var_values:
            return self.global_var_values[global_index]

        global_var_name = self.py_func.__code__.co_names[global_index]
        py_value = self.py_func.__globals__[ global_var_name ]

        r_type = self.get_global_var_type( global_index )
        l_value, l_value_type = self.py_value_as_llvm_value(
            py_value, r_type )
        self.global_var_values[global_index] = l_value
        self.push_value( l_value, r_type )
        return ACTION_PROCESS_NEXT_OPCODE

    def opcode_load_const( self, oparg ):
        constant_index = oparg
        py_const_value = self.py_func.__code__.co_consts[constant_index]
        r_value_type = self.get_constant_type( constant_index )
        l_value, l_value_type = self.py_value_as_llvm_value(
            py_const_value, r_value_type )
        self.push_value( l_value, r_value_type )
        return ACTION_PROCESS_NEXT_OPCODE

    def opcode_call_function( self, oparg ):
        nb_arg = oparg & 0xff
        nb_kw = (oparg >> 8) & 0xff
        if nb_kw:
            raise ValueError( "keywords argument not supported in function call." )
##        kw_args = {}
##        for kw_index in range(0,nb_kw):
##            parameter_type = self.pop_type()
##            parameter_name = self.pop_constant_value()
##            kw_args[parameter_name] = parameter_type
        l_arg_values = []
        for index in range(0,nb_arg):
            l_arg_values.insert( 0, self.pop_value() )
        l_fn_value, r_fn_type = self.pop_value_with_rtype()
        if r_fn_type.is_constructor(): # The call is a constructor invocation
            # We allocate the memory for the type, call the constructor, and
            # use the address of the allocated type as expression value
            l_struct_type = self.module_generator.llvm_type_from_rtype( r_fn_type )
            # @todo allocate memory dynamically instead of on the stack
            l_instance = self.builder.alloca( l_struct_type, self.new_id('instance') )
            l_arg_values.insert( 0, l_instance )
            self.builder.call( l_fn_value, l_arg_values )
            l_return_value = l_instance
        else:
            l_return_value = self.builder.call( l_fn_value, l_arg_values )
        self.push_value( l_return_value, r_fn_type.get_return_type() )
        return ACTION_PROCESS_NEXT_OPCODE

    def opcode_store_fast( self, oparg ):
        """Stores the local variable/parameter value in the current block.
        """
        local_var_index = oparg
        l_value = self.pop_value()
        l_local_ptr = self.locals_ptr[ local_var_index ]
        self.builder.store( l_value, l_local_ptr )
        return ACTION_PROCESS_NEXT_OPCODE

    def opcode_load_fast( self, oparg ):
        """Retrieves the local variable/parameter value from the current block.
        """
        local_var_index = oparg
        l_local_ptr = self.locals_ptr[ local_var_index ]
        l_value = self.builder.load( l_local_ptr )
        r_type = self.annotation.get_local_var_type( local_var_index )
        self.push_value( l_value, r_type )
        return ACTION_PROCESS_NEXT_OPCODE

    def opcode_load_attr( self, oparg ):
        py_code = self.py_func.__code__
        attribute_name = py_code.co_names[oparg]
        l_instance_ptr, r_type_instance = self.pop_value_with_rtype()
        l_attribute_index = self.module_generator.get_attribute_index(
            r_type_instance, attribute_name )
        l_attribute_ptr = self.builder.gep( l_instance_ptr, [L_CONSTANT_0, l_attribute_index] ) # gep =  getelementptr
        l_attribute_value = self.builder.load( l_attribute_ptr )
        r_type_attribute = r_type_instance.get_known_attribute_type( attribute_name )
        self.push_value( l_attribute_value, r_type_attribute )
        return ACTION_PROCESS_NEXT_OPCODE

    def opcode_store_attr( self, oparg ):
        py_code = self.py_func.__code__
        attribute_name = py_code.co_names[oparg]
        l_instance_ptr, r_type_instance = self.pop_value_with_rtype()
        l_attribute_value = self.pop_value()
        l_attribute_index = self.module_generator.get_attribute_index( r_type_instance, attribute_name )
        l_attribute_ptr = self.builder.gep( l_instance_ptr, [L_CONSTANT_0, l_attribute_index] ) # gep =  getelementptr
        self.builder.store( l_attribute_value, l_attribute_ptr )
        return ACTION_PROCESS_NEXT_OPCODE

##
##    def opcode_pop_top( self, oparg ):
##        self.pop_type()
##        return -1
##
    def opcode_return_value( self, oparg ):
        l_value = self.pop_value()
        if self.is_constructor:
            # Python generated code allow constuctor to return value. RPython does not allow this.
            self.builder.ret_void()
        else:
            self.builder.ret( l_value )
        return ACTION_BRANCH

    def opcode_binary_add( self, oparg ):
        return self.generic_binary_op( self.builder.add )

    def opcode_binary_subtract( self, oparg ):
        return self.generic_binary_op( self.builder.sub )

    def opcode_binary_multiply( self, oparg ):
        return self.generic_binary_op( self.builder.mul )

    def opcode_binary_floor_divide( self, oparg ):
        return self.generic_binary_op( self.builder.sdiv )

    def opcode_binary_modulo( self, oparg ):
        return self.generic_binary_op( self.builder.srem )

    opcode_inplace_add = opcode_binary_add
    opcode_inplace_subtract = opcode_binary_subtract
    opcode_inplace_multiply = opcode_binary_multiply
    opcode_inplace_floor_divide = opcode_binary_floor_divide
    opcode_inplace_modulo = opcode_binary_modulo

    def generic_binary_op( self, value_factory ):
        l_value_rhs, rtype_rhs = self.pop_value_with_rtype()
        l_value_lhs, rtype_lhs = self.pop_value_with_rtype()
        l_value = value_factory( l_value_lhs, l_value_rhs )
        self.push_value( l_value, rtype_lhs )
        return ACTION_PROCESS_NEXT_OPCODE

    def opcode_compare_op( self, oparg ):
        l_value_rhs, rtype_rhs = self.pop_value_with_rtype()
        l_value_lhs, rtype_lhs = self.pop_value_with_rtype()
        ipred = _PY_CMP_AS_LLVM[oparg]
        l_value = self.builder.icmp( ipred, l_value_lhs, l_value_rhs )
        self.push_value( l_value, rtypes.BoolType() )
        return ACTION_PROCESS_NEXT_OPCODE

    def opcode_pop_jump_if_false( self, oparg ):
        """Generates a branch instruction depending on a boolean condition.
           Two basic blocks are provided to the branch instruction:
           one if the condition is true, and the other one if the condition
           is false.
           Each basic block is registered using obtain_block_at() and
           associated to the corresponding python code.
        """
        then_branch_index = self.next_instr_index
        else_branch_index = oparg
        # Get block for then/else branch, and rename them
        then_id = self.new_id( 'then' )
        else_id = self.new_id( 'else' )
        cond_id = self.new_id( 'if_cond' )
        block_then = self.obtain_block_at( then_branch_index, then_id )
        block_then.incoming_blocks.append( self.current_block )
        block_else = self.obtain_block_at( else_branch_index, else_id )
        block_else.incoming_blocks.append( self.current_block )
        # Conditional branch instruction
        l_cond_value = self.pop_value() # must be of type i1
        if not l_cond_value.name:
            l_cond_value.name = cond_id
        self.builder.cbranch( l_cond_value,
                              block_then.l_basic_block,
                              block_else.l_basic_block )
        # Force the instruction decoder to pop a register branch target to
        # continue the analysis
        return ACTION_BRANCH

    def opcode_jump_forward( self, oparg ):
        branch_index = oparg + self.next_instr_index
        return self.generic_jump_absolute( branch_index )

    def generic_jump_absolute( self, branch_index ):    
        """Generates a branch instruction.
           Try to retrieve an existing block at target location, and create
           one if none exist.
        """
        br_id = self.new_id( 'branch' )
        # Creates or retrieve block corresponding to branch target index
        block = self.obtain_block_at( branch_index, br_id )
        block.incoming_blocks.append( self.current_block )
        # Emit the branch instruction
        self.builder.branch( block.l_basic_block )
        # Force the instruction decoder to pop a register branch target to
        # continue the analysis
        return ACTION_BRANCH

    def opcode_jump_absolute( self, oparg ):
        branch_index = oparg
        return self.generic_jump_absolute( branch_index )

    def opcode_setup_loop( self, oparg ):
        """This opcode is used to setup the jump location when
        a break statement occurs in a loop.
        It is expected that the next opcode will a branch target when
        the loop occurs.
        Related opcodes: break_loop, pop_block.
        """
        if self.next_instr_index not in self.branch_indexes:
            raise ValueError( 'Logic error: new block expected after setup_loop opcode @%d.' %
                              self.next_instr_index )
        while_id = self.new_id( 'while' )
        self.reset_block_name( self.next_instr_index, while_id )

        branch_index = oparg + self.next_instr_index
        end_while_id = self.new_id( 'end_while' )
        self.reset_block_name( branch_index, end_while_id )

        self.current_block.setup_loop_break_target( branch_index )
        return ACTION_PROCESS_NEXT_OPCODE

    def opcode_break_loop( self, oparg ):
        """Break loop jumps to the target previously defined by the setup_loop
        opcode. This is deduced by execution flow analysis once all blocks
        have been proceceed.
        So at this time, we just mark the current block as a "loop ending"
        block to which the branching instruction will be appended once
        the matching setup_loop has been identified.
        Related opcodes: setup_loop, pop_block.
        """
        self.current_block.ends_with_loop_break()
        self.pending_break_jump_blocks.append( self.current_block )
        return ACTION_BRANCH

    def opcode_pop_block( self, oparg ):
        """Opcodes executed when a while loop ends without break.
           In CPython, this pop the "setup_loop" context from a stack.
           For flow analysis, the current block is marked as ending a while loop,
           so that nested while loop are handled correctly.
        """
        self.current_block.ends_loop()
        return ACTION_PROCESS_NEXT_OPCODE
                
CODE_GENERATOR_OPCODE_FUNCTIONS = make_opcode_functions_map( FunctionCodeGenerator )
