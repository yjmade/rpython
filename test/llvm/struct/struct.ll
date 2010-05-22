; ModuleID = 'structdemo'

%0 = type { i32, i32 }

define void @test_main() {
entry:
  %point_var = alloca %0                          ; <%0*> [#uses=2]
  %0 = getelementptr %0* %point_var, i32 0, i32 0 ; <i32*> [#uses=1]
  %1 = getelementptr %0* %point_var, i32 0, i32 1 ; <i32*> [#uses=1]
  store i32 16, i32* %0
  store i32 16, i32* %1
  ret void
}
