"""Types
"""
import types
import collections

SourceLocation = collections.namedtuple( 'SourceLocation', ('function_name', 'path', 'line', 'detail') )

def make_detailed_location( location, detail ):
    if location is not None:
        return SourceLocation( location.function_name, location.path, location.line, detail )
    return None

class Type(object):
    def __init__( self, location = None ):
        self._location = location
        # set of Unknown type referencing this Type
        self._referenced_by = set() # set( UnknownType )
        
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

    def set_location( self, location ):
        self._location = location

    def get_location( self ):
        return self._location

    def get_location_str( self ):    
        location = self.get_location()
        if location is not None:
            return ' in %s(%d) %s' % (location.path, location.line, location.detail)
        return ''

    def __repr__( self ):
        return '%s(%s @%#x%s)' % (self.__class__.__name__,
                                   self.get_location_str(),
                                   id(self),
                                   self._repr_detail_str() )

    def _repr_detail_str( self ):
        """Should be overridden by sub-classes that needs extra detail."""
        return ''

    def flush_pending_records( self, type_registry  ):
        """Try to resolve all UnknownType referencing this type to flush
           pending attributes.
        """
        self._referenced_by, r_references = set(), self._referenced_by
        for r_unknown_type in r_references:
            r_unknown_type.get_resolved_type( type_registry )

    def is_primitive_type( self ):
        return False

class PrimitiveType(Type):
    def is_primitive_type( self ):
        return True

class NoneType(Type):
    def __repr__( self ):
        return 'NoneType()'

class CallableType(Type):
    def __init__( self ):
        super(CallableType, self).__init__()
        self._arg_types = {}
        self._return_type = UnknownType()

    def set_location( self, location ):
        self._return_type.set_location(
            make_detailed_location( location, 'return type' ) )
        return super(CallableType, self).set_location( location )

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
            arg_location = make_detailed_location( self.get_location(),
                                                   'arg %d type' % index )
            unknown_type.set_location( arg_location )
            self._arg_types[index] = unknown_type
        else:
            unknown_type = self._arg_types[index]
        return unknown_type

    def record_arg_type( self, index, r_type ):
        print( 'Record arg %d type:' % index, r_type )
        r_unknown_type = self.get_arg_type( index )
        r_unknown_type.add_candidate_type( r_type )

    def record_keyword_arg_type( self, param_name, param_type ):
        param_index = self.get_param_index( param_name )
        self.record_arg_type( param_index, param_type )

    def record_return_type( self, return_type ):
        self._return_type.add_candidate_type( return_type )

    def get_param_index( self, param_name ):
        raise NotImplementedError( self.__class__ )

    def is_constructor( self ):
        return False

class FunctionType(CallableType):
    """Associated to a single function.
    """
    def __init__( self, func ):
        super(FunctionType, self).__init__()
        self.py_func = func
        code = self.py_func.__code__
        self.arg_names = code.co_varnames[:code.co_argcount] # function parameter names
        self.methods = {} # Dict {instance_type: method_type}

    def _repr_detail_str( self ):
        args = tuple( self.get_arg_type(i) for i in range(0,self.get_arg_count()) )
        return self.py_func.__module__ + '/' + self.py_func.__name__ + ', args=%r' % (args,)

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
        self.class_type = class_type # rtype
        self.attribute_types = {} # dict{name: UnknownType}

    def _repr_detail_str( self ):
        """Should be overridden by sub-classes that needs extra detail."""
        return ', class=%s' % self.class_type.py_class

    def get_known_attribute_type( self, attribute_name ):
        """Returns the rtype of an attribute.
           Warning: Should be use only during code generation."""
        return self.attribute_types[ attribute_name ]

    def get_instance_attribute_type( self, type_registry, attribute_name ):
        """Gets the type of a module/class/instance attribute.
        """
        if attribute_name in self.attribute_types:
            return self.attribute_types[attribute_name]
        if hasattr( self.class_type.py_class, attribute_name ):
            attribute = getattr( self.class_type.py_class, attribute_name )
            attribute_type = type_registry.from_python_object( attribute )
            attached_attribute_type = attribute_type.attach_to_instance( self )
            self.attribute_types[attribute_name] = attached_attribute_type
            return attached_attribute_type
        attribute_type = UnknownType()
        self.attribute_types[attribute_name] = attribute_type
        return attribute_type

    def record_attribute_type( self, attribute_name, attribute_type ):
        if not hasattr( self.class_type.py_class, attribute_name ): # ignore class attribute
            if attribute_name in self.attribute_types:
                generic_type = self.attribute_types[attribute_name]
            else:
                generic_type = UnknownType()
                self.attribute_types[attribute_name] = generic_type
            generic_type.add_candidate_type( attribute_type )


