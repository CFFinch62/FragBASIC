# FragBASIC Language — VS Code extension

Syntax highlighting, editor behaviours, snippets and one-key running for
[FragBASIC](https://github.com/CFFinch62/FragBASIC) (`.bas` files).

## Getting FragBASIC

This extension highlights and runs `.bas` files — it does not bundle the
interpreter.

> **Note:** FragBASIC is not published on GitHub yet, so
> <https://github.com/CFFinch62/FragBASIC> is not live. The manifest already
> points there for when it is; until then, build from your local checkout.

FragBASIC is free and open source under the **MIT License**, as is this
extension.

```sh
cd FragBASIC          # your local checkout
pip install -e .
```

That puts `fragbasic` on your `PATH`. `fragbasic_core` has no third-party
dependencies — only the Python standard library. If it lives in a virtualenv,
point `fragbasic.interpreterPath` (below) at it with an absolute path.

## What it does

**Syntax highlighting** for all 61 reserved words and the 35 builtin
functions, split by role — statements, type and declaration keywords, word
operators (`AND`, `MOD`, `EQV`…) and builtins each get their own scope.
Matching is case-insensitive, because the lexer upper-cases before comparing:
`print`, `Print` and `PRINT` all highlight the same.

It also handles the details a generic BASIC grammar gets wrong:

- **An apostrophe is a comment only at the start of a line.** Anywhere else it
  opens a QB64 single-quoted string, so `PRINT 'inline'` is a string while
  `' note` is a comment.
- `REM` comments out the rest of the line wherever it appears, but `REMEMBER`
  is just an identifier.
- Type sigils are part of the name: `LEFT$` is a builtin, `name$` a string
  variable, `count%` an integer one.
- A leading number on a line is highlighted as a line number, not arithmetic.

**Editor behaviours** — `'` comment toggling, bracket matching, auto-closing
pairs, and indentation that follows the block keywords: `IF … THEN` / `FOR` /
`WHILE` / `DO` / `SUB` / `FUNCTION` / `SELECT CASE` indent, and `END IF`,
`NEXT`, `WEND`, `LOOP`, `ELSE` and `CASE` dedent. A single-line
`IF x = 1 THEN PRINT "one"` correctly does *not* indent. Folding is
marker-based, since FragBASIC blocks are delimited by keywords rather than by
indentation.

**Snippets** for every block form, `SUB`/`FUNCTION`, `DIM`, `TYPE`,
`DATA`/`READ`, `INPUT`, and a `RANDOMIZE TIMER` starter.

**Commands** — each also available from the Command Palette:

| Command | Default key | What it runs |
|---|---|---|
| FragBASIC: Run File | `Ctrl+F5` | `fragbasic <file>` |
| FragBASIC: Check for Errors | `Ctrl+Shift+F5` | `fragbasic --check <file>` |
| FragBASIC: Run Selection | — | `fragbasic -c "<selection>"` |

**Problems panel** — errors become squiggles in the editor. **Check for
Errors** parses without executing, so nothing is printed and `INPUT` never
blocks. A file's errors are cleared as soon as you edit it.

## Settings

| Setting | Default | Purpose |
|---|---|---|
| `fragbasic.interpreterPath` | `fragbasic` | Path to the `fragbasic` command |
| `fragbasic.saveBeforeRun` | `true` | Save before running or checking |
| `fragbasic.runInTerminal` | `true` | Run in a terminal so `INPUT` works |
| `fragbasic.checkOnSave` | `false` | Run `--check` on every save |
| `fragbasic.timeout` | *(none)* | Seconds before a running program is cancelled |
| `fragbasic.engine` | `tree` | `tree` interpreter, or `vm` for NucleusVM bytecode |

## Why Run and Check are separate

FragBASIC reports errors as `Error on line 4: message` — no filename, no
column. That is the right thing to show a beginner, but not enough for a task
runner to attribute the error to a file.

So the extension parses that format itself and pins those diagnostics to the
file it just ran. `fragbasic --check` sidesteps the problem by printing
`<path>:<line>: <message>`, which is why it is the command bound to a key and
the one `tasks.example.json` attaches a problem matcher to.

Keep `fragbasic.runInTerminal` on — it is what makes `INPUT` work — and use
**Check for Errors** when you want the Problems panel.

## About `.bas`

`.bas` is a crowded extension. This extension claims it for FragBASIC, matching
how the MyCode editor resolves the same overlap; BEAM takes `.yab` instead. If
you also have another BASIC extension installed, VS Code will let you pick the
language for a given file from the status bar.

## Installing from source

```sh
cd editors/vscode
npx @vscode/vsce package
code --install-extension fragbasic-language-0.1.0.vsix
```

## Without the extension

`tasks.example.json` in this directory sets up the same check and run tasks
using only VS Code's built-in task runner and problem matcher — no extension
required. Copy it to your project's `.vscode/tasks.json`.

## License

MIT — see [LICENSE](LICENSE).
