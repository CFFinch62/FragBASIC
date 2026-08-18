"""Tests for the NucleusVM-backed compiler (`fragbasic_core.vm_compiler`) —
the first vertical slice described in NucleusVM's dev-docs/PLAN.md.

Mirrors test_interpreter.py's per-feature style, but the real correctness
contract for this engine is "matches the tree-walker's stdout byte for
byte" (see dev-docs/PLAN.md's verification strategy), so most tests here
run the *same* source through both engines and compare captured output,
rather than asserting a hardcoded expected value independently.
"""
from fragbasic_core import run_source


def run_vm(code, inputs=None):
    output = []
    run_source(code, output_func=output.append, engine="vm")
    return "".join(output)


def run_tree(code):
    output = []
    run_source(code, output_func=output.append, engine="tree")
    return "".join(output)


def run_both(code):
    """Returns (tree_output, vm_output) for the same source."""
    return run_tree(code), run_vm(code)


def test_arithmetic_promotion_matches_tree_walker():
    code = """
    DIM a AS INTEGER
    DIM b AS INTEGER
    a = 7
    b = 2
    PRINT a + b
    PRINT a - b
    PRINT a * b
    PRINT a / b
    PRINT a \\ b
    PRINT a MOD b
    PRINT a ^ b
    """
    tree_out, vm_out = run_both(code)
    assert vm_out == tree_out
    # ^ always produces a float result, but a whole-number float still
    # displays without a decimal point (Variable.__str__'s rule) — "49",
    # not "49.0".
    assert vm_out.splitlines() == ["9", "5", "14", "3.5", "3", "1", "49"]


def test_string_concat_vs_numeric_add():
    code = 'a$ = "foo" + "bar"\nPRINT a$\nPRINT 2 + 3'
    tree_out, vm_out = run_both(code)
    assert vm_out == tree_out
    assert vm_out.splitlines() == ["foobar", "5"]


def test_integer_div_and_mod_truncate_float_operands_first():
    # \ and MOD must truncate BOTH operands to int *before* dividing, even
    # when they're floats — this is the one case Python's raw //, % would
    # silently diverge on (see natives.py's _idiv/_mod).
    code = "PRINT 7.9 \\ 2.9\nPRINT 7.9 MOD 2.9"
    tree_out, vm_out = run_both(code)
    assert vm_out == tree_out
    assert vm_out.splitlines() == ["3", "1"]


def test_power_always_produces_float():
    tree_out, vm_out = run_both("PRINT 2 ^ 3\nPRINT 2 ^ 0.5")
    assert vm_out == tree_out
    lines = vm_out.splitlines()
    assert lines[0] == "8"  # whole-number float still prints without a decimal
    assert lines[1].startswith("1.41421")


def test_comparisons_and_logical_ops_use_minus_one_zero_convention():
    code = """
    PRINT 5 > 3
    PRINT 5 < 3
    PRINT (5 > 3) AND (2 > 1)
    PRINT (5 > 3) AND (2 < 1)
    PRINT NOT (5 > 3)
    """
    tree_out, vm_out = run_both(code)
    assert vm_out == tree_out
    assert vm_out.splitlines() == ["-1", "0", "-1", "0", "0"]


def test_if_elseif_else_chain():
    code = """
    FOR i = 1 TO 5
        IF i = 1 THEN
            PRINT "one"
        ELSEIF i = 2 THEN
            PRINT "two"
        ELSE
            PRINT "other"
        END IF
    NEXT i
    """
    tree_out, vm_out = run_both(code)
    assert vm_out == tree_out
    assert vm_out.splitlines() == ["one", "two", "other", "other", "other"]


def test_for_loop_with_negative_step():
    tree_out, vm_out = run_both("FOR i = 5 TO 1 STEP -1\nPRINT i\nNEXT i")
    assert vm_out == tree_out
    assert vm_out.splitlines() == ["5", "4", "3", "2", "1"]