class ClassType(FunctionType): # Notes: should probably be a subclass of MethodType
    def __init__( self, py_class ):
        py_func = py_class.__init__
        super(ClassType, self).__init__( py_func )
        self.py_class = py_class
        self.instance_type = InstanceType( self )
        # Constructor return type is an instance of the class
        # overridden from base class
        self._return_type = self.instance_type 
        # Set type of 'self' parameter
        self.get_arg_type(0).set_resolved_type( self.instance_type )

    def get_qualified_type_name( self ):
        return self.py_class.__name__

    def get_known_attribute_type( self, attribute_name ):
        """Returns the rtype of an attribute.
           Warning: Should be use only during code generation."""
        return self.instance_type.get_known_attribute_type( self, attribute_name )

    def record_arg_type( self, index, r_type ):
        # An offset of one is applied on the parameter index to
        # take into account the implicit self parameter on
        # constructor call __init__.
        return super(ClassType, self).record_arg_type( index + 1, r_type )


    def record_return_type( self, return_type ):
        """Returns type of the __init__ methods is always known"""
        pass

    def is_constructor( self ):
        return True

class DictType(Type):
    pass

class ListType(Type):
    pass

class IntegralType(PrimitiveType):
    pass

class IntType(IntegralType):
    pass

class BoolType(IntegralType):
    pass

class FloatType(PrimitiveType):
    pass

class StringType(Type):
    def __init__( self, length = -1 ):
        super(StringType, self).__init__()
        self.length = length

    def _repr_detail_str( self ):
        if self.length >= 0:
            return ', length=%d' % self.length
        return ''

class BytesType(Type):
    def __init__( self, length = -1 ):
        super(BytesType, self).__init__()
        self.length = length

    def _repr_detail_str( self ):
        if self.length >= 0:
            return ', length=%d' % self.length
        return ''

class ModuleType(Type):
    def __init__( self, module ):
        super(ModuleType, self).__init__()
        self._module = module # the actual python module object

    def get_instance_attribute_type( self, type_registry, attribute_name ):
        """Gets the type of a module/class/instance attribute.
        """
        if hasattr( self._module, attribute_name ):
            attribute = getattr( self._module, attribute_name )
            attribute_type = type_registry.from_python_object( attribute )
            return attribute_type
        raise ValueError( "Unsupported module attribute: %r.%s" % (self.class_type, attribute_name) )

    def _repr_detail_str( self ):
        return ', module=%s' % self._module

class UnknownType(Type):
    """A type being guessed.
       Records all the candidate types of the expression.
    """
    def __init__( self, location = None ):
        super(UnknownType, self).__init__( location=location )
        self.candidates = []
        self._resolved_type = None
        self.attribute_types = {} # dict{name: UnknownType}

    def add_candidate_type( self, candidate_type ):
        if self._resolved_type is None:
            if self not in candidate_type._referenced_by:
                candidate_type._referenced_by.add( self )
                self.candidates.append( candidate_type )

    def set_resolved_type( self, r_type ):
        """Used to set the resolved type. Usually called by get_resolved_type(),
        but may be called directly in case like an implicit call to __init__
        constructor where the type of self is known without doubt.
        """
        self._resolved_type = r_type
        for attribute_name, attribute_types in self.attribute_types.items():
            for attribute_type in attribute_types:
                r_type.record_attribute_type( attribute_name, attribute_type )

    def get_resolved_type( self, type_registry ):
        if self._resolved_type is None:
            types = set( r_type.get_resolved_type(type_registry)
                         for r_type in self.candidates )
