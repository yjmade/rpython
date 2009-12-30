from rpy.opcodedecoder import make_opcode_functions_map, opname, make_opcode_functions_map, opcode_decoder
from rpy.opcodedecoder import CMP_LT, CMP_LE, CMP_EQ, CMP_NE, CMP_GE, CMP_GT, CMP_IN, CMP_NOT_IN, CMP_IS, CMP_IS_NOT, CMP_EXCEPTION_MATCH
import sys
import rpy.rtypes as rtypes
import llvm.core as lcore

_RTYPE_CONVERTERS = {}

def rtype_to_llvm( rtype, type_registry ):
    return _RTYPE_CONVERTERS[rtype.__class__]( rtype, type_registry )

def rtype_unknown_to_llvm( rtype, type_registry ):
    return rtype_to_llvm( rtype.get_resolved_type( type_registry ),
                          type_registry )

def rtype_callable_to_llvm( rtype_callable, type_registry ):
    l_return_type = rtype_to_llvm( rtype_callable.get_return_type(),
                                   type_registry )
    l_arg_types = [ rtype_to_llvm(r_arg_type, type_registry)
                    for r_arg_type in rtype_callable.get_arg_types() ]
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
        r_func_type = type_registry.from_python_object( py_func )
        l_func_type = rtype_to_llvm( r_func_type, type_registry )
        l_func_name = py_func.__module__ + '__' + py_func.__name__
        l_function = self.l_module.add_function( l_func_type, l_func_name )
        code = py_func.__code__
        for index, arg_name in enumerate( code.co_varnames[:code.co_argcount] ): # function parameter names
            l_function.args[index].name = arg_name
        assert py_func not in self.l_functions
        self.l_functions[ py_func ] = l_function
        return l_function, l_func_type


ACTION_PROCESS_NEXT_OPCODE = 0
# Used by opcode handler to indicate that the instruction was a terminator
# instruction and that a new branch target must be used to find the
# next instruction to process.
ACTION_BRANCH = 1

class BasicBlock(object):
    """Local variables and related basic block."""
    def __init__( self, l_func, name ):
        self.name = name
        self.l_basic_block = l_func.append_basic_block( name )
        self.incoming_blocks = [] # The list of blocks that branch to this block
        #self.outgoing_blocks = []
        self.locals_value = {} # values of local variable by index

    def set_local_var( self, index, l_value ):
        self.locals_value[index] = l_value

    def get_local_var( self, index ):
        return self.locals_value[index]

    def get_modified_local_vars( self ):
        """Return the list of modified local variables in the block."""
        return self.locals_value.keys()

    def __repr__( self ):
        return '<BasicBlock %s: locals=%s, incoming=%s>' % (self.name,
            list(self.locals_value),
            list(block.name for block in self.incoming_blocks) )

