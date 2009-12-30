set RPY_HOME=%~dp0
set RPY_LLVM_HOME=%RPY_HOME%third-parties\llvm-2.6\Release
set RPY_LLVM_PY_HOME=%RPY_HOME%third-parties\llvm-py-3.1

set PATH=%RPY_HOME%src\script;%RPY_LLVM_HOME%;c:\Python31;%PATH%
set PYTHONPATH=%RPY_HOME%src;%RPY_HOME%rpylib;%RPY_LLVM_PY_HOME%
