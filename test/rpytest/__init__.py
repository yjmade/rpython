import os
import sys
import unittest

here = os.path.dirname(os.path.abspath(__file__))

def test_suite():
    # Fix python path
    sys.path.insert( 0, os.path.dirname(here) )
    # Loads all tests in the package
    suite = suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    for fn in os.listdir(here):
        if fn.endswith(".py"):
            modname = "rpytest." + fn[:-3]
            __import__(modname)
            module = sys.modules[modname]
            suite.addTests(loader.loadTestsFromModule(module))
    return suite

MAIN_SUITE = test_suite()

def main():
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(MAIN_SUITE)

if __name__ == '__main__':
    main()
