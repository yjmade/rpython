import rpy
import unittest


class TestFlowControl(unittest.TestCase):
    def test_if1( self ):
        def main_if(x, y):
            if x < y:
                return x
            return y
        self.assertEqual( 1234, rpy.run( main_if, 1234, 4567 ) )

    def test_if2( self ):
        def main_if(x, y):
            if x < y:
                z = 2 * x
            else:
                z = 2 * y
            return z
        self.assertEqual( 20, rpy.run( main_if, 10, 30 ) )
        self.assertEqual( 20, rpy.run( main_if, 30, 10 ) )

    def test_nested_if1( self ):
        def main_if(x, y, z):
            if x < y:
                if x < z:
                    min_value = x
                else:
                    min_value = z
            elif y < z:
                min_value = y
            else:
                min_value = z
            return min_value
        self.assertEqual( 1, rpy.run( main_if, 1, 2, 3 ) )
        self.assertEqual( 1, rpy.run( main_if, 2, 1, 3 ) )
        self.assertEqual( 1, rpy.run( main_if, 2, 3, 1 ) )
        self.assertEqual( 1, rpy.run( main_if, 3, 2, 1 ) )
        self.assertEqual( 1, rpy.run( main_if, 3, 1, 2 ) )

    def test_while1( self ):
        def main_while( x ):
            count = x
            value = 0
            while count > 0:
                value += count
                count -= 1
            return value
        self.assertEqual( 1+2, rpy.run( main_while, 2 ) )

if __name__ == '__main__':
    unittest.main()
