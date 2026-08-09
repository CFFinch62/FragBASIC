"""
Statement parsing for the BASIC interpreter.
Handles parsing of all BASIC statements and declarations.
"""

from .tokens import Token, TokenType
from .ast_nodes import Node, NodeType
from .errors import ParseError


class ParserStatements:
    """
    Mixin class for statement parsing in the BASIC interpreter.
    """

    def statement(self):
        """Parse a statement"""
        # Check for line numbers at the beginning of a statement
        line_number = None
        if self.current_token.type == TokenType.NUMBER:
            line_number = int(self.current_token.value)
            self.advance()

            # Check if this is a line number label (followed by colon)
            if self.current_token.type == TokenType.SEP:  # Colon
                self.advance()  # Skip colon
                # Create a line number label node
                label_node = Node(NodeType.LINE_NUMBER, value=line_number, line_num=line_number)
                return label_node

        # Skip newlines
        self.skip_newlines()

        # Handle empty statement
        if self.current_token.type == TokenType.NONE or self.current_token.type == TokenType.SEP:
            if self.current_token.type == TokenType.SEP:
                self.advance()  # Skip separator
            return Node(NodeType.NULL)

        # Check for keywords
        if self.current_token.type == TokenType.KEYWORD:
            keyword = self.current_token.name

            # Handle different statement types
            if keyword == 'PRINT':
                return self.print_stmt()
            elif keyword == 'INPUT':
                return self.input_stmt()
            elif keyword == 'LET':
                self.advance()  # Skip LET
                return self.assignment_stmt()
            elif keyword == 'DIM':
                return self.dim_stmt()
            elif keyword == 'DATA':
                return self.data_stmt()
            elif keyword == 'READ':
                return self.read_stmt()
            elif keyword == 'RESTORE':
                return self.restore_stmt()
            elif keyword == 'REM':
                return self.rem_stmt()
            elif keyword == 'RANDOMIZE':
                return self.randomize_stmt()
            elif keyword == 'SLEEP':
                return self.sleep_stmt()
            elif keyword == 'RETURN':
                return self.return_stmt()
            elif keyword == 'GOSUB':
                return self.gosub_stmt()
            elif keyword == 'CALL':
                return self.call_stmt()
            elif keyword == 'EXIT':
                return self.exit_stmt()
            elif keyword == 'END':
                return self.end_stmt()
            elif keyword == 'IF':
                return self.if_stmt()
            elif keyword == 'FOR':
                return self.for_stmt()
            elif keyword == 'NEXT':
                return self.next_stmt()
            elif keyword == 'WHILE':
                return self.while_stmt()
            elif keyword == 'WEND':
                return self.wend_stmt()
            elif keyword == 'DO':
                return self.do_loop_stmt()
            elif keyword == 'LOOP':
                return self.loop_stmt()
            elif keyword == 'SELECT':
                return self.select_stmt()
            elif keyword == 'SUB':
                return self.sub_stmt()
            elif keyword == 'FUNCTION':
                return self.function_stmt()
            else:
                raise ParseError(f"Unexpected keyword: {keyword}", self.current_token.line_num)

        # Handle assignment statements without LET or SUB calls
        if self.current_token.type == TokenType.IDENTIFIER:
            # Look ahead to see if this is assignment or SUB call
            if self.cursor_pos + 1 < len(self.tokens):
                next_token = self.tokens[self.cursor_pos + 1]
                if next_token.type == TokenType.SEP:  # Colon
                    # This is a label
                    label_name = self.current_token.name
                    self.advance()  # Skip identifier
                    self.advance()  # Skip colon
                    return Node(NodeType.LABEL, name=label_name)
                elif next_token.type == TokenType.EQ or next_token.type == TokenType.LPAREN:
                    # This is assignment (with = or array indexing)
                    return self.assignment_stmt()
                else:
                    # This might be a SUB call
                    sub_name = self.current_token.name
                    line_num = self.current_token.line_num
                    self.advance()
                    # Create a SUB call node (will be handled as function call with no return value)
                    return Node(NodeType.FUNCTION_CALL, name=sub_name, nodes=[], line_num=line_num)
            else:
                # End of tokens, this might be a SUB call
                sub_name = self.current_token.name
                line_num = self.current_token.line_num
                self.advance()
                # Create a SUB call node (will be handled as function call with no return value)
                return Node(NodeType.FUNCTION_CALL, name=sub_name, nodes=[], line_num=line_num)

        raise ParseError(f"Unexpected token: {self.current_token}", self.current_token.line_num)

    # Basic statement parsers

    def print_stmt(self):
        """Parse a PRINT statement"""
        line_num = self.current_token.line_num
        self.advance()  # Skip PRINT

        expressions = []
        separators = []  # Track whether items are separated by ; or ,

        # Parse the list of expressions to print
        while self.current_token.type != TokenType.NONE and self.current_token.type != TokenType.NL and self.current_token.type != TokenType.SEP:
            # Handle empty PRINT
            if self.current_token.type in [TokenType.SEMICOLON, TokenType.COMMA]:
                separators.append(self.current_token.type)
                self.advance()
                continue

            expressions.append(self.expr())

            # Check for separator
            if self.current_token.type in [TokenType.SEMICOLON, TokenType.COMMA]:
                separators.append(self.current_token.type)
                self.advance()
            else:
                # End of PRINT statement
                break

        # Create the PRINT node with expressions and separator info
        print_node = Node(NodeType.PRINT, nodes=expressions, line_num=line_num)
        print_node.separators = separators

        return print_node

    def input_stmt(self):
        """Parse an INPUT statement"""
        line_num = self.current_token.line_num
        self.advance()  # Skip INPUT

        # Check for optional prompt (can be a string literal or expression)
        prompt = None

        # Look ahead to see if we have a prompt followed by semicolon
        # We need to check if this looks like a prompt pattern
        if (self.current_token.type in [TokenType.STRING, TokenType.IDENTIFIER, TokenType.LPAREN] or
            (self.current_token.type == TokenType.KEYWORD and self.current_token.name in ['STR$', 'CHR$', 'LEFT$', 'RIGHT$', 'MID$'])):

            # Try to parse as expression and look for semicolon
            saved_pos = self.cursor_pos
            try:
                # Parse potential prompt expression
                prompt_expr = self.expr()

                # Check if followed by semicolon (indicates this was a prompt)
                if self.current_token.type == TokenType.SEMICOLON:
                    prompt = prompt_expr
                    self.advance()  # Skip semicolon
                else:
                    # No semicolon, so this wasn't a prompt - restore position
                    self.cursor_pos = saved_pos
                    self.current_token = self.tokens[self.cursor_pos] if self.cursor_pos < len(self.tokens) else Token(TokenType.NONE)
                    prompt = None
            except Exception:
                # If expression parsing failed, restore position and continue without prompt
                self.cursor_pos = saved_pos
                self.current_token = self.tokens[self.cursor_pos] if self.cursor_pos < len(self.tokens) else Token(TokenType.NONE)
                prompt = None

        # Parse variable list
        variables = []
        while True:
            if self.current_token.type != TokenType.IDENTIFIER:
                raise ParseError("Expected variable name in INPUT statement", line_num)

            var_name = self.current_token.name
            self.advance()

            # Handle array indexing if present (similar to read statement)
            indices = self.parse_array_indices(line_num)

            # Create variable access node
            var_node = Node(NodeType.VAR_ACCESS, name=var_name, line_num=line_num)
            if indices:
                var_node.nodes = indices

            variables.append(var_node)

            # Check for comma separator
            if self.current_token.type == TokenType.COMMA:
                self.advance()
            else:
                break

        input_node = Node(NodeType.INPUT, nodes=variables, line_num=line_num)
        if prompt:
            input_node.nodes.insert(0, prompt)

        return input_node

    def assignment_stmt(self):
        """Parse an assignment statement"""
        if self.current_token.type != TokenType.IDENTIFIER:
            raise ParseError("Expected variable name in assignment", self.current_token.line_num)

        var_name = self.current_token.name
        line_num = self.current_token.line_num
        self.advance()

        # Handle array indexing
        indices = self.parse_array_indices(line_num)

        # Check for assignment operator
        if self.current_token.type != TokenType.EQ:
            raise ParseError("Expected = in assignment", line_num)

        self.advance()  # Skip =

        # Parse the value expression
        value_expr = self.expr()

        # Create the assignment node
        assign_node = Node(NodeType.VAR_ASSIGN, name=var_name, nodes=[value_expr], line_num=line_num)

        # Add indices for array assignment
        if indices:
            assign_node.nodes.extend(indices)

        return assign_node

    def dim_stmt(self):
        """Parse a DIM statement - supports both variable and array declarations"""
        line_num = self.current_token.line_num
        self.advance()  # Skip DIM

        declarations = []

        while True:
            if self.current_token.type != TokenType.IDENTIFIER:
                raise ParseError("Expected variable or array name in DIM statement", line_num)

            var_name = self.current_token.name
            self.advance()

            # Check if this is an array declaration (has parentheses) or variable declaration
            if self.current_token.type == TokenType.LPAREN:
                # Array declaration: DIM array(size) AS type
                self.advance()  # Skip (

                dimensions = []
                dimensions.append(self.expr())

                while self.current_token.type == TokenType.COMMA:
                    self.advance()
                    dimensions.append(self.expr())

                if self.current_token.type != TokenType.RPAREN:
                    raise ParseError("Expected ) in array declaration", line_num)

                self.advance()  # Skip )

                # Check for AS type (optional for arrays)
                var_type = None
                if self.current_token.type == TokenType.KEYWORD and self.current_token.name == 'AS':
                    self.advance()  # Skip AS

                    if self.current_token.type != TokenType.KEYWORD:
                        raise ParseError("Expected type after AS in array declaration", line_num)

                    var_type = self.current_token.name.upper()
                    if var_type not in ['INTEGER', 'LONG', 'SINGLE', 'DOUBLE', 'STRING']:
                        raise ParseError(f"Invalid type '{var_type}' in array declaration", line_num)

                    self.advance()

                # Create array declaration node
                array_def = Node(NodeType.DIM, name=var_name, nodes=dimensions, line_num=line_num)
                array_def.var_type = var_type
                array_def.is_array = True

                declarations.append(array_def)

            else:
                # Variable declaration: DIM variable AS type
                if self.current_token.type != TokenType.KEYWORD or self.current_token.name != 'AS':
                    raise ParseError(f"Expected AS type declaration for variable {var_name}", line_num)

                self.advance()  # Skip AS

                if self.current_token.type != TokenType.KEYWORD:
                    raise ParseError("Expected type after AS in variable declaration", line_num)

                var_type = self.current_token.name.upper()
                if var_type not in ['INTEGER', 'LONG', 'SINGLE', 'DOUBLE', 'STRING']:
                    raise ParseError(f"Invalid type '{var_type}' in variable declaration", line_num)

                self.advance()

                # Create variable declaration node
                var_def = Node(NodeType.DIM, name=var_name, line_num=line_num)
                var_def.var_type = var_type
                var_def.is_array = False

                declarations.append(var_def)

            # Check for comma to continue with more declarations
            if self.current_token.type == TokenType.COMMA:
                self.advance()
            else:
                break

        return Node(NodeType.BLOCK, nodes=declarations, line_num=line_num)

    # Data statement parsers

    def data_stmt(self):
        """Parse a DATA statement"""
        line_num = self.current_token.line_num
        self.advance()  # Skip DATA

        values = []

        while True:
            # Parse data value (can be number, string, or expression)
            if self.current_token.type == TokenType.NUMBER:
                value = self.current_token.value
                values.append(Node(NodeType.NUMBER, value=value, line_num=line_num))
                self.advance()
            elif self.current_token.type == TokenType.STRING:
                value = self.current_token.name
                values.append(Node(NodeType.STRING, name=value, line_num=line_num))
                self.advance()
            elif self.current_token.type == TokenType.IDENTIFIER:
                # Could be a variable reference in DATA
                name = self.current_token.name
                values.append(Node(NodeType.VAR_ACCESS, name=name, line_num=line_num))
                self.advance()
            else:
                # Try to parse as expression
                values.append(self.expr())

            # Check for comma separator
            if self.current_token.type == TokenType.COMMA:
                self.advance()
            else:
                break

        return Node(NodeType.DATA, nodes=values, line_num=line_num)

    def read_stmt(self):
        """Parse a READ statement"""
        line_num = self.current_token.line_num
        self.advance()  # Skip READ

        variables = []

        while True:
            if self.current_token.type != TokenType.IDENTIFIER:
                raise ParseError("Expected variable name in READ statement", line_num)

            var_name = self.current_token.name
            self.advance()

            # Handle array indexing
            indices = self.parse_array_indices(line_num)

            # Create variable access node
            var_node = Node(NodeType.VAR_ACCESS, name=var_name, line_num=line_num)
            if indices:
                var_node.nodes = indices

            variables.append(var_node)

            # Check for comma separator
            if self.current_token.type == TokenType.COMMA:
                self.advance()
            else:
                break

        return Node(NodeType.READ, nodes=variables, line_num=line_num)

    def restore_stmt(self):
        """Parse a RESTORE statement"""
        line_num = self.current_token.line_num
        self.advance()  # Skip RESTORE
        return Node(NodeType.RESTORE, line_num=line_num)

    # Other statement parsers

    def rem_stmt(self):
        """Parse a REM statement"""
        line_num = self.current_token.line_num
        self.advance()  # Skip REM

        # Skip everything until end of line
        while (self.current_token.type != TokenType.NONE and
               self.current_token.type != TokenType.NL and
               self.current_token.type != TokenType.SEP):
            self.advance()

        return Node(NodeType.REM, line_num=line_num)

    def randomize_stmt(self):
        """Parse a RANDOMIZE statement"""
        line_num = self.current_token.line_num
        self.advance()  # Skip RANDOMIZE

        # Check for optional seed value
        seed_expr = None
        if (self.current_token.type != TokenType.NONE and
            self.current_token.type != TokenType.NL and
            self.current_token.type != TokenType.SEP):
            seed_expr = self.expr()

        if seed_expr:
            return Node(NodeType.RANDOMIZE, nodes=[seed_expr], line_num=line_num)
        else:
            return Node(NodeType.RANDOMIZE, line_num=line_num)

    def sleep_stmt(self):
        """Parse a SLEEP statement"""
        line_num = self.current_token.line_num
        self.advance()  # Skip SLEEP

        # Check for optional time value (in seconds)
        time_expr = None
        if (self.current_token.type != TokenType.NONE and
            self.current_token.type != TokenType.NL and
            self.current_token.type != TokenType.SEP):
            time_expr = self.expr()

        if time_expr:
            return Node(NodeType.SLEEP, nodes=[time_expr], line_num=line_num)
        else:
            return Node(NodeType.SLEEP, line_num=line_num)

    def return_stmt(self):
        """Parse a RETURN statement"""
        line_num = self.current_token.line_num
        self.advance()  # Skip RETURN

        # Check for optional return value (for functions)
        return_expr = None
        if (self.current_token.type != TokenType.NONE and
            self.current_token.type != TokenType.NL and
            self.current_token.type != TokenType.SEP):
            return_expr = self.expr()

        if return_expr:
            return Node(NodeType.RETURN, nodes=[return_expr], line_num=line_num)
        else:
            return Node(NodeType.RETURN, line_num=line_num)

    def gosub_stmt(self):
        """Parse a GOSUB statement"""
        line_num = self.current_token.line_num
        self.advance()  # Skip GOSUB

        # Parse target (line number or label)
        if self.current_token.type == TokenType.NUMBER:
            target_line = int(self.current_token.value)
            self.advance()
            return Node(NodeType.GOSUB, value=target_line, line_num=line_num)
        elif self.current_token.type == TokenType.IDENTIFIER:
            target_label = self.current_token.name
            self.advance()
            return Node(NodeType.GOSUB, name=target_label, line_num=line_num)
        else:
            raise ParseError("Expected line number or label after GOSUB", line_num)

    def call_stmt(self):
        """Parse a CALL statement"""
        line_num = self.current_token.line_num
        self.advance()  # Skip CALL

        # Parse subroutine name
        if self.current_token.type != TokenType.IDENTIFIER:
            raise ParseError("Expected subroutine name after CALL", line_num)

        sub_name = self.current_token.name
        self.advance()

        # Parse optional arguments
        args = []
        if self.current_token.type == TokenType.LPAREN:
            self.advance()  # Skip (

            # Parse arguments if any
            if self.current_token.type != TokenType.RPAREN:
                args.append(self.expr())

                while self.current_token.type == TokenType.COMMA:
                    self.advance()  # Skip comma
                    args.append(self.expr())

            if self.current_token.type != TokenType.RPAREN:
                raise ParseError("Expected ) in CALL statement", line_num)

            self.advance()  # Skip )

        return Node(NodeType.CALL, name=sub_name, nodes=args, line_num=line_num)

    def exit_stmt(self):
        """Parse an EXIT statement"""
        line_num = self.current_token.line_num
        self.advance()  # Skip EXIT

        # Check for exit type (FOR, WHILE, DO, etc.)
        exit_type = None
        if self.current_token.type == TokenType.KEYWORD:
            exit_type = self.current_token.name
            self.advance()

        return Node(NodeType.EXIT, name=exit_type, line_num=line_num)

    def end_stmt(self):
        """Parse an END statement"""
        line_num = self.current_token.line_num
        self.advance()  # Skip END

        # Check for END IF
        if self.current_token.type == TokenType.KEYWORD and self.current_token.name == 'IF':
            self.advance()  # Skip IF
            return Node(NodeType.END_IF, line_num=line_num)

        return Node(NodeType.END, line_num=line_num)
