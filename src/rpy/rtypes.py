"""Types
"""
import types

class Type(object):
    def get_instance_attribute_type( self, type_registry, attribute_name ):
        """Gets the type of a module/class/instance attribute.
        """
        raise ValueError( 'Unsupported attribute reference: %r.%s' % (self, attribute_name) )

    def attach_to_instance( self, instance_type ):
        """Attachs the type to an instance (attribute look-up).
           Used to convert a function type into a method type.
        """
        return self

    def get_function_object( self ):
        """Returns the associated python function."""
        raise NotImplementedError()

    def get_resolved_type( self, type_registry ):
        """Returns the resolved type corresponding to this type."""
        return self


class NoneType(Type):
    def __repr__( self ):
        return 'NoneType()'

NONE = NoneType()

class CallableType(Type):
    def __init__( self ):
        super(CallableType, self).__init__()
        self._arg_types = {}
        self._return_type = UnknownType()

    def get_return_type( self ):
        return self._return_type

    def get_arg_count( self ):
        raise NotImplementedError()

    def get_arg_types( self ):
        return [ self.get_arg_type(index)
                 for index in range(0, self.get_arg_count()) ]

    def get_arg_type( self, index ):
        assert index < self.get_arg_count()
        if index not in self._arg_types:
            unknown_type = UnknownType()
            self._arg_types[index] = unknown_type
        else:
            unknown_type = self._arg_types[index]
        return unknown_type

    def record_arg_type( self, index, type ):
        unknown_type = self.get_arg_type( index )
        unknown_type.add_candidate_type( type )

    def record_keyword_arg_type( self, param_name, param_type ):
        param_index = self.get_param_index( param_name )
        self.record_arg_type( param_index, param_type )

    def record_return_type( self, return_type ):
        self._return_type.add_candidate_type( return_type )

    def get_param_index( self, param_name ):
        raise NotImplementedError( self.__class__ )

class FunctionType(CallableType):
    """Associated to a single function.
    """
    def __init__( self, func ):
        super(FunctionType, self).__init__()
        self.py_func = func
        code = self.py_func.__code__
        self.arg_names = code.co_varnames[:code.co_argcount] # function parameter names
        self.methods = {} # Dict {instance_type: method_type}

    def get_arg_count( self ):
        return self.py_func.__code__.co_argcount

    def get_param_index( self, param_name ):
        return self.arg_names.index( param_name )

    def get_function_object( self ):
        """Returns the associated python function."""
        return self.py_func

    def attach_to_instance( self, instance_type ):
        """Attachs the type to an instance (attribute look-up).
           Used to convert a function type into a method type.
        """
        if instance_type in self.methods:
            return self.methods[instance_type]
        method_type = MethodType( instance_type, self )
        self.methods[instance_type] = method_type
        return method_type

class MethodType(CallableType):
    """Associated to an instance type and FunctionType (self is an implied parameter).
    """
    def __init__( self, instance_type, function_type ):
        super(MethodType, self).__init__()
        self.function_type = function_type
        self.function_type.record_arg_type( 0, instance_type )

    def get_function_object( self ):
        """Returns the associated python function."""
        return self.function_type.get_function_object()

    def record_arg_type( self, index, type ):
        self.function_type.record_arg_type( index + 1, type )

    def get_return_type( self ):
        return self.function_type.get_return_type()

class InstanceType(Type):
    def __init__( self, class_type ):
        super(InstanceType, self).__init__()
        self.class_type = class_type

    def get_instance_attribute_type( self, type_registry, attribute_name ):
        """Gets the type of a module/class/instance attribute.
        """
        if hasattr( self.class_type.cls, attribute_name ):
            attribute = getattr( self.class_type.cls, attribute_name )
            attribute_type = type_registry.from_python_object( attribute )
            return attribute_type.attach_to_instance( self )
        raise ValueError( "Unsupported instance attribute: %r.%s" % (self.class_type, attribute_name) )
        

class NewClassType(CallableType):
    def __init__( self, cls ):
        super(NewClassType, self).__init__()
        self.cls = cls
        self.instance_type = InstanceType( self )
        self._return_type = self.instance_type # Constructor return type is an instance of the class
        code = cls.__init__.__code__
        self.arg_names = code.co_varnames[:code.co_argcount] # function parameter names

    def get_param_index( self, param_name ):
        return self.arg_names.index( param_name )

class DictType(Type):
    pass

class ListType(Type):
    pass

class IntegralType(Type):
    pass

class IntType(IntegralType):
    pass

INT = IntType()

class BoolType(IntegralType):
    pass

BOOL = BoolType()

