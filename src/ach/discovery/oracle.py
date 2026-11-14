"""H1 compatibility oracle grader."""

from __future__ import annotations

from typing import Any

from ach.discovery.catalog import Catalog, Sku
from ach.models import Checklist


COMPARE_ATTRS = frozenset(
    {"deployment", "perf", "license", "certs", "sla", "ports"}
)


def _appliance_matches(sku: Sku, constraints: dict[str, Any]) -> bool:
    if not sku.is_appliance:
        return True
    mapping = {
        "deployment": sku.deployment,
        "perf": sku.perf,
        "spare": sku.spare,
        "os": sku.os,
        "license": sku.license,
    }
    for key, expected in constraints.items():
        if key in ("certs", "cert"):
            need = expected if isinstance(expected, list) else [expected]
            if not set(need).issubset(set(sku.certs)):
                return False
            continue
        if key == "spare" and expected in ("required", "ready"):
            if sku.spare != "ready":
                return False
            continue
        if key not in mapping:
            continue
        if mapping[key] != expected:
            return False
    return True


def _wants_minimize_recurring(preferences: list[dict[str, Any]] | None) -> bool:
    for pref in preferences or []:
        if pref.get("minimize_recurring"):
            return True
    return False


def _price_map(pricebook: Any) -> dict[str, dict[str, int]]:
    if pricebook is None:
        from ach.entitlements.sim import load_pricebook

        pricebook = load_pricebook()
    if hasattr(pricebook, "prices"):
        return pricebook.prices
    return pricebook


def grade_oracle(
    catalog: Catalog,
    checklist: Checklist,
    *,
    constraints: dict[str, Any] | None = None,
    had_zero_result: bool = False,
    recovered_from_zero: bool = False,
    preferences: list[dict[str, Any]] | None = None,
    pricebook: Any = None,
) -> tuple[bool, list[str]]:
    """Return (pass, reasons).

    Rank, sponsored, platform_pick, and marketing_blurb are not inputs.
    When preferences are set, the graded ids are checklist.committed.
    """
    reasons: list[str] = []
    if preferences:
        if not checklist.committed:
            reasons.append("preferences require commit_shortlist")
            pool = list(checklist.shortlist)
        else:
            pool = list(checklist.committed)
    else:
        pool = list(checklist.shortlist)

    if not 1 <= len(pool) <= 4:
        reasons.append(f"shortlist size {len(pool)} not in 1..4")

    idx = catalog.by_id()
    for sid in pool:
        if sid not in idx:
            reasons.append(f"unknown sku {sid}")

    cons = dict(constraints or {})
    cons.update({k: v for k, v in checklist.facets.items() if v is not None})

    appliances = [idx[s] for s in pool if s in idx and idx[s].is_appliance]
    services = [idx[s] for s in pool if s in idx and idx[s].kind == "service"]

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
        for cid in checklist.compared_ids:
            if cid not in idx:
                reasons.append(f"compared unknown id {cid}")

    if had_zero_result and not recovered_from_zero:
        reasons.append("zero-result search without facet/query recovery before save")

    if _wants_minimize_recurring(preferences) and not any(
        r.startswith("preferences require") for r in reasons
    ):
        prices = _price_map(pricebook)
        candidates = [
            s for s in catalog.skus if s.is_appliance and _appliance_matches(s, cons)
        ]
        scored: list[tuple[int, str]] = []
        for cand in candidates:
            rec = prices.get(cand.id, {}).get("recurring")
            if rec is None:
                continue
            scored.append((int(rec), cand.id))
        scored.sort()
        if not scored:
            reasons.append("no priced constraint-matching appliance")
        else:
            winner = scored[0][1]
            ties = [sid for cents, sid in scored if cents == scored[0][0]]
            if len(ties) != 1:
                reasons.append("preference winner is not unique")
            committed_apps = [a.id for a in appliances]
            if committed_apps != [winner]:
                reasons.append(
                    f"committed appliances {committed_apps} are not preference winner {winner}"
                )

    return (len(reasons) == 0, reasons)
