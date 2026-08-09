"""
FragBASIC — a standalone, dependency-free BASIC interpreter core.

Designed to be reused as a CLI tool and embedded by any IDE (BLADE or
others) without pulling in a GUI toolkit. Everything in this package is
pure Python standard library — no PyQt6, no tkinter, nothing GUI-related.

Typical usage as a library:

    from fragbasic_core import Lexer, Parser, Interpreter

    tokens = Lexer(source).generate_tokens()
    ast = Parser(tokens).parse()

    interpreter = Interpreter()
    interpreter.set_io_functions(input_func=my_input, output_func=my_output)
    interpreter.interpret(ast)

Or, for the common case of just running some source end to end:

    from fragbasic_core import run_source

    run_source(source)  # uses real stdin/stdout by default
"""

import sys

from .ast_nodes import Node, NodeType
from .tokens import Token, TokenType
from .lexer import Lexer
from .parser import Parser
from .interpreter import Interpreter
from .variable import Variable
from .errors import (
    FragBasicError,
    LexerError,
    ParseError,
    BasicRuntimeError,
    ExecutionCancelled,
)

__version__ = "1.0.0"
__author__ = "Chuck Finch - Fragillidae Software"

__all__ = [
    'Node', 'NodeType', 'Parser',
    'Token', 'TokenType', 'Lexer',
    'Interpreter', 'Variable',
    'FragBasicError', 'LexerError', 'ParseError', 'BasicRuntimeError',
    'ExecutionCancelled',
    'run_source',
]


def run_source(source: str, input_func=None, output_func=None, interpreter: Interpreter = None) -> Interpreter:
    """
    Lex, parse, and execute a FragBASIC program in one call.

    By default reads from real stdin and writes to real stdout (flushing
    after every write, since BASIC's PRINT can withhold a trailing
    newline). Pass your own input_func/output_func to embed FragBASIC in
    another application (an IDE console pane, a test harness, etc.).

    Raises LexerError, ParseError, or BasicRuntimeError on a bad program,
    and ExecutionCancelled if the interpreter's request_cancel() was
    called from another thread/signal handler while running.

    Returns the Interpreter instance used, so callers can inspect
    variables/arrays afterward (mainly useful for tests and embedding).
    """
    if interpreter is None:
        interpreter = Interpreter()

    if output_func is None:
        def output_func(text):
            sys.stdout.write(text)
            sys.stdout.flush()

    if input_func is None:
        def input_func():
            line = sys.stdin.readline()
            if line == "":
                raise EOFError
            return line.rstrip("\n")

    interpreter.set_io_functions(input_func=input_func, output_func=output_func)

    tokens = Lexer(source).generate_tokens()
    ast = Parser(tokens).parse()
    interpreter.interpret(ast)

    return interpreter
