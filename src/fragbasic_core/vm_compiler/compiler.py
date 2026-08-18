"""AST -> NucleusVM bytecode compiler for FragBASIC — first vertical slice.

Covers: top-level program compilation with a SUB/FUNCTION forward-reference
pass; scalars (global at top level, real resolved locals inside SUB/
FUNCTION bodies via `symbols.py`); arithmetic/comparison/logical operators;
IF/IF_ELSE/ELSEIF; FOR/NEXT (with STEP); WHILE/WEND; DIM (scalar and 1D/2D/
3D array, both legacy and typed forms); PRINT; SUB/FUNCTION/CALL via the
VM's real CALL/RETURN frame chain; DATA/READ/RESTORE (a compile-time-folded
constant pool plus a runtime cursor — see `_compile_read`); and the 15
builtins the Project Euler solution corpus actually uses (see `natives.py`
and NucleusVM's dev-docs/PLAN.md for the corpus survey behind that list).

Deliberately NOT covered this slice (raises NotImplementedError with a
pointer back to the plan): GOSUB/RETURN/labels (needs new shared NucleusVM
opcodes — a separate checkpoint), SELECT CASE, DO/LOOP, INPUT, and any
builtin outside the 15. None of these appear in any of the 100 existing
FragBASIC Project Euler solutions (confirmed by corpus survey, not
assumption — DATA/READ, originally in this same deferred list, was added
after the survey showed 17 solutions actually use it).

Value representation: unboxed native Python int/float/str/dict (arrays),
no separate type tag — see NucleusVM's PROGRESS.md for the audit that
established `type(x) is int`/`is float` already carries what
`Variable.var_type` encoded. Three deliberate exceptions to "just use
NucleusVM's raw opcode," each routed through `natives.py` via CALL_NATIVE
instead:

- `+` is polymorphic (numeric add vs. string concat, decided by *runtime*
  operand type) — not a plain BINARY_ADD.
- `\\` (INTEGER_DIV) and `MOD` truncate *both* operands to int before
  dividing, even if either is a float — Python's raw `//`/`%` don't
  pre-truncate.
- `^` (POWER) always produces a float result regardless of operand types —
  Python's `**` keeps `int ** int` as `int`.
- Comparisons and `AND`/`OR`/`NOT`/`XOR`/`EQV`/`IMP` return classic-BASIC
  `-1`/`0` (as an INTEGER), not Python `True`/`False` — printing a
  comparison result must show "-1", not "True". NucleusVM's own
  JUMP_IF_FALSE/JUMP_IF_TRUE truthiness (`bool(value)`) still works
  correctly on -1/0 without any extra wrapping, since `bool(-1)` and
  `bool(0)` already match FragBASIC's own `to_single() != 0` condition
  check.

Everything else (`-`, `*`, `/`, unary `-`) already gets Python's own
operator semantics, which match FragBASIC's promotion rules exactly (int op
int stays int, anything else promotes to float) — compiled straight to
NucleusVM's raw BINARY_*/UNARY_* opcodes with zero extra logic.

Auto-vivification: reading a scalar before it's ever been assigned
auto-initializes it to a sigil-based default in the tree-walker
(`interpreter_core.py`'s `visit_var_access`) — NucleusVM's LOAD_GLOBAL/
LOAD_FAST instead *raise* on a never-stored name, so this compiler emits an
explicit default-init prelude (top-level: every scalar name found anywhere
in top-level code; per-SUB/FUNCTION: every local-slot name not bound by a
param) before any real code runs, using the same sigil-based default rule.
Arrays never auto-vivify (`visit_array` hard-errors on an undeclared
array), so no array prelude is needed.
"""
from __future__ import annotations

from nucleus_vm import Chunk, Op

from ..ast_nodes import NodeType
from ..tokens import TokenType
from . import natives
from .symbols import FunctionScope, resolve_locals


