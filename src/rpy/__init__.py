def entry_point( f ):
    f.rpy_entry_point = True
    return f

class CallableGraphAnnotator(object):
    def __init__( self, type_registry ):
        self.to_annotate = set()
        self.referenced_by = {} # Dict {CallableType: [CallableType]}
        self.annotator_by_callable = {} # Dict {CallableType: TypeAnnotator}
        self.annotator_by_func = {} # Dict {py_func: TypeAnnotator}
        self.type_registry = type_registry
        self.entry_point = None
        self.current_callable = None
        type_registry.set_callable_listener( self._on_callable_reference )

    def set_entry_point( self, py_func, call_args ):
        """Sets the python function object used as entry point with the type f its parameters.
        """
        from rpy.typeinference import FunctionLocationHelper # Move this somewhere else...
        func_location = FunctionLocationHelper(py_func.__code__).get_location(0) # and avoid building this twice
        r_arg_types = [ self.type_registry.from_python_object(arg,
                                                              func_location)
                        for arg in call_args ]
        callable_type = self.type_registry.from_python_object( py_func, func_location )
        for index, r_arg_type in enumerate(r_arg_types):
            callable_type.record_arg_type( index, r_arg_type )
        self.to_annotate.add( callable_type )
        self.entry_point = callable_type

    def get_function_annotation( self, py_func ):
        """Returns the TypeAnnotator associated to the specified function.
        """
        return self.annotator_by_func[ py_func ]

    def annotate_dependencies( self ):
        from rpy.typeinference import TypeAnnotator
        while self.to_annotate:
            r_func_type = next( iter( self.to_annotate ) )
            self.to_annotate.remove( r_func_type )
            
            self.current_callable = None
            annotator = TypeAnnotator( r_func_type, self.type_registry )
            self.annotator_by_callable[ r_func_type ] = annotator
            py_func = r_func_type.get_function_object()
            self.annotator_by_func[ py_func ] = annotator
            self.current_callable = annotator.r_func_type

            print( 'Source of %s' % py_func )
            print( annotator.get_function_source() )
            print( 'Disassembly of %s:' % py_func )
            import dis
            dis.dis( py_func )
            annotator.explore_function_opcodes()
            annotator.report()
    
    def _on_callable_reference( self, callable_type ):
        print( '===> Callable added:', callable_type )
        if callable_type not in self.annotator_by_callable:
            self.to_annotate.add( callable_type )
        if self.current_callable is not None:
            if self.current_callable not in self.referenced_by:
                self.referenced_by[self.current_callable] = set()
            self.referenced_by[self.current_callable].add( callable_type )

class CodeGenerator(object):
    def __init__( self, annotator ):
        self.annotator = annotator

def optimize( module ):
    """Run LLVM optimization passes on the provided ModuleGenerator code.
    """
    from llvm.passes import (PassManager,
                             PASS_PROMOTE_MEMORY_TO_REGISTER)
    from llvm.ee import TargetData
    pm = PassManager.new()
    # Add the target data as the first "pass". This is mandatory.
    pm.add( TargetData.new('') )

    passes = []
    # This pass convert memory access to local variable (allocated via alloca)
    # to register and generates the corresponding phi-nodes.
    passes.append( PASS_PROMOTE_MEMORY_TO_REGISTER )
    #passes = [PASS_AGGRESSIVE_DCE, PASS_FUNCTION_INLINING]
    for l_pass in passes:
        pm.add( l_pass )

    # Run all the optimization passes over the module
    pm.run( module.l_module )


def run( py_main_func, *call_args ):
    from rpy.rtypes import ConstantTypeRegistry
    registry = ConstantTypeRegistry()
    # Annotates call graph types (local var, functions param/return...)
    print( '\nAnalysing call graph...\n%s' % ('='*70) )
    annotator = CallableGraphAnnotator( registry )
    annotator.set_entry_point( py_main_func, call_args )
    annotator.annotate_dependencies()
    # Generate LLVM code
    from rpy.codegenerator import ModuleGenerator, FunctionCodeGenerator, L_INT_TYPE, L_BOOL_TYPE
    module = ModuleGenerator( registry )
    l_func_entry, l_func_type = None, None
    # Declares all function in modules
    fn_code_generators = []
    for r_func_type, type_annotator in annotator.annotator_by_callable.items():
        py_func = r_func_type.get_function_object()
        print( '\nDeclaring function:\n%s\nPython: %s\nRType: %s' % ('-'*70, py_func, r_func_type) )
        func_generator = FunctionCodeGenerator( py_func, module,
                                                annotator )
        fn_code_generators.append( (r_func_type, func_generator) )
    # Makes sure that all class type have their struct/attribute index dict initialized
    for r_func_type, _ in fn_code_generators:
        if r_func_type.is_constructor():
            module.llvm_type_from_rtype( r_func_type )
    # Generates function's code, possibly referencing previously declared functions
    for r_func_type, func_generator in fn_code_generators:
        print( '\nGenerating code for function:\n%s\n%s\nSouce:\n' % ('-'*70, r_func_type) )
        print( func_generator.annotation.get_function_source() )
        func_generator.generate_llvm_code()
        func_generator.report()
        if r_func_type.get_function_object() is py_main_func:
            l_func_entry = func_generator.l_func
            l_func_type = func_generator.l_func_type
    print( 'Generated module code:' )
    print( '----------------------\n%s', module.l_module )
    optimize( module )
    print( 'Generated module code after optimization:' )
    print( '-----------------------------------------\n', module.l_module )
    
    # Execute generate code
    # 1) Convert call args into generic value
    print( 'Invoking function with %r' % (call_args,) )
    from llvm.core import ModuleProvider, TYPE_VOID
    from llvm.ee import ExecutionEngine, GenericValue
    module_provider = ModuleProvider.new( module.l_module )
    engine = ExecutionEngine.new( module_provider )
    l_call_args = []
    for py_call_arg, l_arg in zip( call_args, l_func_entry.args ):
        if l_arg.type == L_INT_TYPE:
            l_call_args.append( GenericValue.int_signed( L_INT_TYPE, py_call_arg ) )
        elif l_arg.type == L_BOOL_TYPE:
            l_call_args.append( GenericValue.int( L_BOOL_TYPE, py_call_arg ) )
        else:
            raise ValueError( 'Unsupported parameter "%s" of type: %r' % (py_call_arg, l_arg_type) )
    # 2) run the functions
    l_return_value = engine.run_function( l_func_entry, l_call_args )
    # 3) convert LLVM return value into python type
    if l_func_type.return_type == L_INT_TYPE:
        return l_return_value.as_int_signed()
    elif l_func_type.return_type == L_BOOL_TYPE:
        return l_return_value.as_int() and True or False
    elif l_func_type.return_type.kind == TYPE_VOID:
        return None
    print( 'Return:',  l_return_value )
    raise ValueError( 'Unsupported return type "%s"' % l_func_entry.return_type )
    