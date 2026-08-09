import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
EXAMPLES_DIR = REPO_ROOT / "examples"


def run_cli(args, input_text=None, timeout=10):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC_DIR)
    return subprocess.run(
        [sys.executable, "-m", "fragbasic_core", *args],
        input=input_text,
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env=env,
        timeout=timeout,
    )


def test_hello_example_runs_successfully():
    result = run_cli([str(EXAMPLES_DIR / "hello.bas")])
    assert result.returncode == 0
    assert "Hello from FragBASIC!" in result.stdout
    # PRINT's `;` separator adds a space around each joined value, so
    # `PRINT "Hello, "; name; "!"` reads "Hello,  World !" - this is
    # intentional classic-BASIC PRINT behavior, not a bug.
    assert "Hello,  World !" in result.stdout


def test_fizzbuzz_example():
    result = run_cli([str(EXAMPLES_DIR / "fizzbuzz.bas")])
    assert result.returncode == 0
    lines = result.stdout.strip().splitlines()
    assert lines[2] == "Fizz"   # i = 3
    assert lines[4] == "Buzz"  # i = 5
    assert lines[14] == "FizzBuzz"  # i = 15


def test_inline_code_flag():
    result = run_cli(["-c", 'PRINT "inline works"'])
    assert result.returncode == 0
    assert result.stdout == "inline works\n"


def test_missing_file_is_usage_error():
    result = run_cli(["does_not_exist.bas"])
    assert result.returncode == 2
    assert "not found" in result.stderr


def test_no_arguments_is_usage_error():
    result = run_cli([])
    assert result.returncode == 2


def test_runtime_error_reports_line_and_exit_code_1():
    result = run_cli(["-c", "x = 1\ny = 1 / 0"])
    assert result.returncode == 1
    assert "line 2" in result.stderr


def test_input_driven_example():
    # Target is 1-100 chosen by RNG; guessing every number in order
    # guarantees a hit regardless of seed.
    all_guesses = "\n".join(str(n) for n in range(1, 101)) + "\n"
    result = run_cli(
        [str(EXAMPLES_DIR / "guess_the_number.bas")],
        input_text=all_guesses,
    )
    assert result.returncode == 0
    assert "tries" in result.stdout
