"""
Main BASIC parser class that combines all functionality modules.
"""

from typing import List
from .tokens import Token, TokenType
from .parser_core import ParserCore
from .parser_statements import ParserStatements
from .parser_control import ParserControl


class Parser(ParserCore, ParserStatements, ParserControl):
    """
    Complete BASIC parser that combines all functionality modules.

    This class inherits from multiple mixin classes to provide:
    - Core functionality (basic parsing infrastructure, expression parsing)
    - Statement parsing (PRINT, INPUT, DIM, DATA, READ, etc.)
    - Control structure parsing (IF, FOR, WHILE, DO, SELECT CASE, SUB, FUNCTION)
    """

    def __init__(self, tokens: List[Token]):
        """Initialize the parser"""
        super().__init__(tokens)

    def reset(self, tokens: List[Token]):
        """Reset the parser with new tokens"""
        self.tokens = tokens
        self.cursor_pos = 0
        self.current_token = self.tokens[0] if tokens else Token(TokenType.NONE)

    def get_current_position(self):
        """Get current parser position (for debugging)"""
        return {
            'cursor_pos': self.cursor_pos,
            'current_token': self.current_token,
            'total_tokens': len(self.tokens)
        }

    def peek_token(self, offset=1):
        """Peek at a token ahead without advancing"""
        peek_pos = self.cursor_pos + offset
        if peek_pos < len(self.tokens):
            return self.tokens[peek_pos]
        else:
            return Token(TokenType.NONE)

    def save_position(self):
        """Save current parser position"""
        return self.cursor_pos

    def restore_position(self, position):
        """Restore parser to a saved position"""
        self.cursor_pos = position
        if self.cursor_pos < len(self.tokens):
            self.current_token = self.tokens[self.cursor_pos]
        else:
            self.current_token = Token(TokenType.NONE)
