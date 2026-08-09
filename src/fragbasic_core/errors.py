"""
FragBASIC error types and formatting.

Error hierarchy:
    FragBasicError
    ├── LexerError    — invalid characters, unterminated strings
    ├── ParseError    — syntax violations
    └── BasicRuntimeError  — type mismatches, undefined variables, etc.

All errors carry an optional source line number and format as the
single-line diagnostic: "Error on line N: message" (or "Error: message"
when no line number is available, e.g. some legacy runtime checks).

ExecutionCancelled is a separate, non-language-error signal used for
cooperative cancellation (Ctrl+C, SIGTERM, --timeout) — it is not part
of the FragBasicError hierarchy because it does not represent a bug in
the running BASIC program.
"""


class FragBasicError(Exception):
    """Base class for all FragBASIC language errors."""

    def __init__(self, message: str, line_num: int = None):
        self.message = message
        self.line_num = line_num
        super().__init__(self.format())

    def format(self) -> str:
        """Format as a single-line diagnostic."""
        if self.line_num is not None:
            return f"Error on line {self.line_num}: {self.message}"
        return f"Error: {self.message}"


class LexerError(FragBasicError):
    """Error during tokenization (invalid characters, unterminated strings)."""
    pass


class ParseError(FragBasicError):
    """Error during parsing (syntax violations)."""
    pass


class BasicRuntimeError(FragBasicError):
    """Error during execution (type mismatches, undefined variables, etc.)."""
    pass


class ExecutionCancelled(Exception):
    """Raised cooperatively when a running program is cancelled (Ctrl+C, SIGTERM, timeout)."""
    pass
