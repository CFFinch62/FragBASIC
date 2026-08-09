"""Allows running the interpreter as `python -m fragbasic_core script.bas`."""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
