# NucleusVM parked; dependency made optional

**Date:** 2026-09-07

## What changed

NucleusVM did not deliver the speed-up it was built for when measured, so the
experiment is parked. The compiler (`src/fragbasic_core/vm_compiler/`) and the
`--engine vm` flag both still work and are kept for reference — nothing was
removed.

What did change is how the dependency is declared.

### The problem

`pyproject.toml` listed NucleusVM as a **hard runtime dependency, pinned to an
absolute path on one machine**:

```toml
dependencies = [
    "nucleus-vm @ file:///home/chuck/Dropbox/.../LANGUAGES/NucleusVM",
]
```

It was FragBASIC's *only* runtime dependency, which also made the README's
headline claim untrue — "`src/fragbasic_core` has zero third-party
dependencies — only the Python standard library". A fresh
`pip install -e .` pulled in a package from a path that exists on one machine.

FragBASIC is a public repository. Anyone who cloned it and ran `pip install -e .`
hit an installation failure, because that path does not exist on their machine
— and it failed for a package the default execution path never touches.

### The fix

- `nucleus-vm` moved out of `dependencies` into a new `vm` optional extra.
- `main()` in `src/fragbasic_core/cli.py` now catches `ImportError` around the
  lazy `run_source(..., engine="vm")` call and reports what is missing, rather than
  surfacing a raw traceback:

  ```
  fragbasic: --engine vm needs NucleusVM, which is not installed.
             Install it with:  pip install -e '.[vm]'
             (or drop --engine vm to use the default engine)
  ```

- The README's NucleusVM section says the engine is parked and not installed
  by default, and how to install it from the sibling checkout. With the extra
  removed from `dependencies`, the "zero third-party dependencies" claim is
  true again — a clean install now pulls in nothing at all.
- The VS Code extension's `fragbasic.engine` setting says the same, so the `vm`
  option is not presented as if it were ready to use.

NucleusVM is not on PyPI, so the `vm` extra resolves only against a local
checkout: `pip install -e ../NucleusVM`.

## Verified

- A clean `python -m venv` + `pip install -e .` from a bare checkout now
  succeeds, and `fragbasic` and `fragbasic --check` work in it.
- `--engine vm` in that environment reports the missing dependency and exits 1.
- In a venv that *does* have NucleusVM, `--engine vm` still runs correctly.
- Test suite unchanged: 60 passed.
