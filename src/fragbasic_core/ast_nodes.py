from enum import Enum, auto

# Node Types
class NodeType(Enum):
    NULL = auto()
    NUMBER = auto()
    ADD = auto()
    SUBTRACT = auto()
    DIVIDE = auto()
    MULTIPLY = auto()
    INTEGER_DIV = auto()
    MOD = auto()
    POWER = auto()
    PLUS = auto()     # Unary plus
    MINUS = auto()    # Unary minus
    VAR_ASSIGN = auto()
    VAR_ACCESS = auto()
    AND = auto()
    OR = auto()
    NOT = auto()
    XOR = auto()
    EQV = auto()
    IMP = auto()
    GT = auto()
    LT = auto()
    GTE = auto()
    LTE = auto()
    EE = auto()
    NE = auto()
    IF = auto()
    IF_ELSE = auto()
    ELSEIF = auto()
    SELECT_CASE = auto()
    CASE = auto()
    FOR = auto()
    NEXT = auto()
    WHILE = auto()
    WEND = auto()
    DO_LOOP = auto()
    LOOP = auto()
    PRINT = auto()
    INPUT = auto()
    READ = auto()
    DATA = auto()
    RESTORE = auto()
    STRING = auto()
    LIST = auto()
    ARRAY = auto()
    BLOCK = auto()
    SUB = auto()
    FUNCTION = auto()
    ARGS = auto()
    ARG = auto()
    FUNCTION_CALL = auto()
    RETURN = auto()
    GOSUB = auto()
    CALL = auto()
    EXIT = auto()
    LABEL = auto()
    LINE_NUMBER = auto()
    DIM = auto()
    CONST = auto()
    RANDOMIZE = auto()
    SLEEP = auto()
    INKEY = auto()
    REM = auto()
    END = auto()
    END_IF = auto()
    END_SUB = auto()
    END_FUNCTION = auto()
    RANDOM = auto()

# Node class
class Node:
    def __init__(self, type_, value=None, name=None, nodes=None, line_num=None):
        self.type = type_
        self.value = value  # For numeric literals, etc.
        self.name = name    # For identifiers, etc.
        self.nodes = nodes if nodes is not None else []  # Child nodes
        self.line_num = line_num  # Source line number for error reporting

    def __repr__(self):
        result = f"Node({self.type}"

        if self.value is not None:
            result += f", value={self.value}"

        if self.name is not None:
            result += f", name='{self.name}'"

        if self.nodes:
            result += f", nodes={self.nodes}"

        if self.line_num is not None:
            result += f", line_num={self.line_num}"

        result += ")"
        return result
