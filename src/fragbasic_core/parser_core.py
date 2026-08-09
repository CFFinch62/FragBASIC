"""
Core parser functionality for BASIC language.
Handles basic parsing infrastructure and expression parsing.
"""

from typing import List
from .tokens import Token, TokenType
from .ast_nodes import Node, NodeType
from .errors import ParseError


class ParserCore:
    """
    Core parser functionality for BASIC language syntax.
    Provides basic parsing infrastructure and expression parsing.
    """

    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.cursor_pos = 0
        self.current_token = self.tokens[0] if tokens else Token(TokenType.NONE)

    def advance(self):
        """Advance to the next token"""
        self.cursor_pos += 1
        if self.cursor_pos < len(self.tokens):
            self.current_token = self.tokens[self.cursor_pos]
        else:
            self.current_token = Token(TokenType.NONE)

    def skip_newlines(self):
        """Skip any newline tokens"""
        while self.current_token.type == TokenType.NL:
            self.advance()

    def parse_array_indices(self, line_num):
        """Parse array indices in parentheses"""
        indices = []
        if self.current_token.type == TokenType.LPAREN:
            self.advance()  # Skip (

            # Parse indices
            indices.append(self.expr())

            while self.current_token.type == TokenType.COMMA:
                self.advance()
                indices.append(self.expr())

            if self.current_token.type != TokenType.RPAREN:
                raise ParseError("Expected ) in array indexing", line_num)

            self.advance()  # Skip )

        return indices

    def parse(self):
        """Parse the tokens and return the AST"""
        # Main program is a block of statements
        statements = []

        while self.current_token.type != TokenType.NONE:
            stmt = self.statement()
            if stmt.type != NodeType.NULL:
                statements.append(stmt)

            # Skip optional newlines between statements
            self.skip_newlines()

        if not statements:
            return Node(NodeType.NULL)
        elif len(statements) == 1:
            return statements[0]
        else:
            return Node(NodeType.BLOCK, nodes=statements)

    # Expression parsing

    def expr(self):
        """Parse an expression (lowest precedence)"""
        return self.logical_or()

    def logical_or(self):
        """Parse logical OR expressions"""
        left = self.logical_and()

        while self.current_token.type == TokenType.KEYWORD and self.current_token.name == 'OR':
            op_token = self.current_token
            self.advance()
            right = self.logical_and()
            left = Node(NodeType.OR, nodes=[left, right], line_num=op_token.line_num)

        return left

    def logical_and(self):
        """Parse logical AND expressions"""
        left = self.logical_not()

        while self.current_token.type == TokenType.KEYWORD and self.current_token.name == 'AND':
            op_token = self.current_token
            self.advance()
            right = self.logical_not()
            left = Node(NodeType.AND, nodes=[left, right], line_num=op_token.line_num)

        return left

    def logical_not(self):
        """Parse logical NOT expressions"""
        if self.current_token.type == TokenType.KEYWORD and self.current_token.name == 'NOT':
            op_token = self.current_token
            self.advance()
            operand = self.logical_not()
            return Node(NodeType.NOT, nodes=[operand], line_num=op_token.line_num)

        return self.logical_xor()

    def logical_xor(self):
        """Parse logical XOR, EQV, IMP expressions"""
        left = self.relational()

        while (self.current_token.type == TokenType.KEYWORD and
               self.current_token.name in ['XOR', 'EQV', 'IMP']):
            op_token = self.current_token
            op_name = op_token.name
            self.advance()
            right = self.relational()

            if op_name == 'XOR':
                left = Node(NodeType.XOR, nodes=[left, right], line_num=op_token.line_num)
            elif op_name == 'EQV':
                left = Node(NodeType.EQV, nodes=[left, right], line_num=op_token.line_num)
            elif op_name == 'IMP':
                left = Node(NodeType.IMP, nodes=[left, right], line_num=op_token.line_num)

        return left

    def relational(self):
        """Parse relational expressions (=, <>, <, >, <=, >=)"""
        left = self.additive()

        while self.current_token.type in [TokenType.EQ, TokenType.NE, TokenType.LT,
                                          TokenType.GT, TokenType.LTE, TokenType.GTE]:
            op_token = self.current_token
            self.advance()
            right = self.additive()

            if op_token.type == TokenType.EQ:
                left = Node(NodeType.EE, nodes=[left, right], line_num=op_token.line_num)
            elif op_token.type == TokenType.NE:
                left = Node(NodeType.NE, nodes=[left, right], line_num=op_token.line_num)
            elif op_token.type == TokenType.LT:
                left = Node(NodeType.LT, nodes=[left, right], line_num=op_token.line_num)
            elif op_token.type == TokenType.GT:
                left = Node(NodeType.GT, nodes=[left, right], line_num=op_token.line_num)
            elif op_token.type == TokenType.LTE:
                left = Node(NodeType.LTE, nodes=[left, right], line_num=op_token.line_num)
            elif op_token.type == TokenType.GTE:
                left = Node(NodeType.GTE, nodes=[left, right], line_num=op_token.line_num)

        return left

    def additive(self):
        """Parse additive expressions (+, -)"""
        left = self.multiplicative()

        while self.current_token.type in [TokenType.PLUS, TokenType.MINUS]:
            op_token = self.current_token
            self.advance()
            right = self.multiplicative()

            if op_token.type == TokenType.PLUS:
                left = Node(NodeType.ADD, nodes=[left, right], line_num=op_token.line_num)
            elif op_token.type == TokenType.MINUS:
                left = Node(NodeType.SUBTRACT, nodes=[left, right], line_num=op_token.line_num)

        return left

    def multiplicative(self):
        """Parse multiplicative expressions (*, /, \\, MOD)"""
        left = self.power()

        while (self.current_token.type in [TokenType.MULTIPLY, TokenType.DIVIDE, TokenType.INTEGER_DIV] or
               (self.current_token.type == TokenType.KEYWORD and self.current_token.name == 'MOD')):
            op_token = self.current_token
            self.advance()
            right = self.power()

            if op_token.type == TokenType.MULTIPLY:
                left = Node(NodeType.MULTIPLY, nodes=[left, right], line_num=op_token.line_num)
            elif op_token.type == TokenType.DIVIDE:
                left = Node(NodeType.DIVIDE, nodes=[left, right], line_num=op_token.line_num)
            elif op_token.type == TokenType.INTEGER_DIV:
                left = Node(NodeType.INTEGER_DIV, nodes=[left, right], line_num=op_token.line_num)
            elif op_token.name == 'MOD':
                left = Node(NodeType.MOD, nodes=[left, right], line_num=op_token.line_num)

        return left

    def power(self):
        """Parse power expressions (^)"""
        left = self.unary()

        # Right-associative
        if self.current_token.type == TokenType.POWER:
            op_token = self.current_token
            self.advance()
            right = self.power()  # Right-associative recursion
            return Node(NodeType.POWER, nodes=[left, right], line_num=op_token.line_num)

        return left

    def unary(self):
        """Parse unary expressions (+, -)"""
        if self.current_token.type == TokenType.PLUS:
            op_token = self.current_token
            self.advance()
            operand = self.unary()
            return Node(NodeType.PLUS, nodes=[operand], line_num=op_token.line_num)
        elif self.current_token.type == TokenType.MINUS:
            op_token = self.current_token
            self.advance()
            operand = self.unary()
            return Node(NodeType.MINUS, nodes=[operand], line_num=op_token.line_num)

        return self.primary()

    def primary(self):
        """Parse primary expressions (numbers, strings, variables, function calls, parentheses)"""
        # Numbers
        if self.current_token.type == TokenType.NUMBER:
            value = self.current_token.value
            line_num = self.current_token.line_num
            self.advance()
            return Node(NodeType.NUMBER, value=value, line_num=line_num)

        # Strings
        elif self.current_token.type == TokenType.STRING:
            value = self.current_token.name
            line_num = self.current_token.line_num
            self.advance()
            return Node(NodeType.STRING, name=value, line_num=line_num)

        # Parenthesized expressions
        elif self.current_token.type == TokenType.LPAREN:
            self.advance()  # Skip (
            expr = self.expr()
            if self.current_token.type != TokenType.RPAREN:
                raise ParseError("Expected )", self.current_token.line_num)
            self.advance()  # Skip )
            return expr

        # Identifiers (variables, function calls, array access)
        elif self.current_token.type == TokenType.IDENTIFIER:
            name = self.current_token.name
            line_num = self.current_token.line_num
            self.advance()

            # Check for function call or array access
            if self.current_token.type == TokenType.LPAREN:
                self.advance()  # Skip (

                args = []
                if self.current_token.type != TokenType.RPAREN:
                    args.append(self.expr())

                    while self.current_token.type == TokenType.COMMA:
                        self.advance()
                        args.append(self.expr())

                if self.current_token.type != TokenType.RPAREN:
                    raise ParseError("Expected ) in function call", line_num)

                self.advance()  # Skip )

                # Determine if this is a function call or array access
                # Built-in functions are treated as function calls
                if self.is_builtin_function(name):
                    return Node(NodeType.FUNCTION_CALL, name=name, nodes=args, line_num=line_num)
                else:
                    # Could be array access or user-defined function. Node
                    # normalizes nodes=None to [], so an empty-args call
                    # like f() is indistinguishable from a bare "f" by
                    # nodes alone - mark that parens were present via
                    # value so the interpreter can tell a zero-arg call
                    # apart from a plain variable reference.
                    return Node(NodeType.VAR_ACCESS, name=name, nodes=args, value='CALL', line_num=line_num)
            else:
                # Simple variable access
                return Node(NodeType.VAR_ACCESS, name=name, line_num=line_num)

        # Keywords that can be used as functions
        elif (self.current_token.type == TokenType.KEYWORD and
              self.is_builtin_function(self.current_token.name)):
            name = self.current_token.name
            line_num = self.current_token.line_num
            self.advance()

            # Check for function call
            if self.current_token.type == TokenType.LPAREN:
                self.advance()  # Skip (

                args = []
                if self.current_token.type != TokenType.RPAREN:
                    args.append(self.expr())

                    while self.current_token.type == TokenType.COMMA:
                        self.advance()
                        args.append(self.expr())

                if self.current_token.type != TokenType.RPAREN:
                    raise ParseError("Expected ) in function call", line_num)

                self.advance()  # Skip )

                return Node(NodeType.FUNCTION_CALL, name=name, nodes=args, line_num=line_num)
            else:
                # Function without parentheses (like DATE$, TIME$, TIMER)
                return Node(NodeType.FUNCTION_CALL, name=name, nodes=[], line_num=line_num)

        else:
            raise ParseError(f"Unexpected token in expression: {self.current_token}", self.current_token.line_num)

    def is_builtin_function(self, name):
        """Check if a name is a built-in function"""
        builtin_functions = {
            'ABS', 'SQR', 'SIN', 'COS', 'TAN', 'ATN', 'EXP', 'LOG', 'INT', 'FIX', 'SGN', 'RND',
            'LEN', 'LEFT$', 'RIGHT$', 'MID$', 'CHR$', 'ASC', 'STR$', 'VAL', 'SPACE$', 'STRING$',
            'INSTR', 'UCASE$', 'LCASE$', 'LTRIM$', 'RTRIM$',
            'CINT', 'CLNG', 'CSNG', 'CDBL', 'DATE$', 'TIME$', 'TIMER', 'INKEY$'
        }
        return name.upper() in builtin_functions
