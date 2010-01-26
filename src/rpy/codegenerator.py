from rpy.opcodedecoder import make_opcode_functions_map, opname, make_opcode_functions_map, opcode_decoder, determine_branch_targets
from rpy.opcodedecoder import CMP_LT, CMP_LE, CMP_EQ, CMP_NE, CMP_GE, CMP_GT, CMP_IN, CMP_NOT_IN, CMP_IS, CMP_IS_NOT, CMP_EXCEPTION_MATCH
import sys
import rpy.rtypes as rtypes
import llvm.core as lcore
from rpy.typeinference import FunctionLocationHelper

_RTYPE_CONVERTERS = {}

def rtype_to_llvm( rtype, type_registry ):
    return _RTYPE_CONVERTERS[rtype.__class__]( rtype, type_registry )

def rtype_unknown_to_llvm( rtype, type_registry ):
    return rtype_to_llvm( rtype.get_resolved_type( type_registry ),
                          type_registry )

def rtype_callable_to_llvm( rtype_callable, type_registry ):
    l_return_type = rtype_to_llvm( rtype_callable.get_return_type(),
                                   type_registry )
    l_arg_types = []
    for r_arg_type in rtype_callable.get_arg_types():
        l_arg_types.append( rtype_to_llvm(r_arg_type, type_registry) )
    # Calling convention: lcore.CC_FASTCALL or lcore.CC_X86_FASTCALL
    return lcore.Type.function( l_return_type, l_arg_types )

L_INT_TYPE = lcore.Type.int(32)
L_DOUBLE_TYPE = lcore.Type.double()
L_BOOL_TYPE = lcore.Type.int(1)

_RTYPE_CONVERTERS.update( {
    rtypes.IntType: lambda rtype, registry: L_INT_TYPE,
    rtypes.NoneType: lambda rtype, registry: lcore.Type.void(),
    rtypes.UnknownType: rtype_unknown_to_llvm,
    rtypes.CallableType: rtype_callable_to_llvm,
    rtypes.FunctionType: rtype_callable_to_llvm,
    rtypes.FloatType: lambda rtype, registry: L_DOUBLE_TYPE,
    rtypes.BoolType: lambda rtype, registry: L_BOOL_TYPE,
    } )

# Maps Python comparison to LLVM comparison predicate
_PY_CMP_AS_LLVM = {
    CMP_LT: lcore.IPRED_SLT,
    CMP_LE: lcore.IPRED_SLE,
    CMP_EQ: lcore.IPRED_EQ,
    CMP_NE: lcore.IPRED_NE,
    CMP_GE: lcore.IPRED_SGE,
    CMP_GT: lcore.IPRED_SGT,
    }

class ModuleGenerator(object):
    def __init__( self ):
        self.l_module = lcore.Module.new('main_module')
        self.l_functions = {} # dict { py_func: l_func }

    def add_function( self, py_func, type_registry ):
        func_location = FunctionLocationHelper(
            py_func.__code__ ).get_location(0)
        r_func_type = type_registry.from_python_object( py_func, func_location )
        l_func_type = rtype_to_llvm( r_func_type, type_registry )
        l_func_name = py_func.__module__ + '__' + py_func.__name__
        l_function = self.l_module.add_function( l_func_type, l_func_name )
        code = py_func.__code__
        for index, arg_name in enumerate( code.co_varnames[:code.co_argcount] ): # function parameter names
            l_function.args[index].name = arg_name
        assert py_func not in self.l_functions
        self.l_functions[ py_func ] = l_function
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
    def __init__( self, py_func, type_registry, module_generator, annotator ):
        self.py_func = py_func
        self.module_generator = module_generator
        self.annotator = annotator
        self.annotation = self.annotator.get_function_annotation( self.py_func )
        self.l_func, self.l_func_type = module_generator.add_function( py_func, type_registry )
        self.arg_count = self.l_func_type.arg_count
        self.type_registry = type_registry
        self.blocks_by_target = {} # dict{opcode_index: basic_block}
        self.branch_indexes = determine_branch_targets( self.py_func.__code__.co_code ) # read-only
        self.global_var_values = {} # dict{global_index: l_value}
        self._next_id_by_prefix = {}
        self.value_stack = []
        self.pending_break_jump_blocks = [] # List of blocks that need a final "break" jump
        # self.locals_ptr: dict{local_var_index: l_value}
        #   This dictionary contains pointer to local variable memory
        #   allocated via alloca().
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
        for local_var_index in range(self.arg_count, py_code.co_nlocals ):
            local_var_name = py_code.co_varnames[local_var_index]
            r_type = self.annotation.get_local_var_type( local_var_index )
            l_type = rtype_to_llvm( r_type, self.type_registry )
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

    def push_value( self, l_value ):
        self.value_stack.append( l_value )

    def pop_value( self ):
        return self.value_stack.pop()

    def warning( self, message ):
        print( message, file=sys.stderr )

    def get_constant_type( self, constant_index ):
        return self.annotation.get_constant_type( constant_index )

    def get_global_var_type( self, global_index ):
        return self.annotation.get_global_type( global_index )

    def py_value_as_llvm_value( self, py_value, r_value_type ):
        """Returns a tuple (l_value, r_type) for the specified python object.
        """
        l_value_type = rtype_to_llvm( r_value_type, self.type_registry )
        if l_value_type == L_INT_TYPE:
            l_value = lcore.Constant.int( L_INT_TYPE, py_value )
        elif isinstance( l_value_type, lcore.FunctionType ):
            l_value = self.module_generator.get_function( py_value )
        else:
            raise NotImplementedError( 'Can not managed code generator for constant: %r' % py_const_value )
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
        self.push_value( l_value )
        return ACTION_PROCESS_NEXT_OPCODE

    def opcode_load_const( self, oparg ):
        constant_index = oparg
        py_const_value = self.py_func.__code__.co_consts[constant_index]
        r_value_type = self.get_constant_type( constant_index )
        l_value, l_value_type = self.py_value_as_llvm_value(
            py_const_value, r_value_type )
        self.push_value( l_value )
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
        l_fn_value = self.pop_value()
        l_return_value = self.builder.call( l_fn_value, l_arg_values )
        self.push_value( l_return_value )
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
        if local_var_index < self.arg_count: # accessing parameter value
            l_value = self.l_func.args[local_var_index]
            self.push_value( l_value )
        else:
            l_local_ptr = self.locals_ptr[ local_var_index ]
            l_value = self.builder.load( l_local_ptr )
            self.push_value( l_value )
        return ACTION_PROCESS_NEXT_OPCODE
##
##    def opcode_load_attr( self, oparg ):
##        attribute_name = self.func_code.co_names[oparg]
##        self_type = self.pop_type()
##        attribute_type = self_type.get_instance_attribute_type(
##            self.type_registry, attribute_name )
##        self.push_type( attribute_type )
##        return -1
##
##    def opcode_pop_top( self, oparg ):
##        self.pop_type()
##        return -1
##
    def opcode_return_value( self, oparg ):
        l_value = self.pop_value()
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
        l_value_rhs = self.pop_value()
        l_value_lhs = self.pop_value()
        l_value = value_factory( l_value_lhs, l_value_rhs )
        self.push_value( l_value )
        return ACTION_PROCESS_NEXT_OPCODE

    def opcode_compare_op( self, oparg ):
        l_value_rhs = self.pop_value()
        l_value_lhs = self.pop_value()
        ipred = _PY_CMP_AS_LLVM[oparg]
        l_value = self.builder.icmp( ipred, l_value_lhs, l_value_rhs )
        self.push_value( l_value )
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
