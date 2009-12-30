from opcode import opname, EXTENDED_ARG, HAVE_ARGUMENT, cmp_op

class BytecodeCorruption(Exception):
    pass

def _opname2id( opname ):
    """Converts an opcode name into a valid python identifier.
       SLICE+0 => slice_0
    """
    opname = opname.replace('+', '_')
    return opname.lower()

def _make_op_ids():
    ids_by_code = {}
    for code, name in enumerate(opname):
        if not name.startswith('<'): # missing code
            ids_by_code[ code ] = _opname2id(name)
    return ids_by_code

# Dict of operation name by code
opcode_method_names = _make_op_ids()

CMP_LT = cmp_op.index('<')
CMP_LE = cmp_op.index('<=')
CMP_EQ = cmp_op.index('==')
CMP_NE = cmp_op.index('!=')
CMP_GT = cmp_op.index('>')
CMP_GE = cmp_op.index('>=')
CMP_IN = cmp_op.index('in')
CMP_NOT_IN = cmp_op.index('not in')
CMP_IS = cmp_op.index('is')
CMP_IS_NOT = cmp_op.index('is not')
CMP_EXCEPTION_MATCH = cmp_op.index('exception match')


def opcode_decoder( co_code, next_instr ):
    opcode = co_code[next_instr]
    next_instr += 1
    if opcode > HAVE_ARGUMENT:
        lo = co_code[next_instr]
        hi = co_code[next_instr+1]
        next_instr += 2
        oparg = (hi << 8) | lo
    else:
        oparg = 0
    while opcode == EXTENDED_ARG:
        opcode = co_code[next_instr]
        if opcode < HAVE_ARGUMENT:
            raise BytecodeCorruption( "Badly encoded extended arg opcode" )
        lo = co_code[next_instr+1]
        hi = co_code[next_instr+2]
        next_instr += 3
        oparg = (oparg << 16) | (hi << 8) | lo
    return next_instr, opcode, oparg

def make_opcode_functions_map( cls ):
    """Returns a dict { opcode : function(self, oparg) }.
    """
    functions_by_opcode = {}
    for opcode, name in opcode_method_names.items():
        function = getattr( cls, 'opcode_' + name, None )
        if function:
            functions_by_opcode[opcode] = function
##            print 'HANDLER FOR:', name
##        else:
##            print 'NO HANDLER FOR:', name
    return functions_by_opcode

if __name__ == '__main__':
    print( _opname2id( "SLICE+0" ) )
