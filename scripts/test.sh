#!/usr/bin/env bash
# Run the full pytest suite (or pass through args).
# Usage:
#   ./scripts/test.sh
#   ./scripts/test.sh tests/test_scenarios.py -q
set -euo pipefail
# shellcheck source=/dev/null
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"

if [[ $# -eq 0 ]]; then
  exec "$PYTHON" -m pytest -q
fi
exec "$PYTHON" -m pytest "$@"