_BINARY_NATIVE = {
    NodeType.ADD: "_add",
    NodeType.INTEGER_DIV: "_idiv",
    NodeType.MOD: "_mod",
    NodeType.POWER: "_pow",
    NodeType.EE: "_eq",
    NodeType.NE: "_ne",
    NodeType.LT: "_lt",
    NodeType.GT: "_gt",
    NodeType.LTE: "_le",
    NodeType.GTE: "_ge",
    NodeType.AND: "_and",
    NodeType.OR: "_or",
    NodeType.XOR: "_xor",
    NodeType.EQV: "_eqv",
    NodeType.IMP: "_imp",
}

_BINARY_OPCODE = {
    NodeType.SUBTRACT: Op.BINARY_SUB,
    NodeType.MULTIPLY: Op.BINARY_MUL,
    NodeType.DIVIDE: Op.BINARY_DIV,
}

_UNSUPPORTED_HINT = (
    "is not yet supported by the NucleusVM compiler slice — see "
    "dev-docs/PLAN.md's Phase 1 deferred list in the NucleusVM repo"
)

# DATA/READ globals: a flat, compile-time-collected constant pool plus a
# runtime cursor into it. NUL-prefixed like FOR's/array-set's synthetic
# temps — guaranteed to never collide with a real BASIC identifier.
_DATA_POOL_NAME = "\0data_pool"
_DATA_INDEX_NAME = "\0data_index"