class FunctionCodeGenerator(object):
    def __init__( self, py_func, type_registry, module_generator, annotator ):
        self.py_func = py_func
        self.module_generator = module_generator
        self.annotator = annotator
        self.l_func, self.l_func_type = module_generator.add_function( py_func, type_registry )
        self.arg_count = self.l_func_type.arg_count
        self.type_registry = type_registry
        self.visited_indexes = set()
        self.blocks_by_target = {} # dict{opcode_index: basic_block}
        self.branch_indexes = []
        self.local_var_value_by_block = {} # dict{basic_block: 
        self._next_id = 0
        self.value_stack = []
        self._next_if = 0
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
        entry_block = BasicBlock( self.l_func, 'entry' )
        builder = lcore.Builder.new( entry_block.l_basic_block )
        annotation = self.annotator.get_function_annotation( self.py_func )
        py_code = self.py_func.__code__
        locals_ptr = {}
        for local_var_index in range(self.arg_count, py_code.co_nlocals ):
            local_var_name = py_code.co_varnames[local_var_index]
            r_type = annotation.get_local_var_type( local_var_index )
            l_type = rtype_to_llvm( r_type, self.type_registry )
            l_value = builder.alloca( l_type, local_var_name )
            locals_ptr[local_var_index] = l_value
        return (builder, entry_block, locals_ptr)

    def report( self ):
        print( 'Code for function', self.l_func )

    def explore_function_opcodes( self ):
        next_instr = 0
        co_code = self.py_func.__code__.co_code
        print( repr(co_code) )
        while True:
            self.visited_indexes.add( next_instr )
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
                    self.branch_indexes.remove( next_instr )
                    branch_block = self.blocks_by_target[next_instr]
                    branch_block.incoming_blocks.append( self.current_block )
                    self.builder.branch( branch_block.l_basic_block )
                    # Set branch basic block as builder target
                    self.builder.position_at_end( branch_block.l_basic_block )
                    self.current_block = branch_block
                    self.emit_phi_nodes()
                else:
                    # next_instr has already been initialized, checks that last instruction
                    # was a terminator
                    if next_instr >= len(co_code):
                        raise ValueError( 'Attempting to process instruction beyond end of code block.' )
            elif action == ACTION_BRANCH:
                if self.branch_indexes:
                    next_instr = self.branch_indexes.pop(0)
                    # Set branch basic block as builder target
                    print( 'Switched to new block @%d' % next_instr )
                    branch_block = self.blocks_by_target[next_instr]
                    self.builder.position_at_end( branch_block.l_basic_block )
                    self.current_block = branch_block
                    self.emit_phi_nodes()
                else: # Done, nothing to interpret
                    break
            else:
                raise ValueError( 'Invalid action: %d' % action )

    def register_branch_target( self, branch_opcode_index, block ):
        """Register a basic block for a branch target.
           Parameters:
           branch_opcode_index: index of the opcode of the first instruction
                                corresponding to the basic block.
           basic_block: basic block used to store translated instruction.
                        This basic block must have been added to a LLVM branch
                        instruction.
        """
        if branch_opcode_index in self.blocks_by_target:
            raise ValueError( 'Logic error: a basic block has already been '
                              'registered for index %d' % branch_opcode_index )
        self.blocks_by_target[branch_opcode_index] = block
        self.branch_indexes.append( branch_opcode_index )

    def get_or_register_target_branch_block( self, branch_index, name ):
        """
        """
        if branch_index in self.blocks_by_target:
            return self.blocks_by_target[branch_index]
        print('Created block for index %d' % branch_index )
        target_block = BasicBlock( self.l_func, name )
        self.blocks_by_target[branch_index] = target_block
        self.branch_indexes.append( branch_index )
        return target_block

    def emit_phi_nodes( self ):
        """Emits the phi-nodes for the new basic block.
        """
##        print( 'Emitted phi nodes' )
##        local_var_indexes = {}
##        for block in self.current_block.incoming_blocks:
##            print( 'Incoming: %s' % block )
##            for local_var_index in block.get_modified_local_vars():
##                if local_var_index not in local_var_indexes:
##                    local_var_indexes[local_var_index] = []
##                local_var_indexes[local_var_index].append( block )
##        for local_var_index, blocks in local_var_indexes.items():
##            if len(blocks) > 1: # at least 2 blocks modify this local variable
##                l_value_type = blocks[0].get_local_var( local_var_index ).type
##                l_value_name = self.new_local(local_var_index)
##                l_phi_node = self.builder.phi( l_value_type, l_value_name )
##                for block in blocks:
##                    l_value = block.get_local_var( local_var_index )
##                    l_phi_node.add_incoming( l_value, block.l_basic_block )
##                self.current_block.set_local_var( local_var_index, l_phi_node )
##        print( self.current_block )

    def new_var( self ):
        self._next_id += 1
        return 'tmp%d' % self._next_id

    def new_if( self ):
        self._next_if += 1
        return 'if%d' % self._next_if

    def new_local( self, local_var_index ):
        next_id = self._local_ids.get(local_var_index, 0) + 1
        self._local_ids[local_var_index] = next_id
        local_var_name = self.py_func.__code__.co_varnames[local_var_index]
        return '%s.%d' % (local_var_name, next_id)

    def push_value( self, name ):
        self.value_stack.append( name )

    def pop_value( self ):
        return self.value_stack.pop()

    def warning( self, message ):
        print( message, file=sys.stderr )

