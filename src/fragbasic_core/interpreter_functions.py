"""
Built-in functions and user-defined SUB/FUNCTION handling for the BASIC interpreter.
"""

import math
import random
import datetime

from .variable import Variable
from .platform_io import read_key_nonblocking
from .interpreter_core import ExitException
from .ast_nodes import Node, NodeType


class InterpreterFunctions:
    """
    Mixin class for function handling in the BASIC interpreter.
    """

    def visit_function_call(self, node):
        """Visit a FUNCTION_CALL node"""
        func_name = node.name.upper()
        args = [self.visit(arg_node) for arg_node in node.nodes]

        # Check for user-defined functions first
        if func_name in self.functions:
            return self.call_function(func_name, args)

        # Check for user-defined subroutines
        if func_name in self.subs:
            self.call_sub(func_name, args)
            return None

        # Built-in mathematical functions
        if func_name == 'ABS':
            if len(args) != 1:
                self.error(f"ABS expects 1 argument, got {len(args)}")
            arg = args[0]
            if arg.var_type == 'INTEGER':
                return Variable(abs(arg.to_integer()), 'INTEGER')
            else:
                return Variable(abs(arg.to_single()), 'SINGLE')

        elif func_name == 'SQR':
            if len(args) != 1:
                self.error(f"SQR expects 1 argument, got {len(args)}")
            return Variable(math.sqrt(args[0].to_single()), 'SINGLE')

        elif func_name == 'SIN':
            if len(args) != 1:
                self.error(f"SIN expects 1 argument, got {len(args)}")
            return Variable(math.sin(args[0].to_single()), 'SINGLE')

        elif func_name == 'COS':
            if len(args) != 1:
                self.error(f"COS expects 1 argument, got {len(args)}")
            return Variable(math.cos(args[0].to_single()), 'SINGLE')

        elif func_name == 'TAN':
            if len(args) != 1:
                self.error(f"TAN expects 1 argument, got {len(args)}")
            return Variable(math.tan(args[0].to_single()), 'SINGLE')

        elif func_name == 'ATN':
            if len(args) != 1:
                self.error(f"ATN expects 1 argument, got {len(args)}")
            return Variable(math.atan(args[0].to_single()), 'SINGLE')

        elif func_name == 'EXP':
            if len(args) != 1:
                self.error(f"EXP expects 1 argument, got {len(args)}")
            return Variable(math.exp(args[0].to_single()), 'SINGLE')

        elif func_name == 'LOG':
            if len(args) != 1:
                self.error(f"LOG expects 1 argument, got {len(args)}")
            return Variable(math.log(args[0].to_single()), 'SINGLE')

        elif func_name == 'INT':
            if len(args) != 1:
                self.error(f"INT expects 1 argument, got {len(args)}")
            return Variable(int(args[0].to_single()), 'INTEGER')

        elif func_name == 'FIX':
            if len(args) != 1:
                self.error(f"FIX expects 1 argument, got {len(args)}")
            return Variable(math.trunc(args[0].to_single()), 'INTEGER')

        elif func_name == 'SGN':
            if len(args) != 1:
                self.error(f"SGN expects 1 argument, got {len(args)}")
            val = args[0].to_single()
            if val > 0:
                return Variable(1, 'INTEGER')
            elif val < 0:
                return Variable(-1, 'INTEGER')
            else:
                return Variable(0, 'INTEGER')

        elif func_name == 'RND':
            return Variable(random.random(), 'SINGLE')

        # String functions
        elif func_name == 'LEN':
            if len(args) != 1:
                self.error(f"LEN expects 1 argument, got {len(args)}")
            return Variable(len(args[0].to_string()), 'INTEGER')

        elif func_name == 'LEFT$':
            if len(args) != 2:
                self.error(f"LEFT$ expects 2 arguments, got {len(args)}")
            string_val = args[0].to_string()
            length = args[1].to_integer()
            return Variable(string_val[:length], 'STRING')

        elif func_name == 'RIGHT$':
            if len(args) != 2:
                self.error(f"RIGHT$ expects 2 arguments, got {len(args)}")
            string_val = args[0].to_string()
            length = args[1].to_integer()
            return Variable(string_val[-length:] if length > 0 else "", 'STRING')

        elif func_name == 'MID$':
            if len(args) < 2 or len(args) > 3:
                self.error(f"MID$ expects 2 or 3 arguments, got {len(args)}")
            string_val = args[0].to_string()
            start = args[1].to_integer() - 1  # BASIC uses 1-based indexing
            if len(args) == 3:
                length = args[2].to_integer()
                return Variable(string_val[start:start+length], 'STRING')
            else:
                return Variable(string_val[start:], 'STRING')

        elif func_name == 'CHR$':
            if len(args) != 1:
                self.error(f"CHR$ expects 1 argument, got {len(args)}")
            ascii_val = args[0].to_integer()
            if 0 <= ascii_val <= 255:
                return Variable(chr(ascii_val), 'STRING')
            else:
                return Variable("", 'STRING')

        elif func_name == 'ASC':
            if len(args) != 1:
                self.error(f"ASC expects 1 argument, got {len(args)}")
            string_val = args[0].to_string()
            if len(string_val) > 0:
                return Variable(ord(string_val[0]), 'INTEGER')
            else:
                return Variable(0, 'INTEGER')

        elif func_name == 'STR$':
            if len(args) != 1:
                self.error(f"STR$ expects 1 argument, got {len(args)}")
            num_val = args[0].to_single()
            # STR$ adds a leading space for positive numbers
            if num_val >= 0:
                return Variable(" " + str(num_val), 'STRING')
            else:
                return Variable(str(num_val), 'STRING')

        elif func_name == 'VAL':
            if len(args) != 1:
                self.error(f"VAL expects 1 argument, got {len(args)}")
            string_val = args[0].to_string().strip()
            try:
                # Try to parse as number
                if '.' in string_val:
                    return Variable(float(string_val), 'SINGLE')
                else:
                    return Variable(int(string_val), 'INTEGER')
            except ValueError:
                return Variable(0, 'INTEGER')

        elif func_name == 'SPACE$':
            if len(args) != 1:
                self.error(f"SPACE$ expects 1 argument, got {len(args)}")
            count = args[0].to_integer()
            return Variable(" " * max(0, count), 'STRING')

        elif func_name == 'STRING$':
            if len(args) != 2:
                self.error(f"STRING$ expects 2 arguments, got {len(args)}")
            count = args[0].to_integer()
            char_arg = args[1]

            if count < 0:
                count = 0

            # Handle both string and numeric character arguments
            if char_arg.is_string():
                char_str = char_arg.to_string()
                if len(char_str) == 0:
                    char = ""
                else:
                    char = char_str[0]  # Use first character
            else:
                # Numeric argument - convert to ASCII character
                ascii_val = char_arg.to_integer()
                if 0 <= ascii_val <= 255:
                    char = chr(ascii_val)
                else:
                    char = ""

            return Variable(char * count, 'STRING')

        elif func_name == 'INSTR':
            if len(args) < 2 or len(args) > 3:
                self.error(f"INSTR expects 2 or 3 arguments, got {len(args)}")

            if len(args) == 2:
                # INSTR(string, substring)
                string_val = args[0].to_string()
                search_val = args[1].to_string()
                start_pos = 0
            else:
                # INSTR(start, string, substring)
                start_pos = args[0].to_integer() - 1  # BASIC uses 1-based indexing
                string_val = args[1].to_string()
                search_val = args[2].to_string()

                if start_pos < 0:
                    start_pos = 0

            # Find the substring
            try:
                position = string_val.find(search_val, start_pos)
                if position == -1:
                    return Variable(0, 'INTEGER')  # Not found
                else:
                    return Variable(position + 1, 'INTEGER')  # Convert to 1-based indexing
            except Exception:
                return Variable(0, 'INTEGER')

        elif func_name == 'UCASE$':
            if len(args) != 1:
                self.error(f"UCASE$ expects 1 argument, got {len(args)}")
            string_val = args[0].to_string()
            return Variable(string_val.upper(), 'STRING')

        elif func_name == 'LCASE$':
            if len(args) != 1:
                self.error(f"LCASE$ expects 1 argument, got {len(args)}")
            string_val = args[0].to_string()
            return Variable(string_val.lower(), 'STRING')

        elif func_name == 'LTRIM$':
            if len(args) != 1:
                self.error(f"LTRIM$ expects 1 argument, got {len(args)}")
            string_val = args[0].to_string()
            return Variable(string_val.lstrip(), 'STRING')

        elif func_name == 'RTRIM$':
            if len(args) != 1:
                self.error(f"RTRIM$ expects 1 argument, got {len(args)}")
            string_val = args[0].to_string()
            return Variable(string_val.rstrip(), 'STRING')

        # Type conversion functions
        elif func_name == 'CINT':
            if len(args) != 1:
                self.error(f"CINT expects 1 argument, got {len(args)}")
            # Convert to integer with rounding
            val = args[0].to_single()
            return Variable(int(round(val)), 'INTEGER')

        elif func_name == 'CLNG':
            if len(args) != 1:
                self.error(f"CLNG expects 1 argument, got {len(args)}")
            # Convert to long integer
            val = args[0].to_single()
            return Variable(int(val), 'INTEGER')

        elif func_name == 'CSNG':
            if len(args) != 1:
                self.error(f"CSNG expects 1 argument, got {len(args)}")
            # Convert to single precision float
            val = args[0].to_single()
            return Variable(val, 'SINGLE')

        elif func_name == 'CDBL':
            if len(args) != 1:
                self.error(f"CDBL expects 1 argument, got {len(args)}")
            # Convert to double precision float
            val = args[0].to_single()
            return Variable(val, 'DOUBLE')

        # System functions
        elif func_name == 'DATE$':
            if len(args) != 0:
                self.error(f"DATE$ expects 0 arguments, got {len(args)}")
            # Return current date in MM-DD-YYYY format
            current_date = datetime.datetime.now()
            date_str = current_date.strftime("%m-%d-%Y")
            return Variable(date_str, 'STRING')

        elif func_name == 'TIME$':
            if len(args) != 0:
                self.error(f"TIME$ expects 0 arguments, got {len(args)}")
            # Return current time in HH:MM:SS format
            current_time = datetime.datetime.now()
            time_str = current_time.strftime("%H:%M:%S")
            return Variable(time_str, 'STRING')

        elif func_name == 'TIMER':
            if len(args) != 0:
                self.error(f"TIMER expects 0 arguments, got {len(args)}")
            # Return seconds since midnight
            current_time = datetime.datetime.now()
            midnight = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
            seconds_since_midnight = (current_time - midnight).total_seconds()
            return Variable(seconds_since_midnight, 'SINGLE')

        elif func_name == 'INKEY$':
            if len(args) != 0:
                self.error(f"INKEY$ expects 0 arguments, got {len(args)}")
            # Best-effort non-blocking single-key read; see platform_io.py
            # for the platform-specific behavior and limitations.
            return Variable(read_key_nonblocking(), 'STRING')

        else:
            self.error(f"Unknown function: {func_name}")

    def visit_call(self, node):
        """Visit a CALL node (explicit `CALL Sub(args)` statement)"""
        name = node.name.upper()
        args = [self.visit(arg_node) for arg_node in node.nodes]

        if name in self.subs:
            self.call_sub(name, args)
        elif name in self.functions:
            self.call_function(name, args)
        else:
            self.error(f"SUB {node.name} not defined")

        return None

    def call_sub(self, sub_name, args):
        """Call a SUB"""
        if sub_name not in self.subs:
            self.error(f"SUB {sub_name} not defined")

        sub_node = self.subs[sub_name]

        # Check parameter count
        expected_params = getattr(sub_node, 'params', [])
        if len(args) != len(expected_params):
            self.error(f"SUB {sub_name} expects {len(expected_params)} arguments, got {len(args)}")

        # Save current variable state
        saved_vars = self.variables.copy()

        # Set up parameters
        for i, param_name in enumerate(expected_params):
            self.variables[param_name] = args[i]

        # Execute SUB body. Routed through visit_block (the same executor
        # used for the top-level program and IF/CASE blocks) instead of a
        # bare per-statement Python loop, since FOR/WHILE/DO control flow
        # only works when driven by visit_block's index-based jump logic -
        # a plain `for stmt in body: self.visit(stmt)` can't loop back for
        # WHILE/WEND at all and crashes outright on a bare FOR (see
        # execute_for_loop's "should be handled by execute_for_loop" guard).
        self._proc_call_depth = getattr(self, '_proc_call_depth', 0) + 1
        # A RETURN from inside an active WHILE/DO loop breaks out of that
        # loop's visit_block before its WEND/LOOP ever runs, so the loop's
        # entry never gets popped off the (shared, global) while_stack/
        # do_stack - remember the depth now and truncate back to it below,
        # or a stale entry corrupts whatever loop resumes after this call.
        saved_while_depth = len(getattr(self, 'while_stack', []))
        saved_do_depth = len(getattr(self, 'do_stack', []))
        try:
            body_block = Node(NodeType.BLOCK, nodes=getattr(sub_node, 'body', []))
            try:
                self.visit(body_block)
            except ExitException as exit_ex:
                if exit_ex.exit_type != 'SUB':
                    raise
            if getattr(self, 'sub_returned', False):
                self.sub_returned = False
        finally:
            self._proc_call_depth -= 1
            if hasattr(self, 'while_stack'):
                del self.while_stack[saved_while_depth:]
            if hasattr(self, 'do_stack'):
                del self.do_stack[saved_do_depth:]
            # Restore variable state
            self.variables = saved_vars

        return None

    def call_function(self, func_name, args):
        """Call a FUNCTION"""
        if func_name not in self.functions:
            self.error(f"FUNCTION {func_name} not defined")

        func_node = self.functions[func_name]

        # Check parameter count
        expected_params = getattr(func_node, 'params', [])
        if len(args) != len(expected_params):
            self.error(f"FUNCTION {func_name} expects {len(expected_params)} arguments, got {len(args)}")

        # Save current variable state
        saved_vars = self.variables.copy()
        saved_return_value = self.return_value

        # Start with no return value yet (NOT a dummy Variable(0,...) - that
        # used to be truthy-for-"is not None" and made visit_block's
        # early-break check fire after the very first body statement,
        # regardless of whether a RETURN had actually happened).
        self.return_value = None

        # Set up parameters
        for i, param_name in enumerate(expected_params):
            self.variables[param_name] = args[i]

        # Execute FUNCTION body - see call_sub for why this goes through
        # visit_block rather than a bare per-statement Python loop.
        explicit_return = False
        self._proc_call_depth = getattr(self, '_proc_call_depth', 0) + 1
        # See call_sub for why while_stack/do_stack need truncating back
        # after the call - an early RETURN can otherwise strand a loop
        # entry that never reached its WEND/LOOP.
        saved_while_depth = len(getattr(self, 'while_stack', []))
        saved_do_depth = len(getattr(self, 'do_stack', []))
        try:
            body_block = Node(NodeType.BLOCK, nodes=getattr(func_node, 'body', []))
            try:
                self.visit(body_block)
            except ExitException as exit_ex:
                if exit_ex.exit_type != 'FUNCTION':
                    raise
            if getattr(self, 'function_returned', False):
                self.function_returned = False
                explicit_return = True
        finally:
            self._proc_call_depth -= 1
            if hasattr(self, 'while_stack'):
                del self.while_stack[saved_while_depth:]
            if hasattr(self, 'do_stack'):
                del self.do_stack[saved_do_depth:]
            # An explicit `RETURN expr` always wins. Otherwise, fall back
            # to the classic BASIC idiom of assigning the function's own
            # name as its return value (e.g. `Square = n * n`), since that
            # assignment just landed in self.variables like any other var.
            result = self.return_value
            if not explicit_return:
                name_key = next((k for k in self.variables if k.upper() == func_name), None)
                if name_key is not None:
                    result = self.variables[name_key]
            # Restore variable state
            self.variables = saved_vars
            self.return_value = saved_return_value

        return result if result is not None else Variable(0, 'SINGLE')
