import unittest
import os.path
import os
from rpybuiltin.builtin import open

TEST_DATA_DIR = os.path.join( os.path.dirname(os.path.abspath(__file__)), 'test_data' )

PATH_ZERO = os.path.join( TEST_DATA_DIR, 'zero.data' )
PATH_256 = os.path.join( TEST_DATA_DIR, '256.data' )
PATH_EMPTY = os.path.join( TEST_DATA_DIR, 'empty.data' )
PATH_5LINES = os.path.join( TEST_DATA_DIR, '5lines.data' )

EXPECTED_5LINES = [
    b'line\0one\n',
    b'second\0 line\n',
    b'third\0\tline\n',
    b'fourth \0line'
    ]


class TestReadOnlyRawFile(unittest.TestCase):
    def test_open_binary_ro_empty( self ):
        with open( PATH_EMPTY, 'rb' ) as f:
            self.assertEquals( b'', f.read() )
        self.assertRaises( ValueError, f.read ) # ValueError: I/O operation on closed file

    def test_open_binary_ro_zero( self ):
        with open( PATH_ZERO, 'rb' ) as f:
            self.assertEquals( b'\0', f.read() )
            self.assertEquals( b'', f.read() )

    def test_open_binary_ro_256( self ):
        with open( PATH_256, 'rb' ) as f:
            expected = bytes( x for x in range(0,256) )
            self.assertEquals( expected[:1], f.read(1) )
            self.assertEquals( expected[1:8], f.read(7) )
            self.assertEquals( expected[8:], f.read() )
            self.assertEquals( b'', f.read() )

    def test_tell( self ):
        with open( PATH_256, 'rb' ) as f:
            self.assertEquals( 0, f.tell() )
            f.read(7)
            self.assertEquals( 7, f.tell() )
            f.read() # read until eof
            self.assertEquals( 256, f.tell() )
        self.assertRaises( ValueError, f.tell ) # ValueError: I/O operation on closed file

    def test_seek( self ):
        with open( PATH_256, 'rb' ) as f:
            # relative to start
            f.seek( 7, os.SEEK_SET )
            self.assertEquals( 7, f.tell() )
            f.seek( 256, os.SEEK_SET )
            self.assertEquals( 256, f.tell() )
            f.seek( 512, os.SEEK_SET ) # beyond eof
            self.assertEquals( 512, f.tell() )
            # relative to end
            f.seek( 0, os.SEEK_END )
            self.assertEquals( 256, f.tell() )
            f.seek( 256, os.SEEK_END )
            self.assertEquals( 512, f.tell() )
            f.seek( -256, os.SEEK_END )
            self.assertEquals( 0, f.tell() )
            f.seek( -249, os.SEEK_END )
            self.assertEquals( 7, f.tell() )
            # relative to current
            f.seek( -6, os.SEEK_CUR )
            self.assertEquals( 1, f.tell() )
            f.seek( -1, os.SEEK_CUR )
            self.assertEquals( 0, f.tell() )
            self.assertRaises( IOError, f.seek, -1, os.SEEK_CUR )
            self.assertEquals( 0, f.tell() )
            f.seek( 256, os.SEEK_CUR )
            self.assertEquals( 256, f.tell() )
            f.seek( 256, os.SEEK_CUR )
            self.assertEquals( 512, f.tell() )
        self.assertRaises( ValueError, f.seek, 0, os.SEEK_SET ) # ValueError: I/O operation on closed file

    def test_closed( self ):
        with open( PATH_ZERO, 'rb' ) as f:
            self.assertTrue( not f.closed )
        self.assertTrue( f.closed )

    def test_readable( self ):
        with open( PATH_ZERO, 'rb' ) as f:
            self.assertTrue( f.readable() )
        self.assertRaises( ValueError, f.readable ) # ValueError: I/O operation on closed file

    def test_seekable( self ):
        with open( PATH_ZERO, 'rb' ) as f:
            self.assertTrue( f.seekable() )
        self.assertRaises( ValueError, f.seekable ) # ValueError: I/O operation on closed file

    def test_writable( self ):
        with open( PATH_ZERO, 'rb' ) as f:
            self.assertTrue( not f.writable() )
        self.assertRaises( ValueError, f.writable ) # ValueError: I/O operation on closed file

    def test_fileno( self ):
        with open( PATH_ZERO, 'rb' ) as f:
            n1 = f.fileno()
            n2 = f.fileno()
            self.assertEquals( n1, n2 )
        self.assertRaises( ValueError, f.fileno ) # ValueError: I/O operation on closed file

    def test_flush( self ):
        with open( PATH_ZERO, 'rb' ) as f:
            f.flush()

    def test_close( self ):
        with open( PATH_ZERO, 'rb' ) as f:
            self.assertTrue( not f.closed )
        f.close()
        self.assertTrue( f.closed )
        f.close() # no effect
        self.assertRaises( ValueError, f.read )
        self.assertRaises( ValueError, f.readable )
        self.assertRaises( ValueError, f.tell )

    def test_readlines( self ):
        with open( PATH_5LINES, 'rb' ) as f:
            lines = f.readlines()
            self.assertSequenceEqual( EXPECTED_5LINES, lines )

    def test_readline( self ):
        with open( PATH_5LINES, 'rb' ) as f:
            self.assertEqual( EXPECTED_5LINES[0], f.readline() )
            self.assertEqual( EXPECTED_5LINES[1], f.readline() )
            self.assertEqual( EXPECTED_5LINES[2], f.readline() )
            self.assertEqual( EXPECTED_5LINES[3], f.readline() )
            self.assertEqual( b'', f.readline() )
