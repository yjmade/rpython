set RPY_HOME=%~dp0src
set RPY_LLVM_HOME=%RPY_HOME%\third-parties\llvm-2.6\Debug
set RPY_LLVM_PY_HOME=%RPY_HOME%\third-parties\llvm-py-3.1

set PATH=%RPY_HOME%\script;%RPY_LLVM_HOME%;c:\Python31;%PATH%
set PYTHONPATH=%RPY_HOME%;%RPY_LLVM_PY_HOME%