class VMCompiler:
    def __init__(self):
        self.chunk = Chunk("fragbasic_program")
        self.subs: dict[str, object] = {}
        self.functions: dict[str, object] = {}
        self._sub_addr: dict[str, int] = {}
        self._func_addr: dict[str, int] = {}
        self._pending_calls: list[tuple[int, str, int]] = []
        self._synth_counter = 0
        self._scope: FunctionScope | None = None
        self._in_function = False
        self.data_pool: list = []

    # ------------------------------------------------------------------
    # Top level
    # ------------------------------------------------------------------

    def compile_program(self, ast_root) -> Chunk:
        statements = _flatten_root(ast_root)
        self._collect_definitions(statements)
        self._emit_data_pool_prelude()
        self._emit_top_level_prelude(statements)
        self._compile_block(statements)
        self.chunk.emit(Op.HALT)

        for name, node in self.subs.items():
            self._compile_procedure(name, node, is_function=False)
        for name, node in self.functions.items():
            self._compile_procedure(name, node, is_function=True)

        self._resolve_pending_calls()
        return self.chunk

    def _collect_definitions(self, statements):
        # Mirrors interpreter_core.py's collect_definitions exactly,
        # including its scope: only the top-level flat statement list
        # (recursing into nested BLOCK, e.g. a multi-declaration DIM) is
        # scanned — SUB/FUNCTION bodies are never reached this way (they
        # live in `.body`, not `.nodes`), so DATA inside one is invisible
        # to READ, same as the tree-walker.
        for node in statements:
            if node.type == NodeType.BLOCK:
                self._collect_definitions(node.nodes)
            elif node.type == NodeType.SUB:
                self.subs[node.name.upper()] = node
            elif node.type == NodeType.FUNCTION:
                self.functions[node.name.upper()] = node
            elif node.type == NodeType.DATA:
                for value_node in node.nodes:
                    self.data_pool.append(_fold_data_value(value_node))

    def _emit_data_pool_prelude(self):
        self.chunk.emit(Op.LOAD_CONST, self.chunk.add_constant(tuple(self.data_pool)))
        self.chunk.emit(Op.STORE_GLOBAL, _DATA_POOL_NAME)
        self.chunk.emit(Op.LOAD_CONST, self.chunk.add_constant(0))
        self.chunk.emit(Op.STORE_GLOBAL, _DATA_INDEX_NAME)

    def _emit_top_level_prelude(self, statements):
        for name in sorted(_collect_scalar_names(statements)):
            self._emit_sigil_default(name)
            self.chunk.emit(Op.STORE_GLOBAL, name)

    # ------------------------------------------------------------------
    # SUB/FUNCTION bodies
    # ------------------------------------------------------------------

    def _compile_procedure(self, name, node, is_function):
        scope = resolve_locals(node)
        prev_scope, prev_in_function = self._scope, self._in_function
        self._scope, self._in_function = scope, is_function

        addr = self.chunk.here()
        if is_function:
            self._func_addr[name] = addr
        else:
            self._sub_addr[name] = addr

        # Unpack positional call-frame slots (bound by the VM's own CALL
        # handler to integer keys 0..argcount-1) into name-keyed slots, so
        # every other local can be addressed uniformly by name afterward.
        for i, pname in enumerate(scope.params):
            self.chunk.emit(Op.LOAD_FAST, i)
            self.chunk.emit(Op.STORE_FAST, pname)

        # Default-init every other local (sigil-based, same rule as the
        # top-level prelude), including the implicit own-name return slot.
        for lname in sorted(scope.locals):
            if lname in scope.params:
                continue
            self._emit_sigil_default(lname)
            self.chunk.emit(Op.STORE_FAST, lname)

        self._compile_block(node.body)

        # Implicit return: control fell off the end without an explicit
        # RETURN. A FUNCTION falls back to its own-name slot (the classic
        # `FuncName = expr` idiom); a SUB's return value is never used by
        # its caller (CALL always pops+discards it) so any placeholder works.
        if is_function:
            self.chunk.emit(Op.LOAD_FAST, scope.own_name)
        else:
            self.chunk.emit(Op.LOAD_CONST, self.chunk.add_constant(0.0))
        self.chunk.emit(Op.RETURN)

        self._scope, self._in_function = prev_scope, prev_in_function

    # ------------------------------------------------------------------
    # Block / statement-list compilation (index-driven — FOR/NEXT and
    # WHILE/WEND are flat sibling markers in the AST, not nested, so
    # pairing them is done here exactly like the tree-walker's own
    # find_matching_next/find_matching_wend, just once at compile time)
    # ------------------------------------------------------------------

    def _compile_block(self, statements):
        i = 0
        n = len(statements)
        while i < n:
            stmt = statements[i]
            t = stmt.type
            if t == NodeType.FOR:
                i = self._compile_for(statements, i)
                continue
            if t == NodeType.WHILE:
                i = self._compile_while(statements, i)
                continue
            if t in (
                NodeType.NEXT, NodeType.WEND, NodeType.SUB, NodeType.FUNCTION,
                NodeType.LABEL, NodeType.LINE_NUMBER, NodeType.NULL, NodeType.REM,
            ):
                i += 1
                continue
            if t == NodeType.BLOCK:
                # DIM wraps even a single declaration in a BLOCK (see
                # parser_statements.py's dim_stmt) — not a real nested
                # scope, just a comma-separated list; unwrap inline.
                self._compile_block(stmt.nodes)
                i += 1
                continue
            self._compile_stmt(stmt)
            i += 1

    def _find_matching_next(self, statements, for_index):
        nest = 0
        for i in range(for_index + 1, len(statements)):
            t = statements[i].type
            if t == NodeType.FOR:
                nest += 1
            elif t == NodeType.NEXT:
                if nest == 0:
                    return i
                nest -= 1
        raise NotImplementedError("FOR without matching NEXT")

    def _find_matching_wend(self, statements, while_index):
        nest = 0
        for i in range(while_index + 1, len(statements)):
            t = statements[i].type
            if t == NodeType.WHILE:
                nest += 1
            elif t == NodeType.WEND:
                if nest == 0:
                    return i
                nest -= 1
        raise NotImplementedError("WHILE without matching WEND")

    def _compile_for(self, statements, i):
        for_node = statements[i]
        next_index = self._find_matching_next(statements, i)
        var_node, start_expr, end_expr = for_node.nodes[0], for_node.nodes[1], for_node.nodes[2]
        step_expr = for_node.nodes[3] if len(for_node.nodes) > 3 else None
        var_name = var_node.name

        end_tmp = self._synthetic_name("for_end")
        step_tmp = self._synthetic_name("for_step")

        # FOR's induction variable is always stored as a raw float,
        # bypassing sigil coercion entirely (execute_for_loop writes
        # `Variable(current_val, 'SINGLE')` directly, not through
        # visit_var_assign's suffix-coercion path) — use the raw store,
        # never the sigil-coercing one.
        self._compile_expr(start_expr)
        self.chunk.emit(Op.CALL_NATIVE, ("_tofloat", 1))
        self._emit_store_raw(var_name)

        self._compile_expr(end_expr)
        self.chunk.emit(Op.CALL_NATIVE, ("_tofloat", 1))
        self.chunk.emit(Op.STORE_GLOBAL, end_tmp)

        if step_expr is not None:
            self._compile_expr(step_expr)
            self.chunk.emit(Op.CALL_NATIVE, ("_tofloat", 1))
        else:
            self.chunk.emit(Op.LOAD_CONST, self.chunk.add_constant(1.0))
        self.chunk.emit(Op.STORE_GLOBAL, step_tmp)

        loop_start = self.chunk.here()
        self._emit_load_raw(var_name)
        self.chunk.emit(Op.LOAD_GLOBAL, end_tmp)
        self.chunk.emit(Op.LOAD_GLOBAL, step_tmp)
        self.chunk.emit(Op.CALL_NATIVE, ("_for_should_exit", 3))
        exit_jump = self.chunk.emit(Op.JUMP_IF_TRUE, None)

        body = statements[i + 1 : next_index]
        self._compile_block(body)

        self._emit_load_raw(var_name)
        self.chunk.emit(Op.LOAD_GLOBAL, step_tmp)
        self.chunk.emit(Op.BINARY_ADD)
        self._emit_store_raw(var_name)
        self.chunk.emit(Op.JUMP, loop_start)

        self.chunk.patch_arg(exit_jump, self.chunk.here())
        return next_index + 1

    def _compile_while(self, statements, i):
        while_node = statements[i]
        wend_index = self._find_matching_wend(statements, i)
        condition_expr = while_node.nodes[0]

        loop_start = self.chunk.here()
        self._compile_expr(condition_expr)
        exit_jump = self.chunk.emit(Op.JUMP_IF_FALSE, None)

        body = statements[i + 1 : wend_index]
        self._compile_block(body)
        self.chunk.emit(Op.JUMP, loop_start)

        self.chunk.patch_arg(exit_jump, self.chunk.here())
        return wend_index + 1

    # ------------------------------------------------------------------
    # Statements
    # ------------------------------------------------------------------

    def _compile_stmt(self, node):
        t = node.type

        if t == NodeType.FUNCTION_CALL:
            # A bare statement call (`MySub`, or a builtin called purely
            # for effect) — the pushed result is unused.
            self._compile_function_call(node)
            self.chunk.emit(Op.POP_TOP)
            return

        if t == NodeType.VAR_ACCESS:
            self._compile_var_access(node)
            self.chunk.emit(Op.POP_TOP)
            return

        if t == NodeType.VAR_ASSIGN:
            self._compile_var_assign(node)
            return
        if t == NodeType.DIM:
            self._compile_dim(node)
            return
        if t == NodeType.PRINT:
            self._compile_print(node)
            return
        if t == NodeType.IF:
            self._compile_if(node)
            return
        if t == NodeType.IF_ELSE:
            self._compile_if_else(node)
            return
        if t == NodeType.CALL:
            self._compile_call_stmt(node)
            return
        if t == NodeType.RETURN:
            self._compile_return(node)
            return
        if t == NodeType.END:
            self.chunk.emit(Op.HALT)
            return
        if t == NodeType.DATA:
            return  # already folded into self.data_pool at compile time
        if t == NodeType.READ:
            self._compile_read(node)
            return
        if t == NodeType.RESTORE:
            self._compile_restore(node)
            return

        raise NotImplementedError(f"FragBASIC statement {t.name} {_UNSUPPORTED_HINT}")

    def _compile_read(self, node):
        for var_node in node.nodes:
            self.chunk.emit(Op.LOAD_GLOBAL, _DATA_POOL_NAME)
            self.chunk.emit(Op.LOAD_GLOBAL, _DATA_INDEX_NAME)
            self.chunk.emit(Op.CALL_NATIVE, ("_read_next", 2))

            name = var_node.name
            if name.endswith("$"):
                self.chunk.emit(Op.CALL_NATIVE, ("_tostr", 1))
            elif name.endswith("%"):
                self.chunk.emit(Op.CALL_NATIVE, ("_toint", 1))
            else:
                # '!', '#', and no-sigil all default to SINGLE (visit_read's
                # else branch also uses to_single()).
                self.chunk.emit(Op.CALL_NATIVE, ("_tofloat", 1))

            if var_node.nodes:
                # Array target — same value-before-indices evaluation
                # order as _compile_array_set.
                tmp = self._synthetic_name("read_val")
                self.chunk.emit(Op.STORE_GLOBAL, tmp)
                self.chunk.emit(Op.LOAD_GLOBAL, var_node.name)
                for idx_node in var_node.nodes[:-1]:
                    self._compile_expr(idx_node)
                    self.chunk.emit(Op.CALL_NATIVE, ("_toint", 1))
                    self.chunk.emit(Op.INDEX_GET)
                self._compile_expr(var_node.nodes[-1])
                self.chunk.emit(Op.CALL_NATIVE, ("_toint", 1))
                self.chunk.emit(Op.LOAD_GLOBAL, tmp)
                self.chunk.emit(Op.INDEX_SET)
            else:
                self._emit_store_raw(name)

            self.chunk.emit(Op.LOAD_GLOBAL, _DATA_INDEX_NAME)
            self.chunk.emit(Op.LOAD_CONST, self.chunk.add_constant(1))
            self.chunk.emit(Op.BINARY_ADD)
            self.chunk.emit(Op.STORE_GLOBAL, _DATA_INDEX_NAME)

    def _compile_restore(self, node):
        self.chunk.emit(Op.LOAD_CONST, self.chunk.add_constant(0))
        self.chunk.emit(Op.STORE_GLOBAL, _DATA_INDEX_NAME)

    def _compile_var_assign(self, node):
        if len(node.nodes) > 1:
            self._compile_array_set(node)
            return
        self._compile_expr(node.nodes[0])
        name = node.name
        if name.endswith("$"):
            self.chunk.emit(Op.CALL_NATIVE, ("_tostr", 1))
        elif name.endswith("%"):
            self.chunk.emit(Op.CALL_NATIVE, ("_toint", 1))
        elif name.endswith("!") or name.endswith("#"):
            self.chunk.emit(Op.CALL_NATIVE, ("_tofloat", 1))
        self._emit_store_raw(name)

    def _compile_array_set(self, node):
        value_expr = node.nodes[0]
        idx_nodes = node.nodes[1:]
        # Original evaluates the value expression before the indices
        # (visit_array_assign) — stash it so our index-first traversal
        # below preserves that evaluation order for any side effects.
        self._compile_expr(value_expr)
        tmp = self._synthetic_name("val")
        self.chunk.emit(Op.STORE_GLOBAL, tmp)

        self.chunk.emit(Op.LOAD_GLOBAL, node.name)
        for idx_node in idx_nodes[:-1]:
            self._compile_expr(idx_node)
            self.chunk.emit(Op.CALL_NATIVE, ("_toint", 1))
            self.chunk.emit(Op.INDEX_GET)
        self._compile_expr(idx_nodes[-1])
        self.chunk.emit(Op.CALL_NATIVE, ("_toint", 1))
        self.chunk.emit(Op.LOAD_GLOBAL, tmp)
        self.chunk.emit(Op.INDEX_SET)

    def _compile_dim(self, node):
        var_type = getattr(node, "var_type", None)
        is_array = getattr(node, "is_array", False)

        if not is_array:
            default = _dim_scalar_default(var_type)
            self.chunk.emit(Op.LOAD_CONST, self.chunk.add_constant(default))
            self._emit_store_raw(node.name)
            return

        dims = node.nodes
        ndims = len(dims)
        if ndims < 1 or ndims > 3:
            raise NotImplementedError(f"array {node.name!r} {_UNSUPPORTED_HINT} (1-3 dimensions only)")

        if var_type:
            # Typed `DIM ... AS type` — matches the current interpreter's
            # own (unread) 'dimensions'/'base'/'data' wrapper: elements are
            # never pre-filled. Still evaluate the dimension expressions
            # for side-effect parity, just discard them.
            for d in dims:
                self._compile_expr(d)
                self.chunk.emit(Op.CALL_NATIVE, ("_toint", 1))
                self.chunk.emit(Op.POP_TOP)
            self.chunk.emit(Op.CALL_NATIVE, (f"_alloc_array{ndims}_empty", 0))
        else:
            for d in dims:
                self._compile_expr(d)
                self.chunk.emit(Op.CALL_NATIVE, ("_toint", 1))
            self.chunk.emit(Op.LOAD_CONST, self.chunk.add_constant(0.0))
            self.chunk.emit(Op.CALL_NATIVE, (f"_alloc_array{ndims}", ndims + 1))

        # Arrays are never part of FragBASIC's save/restore scoping (see
        # module docstring) — always a VM global, regardless of scope.
        self.chunk.emit(Op.STORE_GLOBAL, node.name)

    def _compile_print(self, node):
        if not node.nodes:
            self.chunk.emit(Op.CALL_NATIVE, ("_print_blank", 0))
            self.chunk.emit(Op.POP_TOP)
            return
        seps = tuple(
            "SEMI" if s == TokenType.SEMICOLON else "COMMA"
            for s in getattr(node, "separators", [])
        )
        self.chunk.emit(Op.LOAD_CONST, self.chunk.add_constant(seps))
        for expr in node.nodes:
            self._compile_expr(expr)
        self.chunk.emit(Op.CALL_NATIVE, ("_print", len(node.nodes) + 1))
        self.chunk.emit(Op.POP_TOP)

    def _compile_if(self, node):
        cond, then_block = node.nodes[0], node.nodes[1]
        self._compile_expr(cond)
        skip_jump = self.chunk.emit(Op.JUMP_IF_FALSE, None)
        self._compile_block(_as_list(then_block))
        self.chunk.patch_arg(skip_jump, self.chunk.here())

    def _compile_if_else(self, node):
        cond, then_block = node.nodes[0], node.nodes[1]
        rest = node.nodes[2:]

        self._compile_expr(cond)
        next_jump = self.chunk.emit(Op.JUMP_IF_FALSE, None)
        self._compile_block(_as_list(then_block))
        end_jumps = [self.chunk.emit(Op.JUMP, None)]
        self.chunk.patch_arg(next_jump, self.chunk.here())

        for clause in rest:
            if clause.type == NodeType.ELSEIF:
                elseif_cond, elseif_block = clause.nodes[0], clause.nodes[1]
                self._compile_expr(elseif_cond)
                nj = self.chunk.emit(Op.JUMP_IF_FALSE, None)
                self._compile_block(_as_list(elseif_block))
                end_jumps.append(self.chunk.emit(Op.JUMP, None))
                self.chunk.patch_arg(nj, self.chunk.here())
            else:
                # The trailing bare ELSE block.
                self._compile_block(_as_list(clause))

        end_addr = self.chunk.here()
        for j in end_jumps:
            self.chunk.patch_arg(j, end_addr)

    def _compile_call_stmt(self, node):
        name = node.name.upper()
        self._emit_args(node.nodes)
        self._emit_call(name, len(node.nodes))
        self.chunk.emit(Op.POP_TOP)

    def _compile_return(self, node):
        if self._scope is None:
            raise NotImplementedError(f"GOSUB/RETURN {_UNSUPPORTED_HINT}")
        if self._in_function:
            if node.nodes:
                self._compile_expr(node.nodes[0])
            else:
                # Bare RETURN inside a FUNCTION: not an explicit return
                # value in the tree-walker either (visit_return only sets
                # function_returned when node.nodes is non-empty) — falls
                # back to the own-name idiom, same as falling off the end.
                self.chunk.emit(Op.LOAD_FAST, self._scope.own_name)
            self.chunk.emit(Op.RETURN)
        else:
            if node.nodes:
                self._compile_expr(node.nodes[0])
                self.chunk.emit(Op.POP_TOP)
            self.chunk.emit(Op.LOAD_CONST, self.chunk.add_constant(0.0))
            self.chunk.emit(Op.RETURN)

    # ------------------------------------------------------------------
    # Expressions
    # ------------------------------------------------------------------

    def _compile_expr(self, node):
        t = node.type

        if t == NodeType.NUMBER:
            value = node.value
            if isinstance(value, float) and value.is_integer():
                value = int(value)
            self.chunk.emit(Op.LOAD_CONST, self.chunk.add_constant(value))
            return
        if t == NodeType.STRING:
            self.chunk.emit(Op.LOAD_CONST, self.chunk.add_constant(node.name))
            return
        if t == NodeType.VAR_ACCESS:
            self._compile_var_access(node)
            return
        if t == NodeType.FUNCTION_CALL:
            self._compile_function_call(node)
            return
        if t == NodeType.PLUS:
            self._compile_expr(node.nodes[0])
            return
        if t == NodeType.MINUS:
            self._compile_expr(node.nodes[0])
            self.chunk.emit(Op.UNARY_NEG)
            return
        if t == NodeType.NOT:
            self._compile_expr(node.nodes[0])
            self.chunk.emit(Op.CALL_NATIVE, ("_not", 1))
            return
        if t in _BINARY_NATIVE:
            self._compile_expr(node.nodes[0])
            self._compile_expr(node.nodes[1])
            self.chunk.emit(Op.CALL_NATIVE, (_BINARY_NATIVE[t], 2))
            return
        if t in _BINARY_OPCODE:
            self._compile_expr(node.nodes[0])
            self._compile_expr(node.nodes[1])
            self.chunk.emit(_BINARY_OPCODE[t])
            return

        raise NotImplementedError(f"expression {t.name} {_UNSUPPORTED_HINT}")

    def _compile_var_access(self, node):
        name = node.name
        if node.nodes or node.value == "CALL":
            upper = name.upper()
            if upper in self.functions or upper in self.subs:
                self._emit_args(node.nodes)
                self._emit_call(upper, len(node.nodes))
                return
            self._compile_array_get(node)
            return
        self._emit_load_raw(name)

    def _compile_array_get(self, node):
        self.chunk.emit(Op.LOAD_GLOBAL, node.name)
        for idx_node in node.nodes:
            self._compile_expr(idx_node)
            self.chunk.emit(Op.CALL_NATIVE, ("_toint", 1))
            self.chunk.emit(Op.INDEX_GET)

    def _compile_function_call(self, node):
        name = node.name.upper()
        if name in self.functions or name in self.subs:
            self._emit_args(node.nodes)
            self._emit_call(name, len(node.nodes))
            return
        if name in natives.BUILTIN_ARITY:
            self._emit_args(node.nodes)
            self.chunk.emit(Op.CALL_NATIVE, (name, len(node.nodes)))
            return
        raise NotImplementedError(
            f"builtin/procedure {node.name!r} {_UNSUPPORTED_HINT}"
        )

    def _emit_args(self, arg_nodes):
        for a in arg_nodes:
            self._compile_expr(a)

    def _emit_call(self, name, argcount):
        idx = self.chunk.emit(Op.CALL, None)
        self._pending_calls.append((idx, name, argcount))

    def _resolve_pending_calls(self):
        for idx, name, argcount in self._pending_calls:
            if name in self._func_addr:
                addr = self._func_addr[name]
            elif name in self._sub_addr:
                addr = self._sub_addr[name]
            else:
                raise NameError(f"call to undefined SUB/FUNCTION {name!r}")
            self.chunk.patch_arg(idx, (addr, argcount))

    # ------------------------------------------------------------------
    # Scalar load/store helpers
    # ------------------------------------------------------------------

    def _emit_load_raw(self, name):
        if self._scope is not None and self._scope.is_local(name):
            self.chunk.emit(Op.LOAD_FAST, name)
        else:
            self.chunk.emit(Op.LOAD_GLOBAL, name)

    def _emit_store_raw(self, name):
        if self._scope is not None and self._scope.is_local(name):
            self.chunk.emit(Op.STORE_FAST, name)
        else:
            self.chunk.emit(Op.STORE_GLOBAL, name)

    def _emit_sigil_default(self, name):
        self.chunk.emit(Op.LOAD_CONST, self.chunk.add_constant(_sigil_default(name)))

    def _synthetic_name(self, prefix):
        self._synth_counter += 1
        # NUL-prefixed: guaranteed to never collide with a real BASIC
        # identifier (the lexer can't produce one), safe as a dict key
        # alongside real global names.
        return f"\0{prefix}{self._synth_counter}"


