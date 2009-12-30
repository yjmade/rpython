import os
import sys
import unittest

here = os.path.dirname(os.path.abspath(__file__))

def test_suite():
    suite = suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    for fn in os.listdir(here):
        if fn.startswith("test") and fn.endswith(".py"):
            modname = "rpybuiltin.tests." + fn[:-3]
            __import__(modname)
            module = sys.modules[modname]
            suite.addTests(loader.loadTestsFromModule(module))
    return suite

MAIN_SUITE = test_suite()

def main():
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(MAIN_SUITE)

if __name__ == '__main__':
    import rpy
    rpy.run( main )
    #main()
