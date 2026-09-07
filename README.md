# FragBASIC

A standalone, dependency-free educational BASIC interpreter, distributed as a
CLI tool and as an embeddable Python package. FragBASIC is IDE-agnostic by
design: any editor or IDE — [BLADE](../../IDES/IDE_Suite%202/BLADE), or
anything else that can launch a subprocess or import a Python package — can
run FragBASIC programs without bundling a GUI toolkit.

`src/fragbasic_core` has zero third-party dependencies — only the Python
standard library — so it's safe to embed anywhere Python 3.8+ runs.

**[docs/user-guide.md](docs/user-guide.md)** is the full reference: every
keyword, operator, and built-in function, with examples, plus complete CLI
usage. This README covers installing and embedding; the user guide covers
writing FragBASIC programs.

## Getting started

```bash
git clone https://github.com/CFFinch62/FragBASIC.git
cd FragBASIC
```

Then:

```bash
./setup.sh                                # creates venv, installs dev extras
source venv/bin/activate
python -m pytest tests/ -v                # run the interpreter test suite
./run.sh examples/hello.bas                # run a program from source
./run.sh -c 'PRINT "hi"'                   # run inline code
```

To install the `fragbasic` command itself:

```bash
pip install -e .
fragbasic examples/fizzbuzz.bas
```

## CLI usage

```
fragbasic <file.bas>
fragbasic -c "<code>"
fragbasic <file.bas> --timeout <seconds>
fragbasic --check <file.bas>
```

- Program output goes to stdout, flushed after every write (so it streams
  live rather than buffering — important when a parent process, like BLADE's
  `QProcess`, is reading it incrementally).
- `INPUT` reads one line at a time from stdin.
- Errors (lex/parse/runtime) are printed to stderr as a single line:
  `Error on line N: <message>`.
- Exit codes: `0` success, `1` a BASIC-level error, `2` a usage error (bad
  arguments, file not found), `130` execution was cancelled (Ctrl+C,
  SIGTERM, or `--timeout` expired).
- `--timeout` cancels a CPU-bound program between statements. It cannot
  interrupt a program that's blocked waiting on `INPUT` — use Ctrl+C or
  SIGTERM for that instead.
- `--check` lexes and parses without running: nothing is printed, `INPUT`
  never blocks, and it returns immediately. Errors are reported as
  `<path>:<line>: <message>` — prefixed with the file, unlike the bare
  `Error on line N:` a run produces — so an editor or build tool can
  attribute them. Exit `0` if the program parses, `1` if it does not.

## Editor support

[editors/vscode](editors/vscode) is a VS Code extension for `.bas` files:
case-insensitive highlighting for all 61 reserved words and 35 builtins, Run
and Check commands, Run Selection via `-c`, and the Problems panel. It handles
the details a generic BASIC grammar misses — an apostrophe is a comment only at
the start of a line, and a QB64 single-quoted string anywhere else.

## Embedding

```python
from fragbasic_core import run_source, Lexer, Parser, Interpreter

# Quick one-shot run against real stdin/stdout:
run_source(open("program.bas").read())

# Or wire up your own I/O (e.g. an IDE's console pane):
interpreter = Interpreter()
interpreter.set_io_functions(input_func=my_input, output_func=my_output)
tokens = Lexer(source).generate_tokens()
ast = Parser(tokens).parse()
interpreter.interpret(ast)

# Cooperative cancellation (e.g. a Stop button), from another thread:
interpreter.request_cancel()
```

Errors raise `fragbasic_core.LexerError`, `ParseError`, or
`BasicRuntimeError` (all subclasses of `FragBasicError`), each carrying a
`.line_num` and a pre-formatted `.format()` string. A cancelled run raises
`ExecutionCancelled`.

## NucleusVM execution engine (experimental)

FragBASIC can also run programs by compiling them to bytecode for
[NucleusVM](../NucleusVM), a shared VM built to give this and other
Python-hosted teaching languages a faster execution path than tree-walking,
instead of interpreting the AST directly. It's opt-in and additive — the
tree-walking interpreter above remains the default, is untouched by this,
and is what every other section of this README describes.

```bash
fragbasic --engine vm examples/fizzbuzz.bas
```

```python
from fragbasic_core import run_source

run_source(open("program.bas").read(), engine="vm")  # engine="tree" is the default
```

**Status**: a first vertical slice, not the full language yet. It covers
scalars, arithmetic/comparison/logical operators, `IF`/`FOR`/`WHILE`,
1D–3D arrays, `PRINT`, `DATA`/`READ`/`RESTORE`, `SUB`/`FUNCTION`/`CALL`,
and the built-ins real usage across all 100 of the sibling `PROJECT_EULER`
project's Project Euler solutions showed matter (`LEN`, `MID$`, `CHR$`,
`ASC`, `VAL`, `INT`, `FIX`, `SGN`, `SQR`, `RND`, `LEFT$`, `RIGHT$`, `STR$`,
`LOG`, `ABS`, `STRING$`). `GOSUB`, `SELECT CASE`, `DO`/`LOOP`, and `INPUT`
aren't implemented yet (none of those 100 solutions use them either) — an
unsupported construct raises a clear `NotImplementedError` at compile
time rather than running incorrectly. `--timeout`/Ctrl+C cancellation
isn't supported by this engine yet either (only the tree-walker checks
for it); `euler_benchmark.py`-style external process timeouts still work
fine, since those don't depend on FragBASIC's own cancellation hook.

**Verified**: every one of the 100 Project Euler solutions that completes
within a practical time budget under the tree-walker produces
byte-identical stdout under the VM engine too (0 divergences found across
repeated full-corpus sweeps). **Measured faster**, not just architecturally
different: ~3.7x on call-heavy recursive code, ~47% on loop-heavy
arithmetic/comparison code (the shape most Project Euler solutions
actually take) — see NucleusVM's `PROGRESS.md` for the full investigation,
including a real regression this project's own profiling caught and fixed
in NucleusVM's shared core along the way.

## Language

FragBASIC is a teaching-focused BASIC dialect: five value types, arrays up
to 3 dimensions, the usual arithmetic/comparison/logical operators,
`IF`/`SELECT CASE`/`FOR`/`WHILE`/`DO`/`GOSUB` control flow, `SUB`/
`FUNCTION`, `PRINT`/`INPUT`/`DATA`/`READ`, and ~35 built-in math/string/
conversion/system functions. Graphics, sound, and file-system statements
(`LINE`, `CIRCLE`, `SOUND`, `FILES`, `SHELL`, etc.) are intentionally not
implemented — this is a teaching-focused subset, not a full QBasic clone.

**See [docs/user-guide.md](docs/user-guide.md) for the complete language
reference** (every keyword and built-in, with examples) and its "Not
implemented" / limitations notes (`CONST`, `INKEY$` on POSIX, etc.).

For what's missing, why, and what's actually planned versus intentionally
excluded, see
[dev-docs/qbasic-compatibility-roadmap.md](dev-docs/qbasic-compatibility-roadmap.md).

## Design

FragBASIC ships as a structured error hierarchy with line numbers
(`errors.py`), a cooperative cancellation hook usable by an IDE's Stop
button or `--timeout`, and a real (if platform-limited) `INKEY$` — see
`src/fragbasic_core/` for the implementation.

BLADE can run FragBASIC as an interpreter backend alongside Yabasic — see
BLADE's `app/basic_language.py` `BACKENDS` registry.
