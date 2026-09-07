# FragBASIC User Guide

FragBASIC is a small, educational BASIC dialect, packaged as a standalone
command you can call from a terminal or launch from any IDE. This guide
covers the `fragbasic` command itself, then documents the language: every
keyword, operator, and built-in function, with examples.

If you just want a quick tour, read [§1](#1-running-fragbasic-programs)
and [§2](#2-a-first-program), then use [§10](#10-keyword-reference) and
[§11](#11-built-in-function-reference) as lookup tables while you write.

---

## 1. Running FragBASIC programs

```bash
fragbasic script.bas              # run a file
fragbasic -c 'PRINT "hi"'         # run a snippet directly
fragbasic script.bas --timeout 10 # cancel after 10 seconds of running
fragbasic --check script.bas      # report syntax errors without running it
fragbasic --version
```

- Output is written to stdout as the program runs (not buffered until
  exit), and `INPUT` reads one line at a time from stdin.
- Errors are printed to stderr as a single line:
  `Error on line N: <message>`.
- **Exit codes**: `0` the program finished normally, `1` a lex/parse/
  runtime error in the program, `2` a usage error (bad arguments, file not
  found), `130` execution was cancelled (Ctrl+C, SIGTERM, or `--timeout`
  expired).
- `--check` answers "does this parse?" without side effects. It lexes and
  parses only, so nothing is printed and `INPUT` never blocks — which is what
  makes it usable from an editor, where a program waiting on stdin that nobody
  is typing into would hang forever. Its errors carry the file path
  (`script.bas:4: unexpected token`), unlike a run's `Error on line 4:`, so a
  tool can place them.

  ```console
  $ fragbasic --check examples/fizzbuzz.bas
  examples/fizzbuzz.bas: no syntax errors

  $ fragbasic --check broken.bas
  broken.bas:2: Unexpected token in expression
  ```

- `--timeout` only interrupts a *running* program between statements — it
  cannot interrupt a program that's blocked waiting on `INPUT`. Use
  Ctrl+C (or send SIGTERM) for that.

If you're wiring FragBASIC into an IDE as a subprocess rather than running
it by hand, see the main [README](../README.md)'s "Embedding" section for
the equivalent Python API.

---

## 2. A first program

```basic
PRINT "Hello, world!"

DIM name AS STRING
name = "World"
PRINT "Hello, "; name; "!"
```

`PRINT` writes each comma/semicolon-separated value in turn — see
[§8](#8-print-formatting-in-detail) for exactly how the separators behave.
`DIM ... AS STRING` declares a variable's type; you can also skip
declaration entirely and let the variable's name suffix say what it holds
(`name$` is always a string — see [§3](#3-types-and-variable-names)).

Comments start with `REM` or `'`:

```basic
REM this is a comment
' so is this
PRINT 1 ' and this, at the end of a line
```

---

## 3. Types and variable names

FragBASIC has five value types. A variable's type is either declared with
`DIM`, or inferred from a suffix character on its name:

| Suffix | Type | Meaning | Default value |
|---|---|---|---|
| `%` | `INTEGER` | whole number | `0` |
| (none, `LONG` via `DIM`) | `LONG` | whole number | `0` |
| `!` | `SINGLE` | floating point (**this is the default type** for unsuffixed, undeclared names) | `0.0` |
| `#` | `DOUBLE` | floating point, same storage as `SINGLE` internally | `0.0` |
| `$` | `STRING` | text | `""` |

```basic
count%  = 5        ' INTEGER, because of %
price!  = 19.99     ' SINGLE, because of !
name$   = "Ada"      ' STRING, because of $
x       = 3.5        ' SINGLE, because there's no suffix and no DIM
```

Using a variable before assigning it does **not** error — it's
auto-initialized based on its suffix (see the table above). Reading an
undeclared, unsuffixed variable gives `0.0`.

### Declaring with DIM

```basic
DIM age AS INTEGER
DIM price AS SINGLE
DIM name AS STRING
DIM balance AS DOUBLE
DIM total AS LONG
```

A `DIM ... AS TYPE` declaration locks in a variable's storage type
regardless of its name. Declaring the same variable twice is an error
(`Variable X is already declared`).

### Arrays

```basic
DIM scores(10) AS INTEGER      ' 1D, indices 0 to 10 (11 elements)
DIM grid(4, 4) AS SINGLE       ' 2D, indices 0-4 by 0-4
DIM cube(2, 2, 2) AS DOUBLE    ' 3D, up to 3 dimensions supported

scores(0) = 100
PRINT scores(0)
```

Arrays are always 0-based, and the declared size is *inclusive* —
`DIM arr(4)` gives you five elements, indices `0` through `4`. You can
also declare an array without `AS TYPE` (`DIM arr(4)`), which defaults
every element to `SINGLE`.

`OPTION BASE` (to switch to 1-based arrays) is **not implemented** —
arrays are always 0-based.

### Not implemented

These are recognized as keywords (so using them as a variable name will
misbehave) but have no actual effect: `CONST`, `SHARED`, `STATIC`,
`TYPE`, `OPTION`, `BASE`, `DEFINT`, `DEFLNG`, `DEFSNG`, `DEFDBL`,
`DEFSTR`. In particular, **`CONST` looks like it should declare a
constant but is not parseable as a statement at all** — writing
`CONST PI = 3.14` raises `Unexpected keyword: CONST`. Just use a regular
variable by convention instead.

---

## 4. Operators

```
+  - concatenates strings when either side is a STRING, otherwise adds
-  * /  \  ^  MOD    standard arithmetic (\ is integer division, ^ is power)
=  <>  <  >  <=  >=  comparisons (work on numbers or strings)
AND  OR  NOT  XOR  EQV  IMP    logical operators
```

Comparisons and logical operators use classic BASIC truth values:
**`-1` for true, `0` for false** — not `1`/`0`. `IF` and `WHILE`/`UNTIL`
conditions treat any nonzero value as true.

`\` (integer division) and `MOD` both truncate toward zero and raise a
runtime error on division by zero, same as `/`.

### Precedence (loosest to tightest)

```
OR
AND
NOT
XOR, EQV, IMP
=  <>  <  >  <=  >=
+  -
*  /  \  MOD
^                     (right-associative: 2^3^2 = 2^(3^2) = 512)
unary + / -
```

This is *not* the same order every BASIC dialect uses — notably, the
relational operators (`=`, `<`, etc.) bind **tighter** than `XOR`/`EQV`/
`IMP` here, so `a = b XOR c = d` parses as `(a = b) XOR (c = d)` without
needing parentheses. When in doubt, parenthesize.

---

## 5. Control flow

### IF

```basic
IF x > 0 THEN PRINT "positive"                     ' single-line
IF x > 0 THEN PRINT "positive" ELSE PRINT "other"   ' single-line with ELSE

IF x > 0 THEN                 ' multi-line
    PRINT "positive"
ELSEIF x < 0 THEN
    PRINT "negative"
ELSE
    PRINT "zero"
END IF
```

### SELECT CASE

```basic
SELECT CASE grade
    CASE 90 TO 100
        PRINT "A"
    CASE 80 TO 89
        PRINT "B"
    CASE 0
        PRINT "no submission"
    CASE ELSE
        PRINT "F"
END SELECT
```

`CASE` values can be a single expression, a comma-separated list, or a
`lo TO hi` inclusive range.

### FOR / NEXT

```basic
FOR i = 1 TO 10
    PRINT i
NEXT i

FOR i = 10 TO 1 STEP -1   ' STEP can be negative or fractional
    PRINT i
NEXT i
```

The loop variable, bounds, and `STEP` are all evaluated once at loop
start (changing the end bound inside the loop body doesn't affect how
many iterations run). `NEXT` optionally takes the loop variable's name,
but it's not checked against anything — it's purely documentation.

### WHILE / WEND and DO / LOOP

```basic
WHILE x < 10
    x = x + 1
WEND

DO WHILE x < 10       ' condition checked at the top
    x = x + 1
LOOP

DO UNTIL x >= 10       ' condition checked at the top, inverted sense
    x = x + 1
LOOP

DO                      ' condition checked at the bottom - runs at least once
    x = x + 1
LOOP WHILE x < 10

DO
    x = x + 1
LOOP UNTIL x >= 10
```

### EXIT

`EXIT FOR`, `EXIT WHILE`, `EXIT DO`, `EXIT SUB`, and `EXIT FUNCTION` all
immediately leave their enclosing construct. `EXIT FUNCTION` keeps
whatever return value has been set so far (see [§7](#7-subs-and-functions)).

### GOSUB / RETURN and labels

FragBASIC has **no `GOTO`** — only `GOSUB`, which pushes a return address
before jumping, and `RETURN`, which pops it. A jump target is either a
line number or a name, and **must end with a colon** to actually become a
usable label:

```basic
GOSUB 100
PRINT "back in the main flow"
END

100:
PRINT "in the subroutine"
RETURN
```

```basic
GOSUB DoWork
END

DoWork:
PRINT "working"
RETURN
```

A bare `100 PRINT "hi"` (a leading number with **no** colon, the classic
line-numbered BASIC style) does **not** create a jump target — the
leading number is silently discarded and the rest of the line runs as a
normal statement. If you want `GOSUB 100` to work, the target line must
be written as `100:` on its own.

`RETURN` executed with nothing on the GOSUB stack (i.e. not inside a
called subroutine) is simply a no-op, not an error.

---

## 6. Input and output

### PRINT

```basic
PRINT "hello"                  ' hello\n
PRINT "a"; "b"                 ' a b\n   (";" adds a space between items)
PRINT "a", "b"                 ' a             b\n   ("," pads to the next 14-column tab stop)
PRINT "no newline";            ' trailing ";" suppresses the final newline
PRINT                          ' blank line
```

See [§8](#8-print-formatting-in-detail) for the exact column-tab math.

### INPUT

```basic
INPUT x                        ' prints "? " as the default prompt
INPUT "Enter your name: "; name$
INPUT "x, y: "; x, y            ' comma-separated: user types "3, 4"
```

A prompt is only recognized as a prompt if it's followed by a semicolon.
Multiple variables read from one comma-separated line of input; missing
fields become `""` (for `$` variables) or `0` (for numeric variables), and
unparseable numeric input also becomes `0` rather than raising an error.

Pressing Ctrl+C (or reaching end-of-input/EOF) at an `INPUT` prompt
supplies an empty value for that one read, and — because `fragbasic`'s
Ctrl+C handler also requests cancellation — the program then stops at the
very next statement rather than continuing.

### DATA / READ / RESTORE

```basic
DATA 1, 2, 3, "four", 5.5

READ a
READ b, c
PRINT a; b; c

RESTORE          ' rewind the DATA pointer back to the first value
READ a
```

All `DATA` statements in a program are collected into one pool before
execution starts (regardless of where they appear), and `READ` pulls from
that pool in order. Reading past the last value is a runtime error:
`Out of DATA`.

---

## 7. Subs and functions

```basic
SUB Greet(name$)
    PRINT "Hello, " + name$
END SUB

CALL Greet("World")   ' call with arguments - needs the CALL keyword
```

```basic
SUB SayHi()
    PRINT "hi"
END SUB

SayHi                  ' a zero-argument SUB can be called bare, no CALL needed
```

```basic
FUNCTION Square(n)
    Square = n * n     ' classic BASIC idiom: assign the function's own name
END FUNCTION

PRINT Square(5)         ' 25
```

```basic
FUNCTION Abs2(n)
    IF n < 0 THEN
        RETURN -n        ' RETURN <expr> is an explicit, early return
    END IF
    RETURN n
END FUNCTION
```

Rules worth knowing:

- SUB/FUNCTION names are **case-insensitive** — `SUB Greet` can be called
  as `CALL greet(...)` or `GREET(...)`.
- **Calling a SUB with arguments as a statement requires the `CALL`
  keyword.** Writing `Greet("World")` or `Greet "World"` directly as a
  statement (without `CALL`) is a parse error — only a bare, zero-argument
  name (`Greet` alone, no parentheses) works without `CALL`. This
  restriction is specific to statement position: `Name(args)` parses fine
  wherever an *expression* is expected — the right side of `=`, inside
  `PRINT`, inside a condition, or as an argument to another call — which
  is why `PRINT Square(5)` and `result = Square(5)` both work without
  `CALL`.
- If both an explicit `RETURN <expr>` and a `FunctionName = value`
  assignment happen in the same call, the explicit `RETURN` wins.
- If neither happens, a `FUNCTION` returns `0`.
- **Scalar variables are always local to the SUB/FUNCTION call that
  assigns them, including the call's own parameters.** Every scalar
  variable change made during a call — parameters, and any other
  variable you assign in the body, even one that shares a name with an
  outer/global variable — is discarded when the call returns; the outer
  variable is left completely untouched. There's no way to write through
  to an outer scalar variable from inside a `SUB`/`FUNCTION` today (the
  `SHARED` keyword that would normally provide this in QBasic-style BASIC
  is recognized but not implemented — see the note in [§3](#3-types-and-variable-names)).
- **Arrays are the opposite: always global**, never snapshotted or
  restored around a call. An element assignment made to an array inside
  a `SUB`/`FUNCTION` is visible to the caller immediately and permanently.
  Keep this asymmetry in mind: if you need a `SUB` to hand a value back to
  its caller, either use a `FUNCTION`'s return value or write into an
  array element, not a plain variable.
- `SUB`/`FUNCTION` definitions must appear as top-level statements (not
  nested inside `IF`/`FOR`/etc.) — they're collected in a pass over the
  program before it runs, so definition order relative to call sites
  doesn't matter, but nesting them inside another construct does.
- Calling an undefined `SUB`/`FUNCTION` name by writing `Name(args)`
  inside an expression without a matching definition is instead treated
  as **array access** on an array named `Name` — if no such array exists
  either, you'll get `Array NAME not defined` rather than a more specific
  "not a function" error. If you see that error unexpectedly, check for a
  typo in the SUB/FUNCTION name.

---

## 8. PRINT formatting in detail

Each item in a `PRINT` list is converted with `str()`-like formatting
(whole-number floats print without a decimal point: `5.0` becomes `5`).
Separators control what goes *between* items and whether a trailing
newline is added:

- **`;`** inserts a single space between the two items it separates.
- **`,`** pads with spaces up to the next multiple of 14 columns
  (measured from the start of the current `PRINT` statement's output, not
  the whole program's output) — the classic BASIC "print zone" tab stop.
- If the **last** separator in the statement is `;`, no trailing newline
  is added (so the next `PRINT` continues on the same line). Any other
  ending (a `,`-terminated statement, or no trailing separator at all)
  adds a newline.
- `PRINT` with no arguments at all writes just a newline.

---

## 9. Errors

Every lex, parse, and runtime error is one line to stderr:

```
Error on line 4: Division by zero
```

- **Lex errors** — illegal characters, unterminated strings.
- **Parse errors** — malformed statements (missing `THEN`, unbalanced
  parentheses, etc.).
- **Runtime errors** — undefined arrays, division by zero, wrong argument
  counts to a built-in function, out-of-bounds array access, `Out of
  DATA`, and so on. The line number attached is the line of the
  statement or expression being evaluated when the error was raised —
  for deeply nested expressions this is the statement's line, not
  necessarily the exact sub-expression.

If you ever see `fragbasic: internal error: ...` instead of the format
above, that's a genuine interpreter bug (not a mistake in your program) —
please report it.

---

## 10. Keyword reference

| Keyword | Purpose |
|---|---|
| `PRINT` | write output |
| `INPUT` | read a line of input into one or more variables |
| `LET` | optional keyword before an assignment (`LET x = 5` = `x = 5`) |
| `DIM` | declare a variable or array, optionally `AS` a type |
| `AS` | introduces a type in `DIM`/array declarations |
| `INTEGER`, `LONG`, `SINGLE`, `DOUBLE`, `STRING` | the five storage types, used after `AS` |
| `DATA` | declare literal values for `READ` |
| `READ` | pull the next `DATA` value into a variable |
| `RESTORE` | rewind the `DATA` pointer to the start |
| `IF`, `THEN`, `ELSEIF`, `ELSE`, `END IF` | conditional branching |
| `SELECT`, `CASE`, `END SELECT` | multi-way branching |
| `FOR`, `TO`, `STEP`, `NEXT` | counted loop |
| `WHILE`, `WEND` | pre-condition loop |
| `DO`, `LOOP`, `UNTIL` | pre- or post-condition loop (`WHILE` reused for pre-condition) |
| `GOSUB`, `RETURN` | jump to a label/line and come back |
| `SUB`, `END SUB`, `CALL` | define/invoke a subroutine |
| `FUNCTION`, `END FUNCTION` | define a value-returning routine |
| `EXIT` | leave a `FOR`/`WHILE`/`DO`/`SUB`/`FUNCTION` early |
| `RANDOMIZE` | reseed the random number generator, optionally with a seed |
| `SLEEP` | pause execution (seconds), or ~1 second with no argument |
| `REM`, `'` | comment to end of line |
| `END` | terminate the program |
| `AND`, `OR`, `NOT`, `XOR`, `EQV`, `IMP`, `MOD` | operators — see [§4](#4-operators) |
| `CONST`, `SHARED`, `STATIC`, `TYPE`, `OPTION`, `BASE`, `DEFINT`, `DEFLNG`, `DEFSNG`, `DEFDBL`, `DEFSTR` | recognized but **not implemented** — see [§3](#3-types-and-variable-names) |

---

## 11. Built-in function reference

### Math

| Function | Signature | Notes |
|---|---|---|
| `ABS(n)` | number → number | absolute value |
| `SQR(n)` | number → SINGLE | square root |
| `SIN(n)`, `COS(n)`, `TAN(n)`, `ATN(n)` | number → SINGLE | radians |
| `EXP(n)` | number → SINGLE | eⁿ |
| `LOG(n)` | number → SINGLE | natural log |
| `INT(n)` | number → INTEGER | floor toward negative infinity |
| `FIX(n)` | number → INTEGER | truncate toward zero |
| `SGN(n)` | number → INTEGER | -1, 0, or 1 |
| `RND` | → SINGLE | random number in `[0, 1)`. Written **without** parentheses. |

### Strings

| Function | Signature | Notes |
|---|---|---|
| `LEN(s$)` | string → INTEGER | length |
| `LEFT$(s$, n)` | → STRING | first `n` characters |
| `RIGHT$(s$, n)` | → STRING | last `n` characters |
| `MID$(s$, start, [len])` | → STRING | substring; `start` is 1-based; `len` omitted means "to the end" |
| `CHR$(n)` | INTEGER → STRING | character for ASCII code `n` (0-255; otherwise `""`) |
| `ASC(s$)` | STRING → INTEGER | ASCII code of the first character (`0` for empty string) |
| `STR$(n)` | number → STRING | number as text; **leading space for non-negative numbers** |
| `VAL(s$)` | STRING → number | parses a leading number from a string; `0` if unparseable |
| `SPACE$(n)` | INTEGER → STRING | `n` spaces |
| `STRING$(n, char)` | (INTEGER, STRING-or-INTEGER) → STRING | `char` repeated `n` times; `char` may be a one-character string or an ASCII code |
| `INSTR([start,] s$, sub$)` | → INTEGER | 1-based position of `sub$` in `s$`, `0` if not found; optional 1-based `start` |
| `UCASE$(s$)`, `LCASE$(s$)` | → STRING | case conversion |
| `LTRIM$(s$)`, `RTRIM$(s$)` | → STRING | strip leading/trailing whitespace |

### Type conversion

| Function | Notes |
|---|---|
| `CINT(n)` | round to nearest INTEGER |
| `CLNG(n)` | truncate to INTEGER |
| `CSNG(n)` | to SINGLE |
| `CDBL(n)` | to DOUBLE |

### System

| Function | Notes |
|---|---|
| `DATE$` | current date, `MM-DD-YYYY`. No parentheses. |
| `TIME$` | current time, `HH:MM:SS`. No parentheses. |
| `TIMER` | seconds since midnight, as a SINGLE. No parentheses. |
| `INKEY$` | best-effort non-blocking single-key read; see the note below. No parentheses. |

**`INKEY$` limitation**: on Windows it's truly non-blocking. On POSIX
(Linux/macOS), FragBASIC deliberately does *not* put the terminal into
raw/cbreak mode — doing so risks breaking `INPUT` — so a key you press
only becomes visible to `INKEY$` after you press Enter. Polling
`INKEY$` in a tight loop waiting for a specific key works, but won't feel
like a real-time game-input read on POSIX. See
`src/fragbasic_core/platform_io.py` for the implementation.

Every built-in function call is written with parentheses (`ABS(-5)`)
*except* the four zero-argument system functions above and `RND`, which
are written bare.

---

## 12. Where to look next

- [`../README.md`](../README.md) — installing and embedding FragBASIC in
  Python.
- [`../examples/`](../examples/) — runnable sample programs
  (`hello.bas`, `fizzbuzz.bas`, `guess_the_number.bas`, `arrays.bas`).
- `src/fragbasic_core/` — the interpreter itself, if you want to see
  exactly how a construct is implemented.
