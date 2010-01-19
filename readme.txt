Notes: this project is very experimental and a playground to learn LLVM.

This projects aims to provide efficient and fast code generation for restricted python (RPython).

RPython is subset of python that is statically typed. A valid RPython is a valid python programm. The concept of RPython was created by the PyPy project (http://codespeak.net/pypy/dist/pypy/doc/) and is developped in the following paper:
http://www.disi.unige.it/person/AnconaD/papers/Recent_abstracts.html#AACM-DLS07


The translation is done by analysis python bytecode of the function object provided as entry point. This means that the full power/dynamism of python can be use to generate the code (generate class methods...)

Python bindings for LLVM are used to generate the code (http://mdevan.nfshost.com/llvm-py/examples.html).
