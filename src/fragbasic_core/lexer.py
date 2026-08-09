from typing import List
from .tokens import Token, TokenType
from .errors import LexerError

# Lexer class
class Lexer:
    # Keywords that the language recognizes (Educational BASIC subset)
    # Graphics keywords removed: LINE, CIRCLE, PSET, DRAW, PAINT, VIEW, WINDOW
    KEYWORDS = [
        'PRINT', 'INPUT', 'LET', 'DIM', 'DATA', 'READ', 'RESTORE',
        'IF', 'THEN', 'ELSE', 'ELSEIF', 'END', 'FOR', 'TO', 'STEP', 'NEXT',
        'WHILE', 'WEND', 'DO', 'LOOP', 'UNTIL', 'GOSUB', 'RETURN',
        'SUB', 'FUNCTION', 'EXIT', 'SHARED', 'STATIC', 'RANDOMIZE', 'REM',
        'INKEY$', 'SLEEP', 'CALL',
        'AND', 'OR', 'NOT', 'XOR', 'EQV', 'IMP', 'MOD', 'AS',
        'INTEGER', 'LONG', 'SINGLE', 'DOUBLE', 'STRING', 'CONST',
        'TYPE', 'OPTION', 'BASE', 'DEFINT', 'DEFLNG', 'DEFSNG', 'DEFDBL', 'DEFSTR',
        'SELECT', 'CASE',
        # Built-in functions that can be called without parentheses
        'RND', 'TIMER', 'DATE$', 'TIME$', 'INKEY$'
    ]

    def __init__(self, code: str):
        self.code = code
        self.cursor_pos = 0
        self.line_num = 1  # Track line numbers for error reporting
        self.current_char = self.code[0] if len(self.code) > 0 else None

    def advance(self):
        """Advance the cursor position and set the current character"""
        # Bump line_num when stepping *past* a newline (not when landing on
        # one) so a multi-char token whose last advance() lands it on '\n'
        # (e.g. a number or identifier at end-of-line) still gets tagged
        # with the line it's actually on, not the line after it.
        if self.current_char == '\n':
            self.line_num += 1
        self.cursor_pos += 1
        if self.cursor_pos < len(self.code):
            self.current_char = self.code[self.cursor_pos]
        else:
            self.current_char = None

    def generate_tokens(self) -> List[Token]:
        """Convert code string into a list of tokens"""
        tokens = []

        while self.current_char is not None:
            # Skip whitespace
            if self.current_char.isspace() and self.current_char != '\n':
                self.advance()
            # Handle newlines
            elif self.current_char == '\n':
                tokens.append(Token(TokenType.NL, line_num=self.line_num))
                self.advance()
            # Handle numbers (including line numbers at start of line)
            elif self.current_char.isdigit():
                tokens.append(self.generate_number())
            # Handle identifiers and keywords
            elif self.current_char.isalpha():
                word_token = self.generate_word()
                tokens.append(word_token)

                # Special handling for REM statements - consume rest of line as comment
                if word_token.type == TokenType.KEYWORD and word_token.name == 'REM':
                    comment_text = ""
                    while self.current_char is not None and self.current_char != '\n':
                        comment_text += self.current_char
                        self.advance()
                    # Create a special REM content token if there's comment text
                    if comment_text.strip():
                        tokens.append(Token(TokenType.STRING, name=comment_text.strip(), line_num=self.line_num))
                    continue

            # Handle strings
            elif self.current_char == '"':
                tokens.append(self.generate_string())
            # Handle single-quoted strings (QB64 extension)
            elif self.current_char == "'":
                # Check if it's a comment or a string
                if self.is_at_start_of_line():
                    self.skip_comment()
                else:
                    tokens.append(self.generate_single_quoted_string())
            # Handle operators and symbols
            elif self.current_char == '+':
                tokens.append(Token(TokenType.PLUS, line_num=self.line_num))
                self.advance()
            elif self.current_char == '-':
                tokens.append(Token(TokenType.MINUS, line_num=self.line_num))
                self.advance()
            elif self.current_char == '*':
                tokens.append(Token(TokenType.MULTIPLY, line_num=self.line_num))
                self.advance()
            elif self.current_char == '/':
                tokens.append(Token(TokenType.DIVIDE, line_num=self.line_num))
                self.advance()
            elif self.current_char == '\\':
                tokens.append(Token(TokenType.INTEGER_DIV, line_num=self.line_num))
                self.advance()
            elif self.current_char == '^':
                tokens.append(Token(TokenType.POWER, line_num=self.line_num))
                self.advance()
            elif self.current_char == '(':
                tokens.append(Token(TokenType.LPAREN, line_num=self.line_num))
                self.advance()
            elif self.current_char == ')':
                tokens.append(Token(TokenType.RPAREN, line_num=self.line_num))
                self.advance()
            elif self.current_char == '[':
                tokens.append(Token(TokenType.LSQBRACKET, line_num=self.line_num))
                self.advance()
            elif self.current_char == ']':
                tokens.append(Token(TokenType.RSQBRACKET, line_num=self.line_num))
                self.advance()
            elif self.current_char == '=':
                tokens.append(Token(TokenType.EQ, line_num=self.line_num))
                self.advance()
            elif self.current_char == '<':
                self.advance()
                # Check for <= or <>
                if self.current_char == '=':
                    tokens.append(Token(TokenType.LTE, line_num=self.line_num))
                    self.advance()
                elif self.current_char == '>':
                    tokens.append(Token(TokenType.NE, line_num=self.line_num))
                    self.advance()
                else:
                    tokens.append(Token(TokenType.LT, line_num=self.line_num))
            elif self.current_char == '>':
                self.advance()
                # Check for >=
                if self.current_char == '=':
                    tokens.append(Token(TokenType.GTE, line_num=self.line_num))
                    self.advance()
                else:
                    tokens.append(Token(TokenType.GT, line_num=self.line_num))
            elif self.current_char == ',':
                tokens.append(Token(TokenType.COMMA, line_num=self.line_num))
                self.advance()
            elif self.current_char == ';':
                tokens.append(Token(TokenType.SEMICOLON, line_num=self.line_num))
                self.advance()
            elif self.current_char == ':':
                tokens.append(Token(TokenType.SEP, line_num=self.line_num))
                self.advance()
            elif self.current_char == '$':
                tokens.append(Token(TokenType.DOLLAR, line_num=self.line_num))
                self.advance()
            elif self.current_char == '!':
                tokens.append(Token(TokenType.EXCLAMATION, line_num=self.line_num))
                self.advance()
            elif self.current_char == '%':
                tokens.append(Token(TokenType.PERCENT, line_num=self.line_num))
                self.advance()
            elif self.current_char == '#':
                tokens.append(Token(TokenType.HASH, line_num=self.line_num))
                self.advance()
            else:
                raise LexerError(f"Illegal character '{self.current_char}'", self.line_num)

        return tokens

    def is_at_start_of_line(self):
        """Check if the current position is at the start of a line (ignoring whitespace)"""
        pos = self.cursor_pos - 1
        while pos >= 0 and self.code[pos].isspace() and self.code[pos] != '\n':
            pos -= 1
        return pos < 0 or self.code[pos] == '\n'

    def skip_comment(self):
        """Skip a comment (REM or ' until the end of the line)"""
        while self.current_char is not None and self.current_char != '\n':
            self.advance()

    def generate_number(self) -> Token:
        """Generate a number token from consecutive digits and decimal point"""
        num_str = ""
        decimal_point_count = 0

        while self.current_char is not None and (self.current_char.isdigit() or self.current_char == '.'):
            if self.current_char == '.':
                decimal_point_count += 1
                if decimal_point_count > 1:
                    break

            num_str += self.current_char
            self.advance()

        if num_str.startswith('.'):
            num_str = '0' + num_str
        if num_str.endswith('.'):
            num_str += '0'

        # Check for type suffixes
        type_suffix = None
        if self.current_char in ['!', '#', '%']:
            type_suffix = self.current_char
            self.advance()

        value = float(num_str)
        if type_suffix == '%':
            value = int(value)  # Integer

        return Token(TokenType.NUMBER, value=value, line_num=self.line_num)

    def generate_word(self) -> Token:
        """Generate an identifier or keyword token from consecutive letters"""
        word = ""

        while self.current_char is not None and (self.current_char.isalnum() or self.current_char == '_'):
            word += self.current_char
            self.advance()

        # Check for type suffixes in identifiers
        if self.current_char in ['$', '!', '#', '%']:
            word += self.current_char
            self.advance()

        if word.upper() in self.KEYWORDS:
            return Token(TokenType.KEYWORD, name=word.upper(), line_num=self.line_num)
        else:
            return Token(TokenType.IDENTIFIER, name=word, line_num=self.line_num)

    def generate_string(self) -> Token:
        """Generate a string token from text between double quotes"""
        string = ""
        self.advance()  # Skip the opening quote

        # Handle escape characters and collect the string
        while self.current_char is not None and self.current_char != '"':
            string += self.current_char
            self.advance()

        if self.current_char is None:
            raise LexerError("Unterminated string", self.line_num)

        # Skip the closing quote
        self.advance()

        return Token(TokenType.STRING, name=string, line_num=self.line_num)

    def generate_single_quoted_string(self) -> Token:
        """Generate a string token from text between single quotes (QB64 extension)"""
        string = ""
        self.advance()  # Skip the opening quote

        # Handle escape characters and collect the string
        while self.current_char is not None and self.current_char != "'":
            string += self.current_char
            self.advance()

        if self.current_char is None:
            raise LexerError("Unterminated string", self.line_num)

        # Skip the closing quote
        self.advance()

        return Token(TokenType.STRING, name=string, line_num=self.line_num)
