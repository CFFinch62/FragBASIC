"""AST-to-NucleusVM-bytecode compiler for FragBASIC.

This is a *new*, additive execution path — see `compiler.py`'s module
docstring for the language subset covered and why (dev-docs/PLAN.md in the
NucleusVM repo has the full rationale). Nothing in the existing tree-walking
interpreter (`interpreter_core.py` and friends) is touched by this package.
"""
from .compiler import VMCompiler, compile_program

__all__ = ["VMCompiler", "compile_program"]
