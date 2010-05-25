import rpy.typeinference2 as typeinference
import unittest
import os.path
import sys
import glob
import io

here = os.path.join( '.', os.path.dirname(__file__) )
test_data_dir = os.path.join( here, 'test_data' )
test_data_out_dir = os.path.join( here, 'test_data.out' )

THIS_MODULE = 'rpytypeinference'

def test_suite():
    suite = additional_tests()
    loader = unittest.TestLoader()
    for fn in os.listdir(here):
        if fn.startswith("test") and fn.endswith(".py"):
            modname = THIS_MODULE + '.' + fn[:-3]
            __import__(modname)
            module = sys.modules[modname]
            suite.addTests(loader.loadTestsFromModule(module))
    return suite

def _to_test_method_name( path ):
    filename = os.path.basename( path )
    name = 'test_' + filename.replace('.', '_').replace('-','_')[:-5]
    return name.rstrip('_')

def _execfile(path, globals, locals):
    with open(path, "r") as f:
        compiled = compile(f.read(), path, 'exec')
        exec( compiled, globals, locals)

class TypeInferenceTest(unittest.TestCase):
    def check_type_inference( self, module_name, base_path ):
        """Executes the specified python module, and provides the following in global:
        tit_test: a function decorator used to mark test function entry point. It
                  takes a list of TIT_* corresponding to the entry point parameter
                  types.
        """
        type_manager = typeinference.TypeManager()
        entry_points = []
        def test_marker( *arg_types ):
            def decorator( f ):
                entry_points.append( (f, arg_types) )
                return f
            return decorator
        globals = {
            'type_manager': type_manager,
            'TIT_INTEGER': typeinference.TIT_INTEGER,
            'tit_test': test_marker
            }
        locals = {}
        _execfile( base_path + '.py', globals, locals )
        for entry_point, arg_types in entry_points:
            type_manager.add_typed_function( entry_point, arg_types )
        type_manager.infer_types()
        def sort_key( ti_function ):
            if ti_function.py_callable in entry_points:
                index = entry_points.index( ti_function.py_callable )
                return (0, index, ti_function.short_repr())
            return (1, 0, ti_function.short_repr())
        ti_functions = sorted( type_manager.all_ti_functions(),
                               key=sort_key )
        report = io.StringIO()
        for ti_function in ti_functions:
            print( 'Function %s:' % (ti_function.short_repr()),
                   file=report )
            for index in range(0, ti_function.nb_args):
                element = ti_function.arg_element(index)
                print( '  Arg[%s:%d]: %s' % (element.name, index+1,
                                             element.type_repr()),
                   file=report )
            element = ti_function.return_element
            print( '  Return: %s' % (element.type_repr()), file=report )
            for index in range(0, ti_function.nb_local_vars):
                element = ti_function.local_var_element(index)
                print( '  LocalVar[%s:%d]: %s' % (element.name, index+1,
                                                  element.type_repr()),
                   file=report )
            print(file=report)
        print( report.getvalue() )
        report_path = os.path.join( test_data_out_dir,
                                    os.path.basename(base_path) + '.report.txt' )
        if not os.path.isdir( test_data_out_dir ):
            os.makedirs( test_data_out_dir )
        with open( report_path, 'w', encoding='utf-8' ) as f:
            f.write( report.getvalue() )
        expected_report_path = base_path + '.report.txt'
        assert os.path.isfile( expected_report_path ), expected_report_path + ' is missing'
        with open( report_path, 'r', encoding='utf-8' ) as f:
            expected_report = f.read().replace('\r\n','\n')
        assert expected_report == report.getvalue(), expected_report_path + ' != ' + report_path
        

def additional_tests():
    """Generates test method on TypeInferenceTest based on test_data file names.
    """
    print( 'Scanning:', os.path.join( test_data_dir, '*test.py' ) )
    for entry in glob.glob( os.path.join( test_data_dir, '*test.py' ) ):
        filename = os.path.basename( entry )
        module_name = THIS_MODULE + '.test_data.' + filename[:-3]
        base_path = os.path.splitext(entry)[0]
        def test_type_inference( self, basename=filename, module_name=module_name, base_path=base_path):
            self.check_type_inference( module_name, base_path )
        setattr( TypeInferenceTest, _to_test_method_name(base_path), test_type_inference )
    test_suite = unittest.TestSuite()
    loader = unittest.TestLoader().loadTestsFromTestCase
    test_suite.addTests( loader(TypeInferenceTest) )
    return test_suite

def main():
    suite = test_suite()
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)

if __name__ == '__main__':
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    main()
