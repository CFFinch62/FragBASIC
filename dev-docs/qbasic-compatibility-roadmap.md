# QBasic Compatibility Roadmap

FragBASIC's dialect was originally designed (in its prior home, an
educational IDE's built-in interpreter) with the explicit goal of getting
as close to real QBasic as was practical for a teaching tool, while
deliberately excluding anything that posed a security risk or fell
outside educational scope. That project tracked its own gaps against
QBasic in a README and an implementation-status checklist.

This document re-derives that gap analysis for FragBASIC specifically —
verified against FragBASIC's actual current source, not copied from the
old status doc — and turns it into a prioritized backlog. Every claim
below was checked by actually running `fragbasic` against the example in
question, not inferred from documentation, because (as §1 shows) the old
documentation and the old implementation had already drifted apart in
several places.

---

## 1. Documented-as-working but actually broken

These are the highest-value items: each one was written up as a supported
feature — the old README even used it in canonical examples, and one was
checked off "IMPLEMENTED" in a status checklist — but running it against
FragBASIC's real parser shows it doesn't work at all. Nobody using
FragBASIC today would know these are broken until they hit the parse
error; fixing them is pure upside with no design decision required.

### 1.1 `CONST` is not parseable at all

```basic
CONST PI = 3.14159
```
```
Error on line 1: Unexpected keyword: CONST
```

`CONST` is a recognized keyword, and `Interpreter.__init__` already
allocates a `self.constants` dict for it — but no parser statement
handler for `CONST` exists, so it's a syntax error every time. Also
worth deciding while fixing this: should assigning to a declared constant
afterward be a runtime error (true immutability), or should `CONST` just
be sugar for `DIM ... AS TYPE` + assignment with no enforcement? The
existing (unused) `self.constants` dict suggests the original design
intended real enforcement.

**Effort:** small. Add a `const_stmt()` parser method (`CONST name [AS
type] = expr`, modeled on the `DIM` parser) and a `visit_const`
interpreter method that populates `self.constants` and initializes the
variable; add an immutability check in `visit_var_assign` if enforcement
is wanted.

### 1.2 `INPUT` only accepts `;` before the prompt, not `,`

```basic
INPUT "Enter your name: ", name$
```
```
Error on line 1: Expected variable name in INPUT statement
```

This is the *exact syntax the old README used in its own "first program"
example*. Only the semicolon form works today:

```basic
INPUT "Enter your name: "; name$   ' this works
```

Real QBasic accepts both, with a minor behavioral difference (a
comma-separated prompt suppresses the automatic `?` that a *promptless*
`INPUT` would otherwise print — moot here, since FragBASIC never appends
`?` when any prompt is given, only when there's no prompt at all).

**Effort:** small. In `input_stmt()`, accept `TokenType.COMMA` anywhere
the code currently checks for `TokenType.SEMICOLON` after the speculative
prompt expression.

### 1.3 Typed `SUB`/`FUNCTION` parameters, and `FUNCTION` return-type annotations

```basic
SUB DisplayMessage(msg AS STRING)
FUNCTION Square(x AS SINGLE) AS SINGLE
```
```
Error on line 1: Expected ) in SUB declaration
Error on line 1: Expected ) in FUNCTION declaration
```

Both are straight from the old README's canonical examples. Parameters
today are name-only; a parameter's effective type is just whatever the
caller happened to pass in, and there's no way to write down (or have the
interpreter enforce/coerce) an expected type. The trailing `AS TYPE`
after a `FUNCTION`'s parameter list — declaring its return type — isn't
consumed by the parser at all, so it's a guaranteed syntax error on any
`FUNCTION` written the way the README shows.

**Effort:** medium. Parsing is straightforward — accept an optional
`AS TYPE` after each parameter name, and after a `FUNCTION`'s closing
`)`, and stash the type(s) on the `SUB`/`FUNCTION` node. What to *do*
with that type once parsed is the real design question: the minimum
useful behavior is coercing each argument to the declared type on entry
(same coercion `visit_var_assign` already does based on name suffix), and
coercing a `FUNCTION`'s return value on the way out.

