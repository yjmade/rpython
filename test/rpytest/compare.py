import rpy
import unittest

MIN_INT = -2147483648
MAX_INT = 2147483647

class TestCompare(unittest.TestCase):
    def test_lt( self ):
        def main_lt(x, y):
            return x < y
        self.assertEqual( True, rpy.run( main_lt, MIN_INT, MAX_INT ) )
        self.assertEqual( False, rpy.run( main_lt, MAX_INT, MIN_INT ) )
        self.assertEqual( False, rpy.run( main_lt, MAX_INT, MAX_INT ) )

    def test_le( self ):
        def main_le(x, y):
            return x <= y
        self.assertEqual( True, rpy.run( main_le, MIN_INT, MAX_INT ) )
        self.assertEqual( False, rpy.run( main_le, MAX_INT, MIN_INT ) )
        self.assertEqual( True, rpy.run( main_le, MAX_INT, MAX_INT ) )
        self.assertEqual( True, rpy.run( main_le, MIN_INT, MIN_INT ) )

    def test_eq( self ):
        def main_eq(x, y):
            return x == y
        self.assertEqual( False, rpy.run( main_eq, MIN_INT, MAX_INT ) )
        self.assertEqual( False, rpy.run( main_eq, MAX_INT, MIN_INT ) )
        self.assertEqual( True, rpy.run( main_eq, MAX_INT, MAX_INT ) )
        self.assertEqual( True, rpy.run( main_eq, MIN_INT, MIN_INT ) )

    def test_ne( self ):
        def main_ne(x, y):
            return x != y
        self.assertEqual( True, rpy.run( main_ne, MIN_INT, MAX_INT ) )
        self.assertEqual( True, rpy.run( main_ne, MAX_INT, MIN_INT ) )
        self.assertEqual( False, rpy.run( main_ne, MAX_INT, MAX_INT ) )
        self.assertEqual( False, rpy.run( main_ne, MIN_INT, MIN_INT ) )

    def test_ge( self ):
        def main_ge(x, y):
            return x >= y
        self.assertEqual( False, rpy.run( main_ge, MIN_INT, MAX_INT ) )
        self.assertEqual( True, rpy.run( main_ge, MAX_INT, MIN_INT ) )
        self.assertEqual( True, rpy.run( main_ge, MAX_INT, MAX_INT ) )
        self.assertEqual( True, rpy.run( main_ge, MIN_INT, MIN_INT ) )

    def test_gt( self ):
        def main_gt(x, y):
            return x > y
        self.assertEqual( False, rpy.run( main_gt, MIN_INT, MAX_INT ) )
        self.assertEqual( True, rpy.run( main_gt, MAX_INT, MIN_INT ) )
        self.assertEqual( False, rpy.run( main_gt, MAX_INT, MAX_INT ) )
        self.assertEqual( False, rpy.run( main_gt, MIN_INT, MIN_INT ) )

if __name__ == '__main__':
    unittest.main()