##
##    def opcode_load_global( self, oparg ):
##        var_type = self.get_global_var_type( oparg )
##        self.push_type( var_type )
##        return ACTION_PROCESS_NEXT_OPCODE
##
    def opcode_load_const( self, oparg ):
        py_const_value = self.py_func.__code__.co_consts[oparg]
        r_value_type = self.type_registry.from_python_object( py_const_value )
        l_value_type = rtype_to_llvm( r_value_type, self.type_registry )
        if l_value_type == L_INT_TYPE:
            l_value = lcore.Constant.int( L_INT_TYPE, py_const_value )
        else:
            raise NotImplementedError( 'Can not managed code generator for constant: %r' % py_const_value )
        self.push_value( l_value )
        return ACTION_PROCESS_NEXT_OPCODE
##
##    def opcode_call_function( self, oparg ):
##        nb_arg = oparg & 0xff
##        nb_kw = (oparg >> 8) & 0xff
##        kw_args = {}
##        for kw_index in range(0,nb_kw):
##            parameter_type = self.pop_type()
##            parameter_name = self.pop_constant_value()
##            kw_args[parameter_name] = parameter_type
##        arg_types = self.pop_types( nb_arg )
##        func_type = self.pop_type()
##        for index, arg_type in enumerate(arg_types):
##            func_type.record_arg_type( index, arg_type )
##        for parameter_name, parameter_type in kw_args.items():
##            func_type.record_keyword_arg_type( parameter_name, parameter_type )
##        self.push_type( func_type.get_return_type() )
##        return ACTION_PROCESS_NEXT_OPCODE

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

    def opcode_compare_op( self, oparg ):
        l_value_rhs = self.pop_value()
        l_value_lhs = self.pop_value()
        ipred = _PY_CMP_AS_LLVM[oparg]
        l_value = self.builder.icmp( ipred, l_value_lhs, l_value_rhs )
        self.push_value( l_value )
        return ACTION_PROCESS_NEXT_OPCODE

    def generic_binary_op( self, value_factory ):
        l_value_rhs = self.pop_value()
        l_value_lhs = self.pop_value()
        l_value = value_factory( l_value_lhs, l_value_rhs )
        self.push_value( l_value )
        return ACTION_PROCESS_NEXT_OPCODE

    def opcode_pop_jump_if_false( self, oparg ):
        """Generates a branch instruction depending on a boolean condition.
           Two basic blocks are provided to the branch instruction:
           one if the condition is true, and the other one if the condition
           is false.
           Each basic block is registered using register_branch_target() and
           associated to the corresponding python code.
        """
        then_branch_index = self.next_instr_index
        else_branch_index = oparg
        if_id = self.new_if()
        block_then = BasicBlock( self.l_func, '%s_then' % if_id )
        block_then.incoming_blocks.append( self.current_block )
        block_else = BasicBlock( self.l_func, '%s_else' % if_id )
        block_else.incoming_blocks.append( self.current_block )
        # Conditional branch instruction
        l_cond_value = self.pop_value() # must be of type i1
        if not l_cond_value.name:
            l_cond_value.name = 'cond_' + if_id
        self.builder.cbranch( l_cond_value,
                              block_then.l_basic_block,
                              block_else.l_basic_block )
        # Register branch targets
        self.register_branch_target( then_branch_index, block_then )
        self.register_branch_target( else_branch_index, block_else )
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
        br_id = self.new_if()
        # Creates or retrieve block corresponding to branch target index
        block = self.get_or_register_target_branch_block( branch_index,
                                                          br_id )
        block.incoming_blocks.append( self.current_block )
        # Emit the branch instruction
        self.builder.branch( block.l_basic_block )
        # Force the instruction decoder to pop a register branch target to
        # continue the analysis
        return ACTION_BRANCH

    def opcode_jump_absolute( self, oparg ):
        branch_index = oparg
        return self.generic_jump_absolute( branch_index )
                
CODE_GENERATOR_OPCODE_FUNCTIONS = make_opcode_functions_map( FunctionCodeGenerator )
