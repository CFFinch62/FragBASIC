"""Native functions for the NucleusVM-backed FragBASIC engine.

Every function here operates on NucleusVM's native unboxed values (plain
Python int/float/str/dict — see the Phase 1 value-representation audit in
NucleusVM's PROGRESS.md), replicating the *exact* runtime behavior the
tree-walking interpreter gets from `Variable`/`interpreter_expressions.py`/
`interpreter_functions.py` for the constructs `compiler.py` covers.

Three families of helper exist here for three different reasons — see
compiler.py's module docstring for which opcodes route through which:

1. Operators where Python's own operator already matches FragBASIC's rule
   (`-`, `*`, unary `-`, most comparisons' numeric path) skip this file
   entirely — the compiler emits NucleusVM's raw BINARY_*/UNARY_* opcodes.
2. Operators that are polymorphic or truncate differently than Python's own
   operator (`+`, `\\`, `MOD`, `^`, comparisons, `AND`/`OR`/`NOT`/`XOR`/
   `EQV`/`IMP`) get a thin wrapper here, called via CALL_NATIVE.
3. Everything host-effectful or requiring a lookup table (PRINT formatting,
   builtins, array allocation, sigil coercion) is native by NucleusVM's own
   design (CALL_NATIVE is the one generic escape hatch for that).
"""
import math
import random


def _is_str(x):
    return type(x) is str


def _to_string(x):
    """Mirrors Variable.to_string()."""
    if _is_str(x):
        return x
    return _basic_str(x)


def _to_single(x):
    """Mirrors Variable.to_single(): numeric passthrough-as-float, string
    parse-or-zero on failure."""
    if _is_str(x):
        try:
            return float(x)
        except ValueError:
            return 0.0
    return float(x)


def _to_integer(x):
    """Mirrors Variable.to_integer(): numeric truncate-toward-zero via
    int(), string parse-via-float-then-int, or zero on failure."""
    if _is_str(x):
        try:
            return int(float(x))
        except ValueError:
            return 0
    return int(x)


def _basic_str(x):
    """Mirrors Variable.__str__ for the int/float/str value space this
    compiler unboxes to — no separate var_type tag needed (see the Phase 1
    audit): a whole-number float still displays without a decimal point."""
    if _is_str(x):
        return x
    if type(x) is float:
        if x.is_integer():
            return str(int(x))
        return str(x)
    return str(x)  # int


# ---------------------------------------------------------------------
# Arithmetic operators Python's own operators don't already match exactly
# ---------------------------------------------------------------------

def _add(a, b):
    """+ is polymorphic: numeric add if neither operand is a string,
    otherwise coerce both to string and concatenate (visit_add)."""
    if _is_str(a) or _is_str(b):
        return _to_string(a) + _to_string(b)
    return a + b


def _idiv(a, b):
    """\\ (INTEGER_DIV): both operands truncated to int *before* dividing,
    even if either was a float (visit_integer_div) — Python's raw `//`
    does not pre-truncate, so this can't be a plain BINARY_IDIV."""
    ai, bi = _to_integer(a), _to_integer(b)
    if bi == 0:
        raise ZeroDivisionError("Division by zero")
    return ai // bi


def _mod(a, b):
    """MOD: same truncate-both-first rule as \\ (visit_mod)."""
    ai, bi = _to_integer(a), _to_integer(b)
    if bi == 0:
        raise ZeroDivisionError("Division by zero")
    return ai % bi


def _pow(a, b):
    """^ always produces a float result (visit_power forces to_single()
    on both operands) — Python's ** keeps int**int as int, so this can't
    be a plain BINARY_POW."""
    return _to_single(a) ** _to_single(b)


# ---------------------------------------------------------------------
# Comparisons and logical ops: classic-BASIC -1/0 INTEGER convention, not
# Python bool — printing a comparison result must show "-1"/"0", not
# "True"/"False" (visit_ee etc. / visit_and etc.)
# ---------------------------------------------------------------------