---

## 2. Tracked as not-implemented already, still true today

These were already known gaps (the old status doc explicitly listed them
as `NOT IMPLEMENTED`), confirmed still accurate against FragBASIC's
current parser (all these keywords exist in the lexer's keyword list but
have no parser statement handler).

### 2.1 `SHARED` / `STATIC` — variable scoping across SUB/FUNCTION calls

This is the most consequential gap, and it interacts with a scoping
asymmetry that's worth understanding precisely before touching it.
FragBASIC's actual current behavior, verified:

- **Scalar variables are always local to a call, full stop.** Every
  scalar assignment made inside a `SUB`/`FUNCTION` body — including its
  own parameters — is thrown away when the call returns. A `SUB` cannot
  mutate a same-named outer variable even if one already exists:
  ```basic
  total = 0
  SUB AddFive()
      total = total + 5
  END SUB
  CALL AddFive()
  PRINT total   ' prints 0, not 5
  ```
- **Arrays are always global**, with no save/restore around a call at
  all. An element write inside a `SUB` is immediately visible to (and
  persists for) the caller.

The scalar behavior is actually a reasonable approximation of QBasic's
real default (procedures get fresh locals every call, nothing is shared
unless you opt in) — the missing piece is the opt-in itself. `SHARED`
inside a `SUB`/`FUNCTION` body is how QBasic lets a procedure read and
write a specific outer-scope variable; without it, FragBASIC procedures
can only communicate via parameters, a `FUNCTION`'s return value, or
(inconsistently) arrays.

**Recommendation:** implementing `SHARED name[, name...]` as a statement
that, when executed inside a `SUB`/`FUNCTION` body, aliases the named
variable(s) to the outer scope for the rest of that call would close this
gap and remove the scalar/array asymmetry as a side effect (once `SHARED`
exists, the array behavior can be explained as "arrays behave as if
always `SHARED`," which is at least a documented rule instead of an
accident). `STATIC` (persisting a procedure's locals between calls,
instead of resetting them every call) is lower value for a teaching
language and can be deferred independently.

**Effort:** medium. Requires call_sub/call_function to track which names
are aliased for the current call and route reads/writes for those names
to the outer `self.variables` dict instead of the call-local copy.

### 2.2 `OPTION BASE` — switching arrays from 0-based to 1-based

QBasic's default array base is 0, same as FragBASIC, but `OPTION BASE 1`
lets a program switch to 1-based indexing globally. Not implemented; all
FragBASIC arrays are unconditionally 0-based today.

**Effort:** small, mechanical — thread a `base` value (currently
hardcoded to `0` in `visit_dim`) through from a module-level flag set by
`OPTION BASE`, and adjust the legacy (non-`AS`-typed) `DIM` array
construction the same way.

### 2.3 `TYPE...END TYPE` — user-defined record/struct types

Not implemented at all — no parser or interpreter support, no `Variable`
representation for a compound value. This is the largest single gap in
this document.

**Effort:** large. Needs a new `Variable` type (or a dedicated
`Record`-like value) holding named fields, dotted-name parsing
(`person.name`) threaded through the lexer/parser (`.` isn't currently a
meaningful token in an identifier position), and interpreter support for
field access and assignment, plus arrays-of-`TYPE`. Given FragBASIC's
teaching scope, weigh whether this is worth the complexity it adds versus
the pedagogical value — QBasic's `TYPE` is usually a later-stage teaching
topic, not core to an intro course.

### 2.4 `DEFINT` / `DEFLNG` / `DEFSNG` / `DEFDBL` / `DEFSTR`

Default a range of unsuffixed variable names (`DEFINT A-Z`) to a given
type instead of the hardcoded `SINGLE` default. Not implemented.

