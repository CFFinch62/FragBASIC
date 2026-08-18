"""Per-SUB/FUNCTION local symbol resolution.

FragBASIC has no real lexical scoping: a SUB/FUNCTION body's "locals" are
its params plus *every* scalar name it ever assigns anywhere in its body —
via a plain assignment or as a FOR loop's induction variable — whether or
not that name is ever `DIM`'d. This isn't a design choice, it's what the
tree-walking interpreter's whole-dict save/restore around every call
actually produces: `saved_vars = self.variables.copy()` before the call,
`self.variables = saved_vars` after (`interpreter_functions.py`'s
`call_sub`/`call_function`) discards *any* mutation made during the call,
DIM'd or not — a bare `i = lo` inside a SUB is just as call-scoped as a
`DIM`'d one, since its write gets rolled back the same way. (Confirmed by
a real bug this module used to have: treating only `DIM`'d names as local
made `pe87.bas`'s recursive `merge_sort` SUB's undeclared loop counters
`i`/`j`/`k`/`mid`/`m` compile as VM globals, so nested recursive calls
clobbered each other's counters instead of getting independent copies —
caught by comparing VM output against the tree-walker on a scaled-down
copy of that exact solution.)

This module does the one-time scan that save/restore stands in for: params
+ every scalar name assigned in the body (+ the function's own name, for
the classic `FuncName = expr` return idiom) become real VM locals
(LOAD_FAST/STORE_FAST); every other name — read but never assigned in this
body, i.e. a genuine reference to an enclosing global — compiles to
LOAD_GLOBAL/STORE_GLOBAL. The one deliberate divergence from the original:
if a body reads a same-named global *before* ever assigning it within that
same call (unusual — no real BASIC idiom relies on this), the tree-walker
would see the global's current value, while this compiler's local slot
starts from the sigil-based default instead. Not exercised by any of the
100 Project Euler solutions surveyed for this slice.

Arrays are never part of this: `self.arrays` is never part of FragBASIC's
save/restore scoping either (confirmed empirically — see compiler.py), so
array names always compile as VM globals regardless of which body `DIM`s
them; this module only tracks scalar names.

Variable names are case-sensitive in FragBASIC (only SUB/FUNCTION/builtin
*names* are matched case-insensitively) — every name here keeps its
original source casing, unlike compiler.py's SUB/FUNCTION-name lookups.
"""
from ..ast_nodes import NodeType


class FunctionScope:
    """The local-name set for one compiled SUB/FUNCTION body."""

    def __init__(self, own_name, params):
        self.params = list(params)
        self.own_name = own_name
        self.locals = set(self.params)
        self.locals.add(own_name)

    def is_local(self, name):
        return name in self.locals

    def add_local(self, name):
        self.locals.add(name)


def resolve_locals(node):
    """Build a FunctionScope for a SUB/FUNCTION AST node (must carry
    `.params`/`.body`, set by parser_control.py's sub_stmt/function_stmt)."""
    scope = FunctionScope(node.name, node.params)
    _scan_body(node.body, scope)
    return scope


def _scan_body(statements, scope):
    """Walk every node reachable via `.nodes` (this naturally covers
    IF/IF_ELSE/ELSEIF nesting, DIM's BLOCK-wrapper for a multi-declaration
    statement, and FOR/WHILE bodies, which are flat siblings in the same
    statement list rather than nested — see compiler.py's structural-
    pairing note, so the top-level walk already reaches them)."""

    def walk(node):
        if node.type == NodeType.DIM:
            scope.add_local(node.name)
        elif node.type == NodeType.VAR_ASSIGN:
            if len(node.nodes) <= 1:  # scalar assign, not an array element
                scope.add_local(node.name)
        elif node.type == NodeType.FOR:
            scope.add_local(node.nodes[0].name)  # induction variable
        elif node.type == NodeType.READ:
            for target in node.nodes:
                if not target.nodes:  # scalar target, not an array element
                    scope.add_local(target.name)
        for child in node.nodes:
            walk(child)

    for stmt in statements:
        walk(stmt)
