@tit_test( TIT_INTEGER, TIT_INTEGER )
def add( x, y ):
    return x + y

@tit_test( TIT_INTEGER, TIT_INTEGER )
def sub( x, y ):
    return x - y

@tit_test( TIT_INTEGER, TIT_INTEGER )
def mul( x, y ):
    return x * y

@tit_test( TIT_INTEGER, TIT_INTEGER )
def div( x, y ):
    return x / y

@tit_test( TIT_INTEGER, TIT_INTEGER )
def reminder( x, y ):
    return x % y

@tit_test( TIT_INTEGER, TIT_INTEGER, TIT_INTEGER )
def mixed( a, b, c ):
    return a + b*b + c*c*c

@tit_test( TIT_INTEGER, TIT_INTEGER )
def inplace_add( x, y ):
    x += y
    return x

@tit_test( TIT_INTEGER, TIT_INTEGER )
def inplace_sub( x, y ):
    x -= y
    return x

@tit_test( TIT_INTEGER, TIT_INTEGER )
def inplace_mul( x, y ):
    x *= y
    return x

@tit_test( TIT_INTEGER, TIT_INTEGER )
def inplace_div( x, y ):
    x //= y
    return x

@tit_test( TIT_INTEGER, TIT_INTEGER )
def inplace_reminder( x, y ):
    x %= y
    return x
