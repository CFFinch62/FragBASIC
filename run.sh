#!/bin/bash
# FragBASIC — Development launcher
# Runs the interpreter from source (activates venv if it exists).

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if [ -d "venv" ]; then
    source venv/bin/activate
fi

PYTHONPATH=src python3 -m fragbasic_core "$@"
