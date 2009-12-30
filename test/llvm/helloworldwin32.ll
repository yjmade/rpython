; void * must be mapped to i8*
declare x86_stdcallcc i8* @GetStdHandle(i32)

declare x86_stdcallcc i32 @WriteFile(i8*, i8*, i32, i32 *, i32 *)

; Declare the string constant as a global constant...
@.LC0 = internal constant [13 x i8] c"hello world\0A\00"          ; [13 x i8]*

define i32 @main() {
        %handle = call x86_stdcallcc i8* @GetStdHandle(i32 -11)
        ; Convert [13x i8 ]* to i8  *...
        %hellostr = getelementptr [13 x i8 ]* @.LC0, i64 0, i64 0 ; i8 *
        call x86_stdcallcc i32 @WriteFile( i8 *%handle, 
            i8* %hellostr, i32 12, i32 *null, i32 *null )
        ret i32 0
}
