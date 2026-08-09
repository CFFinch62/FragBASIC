"""
FragBASIC command-line interpreter.

    fragbasic script.bas
    fragbasic -c "PRINT \"hello\""
    fragbasic script.bas --timeout 10

Designed to be driven either directly by a human at a terminal, or as a
child process launched by an IDE (see BLADE's BasicBackend registry):
program output goes to stdout (flushed after every write so it streams
live rather than buffering), errors go to stderr, INPUT reads a line
from stdin, and the process exit code reports success/failure so a
launcher doesn't need to scrape output to know what happened.

Exit codes:
    0   program ran to completion
    1   lex/parse/runtime error in the BASIC program
    2   usage error (bad arguments, missing file, etc.)
    130 interrupted (Ctrl+C, SIGTERM, or --timeout)
"""

import argparse
import signal
import sys
import threading
from pathlib import Path

from . import __version__
from .lexer import Lexer
from .parser import Parser
from .interpreter import Interpreter
from .errors import FragBasicError, ExecutionCancelled


def _output_func(text):
    sys.stdout.write(text)
    sys.stdout.flush()


def _input_func():
    line = sys.stdin.readline()
    if line == "":
        raise EOFError
    return line.rstrip("\n")


def _install_signal_handlers(interpreter):
    """
    Route SIGINT/SIGTERM to the interpreter's cooperative cancellation flag
    *and* raise KeyboardInterrupt, so a program that's mid-computation
    stops at its next check_cancelled() checkpoint, while a program
    blocked on a blocking stdin read (INPUT) is interrupted immediately
    rather than hanging until more input arrives.
    """
    def handle(signum, frame):
        interpreter.request_cancel()
        raise KeyboardInterrupt()

    signal.signal(signal.SIGINT, handle)
    try:
        signal.signal(signal.SIGTERM, handle)
    except (ValueError, AttributeError):
        # SIGTERM isn't available in every environment (e.g. some Windows
        # setups, or when running outside the main thread) - best effort.
        pass


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fragbasic",
        description="Run FragBASIC programs from the command line.",
    )
    parser.add_argument("file", nargs="?", help="path to a .bas source file")
    parser.add_argument(
        "-c", "--code", metavar="CODE",
        help="run BASIC source given directly on the command line instead of a file",
    )
    parser.add_argument(
        "--timeout", type=float, default=None, metavar="SECONDS",
        help="cancel execution after this many seconds of CPU-bound running "
             "(does not interrupt a program blocked waiting on INPUT)",
    )
    parser.add_argument("--version", action="version", version=f"fragbasic {__version__}")
    return parser


def main(argv=None) -> int:
    args = build_arg_parser().parse_args(argv)

    if args.code is None and args.file is None:
        print('fragbasic: no input - pass a .bas file or -c "CODE"', file=sys.stderr)
        return 2

    if args.code is not None and args.file is not None:
        print("fragbasic: pass either a file or -c, not both", file=sys.stderr)
        return 2

    if args.code is not None:
        source = args.code
    else:
        path = Path(args.file)
        if not path.exists():
            print(f"fragbasic: file not found: {path}", file=sys.stderr)
            return 2
        try:
            source = path.read_text(encoding="utf-8")
        except OSError as e:
            print(f"fragbasic: could not read {path}: {e}", file=sys.stderr)
            return 2

    interpreter = Interpreter()
    interpreter.set_io_functions(input_func=_input_func, output_func=_output_func)
    _install_signal_handlers(interpreter)

    timeout_timer = None
    if args.timeout is not None:
        timeout_timer = threading.Timer(args.timeout, interpreter.request_cancel)
        timeout_timer.daemon = True
        timeout_timer.start()

    try:
        tokens = Lexer(source).generate_tokens()
        ast = Parser(tokens).parse()
        interpreter.interpret(ast)
    except FragBasicError as e:
        print(e.format(), file=sys.stderr)
        return 1
    except (ExecutionCancelled, KeyboardInterrupt):
        print("fragbasic: execution cancelled", file=sys.stderr)
        return 130
    except Exception as e:
        # Last-resort safety net: an internal interpreter bug should never
        # surface as a raw Python traceback to someone running a BASIC
        # program - report it like any other program error instead.
        print(f"fragbasic: internal error: {e}", file=sys.stderr)
        return 1
    finally:
        if timeout_timer is not None:
            timeout_timer.cancel()

    return 0


if __name__ == "__main__":
    sys.exit(main())