**Recommendation:** low priority. This is a legacy convenience from an
era of terse variable names; FragBASIC's explicit-suffix and `DIM AS
TYPE` system already covers the same need more legibly for a learner, and
teaching "declare explicitly" is arguably a better habit than teaching
this feature. Consider **not** implementing this one at all.

**Effort (if pursued):** small–medium — needs a per-scope table of
letter-range → type, consulted by the auto-initialization logic in
`visit_var_access` and by `visit_var_assign`'s suffix-based coercion.

---

## 3. Intentionally excluded — recommend leaving these out

The old README called these out explicitly as deliberate exclusions, most
for security reasons or as beyond educational scope, not oversights.
Nothing here is a "bug" to fix; each is a scope decision that was
presumably made carefully. Revisit only if FragBASIC's goals actually
change (e.g. if a sandboxed "safe subset" of file I/O becomes genuinely
useful for a lesson plan).

- **`SYSTEM`, `SHELL`** — arbitrary OS command execution from a BASIC
  program. Actively dangerous to add back; not recommended under any
  circumstance for a teaching tool that might run untrusted student code.
- **File I/O** (`OPEN`, `CLOSE`, `PRINT #`, `INPUT #`, etc.) — the old
  README suggests `DATA`/`READ` and arrays as the pedagogical substitute.
  A sandboxed, path-restricted subset (e.g. read/write only inside a
  directory the host IDE designates) could be worth reconsidering
  someday, but full filesystem access should not be.
- **Networking** — not appropriate for this project.
- **Graphics** (`LINE`, `CIRCLE`, `PSET`, `DRAW`, `PAINT`, `VIEW`,
  `WINDOW`) — a real QBasic teaching feature, but a large undertaking
  (needs an actual drawing surface, which breaks the "just stdin/stdout"
  CLI model this project is built around). Would only make sense paired
  with a graphical console in an embedding IDE, not the bare CLI.
- **Sound/media** (`SOUND`, `PLAY`, `BEEP`) — same reasoning as graphics;
  also not meaningful for a subprocess whose only I/O is text streams.
- **File-system commands** (`FILES`, `NAME`, `KILL`, `CHDIR`, `MKDIR`,
  `RMDIR`) — same security posture as the file I/O note above.

One item from the old README's exclusion list is worth calling out as a
**possible exception** to "leave excluded": **`CLS`, `LOCATE`, `COLOR`**
(clear screen, cursor positioning, text color) were grouped with the
graphics exclusions, but unlike real graphics they're just ANSI escape
codes — genuinely low effort, no security concern, and a real (if minor)
teaching feature for anyone writing text-based games or menus. If
console-based games/UIs become a priority, this would be cheap to add.

---

## 4. Suggested phasing

1. **Phase 1 — fix what's already documented as working** (§1): `CONST`,
   comma-separated `INPUT` prompts, typed parameters/return types. Small,
   independent, no open design questions except `CONST` immutability.
2. **Phase 2 — `SHARED`** (§2.1): the highest-value real feature gap,
   since it's the one thing actively blocking natural QBasic-style
   `SUB`/`FUNCTION` code from working (needing a `FUNCTION` or an array
   just to get one value back out of a `SUB` is a real limitation for
   anyone porting or writing QBasic-style programs).
3. **Phase 3 — `OPTION BASE`, `CLS`/`LOCATE`/`COLOR`** (§2.2, §3): small,
   independent, mostly a matter of priority rather than difficulty.
4. **Phase 4 — reassess `TYPE`, `STATIC`, `DEF*`** (§2.3, §2.1, §2.4)
   once Phases 1–3 are done, based on what a curriculum built on
   FragBASIC actually turns out to need.
5. **Not planned**: everything in §3 except the `CLS`/`LOCATE`/`COLOR`
   carve-out.

Each phase should land with test coverage the same way the existing
interpreter/CLI work was verified — a claim in this document or a future
doc update should be backed by an actual `fragbasic` run, not an
assumption, given how much of §1 exists precisely because that discipline
wasn't applied consistently the first time around.
