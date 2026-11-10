"""Horizon 1 discovery sim — search/facets/compare/addons/shortlist."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ach.discovery.catalog import Catalog, Sku, load_catalog
from ach.discovery.oracle import COMPARE_ATTRS, grade_oracle
from ach.models import Checklist
from ach.paths import DEFAULT_CATALOG, REPO_ROOT


FORBIDDEN = frozenset({"set_amount", "rewrite_sent", "checkout", "create_payment"})


class DiscoverySim:
    def __init__(self, catalog: Catalog | None = None, catalog_path: Path | str | None = None):
        if catalog is not None:
            self.catalog = catalog
        else:
            path = catalog_path or DEFAULT_CATALOG
            if not Path(path).is_absolute():
                path = REPO_ROOT / path
            self.catalog = load_catalog(path)
        self.checklist = Checklist()
        self.last_results: list[str] = []
        self.had_zero_result = False
        self.recovered_from_zero = False
        self._pending_zero = False
        self.history: list[dict[str, Any]] = []

    def observation_hash(self, payload: dict[str, Any]) -> str:
        raw = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _sku_public(self, sku: Sku) -> dict[str, Any]:
        return sku.model_dump()

    def _match(self, sku: Sku, q: str, facets: dict[str, Any]) -> bool:
        text = f"{sku.name} {sku.vendor} {sku.kind} {sku.family} {sku.marketing_blurb}".lower()
        tokens = [t for t in q.lower().replace(",", " ").split() if t]
        # Soft text match: any strong keyword OR empty query with facets
        keyword_hits = {
            "firewall": "ngfw" in sku.family or "firewall" in text or sku.kind != "service",
            "ngfw": "ngfw" in sku.family or "ngfw" in text,
            "branch": True,
            "office": True,
            "2gbps": sku.throughput_gbps == "2_5",
            "ha": sku.ha == "required_capable" or sku.kind == "service",
            "virtual": sku.kind == "virtual" or "virtual" in text,
            "appliance": sku.is_appliance,
            "hybrid": sku.deployment in ("hybrid", "virtual") or sku.kind == "service",
            "cloud": sku.hypervisor == "cloud" or "cloud" in text,
        }
        if tokens:
            # Require kind-ish relevance for appliances when query mentions firewall/virtual
            if any(t in ("firewall", "ngfw") for t in tokens) and sku.kind == "service":
                pass  # services can still appear via facets / later list_addons
            elif any(t in ("firewall", "ngfw") for t in tokens) and "ngfw" not in sku.family and "firewall" not in text and sku.kind == "physical":
                if sku.family.startswith("swg") or sku.family.startswith("ids"):
                    return False
            if "virtual" in tokens and sku.kind == "physical":
                return False

        for key, val in facets.items():
            if val is None:
                continue
            if key in ("deployment",) and sku.is_appliance and sku.deployment != val:
                return False
            if key in ("throughput_gbps", "throughput") and sku.is_appliance and sku.throughput_gbps != val:
                return False
            if key == "ha":
                if sku.is_appliance:
                    need = "required_capable" if val in ("required", "required_capable") else val
                    if sku.ha != need:
                        return False
            if key == "hypervisor" and sku.is_appliance and sku.hypervisor != val:
                return False
            if key == "license" and sku.is_appliance and sku.license != val:
                return False
            if key in ("certs", "cert"):
                need = val if isinstance(val, list) else [val]
                if sku.is_appliance and not set(need).issubset(set(sku.certs)):
                    return False
            if key == "kind" and sku.kind != val:
                return False
            if key == "sla" and sku.sla != val and sku.kind != "service":
                # allow services through unless explicitly filtered
                if sku.is_appliance and sku.sla != val:
                    return False
        return True

    def search(self, q: str = "", **_: Any) -> dict[str, Any]:
        self.checklist.intent = q or self.checklist.intent
        facets = self.checklist.facets
        hits = [s for s in self.catalog.skus if s.kind != "service" and self._match(s, q, facets)]
        # Prefer appliances in search results; services via list_addons
        self.last_results = [s.id for s in hits]
        if not hits:
            self.had_zero_result = True
            self._pending_zero = True
        else:
            if self._pending_zero:
                self.recovered_from_zero = True
                self._pending_zero = False
        payload = {
            "action": "search",
            "count": len(hits),
            "results": [self._sku_public(s) for s in hits[:20]],
        }
        self.history.append(payload)
        return payload

    def set_facets(self, **facets: Any) -> dict[str, Any]:
        # Map scenario ha=required → internal
        cleaned = dict(facets)
        if "throughput" in cleaned and "throughput_gbps" not in cleaned:
            cleaned["throughput_gbps"] = cleaned.pop("throughput")
        self.checklist.facets.update({k: v for k, v in cleaned.items() if v is not None})
        self.checklist.milestones.add("facets_applied")
        if self._pending_zero:
            self.recovered_from_zero = True
            self._pending_zero = False
        # Re-run search with same intent for convenience
        q = self.checklist.intent or ""
        return {"action": "set_facets", "facets": self.checklist.facets, **self.search(q=q)}

    def compare(self, ids: list[str] | None = None, **_: Any) -> dict[str, Any]:
        ids = list(ids or [])
        if not 2 <= len(ids) <= 4:
            return {"action": "compare", "ok": False, "error": "compare requires 2–4 ids"}
        idx = self.catalog.by_id()
        rows = []
        for i in ids:
            if i not in idx:
                return {"action": "compare", "ok": False, "error": f"unknown {i}"}
            sku = idx[i]
            rows.append({k: getattr(sku, k) for k in COMPARE_ATTRS if hasattr(sku, k)})
            rows[-1]["id"] = i
        self.checklist.compared_ids = ids
        self.checklist.milestones.add("compared")
        payload = {"action": "compare", "ok": True, "rows": rows, "dimensions": sorted(COMPARE_ATTRS)}
        self.history.append(payload)
        return payload

    def list_addons(self, appliance_id: str, **_: Any) -> dict[str, Any]:
        idx = self.catalog.by_id()
        if appliance_id not in idx:
            return {"action": "list_addons", "ok": False, "error": "unknown appliance"}
        appliance = idx[appliance_id]
        if not appliance.is_appliance:
            return {"action": "list_addons", "ok": False, "error": "not an appliance"}
        addons = [
            s
            for s in self.catalog.skus
            if s.kind == "service" and appliance.family in s.compatible_with
        ]
        # Also surface incompatible offer for reject scenarios (SkyFence premium)
        offered_incompatible = [
            s
            for s in self.catalog.skus
            if s.kind == "service" and appliance.family not in s.compatible_with
        ][:1]
        ids = [s.id for s in addons]
        self.checklist.listed_addon_ids = list(
            dict.fromkeys(self.checklist.listed_addon_ids + ids + [s.id for s in offered_incompatible])
        )
        if ids or offered_incompatible:
            self.checklist.milestones.add("addon_in_path")
        payload = {
            "action": "list_addons",
            "ok": True,
            "compatible": [self._sku_public(s) for s in addons],
            "incompatible_offers": [self._sku_public(s) for s in offered_incompatible],
        }
        self.history.append(payload)
        return payload

    def attach_addon(self, service_id: str, **_: Any) -> dict[str, Any]:
        idx = self.catalog.by_id()
        if service_id not in idx or idx[service_id].kind != "service":
            return {"action": "attach_addon", "ok": False, "error": "unknown service"}
        self.checklist.attached_addons.append(service_id)
        self.checklist.milestones.add("addon_in_path")
        payload = {"action": "attach_addon", "ok": True, "service_id": service_id}
        self.history.append(payload)
        return payload

    def save_shortlist(self, ids: list[str] | None = None, **_: Any) -> dict[str, Any]:
        ids = list(ids or [])
        # Include attached addons if not already listed
        for a in self.checklist.attached_addons:
            if a not in ids:
                ids.append(a)
        self.checklist.shortlist = ids
        self.checklist.milestones.add("shortlist_saved")
        ok, reasons = grade_oracle(
            self.catalog,
            self.checklist,
            constraints=self.checklist.facets,
            had_zero_result=self.had_zero_result,
            recovered_from_zero=self.recovered_from_zero,
        )
        payload = {
            "action": "save_shortlist",
            "ok": ok,
            "shortlist": ids,
            "oracle_pass": ok,
            "oracle_reasons": reasons,
        }
        self.history.append(payload)
        return payload

    def step(self, action: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        body = dict(body or {})
        if action in FORBIDDEN:
            self.checklist.forbidden_hits.append(action)
            return {"action": action, "ok": False, "error": "forbidden", "forbidden": True}
        handlers = {
            "search": self.search,
            "set_facets": self.set_facets,
            "compare": self.compare,
            "list_addons": self.list_addons,
            "attach_addon": self.attach_addon,
            "save_shortlist": self.save_shortlist,
        }
        if action not in handlers:
            return {"action": action, "ok": False, "error": f"unknown action {action}"}
        # Normalize list bodies
        if action == "compare" and "ids" in body:
            return handlers[action](ids=body["ids"])
        if action == "save_shortlist" and "ids" in body:
            return handlers[action](ids=body["ids"])
        if action == "list_addons":
            return handlers[action](appliance_id=body.get("appliance_id", ""))
        if action == "attach_addon":
            return handlers[action](service_id=body.get("service_id", ""))
        if action == "search":
            return handlers[action](q=body.get("q", ""))
        if action == "set_facets":
            return handlers[action](**{k: v for k, v in body.items() if k != "action"})
        return handlers[action](**body)
