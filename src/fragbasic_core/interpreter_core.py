"""
Core interpreter functionality - main class, visit dispatch, and basic setup.
"""

import math
import random
import datetime

from .ast_nodes import NodeType
from .tokens import TokenType
from .variable import Variable
from .errors import BasicRuntimeError, ExecutionCancelled
from .platform_io import read_key_nonblocking


class ExitException(Exception):
    """Exception used to implement EXIT statements"""
    def __init__(self, exit_type):
        self.exit_type = exit_type
        super().__init__(f"EXIT {exit_type}")


class InterpreterCore:
    """
    Core interpreter functionality for BASIC language.
    Handles initialization, visit dispatch, and basic operations.
    """

    def __init__(self):
        # Variable storage
        self.variables = {}

        # DATA statement storage
        self.data_values = []
        self.data_index = 0

        # Array storage
        self.arrays = {}

        # Static typing support
        self.declared_variables = {}
        self.declared_arrays = {}
        self.constants = {}

        # Function and sub definitions
        self.functions = {}
        self.subs = {}

        # Label mapping for GOSUB
        self.labels = {}

        # Return value storage
        self.return_value = None

        # Gosub return stack
        self.gosub_stack = []

        # I/O functions (can be overridden by the caller, e.g. a CLI or IDE)
        self.input_func = input
        self.output_func = print

        # Source line of the statement/expression currently being executed,
        # used to attach line numbers to runtime errors without threading
        # line_num through every raise site individually.
        self.current_line = None

        # Cooperative cancellation flag, checked between statements/loop
        # iterations so a caller (CLI SIGINT/SIGTERM handler, --timeout,
        # or an embedding IDE's Stop button) can interrupt a running
        # program without needing OS-level process termination.
        self._cancelled = False

    def request_cancel(self):
        """Request that execution stop at the next cooperative checkpoint."""
        self._cancelled = True

    def check_cancelled(self):
        """Raise ExecutionCancelled if a cancellation has been requested."""
        if self._cancelled:
            raise ExecutionCancelled()

    def error(self, message):
        """Raise a BasicRuntimeError tagged with the current source line."""
        raise BasicRuntimeError(message, self.current_line)

    def interpret(self, ast_node):
        """Interpret the AST and execute the program"""
        # First pass: collect all function/sub definitions and labels
        self.collect_definitions(ast_node)

        # Second pass: execute the program
        result = self.visit(ast_node)
        return result

    def collect_definitions(self, node):
        """Collect function/sub definitions, labels, and DATA statements"""
        if node.type == NodeType.BLOCK:
            for child_node in node.nodes:
                self.collect_definitions(child_node)
        elif node.type == NodeType.SUB:
            # Store SUB definition. Keyed uppercase because every call site
            # (visit_function_call, visit_call, visit_var_access) uppercases
            # the name it looks up with, to make SUB/FUNCTION names
            # case-insensitive like the rest of the language.
            self.subs[node.name.upper()] = node
        elif node.type == NodeType.FUNCTION:
            # Store FUNCTION definition (see case-folding note above)
            self.functions[node.name.upper()] = node
        elif node.type == NodeType.LABEL:
            # Store label
            self.labels[node.name] = node
        elif node.type == NodeType.DATA:
            # Collect DATA values during first pass
            for value_node in node.nodes:
                # Evaluate the value and add to data pool
                if value_node.type == NodeType.NUMBER:
                    self.data_values.append(Variable(value_node.value))
                elif value_node.type == NodeType.STRING:
                    self.data_values.append(Variable(value_node.name, 'STRING'))
                else:
                    # For more complex expressions, evaluate them
                    try:
                        value = self.visit(value_node)
                        self.data_values.append(value)
                    except Exception:
                        # If evaluation fails, treat as string
                        self.data_values.append(Variable(str(value_node.name), 'STRING'))

    def visit(self, node):
        """Visit a node and execute its operation"""
        if getattr(node, 'line_num', None) is not None:
            self.current_line = node.line_num
        method_name = f'visit_{node.type.name.lower()}'
        method = getattr(self, method_name, self.no_visit_method)
        return method(node)

    def no_visit_method(self, node):
        """Called when no visit method exists for a node type"""
        self.error(f"No visit_{node.type.name.lower()} method defined")

    # Basic visit methods

    def visit_null(self, _node):
        """Visit a NULL node (does nothing)"""
        return None

    def visit_number(self, node):
        """Visit a NUMBER node"""
        # Determine if this should be an integer or float
        if isinstance(node.value, float) and node.value.is_integer():
            return Variable(int(node.value), 'INTEGER')
        else:
            return Variable(node.value)

    def visit_string(self, node):
        """Visit a STRING node"""
        return Variable(node.name, 'STRING')

    def visit_var_access(self, node):
        """Visit a VAR_ACCESS node (variable reference)"""
        var_name = node.name

        # Check if this is array/call access. Node normalizes nodes=None
        # to [], so a zero-arg call like f() (nodes=[], value='CALL') is
        # indistinguishable from a bare name with no parens (nodes=[],
        # value=None) by nodes alone - the parser tags real parens via
        # value='CALL', which is what must gate this branch instead.
        if node.nodes or node.value == 'CALL':
            # The parser can't tell array access (arr(1)) apart from a
            # user-defined FUNCTION/SUB call written without the CALL
            # keyword (Square(5)) - both parse as VAR_ACCESS with args as
            # "indices". Resolve the ambiguity here, once definitions have
            # been collected: prefer a matching FUNCTION/SUB, else array.
            upper_name = var_name.upper()
            if upper_name in self.functions:
                args = [self.visit(arg_node) for arg_node in node.nodes]
                return self.call_function(upper_name, args)
            if upper_name in self.subs:
                args = [self.visit(arg_node) for arg_node in node.nodes]
                self.call_sub(upper_name, args)
                return None
            return self.visit_array(node)

        # Check for special system functions that can be called without parentheses
        if var_name.upper() == 'DATE$':
            current_date = datetime.datetime.now()
            date_str = current_date.strftime("%m-%d-%Y")
            return Variable(date_str, 'STRING')
        elif var_name.upper() == 'TIME$':
            current_time = datetime.datetime.now()
            time_str = current_time.strftime("%H:%M:%S")
            return Variable(time_str, 'STRING')
        elif var_name.upper() == 'TIMER':
            current_time = datetime.datetime.now()
            midnight = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
            seconds_since_midnight = (current_time - midnight).total_seconds()
            return Variable(seconds_since_midnight, 'SINGLE')
        elif var_name.upper() == 'INKEY$':
            # Best-effort non-blocking single-key read; see platform_io.py
            # for the platform-specific behavior and limitations.
            return Variable(read_key_nonblocking(), 'STRING')

        # Regular variable access
        # Check if variable exists
        if var_name not in self.variables:
            # Auto-initialize variables to 0 or empty string
            if var_name.endswith('$'):
                self.variables[var_name] = Variable("", 'STRING')
            elif var_name.endswith('%'):
                self.variables[var_name] = Variable(0, 'INTEGER')
            elif var_name.endswith('!'):
                self.variables[var_name] = Variable(0.0, 'SINGLE')
            elif var_name.endswith('#'):
                self.variables[var_name] = Variable(0.0, 'DOUBLE')
            else:
                self.variables[var_name] = Variable(0.0, 'SINGLE')

        return self.variables[var_name]

    def visit_var_assign(self, node):
        """Visit a VAR_ASSIGN node (variable assignment)"""
        var_name = node.name

        # Check if this is an array assignment (has indices)
        if len(node.nodes) > 1:
            # This is array assignment: arr(1) = value
            return self.visit_array_assign(node)

        # Regular variable assignment
        value = self.visit(node.nodes[0])

        # Handle type conversion based on variable name suffix
        if var_name.endswith('$') and not value.is_string():
            value = Variable(value.to_string(), 'STRING')
        elif var_name.endswith('%') and not value.var_type == 'INTEGER':
            value = Variable(value.to_integer(), 'INTEGER')
        elif var_name.endswith('!') and not value.var_type == 'SINGLE':
            value = Variable(value.to_single(), 'SINGLE')
        elif var_name.endswith('#') and not value.var_type == 'DOUBLE':
            value = Variable(float(value.to_single()), 'DOUBLE')

        self.variables[var_name] = value
        return value

    def visit_array(self, node):
        """Visit an ARRAY node (array access)"""
        array_name = node.name
        indices = [self.visit(index_node).to_integer() for index_node in node.nodes]

        # Check if array exists
        if array_name not in self.arrays:
            self.error(f"Array {array_name} not defined")

        array = self.arrays[array_name]

        # Check bounds and access element
        try:
            if len(indices) == 1:
                return array[indices[0]]
            elif len(indices) == 2:
                return array[indices[0]][indices[1]]
            elif len(indices) == 3:
                return array[indices[0]][indices[1]][indices[2]]
            else:
                self.error(f"Too many dimensions for array {array_name}")
        except (IndexError, KeyError):
            self.error(f"Array index out of bounds for {array_name}")

    def visit_array_assign(self, node):
        """Visit an array assignment"""
        array_name = node.name
        value = self.visit(node.nodes[0])
        indices = [self.visit(index_node).to_integer() for index_node in node.nodes[1:]]

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

        return value

    def visit_dim(self, node):
        """Visit a DIM node (variable or array declaration with static typing)"""
        var_name = node.name
        var_type = getattr(node, 'var_type', None)
        is_array = getattr(node, 'is_array', False)

        if not var_type:
            # Old-style array declaration without AS type
            dimensions = [self.visit(dim_node).to_integer() for dim_node in node.nodes]

            # Create multi-dimensional array with default SINGLE type
            if len(dimensions) == 1:
                # 1D array
                array = {}
                for i in range(dimensions[0] + 1):  # BASIC arrays are 0-based but size is inclusive
                    array[i] = Variable(0, 'SINGLE')
            elif len(dimensions) == 2:
                # 2D array
                array = {}
                for i in range(dimensions[0] + 1):
                    array[i] = {}
                    for j in range(dimensions[1] + 1):
                        array[i][j] = Variable(0, 'SINGLE')
            elif len(dimensions) == 3:
                # 3D array
                array = {}
                for i in range(dimensions[0] + 1):
                    array[i] = {}
                    for j in range(dimensions[1] + 1):
                        array[i][j] = {}
                        for k in range(dimensions[2] + 1):
                            array[i][j][k] = Variable(0, 'SINGLE')
            else:
                self.error(f"Too many dimensions for array {var_name}")

            self.arrays[var_name] = array
            return None

        # New-style declaration with AS type
        if is_array:
            # Array declaration: DIM array(size) AS type
            dimensions = [self.visit(dim_node).to_integer() for dim_node in node.nodes]

            # Check if array is already declared
            if var_name in self.declared_arrays:
                self.error(f"Array {var_name} is already declared")

            # Register array declaration
            self.declared_arrays[var_name] = var_type

            # Default is 0-based indexing for FragBASIC (educational BASIC)
            base = 0

            # Create array storage
            total_size = 1
            for dim in dimensions:
                total_size *= (dim + 1)  # Add 1 because DIM arr(4) means indices 0 to 4

            # Initialize array elements based on declared type
            if var_type == 'STRING':
                data = [Variable("", 'STRING') for _ in range(total_size)]
            elif var_type == 'INTEGER':
                data = [Variable(0, 'INTEGER') for _ in range(total_size)]
            elif var_type == 'LONG':
                data = [Variable(0, 'LONG') for _ in range(total_size)]
            elif var_type == 'SINGLE':
                data = [Variable(0.0, 'SINGLE') for _ in range(total_size)]
            elif var_type == 'DOUBLE':
                data = [Variable(0.0, 'DOUBLE') for _ in range(total_size)]
            else:
                self.error(f"Invalid array type: {var_type}")

            # Store array information
            self.arrays[var_name] = {
                'dimensions': dimensions,
                'base': base,
                'data': data,
                'var_type': var_type
            }
        else:
            # Variable declaration: DIM variable AS type
            # Check if variable is already declared
            if var_name in self.declared_variables:
                self.error(f"Variable {var_name} is already declared")

            # Register variable declaration
            self.declared_variables[var_name] = var_type

            # Initialize variable based on declared type
            if var_type == 'STRING':
                self.variables[var_name] = Variable("", 'STRING')
            elif var_type == 'INTEGER':
                self.variables[var_name] = Variable(0, 'INTEGER')
            elif var_type == 'LONG':
                self.variables[var_name] = Variable(0, 'LONG')
            elif var_type == 'SINGLE':
                self.variables[var_name] = Variable(0.0, 'SINGLE')
            elif var_type == 'DOUBLE':
                self.variables[var_name] = Variable(0.0, 'DOUBLE')
            else:
                self.error(f"Invalid variable type: {var_type}")

        return None

    def visit_rem(self, _node):
        """Visit a REM node (comment)"""
        # REM statements are comments and don't affect execution
        return None
