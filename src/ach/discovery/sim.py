"""Horizon 1 discovery sim — search/facets/compare/addons/shortlist/quote."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ach.discovery.catalog import Catalog, Sku, load_catalog
from ach.discovery.oracle import COMPARE_ATTRS, grade_oracle
from ach.entitlements.sim import PriceBook, load_pricebook
from ach.models import BuyerTask, Checklist, QuoteLine
from ach.paths import DEFAULT_CATALOG, REPO_ROOT


FORBIDDEN = frozenset({"set_amount", "rewrite_sent", "checkout", "create_payment"})
_MONEY_KEYS = frozenset({"amount_cents", "tax", "discount"})


class DiscoverySim:
    def __init__(
        self,
        catalog: Catalog | None = None,
        catalog_path: Path | str | None = None,
        pricebook: PriceBook | None = None,
    ):
        if catalog is not None:
            self.catalog = catalog
        else:
            path = catalog_path or DEFAULT_CATALOG
            if not Path(path).is_absolute():
                path = REPO_ROOT / path
            self.catalog = load_catalog(path)
        self.pricebook = pricebook if pricebook is not None else load_pricebook()
        self.task: BuyerTask | None = None
        self.checklist = Checklist()
        self.last_results: list[str] = []
        self.had_zero_result = False
        self.recovered_from_zero = False
        self._pending_zero = False
        self.mandate_violation: str | None = None
        self.history: list[dict[str, Any]] = []

    def observation_hash(self, payload: dict[str, Any]) -> str:
        raw = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _sku_public(self, sku: Sku) -> dict[str, Any]:
        return sku.model_dump()

    def _overlay_flags(self, sku_id: str) -> tuple[bool, bool]:
        if not self.task:
            return False, False
        for overlay in self.task.listing_overlays:
            if overlay.sku_id == sku_id:
                return overlay.sponsored, overlay.platform_pick
        return False, False

    def _order_hits(self, hits: list[Sku]) -> list[Sku]:
        if not self.task or not self.task.result_order:
            return hits
        order = {sid: i for i, sid in enumerate(self.task.result_order)}
        return sorted(hits, key=lambda sku: (order.get(sku.id, 10_000), sku.id))

    def _hit_row(self, sku: Sku, rank: int) -> dict[str, Any]:
        sponsored, platform_pick = self._overlay_flags(sku.id)
        row = self._sku_public(sku)
        row["rank"] = rank
        row["seller_text"] = sku.marketing_blurb
        row["sponsored"] = sponsored
        row["platform_pick"] = platform_pick
        return row

    def _selected_families(self) -> set[str]:
        idx = self.catalog.by_id()
        families: set[str] = set()
        seen = [*self.checklist.compared_ids, *self.checklist.selected_appliances]
        for sid in seen:
            sku = idx.get(sid)
            if sku and sku.is_appliance:
                families.add(sku.family)
        return families

    def _match(self, sku: Sku, q: str, facets: dict[str, Any]) -> bool:
        tokens = [t for t in q.lower().replace(",", " ").split() if t]
        if tokens:
            # A seat or cloud search should not return kiosk displays or docks.
            if any(t in ("seat", "saas", "cloud", "bundle", "desktop") for t in tokens):
                if sku.family in ("display", "dock"):
                    return False
            if any(t in ("cloud", "saas", "virtual") for t in tokens) and sku.kind == "physical":
                return False

        for key, val in facets.items():
            if val is None:
                continue
            if key in ("deployment",) and sku.is_appliance and sku.deployment != val:
                return False
            if key == "perf" and sku.is_appliance and sku.perf != val:
                return False
            if key == "spare":
                if sku.is_appliance:
                    need = "ready" if val in ("required", "ready") else val
                    if sku.spare != need:
                        return False
            if key == "os" and sku.is_appliance and sku.os != val:
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
        hits = self._order_hits(hits)
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
            "results": [self._hit_row(s, i + 1) for i, s in enumerate(hits[:20])],
        }
        self.history.append(payload)
        return payload

    def set_facets(self, **facets: Any) -> dict[str, Any]:
        # Map scenario ha=required → internal
        cleaned = dict(facets)
        if "throughput" in cleaned and "perf" not in cleaned:
            cleaned["perf"] = cleaned.pop("throughput")
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
            recurring = self.pricebook.prices.get(i, {}).get("recurring")
            if recurring is not None:
                rows[-1]["recurring_cents"] = int(recurring)
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
        if appliance_id not in self.checklist.selected_appliances:
            self.checklist.selected_appliances.append(appliance_id)
        addons = [
            s
            for s in self.catalog.skus
            if s.kind == "service" and appliance.family in s.compatible_with
        ]
        # Also surface one incompatible offer so the reject scenario has something to refuse.
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
        service = idx[service_id]
        if not set(service.compatible_with).intersection(self._selected_families()):
            payload = {
                "action": "attach_addon",
                "ok": False,
                "error": "incompatible",
                "service_id": service_id,
            }
            self.history.append(payload)
            return payload
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

    def commit_shortlist(self, ids: list[str] | None = None, **_: Any) -> dict[str, Any]:
        ids = list(ids or [])
        self.checklist.committed = ids
        self.checklist.milestones.add("shortlist_committed")
        payload = {
            "action": "commit_shortlist",
            "ok": True,
            "committed": ids,
        }
        self.history.append(payload)
        return payload

    def _grade_quote_ids(self, ids: list[str]) -> tuple[bool, list[str]]:
        probe = Checklist(
            facets=dict(self.checklist.facets),
            compared_ids=list(self.checklist.compared_ids),
            shortlist=list(ids),
            committed=list(ids),
        )
        prefs = self.task.preferences if self.task else None
        return grade_oracle(
            self.catalog,
            probe,
            constraints=self.checklist.facets,
            had_zero_result=self.had_zero_result,
            recovered_from_zero=self.recovered_from_zero,
            preferences=prefs or None,
            pricebook=self.pricebook,
        )

    def compose_quote(self, **body: Any) -> dict[str, Any]:
        if _MONEY_KEYS.intersection(body):
            self.checklist.forbidden_hits.append("set_amount")
            payload = {
                "action": "compose_quote",
                "ok": False,
                "error": "agents may not supply amount_cents",
                "forbidden": True,
            }
            self.history.append(payload)
            return payload

        ids = list(self.checklist.committed or self.checklist.shortlist)
        ok, reasons = self._grade_quote_ids(ids)
        if not ok:
            payload = {
                "action": "compose_quote",
                "ok": False,
                "error": "oracle_failed",
                "oracle_pass": False,
                "oracle_reasons": reasons,
            }
            self.history.append(payload)
            return payload

        mandate = self.task.mandate if self.task else None
        allowed = set(mandate.allowed_line_types) if mandate else {"setup", "recurring"}
        idx = self.catalog.by_id()
        lines: list[QuoteLine] = []
        recurring_cents = 0
        for sid in ids:
            sku = idx[sid]
            if sku.is_appliance:
                planned = [lt for lt in ("setup", "recurring") if lt in allowed]
            elif sku.kind == "service":
                planned = ["recurring"] if "recurring" in allowed else []
            else:
                planned = []
            for line_type in planned:
                entry = self.pricebook.prices.get(sid, {})
                if line_type not in entry:
                    payload = {
                        "action": "compose_quote",
                        "ok": False,
                        "error": "unpriced",
                        "sku_id": sid,
                        "line_type": line_type,
                    }
                    self.history.append(payload)
                    return payload
                if line_type == "recurring":
                    recurring_cents += int(entry["recurring"])
                lines.append(QuoteLine(sku_id=sid, qty=1, line_type=line_type))  # type: ignore[arg-type]

        cap = mandate.max_recurring_cents_per_month if mandate else None
        if cap is not None and recurring_cents > cap:
            self.mandate_violation = f"recurring {recurring_cents} exceeds cap {cap}"
            payload = {
                "action": "compose_quote",
                "ok": False,
                "error": "mandate_violation",
                "mandate_violation": self.mandate_violation,
            }
            self.history.append(payload)
            return payload

        self.mandate_violation = None
        self.checklist.quote_lines = lines
        self.checklist.milestones.add("quote_composed")
        payload = {
            "action": "compose_quote",
            "ok": True,
            "oracle_pass": True,
            "quote_lines": [line.model_dump() for line in lines],
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
            "commit_shortlist": self.commit_shortlist,
            "compose_quote": self.compose_quote,
        }
        if action not in handlers:
            return {"action": action, "ok": False, "error": f"unknown action {action}"}
        # Normalize list bodies
        if action == "compare" and "ids" in body:
            return handlers[action](ids=body["ids"])
        if action == "save_shortlist" and "ids" in body:
            return handlers[action](ids=body["ids"])
        if action == "commit_shortlist":
            return handlers[action](ids=body.get("ids"))
        if action == "list_addons":
            return handlers[action](appliance_id=body.get("appliance_id", ""))
        if action == "attach_addon":
            return handlers[action](service_id=body.get("service_id", ""))
        if action == "search":
            return handlers[action](q=body.get("q", ""))
        if action == "set_facets":
            return handlers[action](**{k: v for k, v in body.items() if k != "action"})
        if action == "compose_quote":
            return handlers[action](**body)
        return handlers[action](**body)
