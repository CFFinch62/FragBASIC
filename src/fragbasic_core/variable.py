"""
Variable class for the FragBASIC interpreter.
"""

class Variable:
    """
    Variable class to store different types of values in BASIC.

    In BASIC, variables can be:
    - Numeric (integers, singles, doubles)
    - Strings
    - Arrays
    """

    def __init__(self, value=None, var_type=None):
        self.value = value
        self.var_type = var_type  # Can be 'INTEGER', 'LONG', 'SINGLE', 'DOUBLE', 'STRING', 'ARRAY'

        # Determine the type if not explicitly specified
        if var_type is None:
            if value is None:
                self.var_type = 'SINGLE'
            elif isinstance(value, str):
                self.var_type = 'STRING'
            elif isinstance(value, int):
                self.var_type = 'INTEGER'
            elif isinstance(value, float):
                self.var_type = 'SINGLE'
            elif isinstance(value, list):
                self.var_type = 'ARRAY'

    def __str__(self):
        if self.value is None:
            return ""

        # Format numbers according to BASIC conventions
        if self.var_type in ['INTEGER', 'LONG']:
            return str(int(self.value))
        elif self.var_type in ['SINGLE', 'DOUBLE']:
            # If it's a whole number, display without decimal point
            if isinstance(self.value, float) and self.value.is_integer():
                return str(int(self.value))
            else:
                return str(self.value)
        else:
            return str(self.value)

    def __repr__(self):
        return f"Variable({self.value}, {self.var_type})"

    def is_string(self):
        return self.var_type == 'STRING'

    def is_numeric(self):
        return self.var_type in ['INTEGER', 'LONG', 'SINGLE', 'DOUBLE']

    def is_array(self):
        return self.var_type == 'ARRAY'

    def to_integer(self):
        """Convert variable to integer"""
        if self.is_numeric():
            return int(self.value)
        elif self.is_string():
            try:
                return int(float(self.value))
            except ValueError:
                return 0
        return 0

    def to_long(self):
        """Convert variable to long integer"""
        if self.is_numeric():
            return int(self.value)
        elif self.is_string():
            try:
                return int(float(self.value))
            except ValueError:
                return 0
        return 0

    def to_single(self):
        """Convert variable to single-precision float"""
        if self.is_numeric():
            return float(self.value)
        elif self.is_string():
            try:
                return float(self.value)
            except ValueError:
                return 0.0
        return 0.0

    def to_string(self):
        """Convert variable to string"""
        return str(self.value) if self.value is not None else ""