def test_while_wend():
    code = "i = 0\nWHILE i < 3\nPRINT i\ni = i + 1\nWEND"
    tree_out, vm_out = run_both(code)
    assert vm_out == tree_out
    assert vm_out.splitlines() == ["0", "1", "2"]


def test_1d_array_legacy_dim():
    code = """
    DIM arr(5)
    FOR i = 0 TO 5
        arr(i) = i * i
    NEXT i
    FOR i = 0 TO 5
        PRINT arr(i)
    NEXT i
    """
    tree_out, vm_out = run_both(code)
    assert vm_out == tree_out
    assert vm_out.splitlines() == ["0", "1", "4", "9", "16", "25"]


def test_2d_and_3d_arrays():
    code = """
    DIM grid(2, 2)
    FOR i = 0 TO 2
        FOR j = 0 TO 2
            grid(i, j) = i * 10 + j
        NEXT j
    NEXT i
    PRINT grid(2, 1)

    DIM cube(1, 1, 1)
    cube(1, 1, 1) = 42
    PRINT cube(1, 1, 1)
    PRINT cube(0, 0, 0)
    """
    tree_out, vm_out = run_both(code)
    assert vm_out == tree_out
    assert vm_out.splitlines() == ["21", "42", "0"]


def test_typed_dim_array():
    # Typed `DIM ... AS type` arrays are NOT pre-filled (confirmed against
    # the tree-walker — see compiler.py's array note): reading an index
    # before it's ever written is a real error under *both* engines, not
    # a VM-only quirk, so this only exercises writes followed by reads of
    # those same indices.
    code = "DIM sieve(10) AS INTEGER\nsieve(5) = 1\nsieve(3) = 0\nPRINT sieve(5)\nPRINT sieve(3)"
    tree_out, vm_out = run_both(code)
    assert vm_out == tree_out
    assert vm_out.splitlines() == ["1", "0"]


def test_sub_call_and_array_shared_globally():
    # A SUB reading an array it was never passed as a param — arrays are
    # never part of FragBASIC's call-scoping (see compiler.py's array note).
    code = """
    DIM nums(3)
    nums(0) = 10
    nums(1) = 20
    nums(2) = 30
    nums(3) = 40

    SUB show(idx)
        PRINT nums(idx)
    END SUB

    FOR i = 0 TO 3
        CALL show(i)
    NEXT i
    """
    tree_out, vm_out = run_both(code)
    assert vm_out == tree_out
    assert vm_out.splitlines() == ["10", "20", "30", "40"]


def test_function_implicit_name_return_idiom():
    code = "FUNCTION Square(n)\nSquare = n * n\nEND FUNCTION\nPRINT Square(6)"
    tree_out, vm_out = run_both(code)
    assert vm_out == tree_out
    assert vm_out.strip() == "36"


def test_function_explicit_return():
    code = "FUNCTION Square(n)\nRETURN n * n\nEND FUNCTION\nPRINT Square(7)"
    tree_out, vm_out = run_both(code)
    assert vm_out == tree_out
    assert vm_out.strip() == "49"


def test_recursive_function_matches_tree_walker():
    code = "FUNCTION fact(n)\nIF n <= 1 THEN\nfact = 1\nELSE\nfact = n * fact(n - 1)\nEND IF\nEND FUNCTION\nPRINT fact(10)"
    tree_out, vm_out = run_both(code)
    assert vm_out == tree_out
    assert vm_out.strip() == "3628800"


def test_recursion_depth_not_bounded_by_python_stack():
    # The tree-walker errors out around depth ~80-100 (Python's own
    # recursion limit — see dev-docs/PLAN.md's research notes); the VM's
    # CALL/RETURN uses its own explicit frame chain, not Python's call
    # stack, so this concrete depth is unreachable under the tree-walker
    # but must succeed under the VM.
    code = (
        "FUNCTION countdown(n)\n"
        "IF n <= 0 THEN\n"
        "countdown = 0\n"
        "ELSE\n"
        "countdown = countdown(n - 1)\n"
        "END IF\n"
        "END FUNCTION\n"
        "PRINT countdown(3000)"
    )
    vm_out = run_vm(code)
    assert vm_out.strip() == "0"


