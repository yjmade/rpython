import re
import sys

print """from __future__ import unicode_literals
import ctypes

_kernel = ctypes.windll.kernel32

# Win32 API => ctypes type mapping
LPCTSTR = ctypes.c_wchar_p
LPTSTR = LPCTSTR
DWORD = ctypes.c_uint # hmm.. actually unsigned long
LPDWORD = ctypes.POINTER(DWORD)
HANDLE = ctypes.c_void_p # Notes: actually represented as int in python
LPCVOID = ctypes.c_void_p
LPVOID = LPCVOID
HANDLE = LPVOID
BOOL = ctypes.c_uint
LARGE_INTEGER = ctypes.c_longlong
PLARGE_INTEGER = ctypes.POINTER(LARGE_INTEGER)
ULONG_PTR = LPVOID
LONG_PTR = LPVOID
va_list = ctypes.c_char_p
va_list_p = ctypes.POINTER(va_list)

class SECURITY_ATTRIBUTES(ctypes.Structure):
    _fields_ = [ ('nLength', DWORD),
                 ('lpSecurityDescriptor', LPVOID),
                 ('bInheritHandle', BOOL) ]
LPSECURITY_ATTRIBUTES = ctypes.POINTER(SECURITY_ATTRIBUTES)

class OVERLAPPED(ctypes.Structure):
    _fields_ = [ ('Internal', ULONG_PTR),
                 ('InternalHigh', ULONG_PTR),
                 ('Offset', DWORD),
                 ('OffsetHigh', DWORD),
                 ('hEvent', HANDLE) ]
LPOVERLAPPED = ctypes.POINTER(OVERLAPPED)

INVALID_HANDLE_VALUE = HANDLE( -1 )
INVALID_FILE_SIZE = DWORD( 0xFFFFFFFF )
INVALID_SET_FILE_POINTER = DWORD( -1 )
INVALID_FILE_ATTRIBUTES = DWORD( -1 )

FILE_BEGIN = DWORD(0)
FILE_CURRENT = DWORD(1)
FILE_END = DWORD(2)

DELETE = (0x00010000)
READ_CONTROL = (0x00020000)
WRITE_DAC = (0x00040000)
WRITE_OWNER = (0x00080000)
SYNCHRONIZE = (0x00100000)

# The following are masks for the predefined standard access types
STANDARD_RIGHTS_REQUIRED = (0x000F0000)

STANDARD_RIGHTS_READ = (READ_CONTROL)
STANDARD_RIGHTS_WRITE = (READ_CONTROL)
STANDARD_RIGHTS_EXECUTE = (READ_CONTROL)

STANDARD_RIGHTS_ALL = (0x001F0000)

SPECIFIC_RIGHTS_ALL = (0x0000FFFF)

# AccessSystemAcl access type
ACCESS_SYSTEM_SECURITY = (0x01000000)

# MaximumAllowed access type
MAXIMUM_ALLOWED = (0x02000000)



FILE_READ_DATA = ( 0x0001 ) #  file & pipe
FILE_LIST_DIRECTORY = ( 0x0001 ) #  directory

FILE_WRITE_DATA = ( 0x0002 ) #  file & pipe
FILE_ADD_FILE = ( 0x0002 ) #  directory

FILE_APPEND_DATA = ( 0x0004 ) #  file
FILE_ADD_SUBDIRECTORY = ( 0x0004 ) #  directory
FILE_CREATE_PIPE_INSTANCE = ( 0x0004 ) #  named pipe


FILE_READ_EA = ( 0x0008 ) #  file & directory

FILE_WRITE_EA = ( 0x0010 ) #  file & directory

FILE_EXECUTE = ( 0x0020 ) #  file
FILE_TRAVERSE = ( 0x0020 ) #  directory

FILE_DELETE_CHILD = ( 0x0040 ) #  directory

FILE_READ_ATTRIBUTES = ( 0x0080 ) #  all

FILE_WRITE_ATTRIBUTES = ( 0x0100 ) #  all

FILE_ALL_ACCESS = (STANDARD_RIGHTS_REQUIRED | SYNCHRONIZE | 0x1FF)

FILE_GENERIC_READ = (STANDARD_RIGHTS_READ     |
                     FILE_READ_DATA           |
                     FILE_READ_ATTRIBUTES     |
                     FILE_READ_EA             |
                     SYNCHRONIZE)


FILE_GENERIC_WRITE = (STANDARD_RIGHTS_WRITE    |
                      FILE_WRITE_DATA          |
                      FILE_WRITE_ATTRIBUTES    |
                      FILE_WRITE_EA            |
                      FILE_APPEND_DATA         |
                      SYNCHRONIZE)

FILE_GENERIC_EXECUTE = (STANDARD_RIGHTS_EXECUTE  |
                        FILE_READ_ATTRIBUTES     |
                        FILE_EXECUTE             |
                        SYNCHRONIZE)


FILE_SHARE_READ = 0x00000001  
FILE_SHARE_WRITE = 0x00000002  
FILE_SHARE_DELETE = 0x00000004  
FILE_ATTRIBUTE_READONLY = 0x00000001  
FILE_ATTRIBUTE_HIDDEN = 0x00000002  
FILE_ATTRIBUTE_SYSTEM = 0x00000004  
FILE_ATTRIBUTE_DIRECTORY = 0x00000010  
FILE_ATTRIBUTE_ARCHIVE = 0x00000020  
FILE_ATTRIBUTE_DEVICE = 0x00000040  
FILE_ATTRIBUTE_NORMAL = 0x00000080  
FILE_ATTRIBUTE_TEMPORARY = 0x00000100  
FILE_ATTRIBUTE_SPARSE_FILE = 0x00000200  
FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400  
FILE_ATTRIBUTE_COMPRESSED = 0x00000800  
FILE_ATTRIBUTE_OFFLINE = 0x00001000  
FILE_ATTRIBUTE_NOT_CONTENT_INDEXED = 0x00002000  
FILE_ATTRIBUTE_ENCRYPTED = 0x00004000  
FILE_ATTRIBUTE_VIRTUAL = 0x00010000  
FILE_NOTIFY_CHANGE_FILE_NAME = 0x00000001   
FILE_NOTIFY_CHANGE_DIR_NAME = 0x00000002   
FILE_NOTIFY_CHANGE_ATTRIBUTES = 0x00000004   
FILE_NOTIFY_CHANGE_SIZE = 0x00000008   
FILE_NOTIFY_CHANGE_LAST_WRITE = 0x00000010   
FILE_NOTIFY_CHANGE_LAST_ACCESS = 0x00000020   
FILE_NOTIFY_CHANGE_CREATION = 0x00000040   
FILE_NOTIFY_CHANGE_SECURITY = 0x00000100   
FILE_ACTION_ADDED = 0x00000001   
FILE_ACTION_REMOVED = 0x00000002   
FILE_ACTION_MODIFIED = 0x00000003   
FILE_ACTION_RENAMED_OLD_NAME = 0x00000004   
FILE_ACTION_RENAMED_NEW_NAME = 0x00000005   
MAILSLOT_NO_MESSAGE = DWORD(-1)
MAILSLOT_WAIT_FOREVER = DWORD(-1)
FILE_CASE_SENSITIVE_SEARCH = 0x00000001  
FILE_CASE_PRESERVED_NAMES = 0x00000002  
FILE_UNICODE_ON_DISK = 0x00000004  
FILE_PERSISTENT_ACLS = 0x00000008  
FILE_FILE_COMPRESSION = 0x00000010  
FILE_VOLUME_QUOTAS = 0x00000020  
FILE_SUPPORTS_SPARSE_FILES = 0x00000040  
FILE_SUPPORTS_REPARSE_POINTS = 0x00000080  
FILE_SUPPORTS_REMOTE_STORAGE = 0x00000100  
FILE_VOLUME_IS_COMPRESSED = 0x00008000  
FILE_SUPPORTS_OBJECT_IDS = 0x00010000  
FILE_SUPPORTS_ENCRYPTION = 0x00020000  
FILE_NAMED_STREAMS = 0x00040000  
FILE_READ_ONLY_VOLUME = 0x00080000  
FILE_SEQUENTIAL_WRITE_ONCE = 0x00100000  
FILE_SUPPORTS_TRANSACTIONS = 0x00200000  

CREATE_NEW         = 1
CREATE_ALWAYS      = 2
OPEN_EXISTING      = 3
OPEN_ALWAYS        = 4
TRUNCATE_EXISTING  = 5

ERROR_HANDLE_EOF = 38

FORMAT_MESSAGE_ALLOCATE_BUFFER = 0x00000100
FORMAT_MESSAGE_IGNORE_INSERTS = 0x00000200
FORMAT_MESSAGE_FROM_STRING = 0x00000400
FORMAT_MESSAGE_FROM_HMODULE = 0x00000800
FORMAT_MESSAGE_FROM_SYSTEM = 0x00001000
FORMAT_MESSAGE_ARGUMENT_ARRAY = 0x00002000
FORMAT_MESSAGE_MAX_WIDTH_MASK = 0x000000FF

def MAKELANGID(p, s):
    return DWORD( (s << 10) | p )

def PRIMARYLANGID(lgid):
    return DWORD( lgid & 0x3ff )
    
def SUBLANGID(lgid):
    return DWORD( lgid >> 10 )

LANG_NEUTRAL = 0x00
SUBLANG_DEFAULT = 0x01    # user default

def make_windows_error( exc_class=WindowsError ):
    'Raise WindowsError exception using GetLastError message.'
    win_error_id = GetLastError();
    flags = DWORD( FORMAT_MESSAGE_FROM_SYSTEM |
                   FORMAT_MESSAGE_IGNORE_INSERTS )
    msg_buffer = ctypes.create_unicode_buffer( 512 )
    lang_id = MAKELANGID(LANG_NEUTRAL, SUBLANG_DEFAULT)
    length = FormatMessageW( flags, LPCVOID(), win_error_id, 
        lang_id, msg_buffer, len(msg_buffer), va_list_p() )
    error = exc_class( msg_buffer.value )
    error.errno = 0
    error.winerror = win_error_id
    error.strerror = msg_buffer.value
    return error

def check_valid_handle( handle, exc_class=WindowsError ):
    if handle.value == INVALID_HANDLE_VALUE:
        raise make_windows_error( exc_class )

def check_succeed( c_bool_value ):
    if not c_bool_value:
        raise make_windows_error()

def check_io_succeed( c_bool_value ):
    if not c_bool_value:
        raise make_windows_error( IOError )

"""

