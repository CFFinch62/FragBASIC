"""
Main BASIC interpreter class that combines all functionality modules.
"""

from .interpreter_core import InterpreterCore
from .interpreter_expressions import InterpreterExpressions
from .interpreter_control import InterpreterControl
from .interpreter_functions import InterpreterFunctions
from .interpreter_io import InterpreterIO


class Interpreter(
    InterpreterCore,
    InterpreterExpressions,
    InterpreterControl,
    InterpreterFunctions,
    InterpreterIO
):
    """
    Complete BASIC interpreter that combines all functionality modules.

    This class inherits from multiple mixin classes to provide:
    - Core functionality (variables, arrays, basic operations)
    - Expression evaluation (arithmetic, comparison, logical)
    - Control flow (IF, FOR, WHILE, DO, SELECT CASE)
    - Built-in functions and user-defined SUB/FUNCTION
    - Input/Output and DATA statement handling

    I/O is fully pluggable via `input_func`/`output_func` (or the
    `set_io_functions` convenience method), so this class works
    identically whether it's driven from a real terminal (see
    fragbasic_core.cli), embedded directly in an IDE process, or
    fed from in-memory buffers in a test.
    """

    def __init__(self):
        """Initialize the interpreter"""
        super().__init__()

        # Additional initialization for control flow
        self.while_stack = []
        self.do_stack = []
        self.program_ended = False
        self.current_statement_index = 0

        # Function/subroutine return flags
        self.function_returned = False
        self.sub_returned = False

    def set_io_functions(self, input_func=None, output_func=None):
        """Set custom input/output functions"""
        if input_func:
            self.input_func = input_func
        if output_func:
            self.output_func = output_func

    def reset(self):
        """Reset the interpreter state"""
        # Clear all variables and arrays
        self.variables.clear()
        self.arrays.clear()

        # Clear DATA values and reset pointer
        self.data_values.clear()
        self.data_index = 0

        # Clear function and sub definitions
        self.functions.clear()
        self.subs.clear()
        self.labels.clear()

        # Clear stacks
        self.gosub_stack.clear()
        self.while_stack.clear()
        self.do_stack.clear()

        # Reset flags
        self.return_value = None
        self.program_ended = False
        self.current_statement_index = 0
        self.function_returned = False
        self.sub_returned = False
        self.current_line = None
        self._cancelled = False

    def get_variable_value(self, var_name):
        """Get the value of a variable (for debugging/testing)"""
        if var_name in self.variables:
            return self.variables[var_name].value
        return None

    def set_variable_value(self, var_name, value, var_type='SINGLE'):
        """Set the value of a variable (for debugging/testing)"""
        from .variable import Variable
        self.variables[var_name] = Variable(value, var_type)

    def get_array_value(self, array_name, *indices):
        """Get the value of an array element (for debugging/testing)"""
        if array_name not in self.arrays:
            return None

        array = self.arrays[array_name]
        try:
            if len(indices) == 1:
                return array[indices[0]].value
            elif len(indices) == 2:
                return array[indices[0]][indices[1]].value
            elif len(indices) == 3:
                return array[indices[0]][indices[1]][indices[2]].value
        except (IndexError, KeyError):
            return None

        return None

    def get_data_values(self):
        """Get all DATA values (for debugging/testing)"""
        return [var.value for var in self.data_values]

    def get_data_index(self):
        """Get current DATA index (for debugging/testing)"""
        return self.data_index
