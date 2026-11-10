#!/usr/bin/env bash
# Create .venv (if missing) and install the package editable with dev deps.
# Usage:
#   ./scripts/install.sh
set -euo pipefail
# shellcheck source=/dev/null
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"

if [[ ! -x "${ROOT}/.venv/bin/python" ]]; then
  echo "Creating .venv …"
  if command -v python3 >/dev/null 2>&1; then
    python3 -m venv "${ROOT}/.venv"
  else
    python -m venv "${ROOT}/.venv"
  fi
  PYTHON="${ROOT}/.venv/bin/python"
fi

echo "Installing agentic-commerce-harness (editable + dev) …"
"$PYTHON" -m pip install -U pip
"$PYTHON" -m pip install -e ".[dev]"
echo "Done. PYTHON=${PYTHON}"