class FloatType(Type):
    pass

class StringType(Type):
    def __init__( self, length = -1 ):
        super(StringType, self).__init__()
        self.length = length

    def __repr__( self ):
        if self.length >= 0:
            return 'StringType(%d)' % self.length
        return 'StringType()'

class BytesType(Type):
    def __init__( self, length = -1 ):
        super(BytesType, self).__init__()
        self.length = length

    def __repr__( self ):
        if self.length >= 0:
            return 'BytesType(%d)' % self.length
        return 'BytesType()'

class ModuleType(Type):
    def __init__( self, module ):
        self._module = module # the actual python module object

    def get_instance_attribute_type( self, type_registry, attribute_name ):
        """Gets the type of a module/class/instance attribute.
        """
        if hasattr( self._module, attribute_name ):
            attribute = getattr( self._module, attribute_name )
            attribute_type = type_registry.from_python_object( attribute )
            return attribute_type
        raise ValueError( "Unsupported module attribute: %r.%s" % (self.class_type, attribute_name) )

    def __repr__( self ):
        return 'Module(%s)' % self._module

class UnknownType(Type):
    """A type being guessed.
       Records all the candidate types of the expression.
    """
    def __init__( self ):
        self.candidates = []
        self._resolved_type = None

    def add_candidate_type( self, candidate_type ):
        assert self._resolved_type is None
        self.candidates.append( candidate_type )

    def get_resolved_type( self, type_registry ):
        if self._resolved_type is None:
            types = set( r_type.get_resolved_type(type_registry)
                         for r_type in self.candidates )
            if len(types) != 1:
                raise ValueError( 'Can not resolve unknown type: %r' % self )
            self._resolved_type = self.candidates[0]
        return self._resolved_type

    def get_instance_attribute_type( self, type_registry, attribute_name ):
        """Gets the type of a class/instance attribute.
        """
        if len(self.candidates) == 1:
            return self.candidates[0].get_instance_attribute_type( type_registry, attribute_name )
        return super(UnknownType, self).get_instance_attribute_type( type_registry, attribute_name )

    def __repr__( self ):
        return 'Unknown( %s )' % ', '.join( repr(c) for c in self.candidates )

##PREDEFINED_MODULES = {
##    'codecs': native_module( {
##        'open': native_function( [('filename': StringType())], [(
##        } )
##    }

class ConstantTypeRegistry(object):
    """
    """
    def __init__( self ):
        self.constant_types = {} # dict {object: Type}
        self.instance_types = {} # dict {id(object): Type} for non-hashable object
        self.on_referenced_callable = None
        self.primitive_factories = {
            list: lambda o: ListType(),
            str: lambda obj: StringType( len(obj) ),
            bytes: lambda obj: BytesType( len(obj) ),
            int: lambda obj: INT
            }

    def set_callable_listener( self, listener ):
        """Set the callback called whenever a new callable is passed to method
           from_python_object.
        """
        self.on_referenced_callable = listener

    def from_python_object( self, obj ):
        """Returns the Type instance corresponding to the given python object.
           If a type was already associated to the python object
           (e.g. class, module, global...), then that type is returned.
        """
        try:
            if obj in self.constant_types:
                return self.constant_types[obj]
            hashable = True
        except TypeError:
            hashable = False
            if id(obj) in self.instance_types:
                return self.instance_types[id(obj)]
        if obj is None:
            obj_type = NONE
        elif isinstance( obj, types.FunctionType ):
            obj_type = FunctionType( obj )
            if self.on_referenced_callable:
                self.on_referenced_callable( obj_type )
## Python 2.6 only:
##        elif isinstance( obj, types.UnboundMethodType ):
##            obj_type = FunctionType( obj )
##            if self.on_referenced_callable:
##                self.on_referenced_callable( obj_type )
        elif isinstance( obj, type ):
            obj_type = NewClassType( obj )
            if self.on_referenced_callable:
                self.on_referenced_callable( obj_type )
        elif isinstance( obj, types.ModuleType ):
            obj_type = ModuleType( obj )
        elif hasattr( obj, '__class__' ):
            if obj.__class__ in self.primitive_factories:
                obj_type = self.primitive_factories[obj.__class__]( obj )
            else:
                class_type = self.from_python_object( obj.__class__ )
                obj_type = InstanceType( class_type )
        else:
            raise ValueError( "Unsupported python type: %r, type: %s" % (obj, type(obj)) )
        if hashable:
            self.constant_types[obj] = obj_type
        else:
            self.instance_types[id(obj)] = obj_type
        return obj_type

#    def get_builtin_type( self, name ):