def compile_program(ast_root) -> Chunk:
    return VMCompiler().compile_program(ast_root)


# ------------------------------------------------------------------
# Free functions
# ------------------------------------------------------------------

def _flatten_root(ast_root):
    if ast_root.type == NodeType.NULL:
        return []
    if ast_root.type == NodeType.BLOCK:
        return ast_root.nodes
    return [ast_root]


def _as_list(node):
    if node.type == NodeType.BLOCK:
        return node.nodes
    if node.type == NodeType.NULL:
        return []
    return [node]


def _sigil_default(name):
    """Mirrors visit_var_access's auto-vivify-on-first-read default."""
    if name.endswith("$"):
        return ""
    if name.endswith("%"):
        return 0
    return 0.0  # '!', '#', and no-sigil all default to SINGLE 0.0


def _dim_scalar_default(var_type):
    if var_type == "STRING":
        return ""
    if var_type in ("INTEGER", "LONG"):
        return 0
    return 0.0  # SINGLE, DOUBLE, or None (legacy DIM with no AS clause)


def _fold_data_value(node):
    """Compile-time constant-fold one DATA entry. Mirrors
    collect_definitions' DATA handling, which only ever sees NUMBER/STRING
    literals in the actual corpus — a bare IDENTIFIER entry (reading a
    variable's value into DATA) is supported by the parser but nonsensical
    at collect time in the tree-walker too (variables aren't set yet), so
    it's not replicated here; negative-number literals (`DATA -5`) parse
    as a unary MINUS/PLUS around a NUMBER and are constant-folded."""
    if node.type == NodeType.NUMBER:
        value = node.value
        return int(value) if isinstance(value, float) and value.is_integer() else value
    if node.type == NodeType.STRING:
        return node.name
    if node.type == NodeType.MINUS:
        return -_fold_data_value(node.nodes[0])
    if node.type == NodeType.PLUS:
        return _fold_data_value(node.nodes[0])
    raise NotImplementedError(
        f"DATA value {node.type.name} {_UNSUPPORTED_HINT} "
        "(only literal numbers/strings are supported)"
    )


def _collect_scalar_names(statements):
    """Every bare-scalar VAR_ACCESS/VAR_ASSIGN name referenced anywhere in
    a flat statement list (recursing into nested expression/IF-block
    structure via `.nodes`) — deliberately does NOT descend into SUB/
    FUNCTION bodies, since those aren't reachable via `.nodes` (they live
    in the separate `.body` attribute) and get their own per-procedure
    prelude instead (see `_compile_procedure`)."""
    names = set()

    def walk(node):
        if node.type == NodeType.VAR_ACCESS:
            if not node.nodes and node.value != "CALL":
                names.add(node.name)
        elif node.type == NodeType.VAR_ASSIGN:
            if len(node.nodes) <= 1:
                names.add(node.name)
        for child in node.nodes:
            walk(child)

    for stmt in statements:
        walk(stmt)
    return names
