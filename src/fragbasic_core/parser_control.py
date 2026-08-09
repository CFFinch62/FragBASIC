"""
Control structure parsing for the BASIC interpreter.
Handles IF, FOR, WHILE, DO, SELECT CASE, SUB, and FUNCTION parsing.
"""

from .tokens import Token, TokenType
from .ast_nodes import Node, NodeType
from .errors import ParseError


class ParserControl:
    """
    Mixin class for control structure parsing in the BASIC interpreter.
    """

    def if_stmt(self):
        """Parse an IF statement with support for both single-line and multi-line formats"""
        line_num = self.current_token.line_num
        self.advance()  # Skip IF

        # Parse condition
        condition = self.expr()

        # Check for THEN
        if self.current_token.type != TokenType.KEYWORD or self.current_token.name != 'THEN':
            raise ParseError("Expected THEN after IF condition", line_num)

        self.advance()  # Skip THEN

        # Check if this is a single-line or multi-line IF
        # If there's a newline immediately after THEN, it's multi-line
        if self.current_token.type == TokenType.NL:
            return self.parse_multiline_if(condition, line_num)

        # Check if we hit ELSEIF, ELSE, or END IF immediately - if so, it's multi-line
        if (self.current_token.type == TokenType.KEYWORD and
            self.current_token.name in ['ELSEIF', 'ELSE', 'END']):
            # Multi-line IF with empty THEN clause
            return self.parse_multiline_if(condition, line_num)

        # Try to parse the THEN statement (single-line IF)
        then_stmt = self.statement()

        # After parsing the THEN statement, check what follows
        # Skip newlines
        self.skip_newlines()

        # If we encounter ELSEIF or END, this is actually a multi-line IF
        if (self.current_token.type == TokenType.KEYWORD and
            self.current_token.name in ['ELSEIF', 'END']):
            # This is a multi-line IF, need to reparse
            return self.parse_multiline_if_with_then(condition, then_stmt, line_num)

        # Single-line IF - check for ELSE
        else_stmt = None
        if self.current_token.type == TokenType.KEYWORD and self.current_token.name == 'ELSE':
            self.advance()  # Skip ELSE
            else_stmt = self.statement()

        # Create single-line IF node
        if else_stmt:
            return Node(NodeType.IF_ELSE, nodes=[condition, then_stmt, else_stmt], line_num=line_num)
        else:
            return Node(NodeType.IF, nodes=[condition, then_stmt], line_num=line_num)

    def parse_multiline_if(self, condition, line_num):
        """Parse a multi-line IF statement starting after THEN"""
        # Skip newlines after THEN
        self.skip_newlines()

        # Parse THEN block
        then_statements = []

        while True:
            if self.current_token.type == TokenType.NONE:
                raise ParseError("Unexpected end of file in IF statement", line_num)

            # Check for keywords that should end the THEN block
            if self.current_token.type == TokenType.KEYWORD:
                keyword = self.current_token.name

                if keyword == 'END':
                    # Look ahead to see if this is END IF
                    if (self.cursor_pos + 1 < len(self.tokens) and
                        self.tokens[self.cursor_pos + 1].type == TokenType.KEYWORD and
                        self.tokens[self.cursor_pos + 1].name == 'IF'):
                        # This is the END IF for our current IF block
                        break
                elif keyword in ['ELSEIF', 'ELSE']:
                    # These keywords end the THEN block
                    break

            stmt = self.statement()
            if stmt.type != NodeType.NULL:
                then_statements.append(stmt)

            # Skip newlines
            self.skip_newlines()

        # Create THEN block
        if len(then_statements) == 0:
            then_block = Node(NodeType.NULL, line_num=line_num)
        elif len(then_statements) == 1:
            then_block = then_statements[0]
        else:
            then_block = Node(NodeType.BLOCK, nodes=then_statements, line_num=line_num)

        return self.parse_multiline_if_with_then(condition, then_block, line_num)

    def parse_multiline_if_with_then(self, condition, then_block, line_num):
        """Parse ELSEIF and ELSE clauses for multi-line IF"""
        elseif_clauses = []

        # Parse ELSEIF clauses
        while (self.current_token.type == TokenType.KEYWORD and
               self.current_token.name == 'ELSEIF'):
            elseif_line_num = self.current_token.line_num
            self.advance()  # Skip ELSEIF

            # Parse ELSEIF condition
            elseif_condition = self.expr()

            # Check for THEN
            if self.current_token.type != TokenType.KEYWORD or self.current_token.name != 'THEN':
                raise ParseError("Expected THEN after ELSEIF condition", elseif_line_num)

            self.advance()  # Skip THEN

            # Skip newlines
            self.skip_newlines()

            # Parse ELSEIF block
            elseif_statements = []

            while True:
                if self.current_token.type == TokenType.NONE:
                    raise ParseError("Unexpected end of file in ELSEIF statement", elseif_line_num)

                # Check for keywords that should end the ELSEIF block
                if self.current_token.type == TokenType.KEYWORD:
                    keyword = self.current_token.name

                    if keyword == 'END':
                        # Look ahead to see if this is END IF
                        if (self.cursor_pos + 1 < len(self.tokens) and
                            self.tokens[self.cursor_pos + 1].type == TokenType.KEYWORD and
                            self.tokens[self.cursor_pos + 1].name == 'IF'):
                            # This is the END IF for our current IF block
                            break
                    elif keyword in ['ELSEIF', 'ELSE']:
                        # These keywords end the ELSEIF block
                        break

                stmt = self.statement()
                if stmt.type != NodeType.NULL:
                    elseif_statements.append(stmt)

                # Skip newlines
                self.skip_newlines()

            # Create ELSEIF block
            if len(elseif_statements) == 0:
                elseif_block = Node(NodeType.NULL, line_num=elseif_line_num)
            elif len(elseif_statements) == 1:
                elseif_block = elseif_statements[0]
            else:
                elseif_block = Node(NodeType.BLOCK, nodes=elseif_statements, line_num=elseif_line_num)

            # Create ELSEIF node
            elseif_node = Node(NodeType.ELSEIF, nodes=[elseif_condition, elseif_block], line_num=elseif_line_num)
            elseif_clauses.append(elseif_node)

        # Parse ELSE clause
        else_block = None
        if self.current_token.type == TokenType.KEYWORD and self.current_token.name == 'ELSE':
            else_line_num = self.current_token.line_num
            self.advance()  # Skip ELSE

            # Skip newlines
            self.skip_newlines()

            # Parse ELSE block
            else_statements = []

            while True:
                if self.current_token.type == TokenType.NONE:
                    raise ParseError("Unexpected end of file in ELSE statement", else_line_num)

                # Check for END IF
                if self.current_token.type == TokenType.KEYWORD and self.current_token.name == 'END':
                    # Look ahead to see if this is END IF
                    if (self.cursor_pos + 1 < len(self.tokens) and
                        self.tokens[self.cursor_pos + 1].type == TokenType.KEYWORD and
                        self.tokens[self.cursor_pos + 1].name == 'IF'):
                        # This is the END IF for our current IF block
                        break

                stmt = self.statement()
                if stmt.type != NodeType.NULL:
                    else_statements.append(stmt)

                # Skip newlines
                self.skip_newlines()

            # Create ELSE block
            if len(else_statements) == 0:
                else_block = Node(NodeType.NULL, line_num=else_line_num)
            elif len(else_statements) == 1:
                else_block = else_statements[0]
            else:
                else_block = Node(NodeType.BLOCK, nodes=else_statements, line_num=else_line_num)

        # Expect END IF
        if (self.current_token.type != TokenType.KEYWORD or self.current_token.name != 'END'):
            raise ParseError("Expected END IF", self.current_token.line_num)

        self.advance()  # Skip END

        if (self.current_token.type != TokenType.KEYWORD or self.current_token.name != 'IF'):
            raise ParseError("Expected IF after END", self.current_token.line_num)

        self.advance()  # Skip IF

        # Build the complete IF_ELSE node
        nodes = [condition, then_block]
        nodes.extend(elseif_clauses)
        if else_block:
            nodes.append(else_block)

        return Node(NodeType.IF_ELSE, nodes=nodes, line_num=line_num)

    def for_stmt(self):
        """Parse a FOR statement"""
        line_num = self.current_token.line_num
        self.advance()  # Skip FOR

        # Parse loop variable
        if self.current_token.type != TokenType.IDENTIFIER:
            raise ParseError("Expected variable name after FOR", line_num)

        var_name = self.current_token.name
        self.advance()

        # Check for =
        if self.current_token.type != TokenType.EQ:
            raise ParseError("Expected = after FOR variable", line_num)

        self.advance()  # Skip =

        # Parse start value
        start_expr = self.expr()

        # Check for TO
        if self.current_token.type != TokenType.KEYWORD or self.current_token.name != 'TO':
            raise ParseError("Expected TO in FOR statement", line_num)

        self.advance()  # Skip TO

        # Parse end value
        end_expr = self.expr()

        # Check for optional STEP
        step_expr = None
        if self.current_token.type == TokenType.KEYWORD and self.current_token.name == 'STEP':
            self.advance()  # Skip STEP
            step_expr = self.expr()

        # Create variable node
        var_node = Node(NodeType.VAR_ACCESS, name=var_name, line_num=line_num)

        # Create FOR node
        nodes = [var_node, start_expr, end_expr]
        if step_expr:
            nodes.append(step_expr)

        return Node(NodeType.FOR, nodes=nodes, line_num=line_num)

    def next_stmt(self):
        """Parse a NEXT statement"""
        line_num = self.current_token.line_num
        self.advance()  # Skip NEXT

        # Optional variable name
        var_name = None
        if self.current_token.type == TokenType.IDENTIFIER:
            var_name = self.current_token.name
            self.advance()

        return Node(NodeType.NEXT, name=var_name, line_num=line_num)

    def while_stmt(self):
        """Parse a WHILE statement"""
        line_num = self.current_token.line_num
        self.advance()  # Skip WHILE

        # Parse condition
        condition = self.expr()

        return Node(NodeType.WHILE, nodes=[condition], line_num=line_num)

    def wend_stmt(self):
        """Parse a WEND statement"""
        line_num = self.current_token.line_num
        self.advance()  # Skip WEND

        return Node(NodeType.WEND, line_num=line_num)

    def do_loop_stmt(self):
        """Parse a DO statement"""
        line_num = self.current_token.line_num
        self.advance()  # Skip DO

        # Check for optional condition at start
        condition_node = None
        condition_type = None

        if self.current_token.type == TokenType.KEYWORD and self.current_token.name in ['WHILE', 'UNTIL']:
            condition_type = self.current_token.name
            self.advance()  # Skip WHILE/UNTIL
            condition_node = self.expr()

        do_node = Node(NodeType.DO_LOOP, line_num=line_num)
        if condition_node:
            do_node.nodes = [condition_node]
            do_node.condition_type = condition_type

        return do_node

    def loop_stmt(self):
        """Parse a LOOP statement"""
        line_num = self.current_token.line_num
        self.advance()  # Skip LOOP

        # Check for optional condition at end
        condition_node = None
        condition_type = None

        if self.current_token.type == TokenType.KEYWORD and self.current_token.name in ['WHILE', 'UNTIL']:
            condition_type = self.current_token.name
            self.advance()  # Skip WHILE/UNTIL
            condition_node = self.expr()

        loop_node = Node(NodeType.LOOP, line_num=line_num)
        if condition_node:
            loop_node.nodes = [condition_node]
            loop_node.condition_type = condition_type
            loop_node.condition_position = 'END'

        return loop_node

    def select_stmt(self):
        """Parse a SELECT CASE statement"""
        line_num = self.current_token.line_num
        self.advance()  # Skip SELECT

        # Check for CASE
        if self.current_token.type != TokenType.KEYWORD or self.current_token.name != 'CASE':
            raise ParseError("Expected CASE after SELECT", line_num)

        self.advance()  # Skip CASE

        # Parse select expression
        select_expr = self.expr()

        # Skip newlines
        self.skip_newlines()

        # Parse CASE clauses
        case_clauses = []

        while True:
            if self.current_token.type == TokenType.NONE:
                raise ParseError("Unexpected end of file in SELECT CASE statement", line_num)

            # Check for END SELECT
            if self.current_token.type == TokenType.KEYWORD and self.current_token.name == 'END':
                # Look ahead to see if this is END SELECT
                if (self.cursor_pos + 1 < len(self.tokens) and
                    self.tokens[self.cursor_pos + 1].type == TokenType.KEYWORD and
                    self.tokens[self.cursor_pos + 1].name == 'SELECT'):
                    break

            # Check for CASE ELSE
            if (self.current_token.type == TokenType.KEYWORD and
                self.current_token.name == 'CASE' and
                self.cursor_pos + 1 < len(self.tokens) and
                self.tokens[self.cursor_pos + 1].type == TokenType.KEYWORD and
                self.tokens[self.cursor_pos + 1].name == 'ELSE'):

                self.advance()  # Skip CASE
                self.advance()  # Skip ELSE

                # Skip newlines
                self.skip_newlines()

                # Parse CASE ELSE block
                else_statements = []

                while True:
                    if self.current_token.type == TokenType.NONE:
                        raise ParseError("Unexpected end of file in CASE ELSE", line_num)

                    # Check for END SELECT
                    if self.current_token.type == TokenType.KEYWORD and self.current_token.name == 'END':
                        # Look ahead to see if this is END SELECT
                        if (self.cursor_pos + 1 < len(self.tokens) and
                            self.tokens[self.cursor_pos + 1].type == TokenType.KEYWORD and
                            self.tokens[self.cursor_pos + 1].name == 'SELECT'):
                            break

                    stmt = self.statement()
                    if stmt.type != NodeType.NULL:
                        else_statements.append(stmt)

                    # Skip newlines
                    self.skip_newlines()

                # Create CASE ELSE block
                if len(else_statements) == 0:
                    else_block = Node(NodeType.NULL, line_num=line_num)
                elif len(else_statements) == 1:
                    else_block = else_statements[0]
                else:
                    else_block = Node(NodeType.BLOCK, nodes=else_statements, line_num=line_num)

                case_clauses.append(else_block)
                break

            # Parse regular CASE clause
            elif self.current_token.type == TokenType.KEYWORD and self.current_token.name == 'CASE':
                case_line_num = self.current_token.line_num
                self.advance()  # Skip CASE

                # Parse case values
                case_values = []
                case_values.append(self.parse_case_value())

                while self.current_token.type == TokenType.COMMA:
                    self.advance()
                    case_values.append(self.parse_case_value())

                # Skip newlines
                self.skip_newlines()

                # Parse case block
                case_statements = []

                while True:
                    if self.current_token.type == TokenType.NONE:
                        raise ParseError("Unexpected end of file in CASE statement", case_line_num)

                    # Check for keywords that should end the CASE block
                    if self.current_token.type == TokenType.KEYWORD:
                        keyword = self.current_token.name

                        if keyword == 'END':
                            # Look ahead to see if this is END SELECT
                            if (self.cursor_pos + 1 < len(self.tokens) and
                                self.tokens[self.cursor_pos + 1].type == TokenType.KEYWORD and
                                self.tokens[self.cursor_pos + 1].name == 'SELECT'):
                                break
                        elif keyword == 'CASE':
                            # This starts a new CASE clause
                            break

                    stmt = self.statement()
                    if stmt.type != NodeType.NULL:
                        case_statements.append(stmt)

                    # Skip newlines
                    self.skip_newlines()

                # Create case block
                if len(case_statements) == 0:
                    case_block = Node(NodeType.NULL, line_num=case_line_num)
                elif len(case_statements) == 1:
                    case_block = case_statements[0]
                else:
                    case_block = Node(NodeType.BLOCK, nodes=case_statements, line_num=case_line_num)

                # Create case values node
                case_values_node = Node(NodeType.BLOCK, nodes=case_values, line_num=case_line_num)

                # Create CASE node
                case_node = Node(NodeType.CASE, nodes=[case_values_node, case_block], line_num=case_line_num)
                case_clauses.append(case_node)

            else:
                raise ParseError("Expected CASE in SELECT statement", self.current_token.line_num)

        # Expect END SELECT
        if (self.current_token.type != TokenType.KEYWORD or self.current_token.name != 'END'):
            raise ParseError("Expected END SELECT", self.current_token.line_num)

        self.advance()  # Skip END

        if (self.current_token.type != TokenType.KEYWORD or self.current_token.name != 'SELECT'):
            raise ParseError("Expected SELECT after END", self.current_token.line_num)

        self.advance()  # Skip SELECT

        # Create SELECT CASE node
        nodes = [select_expr]
        nodes.extend(case_clauses)

        return Node(NodeType.SELECT_CASE, nodes=nodes, line_num=line_num)

    def parse_case_value(self):
        """Parse a case value (can be a single value or a range)"""
        # Parse first value
        value1 = self.expr()

        # Check for TO (range)
        if self.current_token.type == TokenType.KEYWORD and self.current_token.name == 'TO':
            self.advance()  # Skip TO
            value2 = self.expr()

            # Create range node
            range_node = Node(NodeType.BLOCK, nodes=[value1, value2])
            range_node.is_range = True
            return range_node
        else:
            # Single value
            return value1

    def sub_stmt(self):
        """Parse a SUB statement"""
        line_num = self.current_token.line_num
        self.advance()  # Skip SUB

        # Parse SUB name
        if self.current_token.type != TokenType.IDENTIFIER:
            raise ParseError("Expected SUB name", line_num)

        sub_name = self.current_token.name
        self.advance()

        # Parse parameter list
        params = []
        if self.current_token.type == TokenType.LPAREN:
            self.advance()  # Skip (

            if self.current_token.type != TokenType.RPAREN:
                # Parse parameters
                if self.current_token.type != TokenType.IDENTIFIER:
                    raise ParseError("Expected parameter name in SUB", line_num)

                params.append(self.current_token.name)
                self.advance()

                while self.current_token.type == TokenType.COMMA:
                    self.advance()
                    if self.current_token.type != TokenType.IDENTIFIER:
                        raise ParseError("Expected parameter name in SUB", line_num)

                    params.append(self.current_token.name)
                    self.advance()

            if self.current_token.type != TokenType.RPAREN:
                raise ParseError("Expected ) in SUB declaration", line_num)

            self.advance()  # Skip )

        # Skip newlines
        self.skip_newlines()

        # Parse SUB body
        body_statements = []

        while True:
            if self.current_token.type == TokenType.NONE:
                raise ParseError(f"Unexpected end of file in SUB {sub_name}", line_num)

            # Check for END SUB
            if self.current_token.type == TokenType.KEYWORD and self.current_token.name == 'END':
                # Look ahead to see if this is END SUB
                if (self.cursor_pos + 1 < len(self.tokens) and
                    self.tokens[self.cursor_pos + 1].type == TokenType.KEYWORD and
                    self.tokens[self.cursor_pos + 1].name == 'SUB'):
                    break

            stmt = self.statement()
            if stmt.type != NodeType.NULL:
                body_statements.append(stmt)

            # Skip newlines
            self.skip_newlines()

        # Expect END SUB
        if (self.current_token.type != TokenType.KEYWORD or self.current_token.name != 'END'):
            raise ParseError("Expected END SUB", self.current_token.line_num)

        self.advance()  # Skip END

        if (self.current_token.type != TokenType.KEYWORD or self.current_token.name != 'SUB'):
            raise ParseError("Expected SUB after END", self.current_token.line_num)

        self.advance()  # Skip SUB

        # Create SUB node
        sub_node = Node(NodeType.SUB, name=sub_name, line_num=line_num)
        sub_node.params = params
        sub_node.body = body_statements

        return sub_node

    def function_stmt(self):
        """Parse a FUNCTION statement"""
        line_num = self.current_token.line_num
        self.advance()  # Skip FUNCTION

        # Parse FUNCTION name
        if self.current_token.type != TokenType.IDENTIFIER:
            raise ParseError("Expected FUNCTION name", line_num)

        func_name = self.current_token.name
        self.advance()

        # Parse parameter list
        params = []
        if self.current_token.type == TokenType.LPAREN:
            self.advance()  # Skip (

            if self.current_token.type != TokenType.RPAREN:
                # Parse parameters
                if self.current_token.type != TokenType.IDENTIFIER:
                    raise ParseError("Expected parameter name in FUNCTION", line_num)

                params.append(self.current_token.name)
                self.advance()

                while self.current_token.type == TokenType.COMMA:
                    self.advance()
                    if self.current_token.type != TokenType.IDENTIFIER:
                        raise ParseError("Expected parameter name in FUNCTION", line_num)

                    params.append(self.current_token.name)
                    self.advance()

            if self.current_token.type != TokenType.RPAREN:
                raise ParseError("Expected ) in FUNCTION declaration", line_num)

            self.advance()  # Skip )

        # Skip newlines
        self.skip_newlines()

        # Parse FUNCTION body
        body_statements = []

        while True:
            if self.current_token.type == TokenType.NONE:
                raise ParseError(f"Unexpected end of file in FUNCTION {func_name}", line_num)

            # Check for END FUNCTION
            if self.current_token.type == TokenType.KEYWORD and self.current_token.name == 'END':
                # Look ahead to see if this is END FUNCTION
                if (self.cursor_pos + 1 < len(self.tokens) and
                    self.tokens[self.cursor_pos + 1].type == TokenType.KEYWORD and
                    self.tokens[self.cursor_pos + 1].name == 'FUNCTION'):
                    break

            stmt = self.statement()
            if stmt.type != NodeType.NULL:
                body_statements.append(stmt)

            # Skip newlines
            self.skip_newlines()

        # Expect END FUNCTION
        if (self.current_token.type != TokenType.KEYWORD or self.current_token.name != 'END'):
            raise ParseError("Expected END FUNCTION", self.current_token.line_num)

        self.advance()  # Skip END

        if (self.current_token.type != TokenType.KEYWORD or self.current_token.name != 'FUNCTION'):
            raise ParseError("Expected FUNCTION after END", self.current_token.line_num)

        self.advance()  # Skip FUNCTION

        # Create FUNCTION node
        func_node = Node(NodeType.FUNCTION, name=func_name, line_num=line_num)
        func_node.params = params
        func_node.body = body_statements

        return func_node