def test_sub_local_not_dimmed_does_not_leak_or_collide_across_recursive_calls():
    # Regression test for the symbols.py bug this slice caught: an
    # undeclared (not DIM'd) scalar assigned inside a recursive SUB must
    # still be call-local, or nested recursive calls clobber each other's
    # copy of it (see symbols.py's module docstring for the full story).
    code = """
    DIM out(10)
    DIM cnt(0)
    cnt(0) = 0

    SUB fill(lo, hi)
        IF lo <= hi THEN
            mid = (lo + hi) \\ 2
            out(cnt(0)) = mid
            cnt(0) = cnt(0) + 1
            CALL fill(lo, mid - 1)
            CALL fill(mid + 1, hi)
        END IF
    END SUB

    CALL fill(0, 6)
    FOR i = 0 TO 6
        PRINT out(i)
    NEXT i
    """
    tree_out, vm_out = run_both(code)
    assert vm_out == tree_out


def test_sigil_coercion_on_assignment():
    code = 'x% = 3.9\nPRINT x%\ny$ = 42\nPRINT y$\nz! = 5\nPRINT z!'
    tree_out, vm_out = run_both(code)
    assert vm_out == tree_out
    assert vm_out.splitlines() == ["3", "42", "5"]


def test_print_separators():
    code = 'PRINT "a"; "b"\nPRINT 1, 2'
    tree_out, vm_out = run_both(code)
    assert vm_out == tree_out


def test_builtins_len_mid_chr_asc_val_int_sqr_abs():
    code = """
    PRINT LEN("hello")
    PRINT MID$("hello world", 7, 5)
    PRINT CHR$(65)
    PRINT ASC("A")
    PRINT VAL("42")
    PRINT INT(3.9)
    PRINT SQR(16)
    PRINT ABS(-5)
    """
    tree_out, vm_out = run_both(code)
    assert vm_out == tree_out
    # SQR always returns a float, but a whole-number float still prints
    # without a decimal point — "4", not "4.0".
    assert vm_out.splitlines() == ["5", "world", "A", "65", "42", "3", "4", "5"]


def test_unsupported_construct_raises_not_implemented():
    import pytest

    with pytest.raises(NotImplementedError):
        run_vm("DO\nPRINT 1\nLOOP UNTIL 1 = 1")


def test_fix_sgn_string_builtins():
    code = """
    PRINT FIX(3.9)
    PRINT FIX(-3.9)
    PRINT SGN(5)
    PRINT SGN(-5)
    PRINT SGN(0)
    PRINT STRING$(5, "x")
    PRINT STRING$(3, 65)
    """
    tree_out, vm_out = run_both(code)
    assert vm_out == tree_out
    assert vm_out.splitlines() == ["3", "-3", "1", "-1", "0", "xxxxx", "AAA"]


def test_data_read_restore():
    code = """
    DATA 10, 20, "hello", 30
    DIM a AS INTEGER
    DIM b AS INTEGER
    READ a, b
    PRINT a
    PRINT b
    READ c$
    PRINT c$
    RESTORE
    READ d
    PRINT d
    """
    tree_out, vm_out = run_both(code)
    assert vm_out == tree_out
    assert vm_out.splitlines() == ["10", "20", "hello", "10"]


def test_data_read_negative_numbers_and_array_target():
    code = """
    DATA -5, 15, -25
    DIM arr(2)
    FOR i = 0 TO 2
        READ arr(i)
    NEXT i
    FOR i = 0 TO 2
        PRINT arr(i)
    NEXT i
    """
    tree_out, vm_out = run_both(code)
    assert vm_out == tree_out
    assert vm_out.splitlines() == ["-5", "15", "-25"]


def test_read_out_of_data_raises():
    import pytest

    with pytest.raises(Exception):
        run_vm("DATA 1\nREAD a\nREAD b")
