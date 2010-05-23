import rpy
import unittest

def mul2i( x, y ):
    return x * y

class TestFunctionCall(unittest.TestCase):
    def test_fn_call( self ):
        def main_fn_call(x, y):
            return mul2i(x, y )
        self.assertEqual( 12, rpy.run( main_fn_call, 6, 2 ) )


if __name__ == '__main__':
    unittest.main()
