"""
Best-effort, dependency-free non-blocking single-character keyboard read,
used to implement INKEY$.

On Windows, msvcrt gives true non-blocking single-key reads. On POSIX,
without taking the terminal out of canonical (line-buffered) mode — which
would risk interfering with INPUT's use of stdin — the best we can safely
do is a non-blocking check of whatever is already sitting in the input
buffer. In practice that means a POSIX user must press Enter before a
key becomes visible to INKEY$. This is a real limitation inherited from
running as a plain stdin/stdout CLI process rather than owning the
terminal outright (e.g. via curses); it is documented in the README.

Any failure (stdin not a real stream, platform module unavailable, etc.)
degrades to returning "" — the same behavior as the stub this replaces.
"""

import os
import sys


def read_key_nonblocking() -> str:
    """Return the next available character from stdin, or "" if none is ready."""
    try:
        if os.name == 'nt':
            return _read_key_windows()
        return _read_key_posix()
    except Exception:
        return ""


def _read_key_windows() -> str:
    import msvcrt

    if not msvcrt.kbhit():
        return ""
    ch = msvcrt.getch()
    try:
        return ch.decode('utf-8', errors='replace')
    except Exception:
        return ""


def _read_key_posix() -> str:
    import select

    if not sys.stdin.isatty() and not sys.stdin.readable():
        return ""
    ready, _, _ = select.select([sys.stdin], [], [], 0)
    if not ready:
        return ""
    return sys.stdin.read(1)
