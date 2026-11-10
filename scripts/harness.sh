#!/usr/bin/env bash
# Run cert scenarios.
# Usage:
#   ./scripts/harness.sh
#   ./scripts/harness.sh --jsonl /tmp/ach-trajectories.jsonl
#   ./scripts/harness.sh run horizons/discovery/scenarios/h1_branch_ngfw.json
set -euo pipefail
# shellcheck source=/dev/null
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"

if [[ $# -eq 0 ]]; then
  exec "$PYTHON" -m ach.harness.cli run-all
fi

if [[ "$1" == "run" ]]; then
  shift
  exec "$PYTHON" -m ach.harness.cli run "$@"
fi

# Default: run-all with optional flags (e.g. --jsonl PATH)
exec "$PYTHON" -m ach.harness.cli run-all "$@"
