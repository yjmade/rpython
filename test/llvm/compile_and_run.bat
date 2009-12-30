@rem compile_and_run helloworldc
llvm-as.exe -f %1.ll
lli.exe %1.bc
