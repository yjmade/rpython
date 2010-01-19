import rpy
import unittest

class TestIntArithmetic(unittest.TestCase):

    def test_add_param( self ):
        def main(x, y):
            return x + y
        self.assertEqual( 3, rpy.run( main, 1, 2 ) )

    def test_sub_param( self ):
        def main(x, y):
            return x - y
        self.assertEqual( -1, rpy.run( main, 1, 2 ) )

    def test_mul_param( self ):
        def main(x, y):
            return x * y
        self.assertEqual( -6, rpy.run( main, 2, -3 ) )

    def test_div_param( self ):
        def main(x, y):
            return x // y
        self.assertEqual( -4, rpy.run( main, 20, -5 ) )

    def test_reminder_param( self ):
        def main(x, y):
            return x % y
        self.assertEqual( 2, rpy.run( main, 22, 5 ) )

    def test_misc1_param( self ):
        def main(a, b, c):
            return a + b*b + c*c*c
        self.assertEqual( 2 + 3*3 + 5*5*5, rpy.run( main, 2, 3, 5 ) )

class TestIntArithmeticInPlace(unittest.TestCase):

    def test_add_param( self ):
        def main(x, y):
            z = x
            z += y
            return z
        self.assertEqual( 3, rpy.run( main, 1, 2 ) )

    def test_sub_param( self ):
        def main(x, y):
            z = x
            z -= y
            return z
        self.assertEqual( -1, rpy.run( main, 1, 2 ) )

    def test_mul_param( self ):
        def main(x, y):
            z = x
            z *= y
            return z
        self.assertEqual( -6, rpy.run( main, 2, -3 ) )

    def test_div_param( self ):
        def main(x, y):
            z = x
            z //= y
            return z
        self.assertEqual( -4, rpy.run( main, 20, -5 ) )

    def test_reminder_param( self ):
        def main(x, y):
            z = x
            z %= y
            return z
        self.assertEqual( 2, rpy.run( main, 22, 5 ) )

if __name__ == '__main__':
    unittest.main()