##            if len(self.candidates) == 0:
##                print( "**** Can not resolve self:")
            
            first_type = next(iter(types))
            if len(types) == 1:
                self.set_resolved_type( first_type )
            else:
                primitive_types = [t for t in types if t.is_primitive_type()]
                if len(primitive_types) == len(types):
                    same_types = [t for t in types
                                  if isinstance(t, first_type.__class__)]
                    if len(same_types) != len(types):
                        raise ValueError( 'Can not resolve unknown type%s because it is made of distinct primitive types: %r' %
                                          (self.get_location_str(), self) )
                    self.set_resolved_type( first_type )
                else:
                    raise ValueError( 'Can not resolve unknown type%s (made of distinct non primitive types): %r' %
                                      (self.get_location_str(), self) )
        return self._resolved_type

    def get_known_attribute_type( self, attribute_name ):
        if self._resolved_type:
            return self._resolved_type.get_known_attribute_type( attribute_name )
        raise ValueError( 'Can not obtain a known attribute type of an unresolved type' )

    def record_attribute_type( self, attribute_name, attribute_type ):
        """Records attribute's types on assignment.
           When the type is resolved, the recordded attribute's types are "replayed".
        """
        if self._resolved_type:
            self._resolved_type.record_attribute_type( attribute_name, attribute_type )
        if attribute_name in self.attribute_types:
            self.attribute_types[attribute_name].append( attribute_type )
        else:
            self.attribute_types[attribute_name] = [ attribute_type ]

    def get_instance_attribute_type( self, type_registry, attribute_name ):
        """Gets the type of a class/instance attribute.
        """
        if self._resolved_type:
            return self._resolved_type.get_instance_attribute_type( type_registry, attribute_name )
        if len(self.candidates) == 1:
            return self.candidates[0].get_instance_attribute_type( type_registry, attribute_name )
        return super(UnknownType, self).get_instance_attribute_type( type_registry, attribute_name )

    def _repr_detail_str( self ):
        resolved = ', resolved=%s' % repr(self._resolved_type) if self._resolved_type else ''
        return resolved + ', candidates=%s' % ', '.join( repr(c) for c in self.candidates )

##PREDEFINED_MODULES = {
##    'codecs': native_module( {
##        'open': native_function( [('filename': StringType())], [(
##        } )
##    }

class ConstantTypeRegistry(object):
    """Deduces and remember the RPython type associated to a python object (type or constant value).
    """
    def __init__( self ):
        self.constant_types = {} # dict {object: Type}
        self.instance_types = {} # dict {id(object): Type} for non-hashable object
        self.on_referenced_callable = None
        self.primitive_factories = {
            list: lambda o: ListType(),
            str: lambda obj: StringType( len(obj) ),
            bytes: lambda obj: BytesType( len(obj) ),
            int: lambda obj: IntType()
            }

    def set_callable_listener( self, listener ):
        """Set the callback called whenever a new callable is passed to method
           from_python_object.
        """
        self.on_referenced_callable = listener

    def from_python_object( self, obj, location ):
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
            obj_type = NoneType( location )
        elif isinstance( obj, types.FunctionType ):
            obj_type = FunctionType( obj )
            if obj_type.py_func.__name__ == '__init__':
                raise ValueError('logic error')
            if self.on_referenced_callable:
                self.on_referenced_callable( obj_type )
## Python 2.6 only:
##        elif isinstance( obj, types.UnboundMethodType ):
##            obj_type = FunctionType( obj )
##            if self.on_referenced_callable:
##                self.on_referenced_callable( obj_type )
        elif isinstance( obj, type ):
            obj_type = ClassType( obj )
            if self.on_referenced_callable:
                self.on_referenced_callable( obj_type )
        elif isinstance( obj, types.ModuleType ):
            obj_type = ModuleType( obj )
        elif hasattr( obj, '__class__' ):
            if obj.__class__ in self.primitive_factories:
                obj_type = self.primitive_factories[obj.__class__]( obj )
            else:
                class_type = self.from_python_object( obj.__class__, location )
                obj_type = InstanceType( class_type )
        else:
            raise ValueError( "Unsupported python type: %r, type: %s" % (obj, type(obj)) )
        if hashable:
            self.constant_types[obj] = obj_type
        else:
            self.instance_types[id(obj)] = obj_type
        obj_type.set_location( location )
        return obj_type

#    def get_builtin_type( self, name ):