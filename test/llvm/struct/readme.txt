This example demonstrate structure type declaration and manipulation.

The key points are:

* type declaration:

ty_i32 = Type.int(32)
l_attribute_types = (ty_i32, ty_i32)
l_point_struct_type = lcore.Type.struct( l_attribute_types )
=> struct members are not named and are accessed by "index" related to declaration order.

* member usage:

constant_0 = lcore.Constant.int( ty_i32, 0 )
constant_point_x_index = lcore.Constant.int( ty_i32, 0 )
constant_point_y_index = lcore.Constant.int( ty_i32, 1 )
constant_16 = lcore.Constant.int( ty_i32, 16 )
l_px = builder.gep( l_point, [constant_0, constant_point_x_index] ) # gep = getelementptr
l_py = builder.gep( l_point, [constant_0, constant_point_y_index] ) # gep = getelementptr
builder.store( constant_16, l_px )
builder.store( constant_16, l_py )
