"""Repo-root path helpers."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PATTERN_SPEC = REPO_ROOT / "pattern-spec"
DISCOVERY = REPO_ROOT / "horizons" / "discovery"
ENTITLEMENTS = REPO_ROOT / "horizons" / "entitlements"
DEFAULT_CATALOG = DISCOVERY / "catalog" / "v1.json"
DEFAULT_PRICEBOOK = ENTITLEMENTS / "pricebook" / "v1.json"
H1_SCENARIOS = DISCOVERY / "scenarios"
H2_SCENARIOS = ENTITLEMENTS / "scenarios"