def normalize_type( param_type ):
    if param_type == 'va_list*':
        param_type = 'va_list_p'
    return param_type

def output_ctypes_fn( name, return_type, param_types ):
    """Prints generated ctypes code for the specified function."""
    param_types = [ (t[0], normalize_type(t[1]), t[2]) for t in param_types ]
    has_unicode_variant = len([t for t in param_types if t[1] in ('LPCTSTR', 'LPTSTR')]) > 0
    unicode_suffix = has_unicode_variant and 'W' or ''
    fnname = '_kernel.%s%s' % (name, unicode_suffix)
    print '%s.argtypes= [%s]' % (fnname, ', '.join( [t[1] for t in param_types] ))
    print '%s.restype=%s' % (fnname, return_type)
    print '%s.__doc__="%s %s(%s)"' % (fnname, return_type, name,
                                      ', '.join( [' '.join(t) for t in param_types] ) )
    print
    return fnname

##HANDLE WINAPI CreateFile(
##  __in          LPCTSTR lpFileName,
##  __in          DWORD dwDesiredAccess,
##  __in          DWORD dwShareMode,
##  __in          LPSECURITY_ATTRIBUTES lpSecurityAttributes,
##  __in          DWORD dwCreationDisposition,
##  __in          DWORD dwFlagsAndAttributes,
##  __in          HANDLE hTemplateFile
##);
REX = re.compile( r"\b(\w+)\b\s+WINAPI\s+\b(\w+)\b\(([^)]*)\);" )

input = open( sys.argv[1], 'rt' ).read()
fnnames = []
for m in REX.finditer( input ):
    return_type, name, parameters = m.groups()
    parameters = parameters.strip().split(',')
    if len(parameters) == 1 and parameters[0] == 'void':
        param_types = []
    else:
        param_types = []
        for param in parameters:
            in_out, param_type, param_name = [s.strip() for s in param.strip().split()]
            param_types.append( (in_out, param_type, param_name) )
    fnnames.append( output_ctypes_fn( name, return_type, param_types ) )

print
for name in fnnames:
    basename = name.split('.')[1]
    print '%s = %s' % (basename, name)
