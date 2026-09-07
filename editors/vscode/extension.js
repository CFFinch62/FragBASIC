// FragBASIC Language extension — run/check commands for .bas files.
//
// Syntax highlighting, editor behaviours and snippets are entirely
// declarative (package.json + the grammar + language-configuration.json);
// none of them need this file. Everything here exists only to drive the
// `fragbasic` command and turn its errors into entries in the Problems panel.

const vscode = require('vscode');
const cp = require('child_process');
const path = require('path');

/** `fragbasic --check` reports `<path>:<line>: <message>` — it prefixes the
 *  file precisely so an editor knows what the line number belongs to. */
const CHECK_RE = /^(.*?):(\d+):\s+(.*)$/;

/** A failing run reports FragBasicError's own format, `Error on line <n>:
 *  <message>` (fragbasic_core/errors.py), which names no file and no column.
 *  Diagnostics from a run are therefore pinned to the file that was run. */
const RUN_RE = /^Error on line (\d+):\s+(.*)$/;

let diagnostics = null;
let output = null;

function config() {
  return vscode.workspace.getConfiguration('fragbasic');
}

function interpreter() {
  return config().get('interpreterPath', 'fragbasic') || 'fragbasic';
}

/** Quote a path or literal for a shell command line (the terminal path). */
function shellQuote(p) {
  if (process.platform === 'win32') return `"${String(p).replace(/"/g, '""')}"`;
  return `'${String(p).replace(/'/g, `'\\''`)}'`;
}

/** Engine and timeout apply to running, not to --check. */
function runFlags() {
  const cfg = config();
  const flags = [];
  const engine = cfg.get('engine', 'tree');
  if (engine && engine !== 'tree') flags.push('--engine', engine);
  const timeout = cfg.get('timeout', null);
  if (typeof timeout === 'number' && timeout > 0) {
    flags.push('--timeout', String(timeout));
  }
  return flags;
}

async function activeBasicDocument() {
  const editor = vscode.window.activeTextEditor;
  if (!editor || editor.document.languageId !== 'fragbasic') {
    vscode.window.showErrorMessage('FragBASIC: no .bas file is active.');
    return null;
  }
  if (config().get('saveBeforeRun', true) && editor.document.isDirty) {
    await editor.document.save();
  }
  return editor.document;
}

/** Run in the integrated terminal — output appears live and INPUT works.
 *  One reused terminal per workspace. */
function runInTerminal(doc, args) {
  let term = vscode.window.terminals.find((t) => t.name === 'FragBASIC');
  if (!term) {
    term = vscode.window.createTerminal({
      name: 'FragBASIC',
      cwd: path.dirname(doc.fileName),
    });
  }
  term.show(true);
  // Quote anything that is not a bare flag, so a path with spaces and a -c
  // snippet containing quotes and newlines both survive the shell.
  const isFlag = (a) => /^--[a-z-]+$/.test(a) || /^-[a-zA-Z]$/.test(a);
  const parts = [
    shellQuote(interpreter()),
    ...args.map((a) => (isFlag(a) ? a : shellQuote(a))),
  ];
  term.sendText(parts.join(' '));
}

/** Run as a child process — output goes to an Output channel and errors
 *  become squiggles in the editor via the Problems panel. */
function runInOutputChannel(doc, args, label) {
  if (!output) output = vscode.window.createOutputChannel('FragBASIC');
  output.clear();
  output.show(true);

  const exe = interpreter();
  output.appendLine(`> ${exe} ${args.join(' ')}`);
  output.appendLine('');

  const started = Date.now();
  const child = cp.spawn(exe, args, { cwd: path.dirname(doc.fileName) });

  let stderr = '';
  child.stdout.on('data', (d) => output.append(d.toString()));
  child.stderr.on('data', (d) => {
    const text = d.toString();
    stderr += text;
    output.append(text);
  });

  child.on('error', (err) => reportSpawnError(err, exe));

  child.on('close', (code) => {
    if (!reportMissingCheck(stderr, args)) {
      publishDiagnostics(doc, stderr);
    }
    output.appendLine('');
    output.appendLine(
      `[${label} exit ${code} in ${((Date.now() - started) / 1000).toFixed(2)}s]`
    );
  });

  // A program that reads INPUT would otherwise wait forever on a pipe with
  // nothing behind it. Closing stdin makes it fail fast with EOF instead.
  child.stdin.end();
}

function reportSpawnError(err, exe) {
  if (err.code === 'ENOENT') {
    vscode.window
      .showErrorMessage(
        `FragBASIC: '${exe}' not found. Run 'pip install -e .' in the FragBASIC repo, or set fragbasic.interpreterPath.`,
        'Open Settings'
      )
      .then((choice) => {
        if (choice === 'Open Settings') {
          vscode.commands.executeCommand(
            'workbench.action.openSettings',
            'fragbasic.interpreterPath'
          );
        }
      });
  } else {
    vscode.window.showErrorMessage(`FragBASIC: ${err.message}`);
  }
}

/** `--check` was added after the first release, so an older install rejects it
 *  at the argument parser. Say so plainly rather than letting argparse's usage
 *  dump land in the Problems panel as a mystery. */
function reportMissingCheck(stderr, args) {
  if (!args.includes('--check')) return false;
  if (!/unrecognized arguments: --check|no such option: --check/.test(stderr)) {
    return false;
  }
  vscode.window.showWarningMessage(
    'FragBASIC: this install of `fragbasic` has no --check flag. Update the FragBASIC package, or use Run instead.'
  );
  return true;
}

/** Turn error lines from stderr into editor squiggles.
 *
 *  Two formats reach here: `--check` emits `<path>:<line>: <message>`, while a
 *  failing run emits `Error on line <n>: <message>` with no path at all. The
 *  second is pinned to `doc`, which is correct because that is the file we
 *  asked FragBASIC to run. */
function publishDiagnostics(doc, stderr) {
  const byFile = new Map();

  const add = (uri, line, message) => {
    // FragBASIC reports 1-based lines and no column; underline the whole line.
    const lineNo = Math.max(0, parseInt(line, 10) - 1);
    const diag = new vscode.Diagnostic(
      new vscode.Range(lineNo, 0, lineNo, Number.MAX_SAFE_INTEGER),
      message,
      vscode.DiagnosticSeverity.Error
    );
    diag.source = 'fragbasic';
    const key = uri.toString();
    if (!byFile.has(key)) byFile.set(key, { uri, items: [] });
    byFile.get(key).items.push(diag);
  };

  for (const raw of stderr.split('\n')) {
    const line = raw.trim();
    if (!line) continue;

    const run = RUN_RE.exec(line);
    if (run) {
      add(doc.uri, run[1], run[2]);
      continue;
    }

    const chk = CHECK_RE.exec(line);
    // Guard against a Windows drive letter ("C:\...") being read as the line
    // number, and against ordinary prose that happens to contain a colon.
    if (chk && /^\d+$/.test(chk[2])) {
      const uri = vscode.Uri.file(
        path.resolve(path.dirname(doc.fileName), chk[1])
      );
      add(uri, chk[2], chk[3]);
    }
  }

  diagnostics.clear();
  for (const { uri, items } of byFile.values()) {
    diagnostics.set(uri, items);
  }
}

/** `fragbasic --check` in the background, for checkOnSave. */
function checkQuietly(doc) {
  const child = cp.spawn(interpreter(), ['--check', doc.fileName], {
    cwd: path.dirname(doc.fileName),
  });

  let stderr = '';
  child.stderr.on('data', (d) => (stderr += d.toString()));
  // A missing interpreter would fire on every save -- stay silent and let the
  // explicit commands be the ones that complain.
  child.on('error', () => {});
  child.on('close', () => {
    if (/unrecognized arguments: --check/.test(stderr)) return;
    publishDiagnostics(doc, stderr);
  });
  child.stdin.end();
}

async function run() {
  const doc = await activeBasicDocument();
  if (!doc) return;
  const args = [...runFlags(), doc.fileName];
  if (config().get('runInTerminal', true)) runInTerminal(doc, args);
  else runInOutputChannel(doc, args, 'run');
}

/** Parse-only: never executes, so nothing is printed and INPUT never blocks. */
async function checkFile() {
  const doc = await activeBasicDocument();
  if (!doc) return;
  runInOutputChannel(doc, ['--check', doc.fileName], 'check');
}

/** Run just the selected lines via -c, for trying a fragment in isolation. */
async function runSelection() {
  const editor = vscode.window.activeTextEditor;
  if (!editor || editor.document.languageId !== 'fragbasic') {
    vscode.window.showErrorMessage('FragBASIC: no .bas file is active.');
    return;
  }
  const text = editor.document.getText(editor.selection);
  if (!text.trim()) {
    vscode.window.showInformationMessage(
      'FragBASIC: select the lines you want to run first.'
    );
    return;
  }
  const args = [...runFlags(), '-c', text];
  if (config().get('runInTerminal', true)) {
    runInTerminal(editor.document, args);
  } else {
    runInOutputChannel(editor.document, args, 'run selection');
  }
}

function activate(context) {
  diagnostics = vscode.languages.createDiagnosticCollection('fragbasic');

  context.subscriptions.push(
    diagnostics,
    vscode.commands.registerCommand('fragbasic.runFile', run),
    vscode.commands.registerCommand('fragbasic.checkFile', checkFile),
    vscode.commands.registerCommand('fragbasic.runSelection', runSelection),

    // A file's errors are stale the moment it is edited.
    vscode.workspace.onDidChangeTextDocument((e) => {
      if (e.document.languageId === 'fragbasic') {
        diagnostics.delete(e.document.uri);
      }
    }),

    vscode.workspace.onDidSaveTextDocument((doc) => {
      if (doc.languageId === 'fragbasic' && config().get('checkOnSave', false)) {
        checkQuietly(doc);
      }
    })
  );
}

function deactivate() {
  if (output) output.dispose();
}

module.exports = { activate, deactivate };
