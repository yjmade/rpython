from rpy.opcodedecoder import make_opcode_functions_map, opname, make_opcode_functions_map, opcode_decoder
import sys
import rpy.rtypes as rtypes


class TypeInference(object):
    def __init__( self ):
        self.functions_by_name = {}


class TypeAnnotator(object):
    def __init__( self, py_func, type_registry ):
        self.py_func = py_func
        self.type_registry = type_registry
        self.r_func_type = type_registry.from_python_object( py_func )
        self.func_code = py_func.__code__
        self.visited_indexes = set()
        self.branch_indexes = []
        self.type_stack = [] # List of rtypes.Type
        self.local_vars = {} # Dict {local_var_index : [ rtypes.Type ] }
        # Function parameters are the first local variables. Initialize their types
        for index, arg_type in enumerate( self.r_func_type.get_arg_types() ):
            self.local_vars[index] = arg_type

    def get_local_var_type( self, local_var_index ):
        return self.local_vars[local_var_index]

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

    def push_type( self, value_type ):
        self.type_stack.append( (value_type,None) )

    def push_constant_type( self, value_type, value ):
        self.type_stack.append( (value_type, value) )

    def pop_constant_value( self ): # for parameter name in keywords
        _, value = self.type_stack.pop()
        return value

    def pop_type( self ):
        value_type, _ = self.type_stack.pop()
        return value_type

    def pop_types( self, n ):
        if n == 0:
            return []
        value_types = self.type_stack[-n:]
        self.type_stack = self.type_stack[:-n]
        return [t for t, v in value_types]

    def get_global_var_type( self, oparg ):
        """Get a global variable type.
           If the global varuable is not found in the func_globals dictionnary
        then it is a built-in variable.
        """
        global_var_name = self.func_code.co_names[oparg]
        if global_var_name in self.py_func.__globals__:
            global_var_value = self.py_func.__globals__[ global_var_name ]
            return self.type_registry.from_python_object( global_var_value )
        return self.type_registry.get_builtin_type( global_var_name )

    def record_local_var_type( self, local_var_index, var_type ):
        if local_var_index not in self.local_vars:
            unknown_type = rtypes.UnknownType()
            self.local_vars[local_var_index] = unknown_type
        else:
            unknown_type = self.local_vars[local_var_index]
        unknown_type.add_candidate_type( var_type )

    def opcode_load_global( self, oparg ):
        var_type = self.get_global_var_type( oparg )
        self.push_type( var_type )
        return -1

    def opcode_load_const( self, oparg ):
        const_value = self.func_code.co_consts[oparg]
        const_type = self.type_registry.from_python_object( const_value )
        self.push_constant_type( const_type, const_value )
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

    def opcode_pop_top( self, oparg ):
        self.pop_type()
        return -1

    def opcode_return_value( self, oparg ):
        return_type = self.pop_type()
        self.r_func_type.record_return_type( return_type )
        return -1

    def opcode_compare_op( self, oparg ):
        cmp_types = self.pop_types( 2 )
        self.push_type( rtypes.BOOL )
        return -1

    def opcode_pop_jump_if_false( self, oparg ):
        return -1

                
TYPE_ANNOTATOR_OPCODE_FUNCTIONS = make_opcode_functions_map( TypeAnnotator )
            
            
if __name__ == '__main__':
    pass
