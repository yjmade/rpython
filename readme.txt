Notes: this project is very experimental and a playground to learn LLVM.

This projects aims to provide efficient and fast code generation for restricted python (RPython).

RPython is subset of python that is statically typed. A valid RPython is a valid python programm. The concept of RPython was created by the PyPy project (http://codespeak.net/pypy/dist/pypy/doc/) and is developped in the following paper:
http://www.disi.unige.it/person/AnconaD/papers/Recent_abstracts.html#AACM-DLS07


The translation is done by analysis python bytecode of the function object provided as entry point. This means that the full power/dynamism of python can be use to generate the code (generate class methods...)

Python bindings for LLVM are used to generate the code (http://mdevan.nfshost.com/llvm-py/examples.html).

Requirement:
============

- Latest SVN version of llvm-py python module. Precompiled version for windows available for download on http://code.google.com/p/rpython/downloads/list.
  If you are on Windows, just decompress the archive into the directory containing this README file. The env.bat script will automatically add it to the paths.
- Python 3.1 (Object model clean-up and byte/string separation simplify type analysis)


Running tests:
==============

Setup PATH and RPY_HOME:
env.bat

Launch the unit tests (compile python functions to "RPython" LLVM JIT and check execution result)
cd test\rpytest
python __init__.py

Running a specific unit test:
python class.py TestClass.test_class_method
