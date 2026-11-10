"""Horizon 2 entitlement / invoice sim."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from ach.models import Checklist, QuoteLine
from ach.paths import DEFAULT_PRICEBOOK, ENTITLEMENTS, REPO_ROOT

InvoiceState = Literal["draft", "generated", "sent", "credit_memo", "next_invoice"]
LineType = Literal["setup", "recurring", "usage"]

FORBIDDEN = frozenset({"set_amount", "rewrite_sent", "checkout", "create_payment"})


class Attribution(BaseModel):
    partner_id: str | None = None
    smb_id: str | None = None
    subscription_id: str | None = None

    def complete(self) -> bool:
        return bool(self.partner_id and self.smb_id and self.subscription_id)


class InvoiceLine(BaseModel):
    sku_id: str
    line_type: LineType
    qty: int = 1
    amount_cents: int
    attribution: Attribution | None = None


class MeterBatch(BaseModel):
    batch_id: str
    sku_id: str = "usage-ai-overage"
    units: int
    attribution: Attribution
    rated_cents: int | None = None


class PriceBook(BaseModel):
    version: str
    currency: str = "USD"
    prices: dict[str, dict[str, int]]


class Invoice(BaseModel):
    id: str
    state: InvoiceState = "draft"
    lines: list[InvoiceLine] = Field(default_factory=list)
    unexplained_variance_cents: int = 0
    parent_sent_id: str | None = None


def load_pricebook(path: Path | str | None = None) -> PriceBook:
    p = Path(path) if path else DEFAULT_PRICEBOOK
    if not p.is_absolute():
        p = REPO_ROOT / p
    return PriceBook.model_validate(json.loads(p.read_text(encoding="utf-8")))


class EntitlementSim:
    def __init__(
        self,
        pricebook: PriceBook | None = None,
        pricebook_path: Path | str | None = None,
    ):
        self.pricebook = pricebook or load_pricebook(pricebook_path)
        self.checklist = Checklist()
        self.invoice = Invoice(id=f"inv-{uuid.uuid4().hex[:8]}", state="draft")
        self.checklist.invoice_id = self.invoice.id
        self.checklist.invoice_state = self.invoice.state
        self.credit_memos: list[Invoice] = []
        self.next_invoice: Invoice | None = None
        self.meter_batches: dict[str, MeterBatch] = {}
        self.last_recon_blocked = False
        self.sent_rewrite_attempted = False
        self.history: list[dict[str, Any]] = []

    def _price(self, sku_id: str, line_type: LineType) -> int:
        entry = self.pricebook.prices.get(sku_id, {})
        if line_type not in entry:
            raise KeyError(f"no price for {sku_id}.{line_type}")
        return int(entry[line_type])

    def _sync_checklist(self) -> None:
        self.checklist.invoice_id = self.invoice.id
        self.checklist.invoice_state = self.invoice.state
        self.checklist.quote_lines = [
            QuoteLine(sku_id=ln.sku_id, qty=ln.qty, line_type=ln.line_type)
            for ln in self.invoice.lines
            if ln.line_type != "usage" or True
        ]

    def load_shortlist(
        self,
        shortlist_ids: list[str] | None = None,
        quote_lines: list[dict[str, Any]] | None = None,
        fixture: str | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        if fixture:
            path = Path(fixture)
            if not path.is_absolute():
                path = REPO_ROOT / path
            data = json.loads(path.read_text(encoding="utf-8"))
            shortlist_ids = data.get("shortlist_ids", shortlist_ids)
            quote_lines = data.get("quote_lines", quote_lines)
        self.checklist.shortlist = list(shortlist_ids or [])
        for ql in quote_lines or []:
            self.checklist.quote_lines.append(QuoteLine.model_validate(ql))
        payload = {
            "action": "load_shortlist",
            "ok": True,
            "shortlist_ids": self.checklist.shortlist,
            "quote_lines": [q.model_dump() for q in self.checklist.quote_lines],
        }
        self.history.append(payload)
        return payload

    def attach_line(
        self,
        sku_id: str,
        line_type: LineType,
        qty: int = 1,
        attribution: dict[str, Any] | None = None,
        amount_cents: int | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        if amount_cents is not None:
            self.checklist.forbidden_hits.append("set_amount")
            return {
                "action": "attach_line",
                "ok": False,
                "error": "agents may not supply amount_cents",
                "forbidden": True,
            }
        # After credit memo, new lines go on next_invoice only.
        if self.invoice.state == "sent" and self.next_invoice is None:
            self.sent_rewrite_attempted = True
            self.checklist.forbidden_hits.append("rewrite_sent")
            return {
                "action": "attach_line",
                "ok": False,
                "error": "cannot mutate sent invoice",
                "forbidden": True,
            }
        if self.invoice.state == "generated" and self.next_invoice is None:
            return {
                "action": "attach_line",
                "ok": False,
                "error": "return to draft before editing lines",
            }
        try:
            cents = self._price(sku_id, line_type)
        except KeyError as e:
            return {"action": "attach_line", "ok": False, "error": str(e)}

        attr = Attribution.model_validate(attribution or {}) if attribution else None
        if line_type == "usage" and (attr is None or not attr.complete()):
            return {
                "action": "attach_line",
                "ok": False,
                "error": "usage requires partner_id+smb_id+subscription_id",
                "recon_blocked": True,
            }

        if self.next_invoice is not None and self.invoice.state == "sent":
            target = self.next_invoice
        else:
            target = self.invoice

        line = InvoiceLine(
            sku_id=sku_id,
            line_type=line_type,
            qty=qty,
            amount_cents=cents * qty,
            attribution=attr,
        )
        target.lines.append(line)
        self.checklist.milestones.add("lines_attached")
        self._sync_checklist()
        payload = {
            "action": "attach_line",
            "ok": True,
            "line": line.model_dump(),
            "invoice_state": self.invoice.state,
        }
        self.history.append(payload)
        return payload

    def rate_usage(self, batch_id: str, **body: Any) -> dict[str, Any]:
        units = int(body.get("units", 0))
        sku_id = body.get("sku_id", "usage-ai-overage")
        attr = Attribution.model_validate(body.get("attribution") or {})
        if not attr.complete():
            self.last_recon_blocked = True
            payload = {
                "action": "rate_usage",
                "ok": False,
                "recon_blocked": True,
                "error": "incomplete attribution triple",
            }
            self.history.append(payload)
            return payload
        try:
            unit_price = self._price(sku_id, "usage")
        except KeyError as e:
            return {"action": "rate_usage", "ok": False, "error": str(e)}
        rated = unit_price * units
        batch = MeterBatch(
            batch_id=batch_id,
            sku_id=sku_id,
            units=units,
            attribution=attr,
            rated_cents=rated,
        )
        self.meter_batches[batch_id] = batch
        self.last_recon_blocked = False
        # Attach usage line on current draft/next
        return self.attach_line(
            sku_id=sku_id,
            line_type="usage",
            qty=units,
            attribution=attr.model_dump(),
        ) | {"rated_cents": rated, "batch_id": batch_id, "recon_blocked": False}

    def preview_invoice(self, **_: Any) -> dict[str, Any]:
        if self.invoice.state == "sent":
            return {"action": "preview_invoice", "ok": False, "error": "already sent"}
        # Recon: usage lines must match rated batches
        usage_total = sum(ln.amount_cents for ln in self.invoice.lines if ln.line_type == "usage")
        rated_total = sum(b.rated_cents or 0 for b in self.meter_batches.values())
        variance = abs(usage_total - rated_total) if self.meter_batches or usage_total else 0
        # Also block if any usage line has incomplete attribution
        for ln in self.invoice.lines:
            if ln.line_type == "usage" and (ln.attribution is None or not ln.attribution.complete()):
                variance = max(variance, 1)
                self.last_recon_blocked = True

        self.invoice.unexplained_variance_cents = variance
        if variance != 0:
            self.last_recon_blocked = True
            payload = {
                "action": "preview_invoice",
                "ok": False,
                "recon_blocked": True,
                "unexplained_variance_cents": variance,
                "state": self.invoice.state,
            }
            self.history.append(payload)
            return payload

        self.invoice.state = "generated"
        self.last_recon_blocked = False
        self.checklist.milestones.add("preview_ok")
        self._sync_checklist()
        payload = {
            "action": "preview_invoice",
            "ok": True,
            "recon_blocked": False,
            "unexplained_variance_cents": 0,
            "state": self.invoice.state,
            "lines": [ln.model_dump() for ln in self.invoice.lines],
            "total_cents": sum(ln.amount_cents for ln in self.invoice.lines),
        }
        self.history.append(payload)
        return payload

    def request_send(self, **_: Any) -> dict[str, Any]:
        if self.invoice.state != "generated":
            return {
                "action": "request_send",
                "ok": False,
                "error": f"cannot send from state {self.invoice.state}",
            }
        if self.invoice.unexplained_variance_cents != 0:
            self.last_recon_blocked = True
            return {
                "action": "request_send",
                "ok": False,
                "recon_blocked": True,
                "error": "recon variance nonzero",
            }
        self.invoice.state = "sent"
        self.checklist.milestones.add("sent")
        self._sync_checklist()
        payload = {"action": "request_send", "ok": True, "state": "sent", "invoice_id": self.invoice.id}
        self.history.append(payload)
        return payload

    def propose_credit_memo(self, sent_id: str, reason_code: str, **_: Any) -> dict[str, Any]:
        if self.invoice.state != "sent" or self.invoice.id != sent_id:
            # If already on next path, still allow memo referencing original
            if not (self.invoice.state == "sent" or sent_id == self.invoice.id):
                return {
                    "action": "propose_credit_memo",
                    "ok": False,
                    "error": "credit memo requires matching sent invoice",
                }
        cm = Invoice(
            id=f"cm-{uuid.uuid4().hex[:8]}",
            state="credit_memo",
            parent_sent_id=sent_id,
            lines=[],
        )
        self.credit_memos.append(cm)
        self.next_invoice = Invoice(
            id=f"inv-{uuid.uuid4().hex[:8]}",
            state="next_invoice",
            parent_sent_id=sent_id,
        )
        # Keep sent invoice immutable; checklist points at next for further usage
        self.invoice.state = "sent"
        self.checklist.invoice_state = "next_invoice"
        self.checklist.invoice_id = self.next_invoice.id
        self.checklist.milestones.add("credit_memo_only")
        payload = {
            "action": "propose_credit_memo",
            "ok": True,
            "credit_memo_id": cm.id,
            "next_invoice_id": self.next_invoice.id,
            "reason_code": reason_code,
            "sent_immutable": True,
        }
        self.history.append(payload)
        return payload

    def rewrite_sent(self, **_: Any) -> dict[str, Any]:
        """Explicit illegal tool — always forbidden."""
        self.sent_rewrite_attempted = True
        self.checklist.forbidden_hits.append("rewrite_sent")
        return {"action": "rewrite_sent", "ok": False, "forbidden": True, "error": "illegal"}

    def step(self, action: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        body = dict(body or {})
        if action == "rewrite_sent" or action in FORBIDDEN:
            if action == "rewrite_sent":
                return self.rewrite_sent(**body)
            self.checklist.forbidden_hits.append(action)
            return {"action": action, "ok": False, "forbidden": True, "error": "forbidden"}
        if action == "attach_line":
            return self.attach_line(
                sku_id=body["sku_id"],
                line_type=body["line_type"],
                qty=int(body.get("qty", 1)),
                attribution=body.get("attribution"),
                amount_cents=body.get("amount_cents"),
            )
        if action == "rate_usage":
            body = dict(body)
            batch_id = body.pop("batch_id", "batch-1")
            return self.rate_usage(batch_id=batch_id, **body)
        if action == "propose_credit_memo":
            return self.propose_credit_memo(
                sent_id=body.get("sent_id", self.invoice.id),
                reason_code=body.get("reason_code", "correction"),
            )
        if action == "load_shortlist":
            return self.load_shortlist(**body)
        if action == "preview_invoice":
            return self.preview_invoice(**body)
        if action == "request_send":
            return self.request_send(**body)
        return {"action": action, "ok": False, "error": f"unknown action {action}"}