def _cmp_eq(a, b):
    if _is_str(a) or _is_str(b):
        return -1 if _to_string(a) == _to_string(b) else 0
    return -1 if _to_single(a) == _to_single(b) else 0


def _cmp_ne(a, b):
    if _is_str(a) or _is_str(b):
        return -1 if _to_string(a) != _to_string(b) else 0
    return -1 if _to_single(a) != _to_single(b) else 0


def _cmp_lt(a, b):
    if _is_str(a) or _is_str(b):
        return -1 if _to_string(a) < _to_string(b) else 0
    return -1 if _to_single(a) < _to_single(b) else 0


def _cmp_gt(a, b):
    if _is_str(a) or _is_str(b):
        return -1 if _to_string(a) > _to_string(b) else 0
    return -1 if _to_single(a) > _to_single(b) else 0


def _cmp_le(a, b):
    if _is_str(a) or _is_str(b):
        return -1 if _to_string(a) <= _to_string(b) else 0
    return -1 if _to_single(a) <= _to_single(b) else 0


def _cmp_ge(a, b):
    if _is_str(a) or _is_str(b):
        return -1 if _to_string(a) >= _to_string(b) else 0
    return -1 if _to_single(a) >= _to_single(b) else 0


def _logical_and(a, b):
    return -1 if (_to_single(a) != 0 and _to_single(b) != 0) else 0


def _logical_or(a, b):
    return -1 if (_to_single(a) != 0 or _to_single(b) != 0) else 0


def _logical_not(a):
    return -1 if _to_single(a) == 0 else 0


def _logical_xor(a, b):
    return -1 if ((_to_single(a) != 0) != (_to_single(b) != 0)) else 0


def _logical_eqv(a, b):
    return -1 if ((_to_single(a) != 0) == (_to_single(b) != 0)) else 0


def _logical_imp(a, b):
    return -1 if (not (_to_single(a) != 0) or (_to_single(b) != 0)) else 0


# ---------------------------------------------------------------------
# FOR loop exit test — step's sign decides which comparison direction
# applies (execute_for_loop), decided fresh at each check like the
# tree-walker does, since step is only evaluated once but its sign can't
# be baked into the compiled loop shape statically.
# ---------------------------------------------------------------------

def _for_should_exit(current, end, step):
    if step > 0:
        return -1 if current > end else 0
    return -1 if current < end else 0


# ---------------------------------------------------------------------
# Array allocation (see compiler.py's array-representation note): both DIM
# forms end up as plain dict[int, ...] (nested per dimension) at the point
# of actual element access — legacy DIM eagerly pre-fills every valid
# index; typed `DIM ... AS type` does not (confirmed empirically: an
# index read before ever written raises under the *current* interpreter
# too, via a bare KeyError on `self.arrays[name]`, so a mirrored empty
# dict here reproduces that "index out of range" failure the same way).
# ---------------------------------------------------------------------

def _alloc_array1(size, default):
    return {i: default for i in range(size + 1)}


def _alloc_array2(d0, d1, default):
    return {i: {j: default for j in range(d1 + 1)} for i in range(d0 + 1)}


def _alloc_array3(d0, d1, d2, default):
    return {
        i: {j: {k: default for k in range(d2 + 1)} for j in range(d1 + 1)}
        for i in range(d0 + 1)
    }


def _alloc_array1_empty():
    return {}


def _alloc_array2_empty():
    return {}


def _alloc_array3_empty():
    return {}


# ---------------------------------------------------------------------
# Builtins actually used across the Project Euler solution corpus (see
# dev-docs/PLAN.md's survey) — names match interpreter_functions.py's
# `elif func_name == '...'` branches exactly, values/edge-cases ported
# 1:1 from there.
# ---------------------------------------------------------------------

def _bi_abs(x):
    return abs(x)


def _bi_sqr(x):
    return math.sqrt(_to_single(x))


