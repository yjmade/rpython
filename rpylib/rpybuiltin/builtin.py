"""This modules defines python built-in functions and constant object.

Each global is annotated with relevant type information.
"""
from __future__ import unicode_literals
import ctypes
import rpybuiltin._win32kernel as _win32kernel

long = int # @todo introduce int64 type specification

SEEK_SET = 0
SEEK_CUR = 1
SEEK_END = 2

_WIN32_SEEK = { SEEK_SET: _win32kernel.FILE_BEGIN,
                SEEK_CUR: _win32kernel.FILE_CURRENT,
                SEEK_END: _win32kernel.FILE_END }


class RawFile(object):
    """Implementation of the RawFile interface using WIN32 API.
       Notes: only support BINARY file and returns/accepts bytes on read/write.
    """
    def __init__( self, path, mode='r', delete_on_close=False ):
        truncate = False
        if mode[0:1] == 'r':
            wmode = _win32kernel.FILE_GENERIC_READ
            creation_disposition = _win32kernel.OPEN_EXISTING
            self.__readable, self.__writable, self._seekable = True, False, True
        elif mode[0:1] == 'w':
            wmode = _win32kernel.FILE_GENERIC_WRITE
            creation_disposition = CREATE_ALWAYS | TRUNCATE_EXISTING
            self.__readable, self.__writable, self._seekable = False, True, True
        elif mode[0:1] == 'a':
            wmode = _win32kernel.FILE_GENERIC_WRITE
            creation_disposition = 0
            self.__readable, self.__writable, self._seekable = False, True, False
        if mode[1:2] == '+': # open for updating
            self.__readable, self.__writable = True, True
            if wmode == _win32kernel.FILE_GENERIC_WRITE:
                creation_disposition = _win32kernel.TRUNCATE_EXISTING
            else: # Creates file if it does not exist
                creation_disposition = _win32kernel.OPEN_ALWAYS
            wmode = _win32kernel.FILE_GENERIC_READ | _win32kernel.FILE_GENERIC_WRITE

        if delete_on_close:
            flag_attributes = _win32kernel.DWORD(_win32kernel.FILE_FLAG_DELETE_ON_CLOSE)
        else:
            flag_attributes = _win32kernel.DWORD(0)
        share_mode = _win32kernel.DWORD(0)
        creation_disposition = _win32kernel.DWORD(creation_disposition)
        self.__handle = _win32kernel.HANDLE(
            _win32kernel.CreateFileW(
                path, _win32kernel.DWORD(wmode), share_mode,
                _win32kernel.LPSECURITY_ATTRIBUTES(), creation_disposition,
                flag_attributes, _win32kernel.HANDLE() ) )
        self.__seekable = True
        _win32kernel.check_valid_handle( self.__handle, IOError )

    def __enter__( self ):
        return self

    def __exit__( self, exc_type, exc_val, exc_tb ): # context manager protocol
        self.close()
    
    def close( self ):
        if self.__handle != _win32kernel.INVALID_HANDLE_VALUE:
            _win32kernel.CloseHandle( self.__handle )
            self.__handle = _win32kernel.INVALID_HANDLE_VALUE
    close.rpy_return_type = type(None)

    def __check_not_closed( self ):
        if self.__handle == _win32kernel.INVALID_HANDLE_VALUE:
            raise ValueError( 'I/O operation on closed file' )
    __check_not_closed.rpy_return_type = type(None)

    @property
    def closed( self ):
        return self.__handle == _win32kernel.INVALID_HANDLE_VALUE

    def flush( self ):
        """Flush pending write to disk. If file is a pipe, wait for client to read all data.
        """
        self.__check_not_closed()
        # Notes: FlushFileBuffers will fail if file was not open with
        # GENERIC_WRITE access
        if self.__writable: 
            _win32kernel.check_io_succeed(
                _win32kernel.FlushFileBuffers( self.__handle ) )
    flush.rpy_return_type = type(None)

    def fileno( self ):
        """Returns the Windows file handle.
        """
        self.__check_not_closed()
        return self.__handle
    fileno.rpy_return_type = int

    def isatty( self ):
        self.__check_not_closed()
        return False
    isatty.rpy_return_type = bool

    def readable( self ):
        self.__check_not_closed()
        return self.__readable
    readable.rpy_return_type = bool

    def seek( self, offset, whence=SEEK_SET):
        self.__check_not_closed()
        seek_method = _WIN32_SEEK[whence]
        new_pos = _win32kernel.LARGE_INTEGER()
        _win32kernel.check_io_succeed(
            _win32kernel.SetFilePointerEx( self.__handle,
                              _win32kernel.LARGE_INTEGER( offset ),
                              ctypes.byref( new_pos ),
                              seek_method ) )
        return new_pos.value
    seek.rpy_return_type = long
    seek.rpy_parameter_types = {
        'offset': long,
        'whence': ('enum', {'SEEK_SET': SEEK_SET,
                            'SEEK_CUR': SEEK_CUR,
                            'SEEK_END': SEEK_END} )
        }

    def seekable( self ):
        self.__check_not_closed()
        return self.__seekable
    seekable.rpy_return_type = bool

    def tell( self ):
        self.__check_not_closed()
        return self.seek( 0, whence=SEEK_CUR )
    seekable.rpy_return_type = long

    def truncate( self, size=None ):
        self.__check_not_closed()
        if size is not None:
            self.seek( size, whence=SEEK_SET )
        # Truncate file at current position
        _win32kernel.check_io_succeed( SetEndOfFile( self.__handle ) )
    truncate.rpy_return_type = type(None)
    truncate.rpy_parameter_types = {
        'size': ('optional', long) # optional indicates that value may be None
        }

    def writable( self ):
        self.__check_not_closed()
        return self.__writable
    writable.rpy_return_type = bool

    def read( self, n=-1 ):
        """Reads at most the specified number of bytes."""
        if n < 0:
            return self.readall()
        if n > 0x7fffffff:
            raise ValueError( "Can not read more than 0x7fffffff bytes at once." )
        self.__check_not_closed()
        buffer = ctypes.create_string_buffer( n )
        to_read = _win32kernel.DWORD( min(0x7fffffff, n) )
        bytes_read = _win32kernel.DWORD()
        if not _win32kernel.ReadFile( self.__handle, buffer,
            to_read,
            ctypes.byref(bytes_read),
            _win32kernel.LPOVERLAPPED() ):
            if _win32kernel.GetLastError() != _win32kernel.ERROR_HANDLE_EOF:
                raise _win32kernel.make_windows_error()
        size = bytes_read.value
        if size < n:
            return buffer[:size]
        return buffer.raw
    read.rpy_return_type = ('memoryview',)
    read.rpy_parameter_types = { 'n': long }

    def readall( self ):
        """Reads all the data of the file until EOF."""
        self.__check_not_closed()
        size = _win32kernel.LARGE_INTEGER()
        _win32kernel.check_io_succeed(
            _win32kernel.GetFileSizeEx( self.__handle, ctypes.byref(size) ) )
        return self.read( size.value )
    readall.rpy_return_type = ('memoryview',)

    def readline( self, sizehint=0 ):
        if sizehint <= 0:
            sizehint = 2048
        data = self.read( sizehint )
        index = data.find( b'\n' )
        if index != -1:
            offset = index + 1 - len(data)
            if offset:
                self.seek( offset, SEEK_CUR )
            return data[:index+1]
        if len(data) < sizehint: # eof found
            return data

        result = [data]
        while True:
            data = self.read( sizehint )
            index = data.find( b'\n' )
            if index != -1:
                offset = index + 1 - len(data)
                if offset:
                    self.seek( offset, SEEK_CUR )
                result.append( data[:index+1] )
                break
            elif len(data) < sizehint: # eof found
                result.append( data )
                break
        return b''.join( result )
    readline.rpy_return_type = ('memoryview',)

    def readlines( self, sizehint=0 ):
        if sizehint == 0:
            data = self.readall()
        else:
            data = self.read( sizehint )
        lines = []
        index = 0
        while index < len(data):
            next_eol_index = data.find( b'\n', index )
            if next_eol_index != -1:
                lines.append( data[index:next_eol_index+1] )
            elif len(data) < sizehint or sizehint == 0: # eof found
                if index < len(data): # adds last trailing line without eol
                    lines.append( data[index:] )
                break
            else: # no eol found: restore position to last eol found
                offset = index - len(data)
                self.seek( offset, SEEK_CUR )
                break
            index = next_eol_index + 1
        return lines
                
                
        
    
RawFile.rpy_native = True # Indicates that this class is not implemented in rpy

class File(RawFile):

    def next( self ):
        pass
    next.rpy_return_type = str

    def readline( self, limit=-1 ):
        pass
    readline.rpy_return_type = (list, str) # list of string
    readline.rpy_parameter_types = {'limit': int}

    def readlines( self, hint=-1 ):
        pass
    readline.rpy_return_type = (list, str) # list of string
    readline.rpy_parameter_types = {'limit': int}

    def writelines( self, lines ):
        pass
    writelines.rpy_parameter_types = {
        'lines': (list, str) # list of string
        }
            
def open( filename, mode='r', bufsize=-1 ):
    return RawFile( filename, mode )
open.rpy_return_type = RawFile
open.rpy_parameter_types = {
    'filename': str,
    'mode': str,
    'bufsize': int }
