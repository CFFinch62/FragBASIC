"""
Input/Output and DATA statement handling for the BASIC interpreter.
"""

from .tokens import TokenType
from .variable import Variable


class InterpreterIO:
    """
    Mixin class for I/O and DATA operations in the BASIC interpreter.
    """

    def visit_print(self, node):
        """Visit a PRINT node"""
        output = ""

        # Handle empty PRINT statement - should produce a blank line
        if not node.nodes:
            self.output_func("\n")
            return None

        for i, expr_node in enumerate(node.nodes):
            value = self.visit(expr_node)

            # Add the value to output
            output += str(value)

            # Handle separators (semicolon, comma)
            if hasattr(node, 'separators') and i < len(node.separators):
                separator = node.separators[i]
                if separator == TokenType.SEMICOLON:
                    output += " "  # Add a space for semicolon
                elif separator == TokenType.COMMA:
                    # Comma creates a tab effect (14 spaces in classic BASIC)
                    current_pos = len(output) % 14
                    spaces_needed = 14 - current_pos if current_pos > 0 else 0
                    output += " " * spaces_needed

        # Add newline unless the last separator was a semicolon
        if (not hasattr(node, 'separators') or
            not node.separators or
            node.separators[-1] != TokenType.SEMICOLON):
            output += "\n"

        self.output_func(output)
        return None

    def visit_input(self, node):
        """Visit an INPUT node"""
        variables = node.nodes
        prompt = None

        # Check if first node is a prompt
        if variables and hasattr(variables[0], 'type') and variables[0].type.name in ['STRING', 'ADD', 'FUNCTION_CALL']:
            prompt = self.visit(variables[0])
            variables = variables[1:]

        # Display prompt if provided
        if prompt:
            self.output_func(prompt.to_string())
        else:
            self.output_func("? ")  # Default prompt

        # Get input from user
        try:
            user_input = self.input_func()
        except (EOFError, KeyboardInterrupt):
            user_input = ""

        # Parse input values (comma-separated)
        input_values = [val.strip() for val in user_input.split(',')]

        # Assign values to variables
        for i, var_node in enumerate(variables):
            if i < len(input_values):
                input_str = input_values[i]
            else:
                input_str = ""

            # Convert input to appropriate type based on variable
            var_name = var_node.name

            if var_name.endswith('$'):
                # String variable
                value = Variable(input_str, 'STRING')
            else:
                # Numeric variable
                try:
                    if '.' in input_str:
                        value = Variable(float(input_str), 'SINGLE')
                    else:
                        value = Variable(int(input_str), 'INTEGER')
                except ValueError:
                    value = Variable(0, 'INTEGER')

            # Handle array assignment if this is an array access
            if var_node.nodes:
                # This is array assignment
                array_name = var_node.name
                indices = [self.visit(index_node).to_integer() for index_node in var_node.nodes]

                # Check if array exists
                if array_name not in self.arrays:
                    self.error(f"Array {array_name} not defined")

                array = self.arrays[array_name]

                # Assign to array element
                try:
                    if len(indices) == 1:
                        array[indices[0]] = value
                    elif len(indices) == 2:
                        array[indices[0]][indices[1]] = value
                    elif len(indices) == 3:
                        array[indices[0]][indices[1]][indices[2]] = value
                    else:
                        self.error(f"Too many dimensions for array {array_name}")
                except (IndexError, KeyError):
                    self.error(f"Array index out of bounds for {array_name}")
            else:
                # Regular variable assignment
                self.variables[var_name] = value

        return None

    # DATA-READ-RESTORE implementation
    def visit_data(self, _node):
        """Visit a DATA node"""
        # DATA statements are processed during collect_definitions phase
        # During execution, they do nothing
        return None

    def visit_read(self, node):
        """Visit a READ node"""
        variables = node.nodes

        for var_node in variables:
            # Check if we have data available
            if self.data_index >= len(self.data_values):
                self.error("Out of DATA")

            # Get the next data value
            data_value = self.data_values[self.data_index]
            self.data_index += 1

            var_name = var_node.name

            # Convert data value to appropriate type based on variable
            if var_name.endswith('$'):
                # String variable
                value = Variable(data_value.to_string(), 'STRING')
            elif var_name.endswith('%'):
                # Integer variable
                value = Variable(data_value.to_integer(), 'INTEGER')
            elif var_name.endswith('!'):
                # Single precision variable
                value = Variable(data_value.to_single(), 'SINGLE')
            elif var_name.endswith('#'):
                # Double precision variable
                value = Variable(data_value.to_single(), 'DOUBLE')
            else:
                # Default to single precision
                value = Variable(data_value.to_single(), 'SINGLE')

            # Handle array assignment if this is an array access
            if var_node.nodes:
                # This is array assignment
                array_name = var_node.name
                indices = [self.visit(index_node).to_integer() for index_node in var_node.nodes]

                # Check if array exists
                if array_name not in self.arrays:
                    self.error(f"Array {array_name} not defined")

                array = self.arrays[array_name]

                # Assign to array element
                try:
                    if len(indices) == 1:
                        array[indices[0]] = value
                    elif len(indices) == 2:
                        array[indices[0]][indices[1]] = value
                    elif len(indices) == 3:
                        array[indices[0]][indices[1]][indices[2]] = value
                    else:
                        self.error(f"Too many dimensions for array {array_name}")
                except (IndexError, KeyError):
                    self.error(f"Array index out of bounds for {array_name}")
            else:
                # Regular variable assignment
                self.variables[var_name] = value

        return None

    def visit_restore(self, _node):
        """Visit a RESTORE node"""
        # Reset data pointer to beginning
        self.data_index = 0
        return None

    # Subroutine implementations
    def visit_gosub(self, _node):
        """Visit a GOSUB node"""
        # GOSUB logic is handled in visit_block
        return None

    def visit_return(self, node):
        """Visit a RETURN node"""
        # Check if this is a function return with a value
        if node.nodes:
            # This is a function return
            self.return_value = self.visit(node.nodes[0])
            self.function_returned = True
        else:
            # This is a subroutine return
            self.sub_returned = True

        # RETURN logic is handled in visit_block
        return None

    def visit_sub(self, _node):
        """Visit a SUB node (definition)"""
        # SUB definitions are collected during the first pass
        # During execution, they do nothing
        return None

    def visit_function(self, _node):
        """Visit a FUNCTION node (definition)"""
        # FUNCTION definitions are collected during the first pass
        # During execution, they do nothing
        return None

    def visit_line_number(self, _node):
        """Visit a LINE_NUMBER node (label)"""
        # Line number labels do nothing during execution
        return None

    def visit_label(self, _node):
        """Visit a LABEL node"""
        # Labels do nothing during execution - they're just markers for GOTO/GOSUB
        return None

    def visit_randomize(self, node):
        """Visit a RANDOMIZE node"""
        if node.nodes:
            # RANDOMIZE with seed
            seed_value = self.visit(node.nodes[0])
            import random
            random.seed(seed_value.to_integer())
        else:
            # RANDOMIZE without seed - use current time
            import random
            import time
            random.seed(int(time.time()))

        return None

    def visit_sleep(self, node):
        """Visit a SLEEP node"""
        import time

        if node.nodes:
            # SLEEP with time value
            time_value = self.visit(node.nodes[0])
            sleep_seconds = time_value.to_single()
            if sleep_seconds < 0:
                sleep_seconds = 0  # Don't allow negative sleep times
            time.sleep(sleep_seconds)
        else:
            # SLEEP without time - pause until key press (traditional BASIC behavior)
            # For educational purposes, we'll sleep for 1 second as a default
            time.sleep(1)

        return None
