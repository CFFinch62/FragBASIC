#!/bin/bash
# FragBASIC — Development environment setup
# Creates a virtual environment and installs the package (editable) + dev deps.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== FragBASIC Development Environment Setup ==="

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
else
    echo "Virtual environment already exists."
fi

echo "Installing dependencies..."
source venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"

echo ""
echo "=== Setup complete! ==="
echo "To activate the environment:  source venv/bin/activate"
echo "To run tests:                 python -m pytest tests/ -v"
echo "To run a .bas file:           ./run.sh examples/hello.bas"
echo "To run inline code:           ./run.sh -c 'PRINT \"hi\"'"
