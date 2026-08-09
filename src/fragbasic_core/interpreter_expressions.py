"""
Expression evaluation for the BASIC interpreter.
Handles arithmetic, comparison, and logical operations.
"""

from .variable import Variable


class InterpreterExpressions:
    """
    Mixin class for expression evaluation in the BASIC interpreter.
    """

    # Arithmetic operations

    def visit_add(self, node):
        """Visit an ADD node (+ operator)"""
        left = self.visit(node.nodes[0])
        right = self.visit(node.nodes[1])

        # Handle string concatenation
        if left.is_string() or right.is_string():
            return Variable(left.to_string() + right.to_string(), 'STRING')

        # Numeric addition
        if left.var_type == 'INTEGER' and right.var_type == 'INTEGER':
            return Variable(left.to_integer() + right.to_integer(), 'INTEGER')
        else:
            return Variable(left.to_single() + right.to_single(), 'SINGLE')

    def visit_subtract(self, node):
        """Visit a SUBTRACT node (- operator)"""
        left = self.visit(node.nodes[0])
        right = self.visit(node.nodes[1])

        if left.var_type == 'INTEGER' and right.var_type == 'INTEGER':
            return Variable(left.to_integer() - right.to_integer(), 'INTEGER')
        else:
            return Variable(left.to_single() - right.to_single(), 'SINGLE')

    def visit_multiply(self, node):
        """Visit a MULTIPLY node (* operator)"""
        left = self.visit(node.nodes[0])
        right = self.visit(node.nodes[1])

        if left.var_type == 'INTEGER' and right.var_type == 'INTEGER':
            return Variable(left.to_integer() * right.to_integer(), 'INTEGER')
        else:
            return Variable(left.to_single() * right.to_single(), 'SINGLE')

    def visit_divide(self, node):
        """Visit a DIVIDE node (/ operator)"""
        left = self.visit(node.nodes[0])
        right = self.visit(node.nodes[1])

        right_val = right.to_single()
        if right_val == 0:
            self.error("Division by zero")

        return Variable(left.to_single() / right_val, 'SINGLE')

    def visit_integer_div(self, node):
        """Visit an INTEGER_DIV node (\\ operator)"""
        left = self.visit(node.nodes[0])
        right = self.visit(node.nodes[1])

        right_val = right.to_integer()
        if right_val == 0:
            self.error("Division by zero")

        return Variable(left.to_integer() // right_val, 'INTEGER')

    def visit_mod(self, node):
        """Visit a MOD node (MOD operator)"""
        left = self.visit(node.nodes[0])
        right = self.visit(node.nodes[1])

        right_val = right.to_integer()
        if right_val == 0:
            self.error("Division by zero")

        return Variable(left.to_integer() % right_val, 'INTEGER')

    def visit_power(self, node):
        """Visit a POWER node (^ operator)"""
        left = self.visit(node.nodes[0])
        right = self.visit(node.nodes[1])

        return Variable(left.to_single() ** right.to_single(), 'SINGLE')

    def visit_plus(self, node):
        """Visit a unary PLUS node (+value)"""
        operand = self.visit(node.nodes[0])
        return operand  # Unary plus doesn't change the value

    def visit_minus(self, node):
        """Visit a unary MINUS node (-value)"""
        operand = self.visit(node.nodes[0])

        if operand.var_type == 'INTEGER':
            return Variable(-operand.to_integer(), 'INTEGER')
        else:
            return Variable(-operand.to_single(), 'SINGLE')

    # Comparison operations

    def visit_ee(self, node):
        """Visit an EE node (= comparison)"""
        left = self.visit(node.nodes[0])
        right = self.visit(node.nodes[1])

        # String comparison
        if left.is_string() or right.is_string():
            result = left.to_string() == right.to_string()
        else:
            # Numeric comparison
            result = left.to_single() == right.to_single()

        return Variable(-1 if result else 0, 'INTEGER')

    def visit_ne(self, node):
        """Visit an NE node (<> comparison)"""
        left = self.visit(node.nodes[0])
        right = self.visit(node.nodes[1])

        # String comparison
        if left.is_string() or right.is_string():
            result = left.to_string() != right.to_string()
        else:
            # Numeric comparison
            result = left.to_single() != right.to_single()

        return Variable(-1 if result else 0, 'INTEGER')

    def visit_lt(self, node):
        """Visit an LT node (< comparison)"""
        left = self.visit(node.nodes[0])
        right = self.visit(node.nodes[1])

        # String comparison
        if left.is_string() or right.is_string():
            result = left.to_string() < right.to_string()
        else:
            # Numeric comparison
            result = left.to_single() < right.to_single()

        return Variable(-1 if result else 0, 'INTEGER')

    def visit_gt(self, node):
        """Visit a GT node (> comparison)"""
        left = self.visit(node.nodes[0])
        right = self.visit(node.nodes[1])

        # String comparison
        if left.is_string() or right.is_string():
            result = left.to_string() > right.to_string()
        else:
            # Numeric comparison
            result = left.to_single() > right.to_single()

        return Variable(-1 if result else 0, 'INTEGER')

    def visit_lte(self, node):
        """Visit an LTE node (<= comparison)"""
        left = self.visit(node.nodes[0])
        right = self.visit(node.nodes[1])

        # String comparison
        if left.is_string() or right.is_string():
            result = left.to_string() <= right.to_string()
        else:
            # Numeric comparison
            result = left.to_single() <= right.to_single()

        return Variable(-1 if result else 0, 'INTEGER')

    def visit_gte(self, node):
        """Visit a GTE node (>= comparison)"""
        left = self.visit(node.nodes[0])
        right = self.visit(node.nodes[1])

        # String comparison
        if left.is_string() or right.is_string():
            result = left.to_string() >= right.to_string()
        else:
            # Numeric comparison
            result = left.to_single() >= right.to_single()

        return Variable(-1 if result else 0, 'INTEGER')

    # Logical operations

    def visit_and(self, node):
        """Visit an AND node"""
        left = self.visit(node.nodes[0])
        right = self.visit(node.nodes[1])

        left_val = left.to_single() != 0
        right_val = right.to_single() != 0

        return Variable(-1 if (left_val and right_val) else 0, 'INTEGER')

    def visit_or(self, node):
        """Visit an OR node"""
        left = self.visit(node.nodes[0])
        right = self.visit(node.nodes[1])

        left_val = left.to_single() != 0
        right_val = right.to_single() != 0

        return Variable(-1 if (left_val or right_val) else 0, 'INTEGER')

    def visit_not(self, node):
        """Visit a NOT node"""
        operand = self.visit(node.nodes[0])
        result = operand.to_single() == 0

        return Variable(-1 if result else 0, 'INTEGER')

    def visit_xor(self, node):
        """Visit an XOR node"""
        left = self.visit(node.nodes[0])
        right = self.visit(node.nodes[1])

        left_val = left.to_single() != 0
        right_val = right.to_single() != 0

        return Variable(-1 if (left_val != right_val) else 0, 'INTEGER')

    def visit_eqv(self, node):
        """Visit an EQV node (equivalence)"""
        left = self.visit(node.nodes[0])
        right = self.visit(node.nodes[1])

        left_val = left.to_single() != 0
        right_val = right.to_single() != 0

        return Variable(-1 if (left_val == right_val) else 0, 'INTEGER')

    def visit_imp(self, node):
        """Visit an IMP node (implication)"""
        left = self.visit(node.nodes[0])
        right = self.visit(node.nodes[1])

        left_val = left.to_single() != 0
        right_val = right.to_single() != 0

        # Implication: A IMP B is equivalent to (NOT A) OR B
        return Variable(-1 if (not left_val or right_val) else 0, 'INTEGER')
