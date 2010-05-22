import llvm.core as lcore
Type = lcore.Type

ty_i8_ptr = Type.pointer( Type.int(8) )
ty_i32 = Type.int(32)
l_attribute_types = (ty_i32, ty_i32)
l_point_struct_type = lcore.Type.struct( l_attribute_types )

module = lcore.Module.new('structdemo')

type_main = Type.function(Type.void(), [])
fn_main = module.add_function( type_main, 'test_main' )

basic_block = fn_main.append_basic_block("entry")
builder = lcore.Builder.new(basic_block)

# Allocates the structure on the stack
l_point = builder.alloca( l_point_struct_type, 'point_var' )
constant_0 = lcore.Constant.int( ty_i32, 0 )
constant_point_x_index = lcore.Constant.int( ty_i32, 0 )
constant_point_y_index = lcore.Constant.int( ty_i32, 1 )
constant_16 = lcore.Constant.int( ty_i32, 16 )
l_px = builder.gep( l_point, [constant_0, constant_point_x_index] ) # gep = getelementptr
l_py = builder.gep( l_point, [constant_0, constant_point_y_index] ) # gep = getelementptr
builder.store( constant_16, l_px )
builder.store( constant_16, l_py )

builder.ret_void()

print( module )

from llvm.ee import ExecutionEngine, GenericValue
module_provider = lcore.ModuleProvider.new( module )
engine = ExecutionEngine.new( module_provider )
engine.run_function( fn_main, [] )

