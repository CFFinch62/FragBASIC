"""
Token definitions for the FragBASIC interpreter.
"""

from enum import Enum, auto

class TokenType(Enum):
    """Token types for the BASIC language."""
    # Special tokens
    NONE = auto()
    NL = auto()         # Newline
    SEP = auto()        # Separator (colon)

    # Data types
    NUMBER = auto()     # Numeric literals
    STRING = auto()     # String literals

    # Identifiers
    IDENTIFIER = auto() # Variable/function names

    # Operators
    PLUS = auto()       # +
    MINUS = auto()      # -
    MULTIPLY = auto()   # *
    DIVIDE = auto()     # /
    INTEGER_DIV = auto()# \
    MOD = auto()        # MOD
    POWER = auto()      # ^

    # Comparison operators
    EQ = auto()         # =
    LT = auto()         # <
    GT = auto()         # >
    LTE = auto()        # <=
    GTE = auto()        # >=
    NE = auto()         # <>

    # Logical operators
    AND = auto()        # AND
    OR = auto()         # OR
    NOT = auto()        # NOT
    XOR = auto()        # XOR
    EQV = auto()        # EQV
    IMP = auto()        # IMP

    # Parentheses and brackets
    LPAREN = auto()     # (
    RPAREN = auto()     # )
    LSQBRACKET = auto() # [
    RSQBRACKET = auto() # ]

    # Punctuation
    COMMA = auto()      # ,
    SEMICOLON = auto()  # ;
    DOLLAR = auto()     # $ (string type suffix)
    EXCLAMATION = auto() # ! (single precision suffix)
    PERCENT = auto()    # % (integer type suffix)
    HASH = auto()       # # (double precision suffix)

    # Keywords
    KEYWORD = auto()    # All keywords like PRINT, INPUT, etc.

class Token:
    """Token class for the BASIC language."""
    def __init__(self, type_, value=None, name=None, line_num=None):
        self.type = type_
        self.value = value  # For numeric tokens
        self.name = name    # For string, identifier, keyword tokens
        self.line_num = line_num  # For tracking source line numbers

    def __repr__(self):
        if self.value is not None:
            return f"Token({self.type}, {self.value})"
        elif self.name is not None:
            return f"Token({self.type}, '{self.name}')"
        return f"Token({self.type})"
