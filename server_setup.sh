#!/usr/bin/env bash
# Cross-platform friendly setup script for Linux/macOS environments
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_ROOT/mcp_env"
PYTHON_BIN=${PYTHON_BIN:-python3}

log() {
  echo "[setup] $1"
}

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "ERROR: Could not find Python interpreter ('$PYTHON_BIN')." >&2
  echo "Please install Python 3.9+ and re-run this script." >&2
  exit 1
fi

log "Creating virtual environment at $VENV_DIR"
"$PYTHON_BIN" -m venv "$VENV_DIR"

# shellcheck disable=SC1090
source "$VENV_DIR/bin/activate"

log "Upgrading pip"
python -m pip install --upgrade pip

log "Installing Python dependencies"
pip install -r "$PROJECT_ROOT/requirements.txt"

log "Ensuring bundled libclang is available"
python "$PROJECT_ROOT/scripts/download_libclang.py"

cat <<'MSG'
========================================
Setup Complete!
========================================
✓ Virtual environment ready
✓ Python dependencies installed
✓ libclang checked (see output above)

Next steps:
  1. Activate the environment: source mcp_env/bin/activate
  2. Run tests: python scripts/test_installation.py

MSG