def _bi_log(x):
    return math.log(_to_single(x))


def _bi_int(x):
    return int(_to_single(x))


def _bi_rnd():
    return random.random()


def _bi_len(x):
    return len(_to_string(x))


def _bi_left(s, n):
    return _to_string(s)[: _to_integer(n)]


def _bi_right(s, n):
    n = _to_integer(n)
    sv = _to_string(s)
    return sv[-n:] if n > 0 else ""


def _bi_mid(s, start, length=None):
    sv = _to_string(s)
    start_i = _to_integer(start) - 1  # BASIC uses 1-based indexing
    if length is None:
        return sv[start_i:]
    return sv[start_i : start_i + _to_integer(length)]


def _bi_chr(x):
    v = _to_integer(x)
    return chr(v) if 0 <= v <= 255 else ""


def _bi_asc(s):
    sv = _to_string(s)
    return ord(sv[0]) if sv else 0


def _bi_str(x):
    # STR$ adds a leading space for non-negative numbers; always forces
    # float display even for an int argument (num_val = args[0].to_single())
    v = _to_single(x)
    return " " + str(v) if v >= 0 else str(v)


def _bi_val(s):
    sv = _to_string(s).strip()
    try:
        return float(sv) if "." in sv else int(sv)
    except ValueError:
        return 0


BUILTIN_ARITY = {
    "ABS": 1, "SQR": 1, "LOG": 1, "INT": 1, "RND": 0,
    "LEN": 1, "LEFT$": 2, "RIGHT$": 2, "MID$": None,
    "CHR$": 1, "ASC": 1, "STR$": 1, "VAL": 1,
}

_BUILTIN_FUNCS = {
    "ABS": _bi_abs, "SQR": _bi_sqr, "LOG": _bi_log, "INT": _bi_int,
    "RND": _bi_rnd, "LEN": _bi_len, "LEFT$": _bi_left, "RIGHT$": _bi_right,
    "MID$": _bi_mid, "CHR$": _bi_chr, "ASC": _bi_asc, "STR$": _bi_str,
    "VAL": _bi_val,
}


def _make_print(output_func):
    def _print(seps, *values):
        text = ""
        for i, v in enumerate(values):
            text += _basic_str(v)
            if i < len(seps):
                sep = seps[i]
                if sep == "SEMI":
                    text += " "
                elif sep == "COMMA":
                    pos = len(text) % 14
                    text += " " * (14 - pos if pos > 0 else 0)
        if not seps or seps[-1] != "SEMI":
            text += "\n"
        output_func(text)
    return _print


def build_natives(output_func):
    """Build the CALL_NATIVE table for one VM run. `output_func` matches
    the same signature `Interpreter.set_io_functions` expects (a single
    `text` argument)."""
    natives = {
        "_add": _add,
        "_idiv": _idiv,
        "_mod": _mod,
        "_pow": _pow,
        "_eq": _cmp_eq, "_ne": _cmp_ne, "_lt": _cmp_lt, "_gt": _cmp_gt,
        "_le": _cmp_le, "_ge": _cmp_ge,
        "_and": _logical_and, "_or": _logical_or, "_not": _logical_not,
        "_xor": _logical_xor, "_eqv": _logical_eqv, "_imp": _logical_imp,
        "_for_should_exit": _for_should_exit,
        "_toint": _to_integer, "_tofloat": _to_single, "_tostr": _to_string,
        "_alloc_array1": _alloc_array1, "_alloc_array2": _alloc_array2,
        "_alloc_array3": _alloc_array3,
        "_alloc_array1_empty": _alloc_array1_empty,
        "_alloc_array2_empty": _alloc_array2_empty,
        "_alloc_array3_empty": _alloc_array3_empty,
        "_print": _make_print(output_func),
        "_print_blank": lambda: output_func("\n"),
    }
    natives.update(_BUILTIN_FUNCS)
    return natives
