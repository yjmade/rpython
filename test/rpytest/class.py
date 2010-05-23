import rpy
import unittest

class Point:
    def __init__( self, xparam, yparam ):
        self.x = xparam
        self.y = yparam

class TestClass(unittest.TestCase):
    def test_class_decl( self ):
        def main_class_decl(x, y):
            p = Point(x,y)
            return p.x + p.y
        self.assertEqual( 5, rpy.run( main_class_decl, 2, 3 ) )


if __name__ == '__main__':
    unittest.main()
