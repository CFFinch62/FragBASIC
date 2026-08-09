import pytest

from fragbasic_core.lexer import Lexer
from fragbasic_core.parser import Parser
from fragbasic_core.interpreter import Interpreter
from fragbasic_core.errors import BasicRuntimeError, ExecutionCancelled


def run(code, inputs=None):
    """Run BASIC source and return (interpreter, captured_output_string)."""
    tokens = Lexer(code).generate_tokens()
    ast = Parser(tokens).parse()

    interpreter = Interpreter()
    output = []
    interpreter.output_func = lambda s: output.append(s)

    if inputs is not None:
        remaining = list(inputs)
        def fake_input():
            return remaining.pop(0)
        interpreter.input_func = fake_input

    interpreter.interpret(ast)
    return interpreter, "".join(output)


def test_arithmetic_and_variable_assignment():
    interpreter, _ = run("x = 2 + 3 * 4")
    assert interpreter.get_variable_value("x") == 14


def test_string_concatenation():
    interpreter, _ = run('a$ = "foo" + "bar"')
    assert interpreter.get_variable_value("a$") == "foobar"


def test_for_loop_accumulates():
    interpreter, _ = run("total = 0\nFOR i = 1 TO 5\ntotal = total + i\nNEXT i")
    assert interpreter.get_variable_value("total") == 15.0


def test_if_else_branches():
    interpreter, _ = run('IF 1 = 2 THEN\nresult = 1\nELSE\nresult = 2\nEND IF')
    assert interpreter.get_variable_value("result") == 2


def test_print_output():
    _, out = run('PRINT "hello"')
    assert out == "hello\n"


def test_print_semicolon_suppresses_newline():
    _, out = run('PRINT "a";\nPRINT "b"')
    assert out == "a b\n"


def test_array_dim_and_access():
    interpreter, _ = run("DIM arr(3) AS INTEGER\narr(2) = 42")
    assert interpreter.get_array_value("arr", 2) == 42


def test_data_read():
    interpreter, _ = run("DATA 1, 2, 3\nREAD a\nREAD b\nREAD c")
    assert interpreter.get_variable_value("a") == 1.0
    assert interpreter.get_variable_value("b") == 2.0
    assert interpreter.get_variable_value("c") == 3.0


def test_division_by_zero_raises_runtime_error():
    with pytest.raises(BasicRuntimeError):
        run("x = 1 / 0")


def test_input_statement_reads_values():
    interpreter, out = run('INPUT "Name: "; n$', inputs=["Ada"])
    assert interpreter.get_variable_value("n$") == "Ada"
    assert out == "Name: "


def test_sub_call():
    code = """
SUB Greet(name$)
    PRINT "Hello, " + name$
END SUB

CALL Greet("World")
"""
    _, out = run(code)
    assert out == "Hello, World\n"


def test_exit_sub_stops_the_sub_body():
    code = """
SUB Test()
    PRINT "before"
    EXIT SUB
    PRINT "after"
END SUB

CALL Test()
PRINT "done"
"""
    _, out = run(code)
    assert out == "before\ndone\n"


def test_exit_function_keeps_value_set_so_far():
    code = """
FUNCTION F(n)
    F = n
    IF n > 0 THEN EXIT FUNCTION
    F = -1
END FUNCTION

result = F(5)
"""
    interpreter, _ = run(code)
    assert interpreter.get_variable_value("result") == 5.0


def test_function_call_returns_value():
    code = """
FUNCTION Square(n)
    Square = n * n
END FUNCTION

result = Square(5)
"""
    interpreter, _ = run(code)
    assert interpreter.get_variable_value("result") == 25.0


def test_cancellation_stops_infinite_loop():
    tokens = Lexer("WHILE 1 = 1\nWEND").generate_tokens()
    ast = Parser(tokens).parse()

    interpreter = Interpreter()
    interpreter.request_cancel()

    with pytest.raises(ExecutionCancelled):
        interpreter.interpret(ast)


def test_runtime_error_carries_line_number():
    tokens = Lexer("x = 1\ny = 1 / 0").generate_tokens()
    ast = Parser(tokens).parse()

    interpreter = Interpreter()
    with pytest.raises(BasicRuntimeError) as exc_info:
        interpreter.interpret(ast)
    assert exc_info.value.line_num == 2
