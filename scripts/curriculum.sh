#!/usr/bin/env bash
# H1 → H2 curriculum driver (no Counter).
# Usage:
#   ./scripts/curriculum.sh
#   ./scripts/curriculum.sh --h1 horizons/discovery/scenarios/h1_virtual_bundle.json
#   ./scripts/curriculum.sh --out /tmp/handoff.json
set -euo pipefail
# shellcheck source=/dev/null
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"

exec "$PYTHON" -m ach.driver.curriculum "$@"
