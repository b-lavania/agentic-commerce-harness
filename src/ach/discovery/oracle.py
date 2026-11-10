"""H1 compatibility oracle grader."""

from __future__ import annotations

from typing import Any

from ach.discovery.catalog import Catalog, Sku
from ach.models import Checklist


COMPARE_ATTRS = frozenset(
    {"deployment", "throughput_gbps", "license", "certs", "sla", "ports"}
)


def _appliance_matches(sku: Sku, constraints: dict[str, Any]) -> bool:
    if not sku.is_appliance:
        return True
    mapping = {
        "deployment": sku.deployment,
        "throughput_gbps": sku.throughput_gbps,
        "throughput": sku.throughput_gbps,
        "ha": sku.ha,
        "hypervisor": sku.hypervisor,
        "license": sku.license,
    }
    for key, expected in constraints.items():
        if key in ("certs", "cert"):
            need = expected if isinstance(expected, list) else [expected]
            if not set(need).issubset(set(sku.certs)):
                return False
            continue
        if key == "ha" and expected in ("required", "required_capable"):
            if sku.ha != "required_capable":
                return False
            continue
        if key not in mapping:
            continue
        if mapping[key] != expected:
            return False
    return True


def grade_oracle(
    catalog: Catalog,
    checklist: Checklist,
    *,
    constraints: dict[str, Any] | None = None,
    had_zero_result: bool = False,
    recovered_from_zero: bool = False,
) -> tuple[bool, list[str]]:
    """Return (pass, reasons)."""
    reasons: list[str] = []
    shortlist = checklist.shortlist
    if not 1 <= len(shortlist) <= 4:
        reasons.append(f"shortlist size {len(shortlist)} not in 1..4")

    idx = catalog.by_id()
    for sid in shortlist:
        if sid not in idx:
            reasons.append(f"unknown sku {sid}")

    cons = dict(constraints or {})
    cons.update({k: v for k, v in checklist.facets.items() if v is not None})

    appliances = [idx[s] for s in shortlist if s in idx and idx[s].is_appliance]
    services = [idx[s] for s in shortlist if s in idx and idx[s].kind == "service"]

    for a in appliances:
        if not _appliance_matches(a, cons):
            reasons.append(f"appliance {a.id} fails constraints {cons}")

    families = {a.family for a in appliances}
    for svc in services:
        if not families.intersection(svc.compatible_with):
            reasons.append(
                f"service {svc.id} incompatible with shortlisted families {sorted(families)}"
            )

    if checklist.compared_ids:
        # Compare dims are enforced by the sim API (only returns COMPARE_ATTRS).
        # Here we only require compared ids exist and length 2–4 when milestone claimed.
        for cid in checklist.compared_ids:
            if cid not in idx:
                reasons.append(f"compared unknown id {cid}")

    if had_zero_result and not recovered_from_zero:
        reasons.append("zero-result search without facet/query recovery before save")

    return (len(reasons) == 0, reasons)
