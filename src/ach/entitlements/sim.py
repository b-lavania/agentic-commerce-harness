"""Horizon 2 entitlement / invoice sim."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from ach.models import Checklist, QuoteLine
from ach.paths import DEFAULT_PRICEBOOK, REPO_ROOT

InvoiceState = Literal["draft", "generated", "sent", "credit_memo", "next_invoice"]
LineType = Literal["setup", "recurring", "usage"]

FORBIDDEN = frozenset({"set_amount", "rewrite_sent", "checkout", "create_payment"})
_MONEY_KEYS = ("amount_cents", "tax", "discount")


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
    sku_id: str = "usage-backup-gb"
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
    bill_to: Attribution | None = None


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
        self.bill_to: Attribution | None = None
        self.checkout_session_id: str | None = None
        self.credit_memos: list[Invoice] = []
        self.next_invoice: Invoice | None = None
        self.meter_batches: dict[str, MeterBatch] = {}
        self.last_recon_blocked = False
        self.sent_rewrite_attempted = False
        self.mandate_violation: str | None = None
        self.history: list[dict[str, Any]] = []

    def _price(self, sku_id: str, line_type: LineType) -> int:
        entry = self.pricebook.prices.get(sku_id, {})
        if line_type not in entry:
            raise KeyError(f"no price for {sku_id}.{line_type}")
        return int(entry[line_type])

    def _sync_checklist(self) -> None:
        active = self.next_invoice if self.next_invoice and self.invoice.state == "sent" else self.invoice
        self.checklist.invoice_id = active.id
        self.checklist.invoice_state = active.state if active is not self.invoice else self.invoice.state
        if self.next_invoice and self.invoice.state == "sent":
            self.checklist.invoice_state = "next_invoice"
            self.checklist.invoice_id = self.next_invoice.id
        self.checklist.quote_lines = [
            QuoteLine(sku_id=ln.sku_id, qty=ln.qty, line_type=ln.line_type) for ln in self.invoice.lines
        ]

    def _apply_bill_to(self, bill_to: dict[str, Any] | None) -> None:
        if bill_to is None:
            return
        self.bill_to = Attribution.model_validate(bill_to)
        self.invoice.bill_to = self.bill_to

    def load_shortlist(
        self,
        shortlist_ids: list[str] | None = None,
        quote_lines: list[dict[str, Any]] | None = None,
        fixture: str | None = None,
        bill_to: dict[str, Any] | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        if fixture:
            path = Path(fixture)
            if not path.is_absolute():
                path = REPO_ROOT / path
            data = json.loads(path.read_text(encoding="utf-8"))
            shortlist_ids = data.get("shortlist_ids", shortlist_ids)
            quote_lines = data.get("quote_lines", quote_lines)
            if bill_to is None and data.get("bill_to") is not None:
                bill_to = data["bill_to"]
        self._apply_bill_to(bill_to)
        self.checklist.shortlist = list(shortlist_ids or [])
        self.checklist.quote_lines = []
        for ql in quote_lines or []:
            self.checklist.quote_lines.append(QuoteLine.model_validate(ql))
        payload = {
            "action": "load_shortlist",
            "ok": True,
            "shortlist_ids": self.checklist.shortlist,
            "quote_lines": [q.model_dump() for q in self.checklist.quote_lines],
            "bill_to": self.bill_to.model_dump() if self.bill_to else None,
        }
        self.history.append(payload)
        return payload

    def _money_forbidden(self, action: str, amount_cents: int | None, tax: Any, discount: Any) -> dict[str, Any] | None:
        if amount_cents is None and tax is None and discount is None:
            return None
        self.checklist.forbidden_hits.append("set_amount")
        return {
            "action": action,
            "ok": False,
            "error": "agents may not supply amount_cents",
            "forbidden": True,
        }

    def attach_line(
        self,
        sku_id: str,
        line_type: LineType,
        qty: int = 1,
        attribution: dict[str, Any] | None = None,
        amount_cents: int | None = None,
        tax: Any = None,
        discount: Any = None,
        **_: Any,
    ) -> dict[str, Any]:
        blocked = self._money_forbidden("attach_line", amount_cents, tax, discount)
        if blocked:
            return blocked
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
            self.last_recon_blocked = True
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
            "invoice_state": target.state,
        }
        self.history.append(payload)
        return payload

    def remove_line(self, sku_id: str, line_type: str, **_: Any) -> dict[str, Any]:
        if self.invoice.state == "sent" and self.next_invoice is None:
            self.sent_rewrite_attempted = True
            self.checklist.forbidden_hits.append("rewrite_sent")
            return {
                "action": "remove_line",
                "ok": False,
                "error": "cannot mutate sent invoice",
                "forbidden": True,
            }
        if self.invoice.state == "generated" and self.next_invoice is None:
            return {
                "action": "remove_line",
                "ok": False,
                "error": "return to draft before editing lines",
            }
        if self.next_invoice is not None and self.invoice.state == "sent":
            target = self.next_invoice
        else:
            target = self.invoice
        if target.state not in ("draft", "next_invoice"):
            return {
                "action": "remove_line",
                "ok": False,
                "error": f"cannot remove lines from {target.state}",
            }
        kept = [ln for ln in target.lines if not (ln.sku_id == sku_id and ln.line_type == line_type)]
        if len(kept) == len(target.lines):
            return {"action": "remove_line", "ok": False, "error": "line not found"}
        target.lines = kept
        self._sync_checklist()
        payload = {
            "action": "remove_line",
            "ok": True,
            "sku_id": sku_id,
            "line_type": line_type,
            "invoice_state": target.state,
        }
        self.history.append(payload)
        return payload

    def return_to_draft(self, **_: Any) -> dict[str, Any]:
        if self.invoice.state != "generated":
            return {
                "action": "return_to_draft",
                "ok": False,
                "error": f"return_to_draft only from generated, got {self.invoice.state}",
            }
        self.invoice.state = "draft"
        self.invoice.unexplained_variance_cents = 0
        self.checklist.milestones.discard("preview_ok")
        self._sync_checklist()
        payload = {"action": "return_to_draft", "ok": True, "state": "draft"}
        self.history.append(payload)
        return payload

    def rate_usage(self, batch_id: str, **body: Any) -> dict[str, Any]:
        blocked = self._money_forbidden(
            "rate_usage",
            body.get("amount_cents"),
            body.get("tax"),
            body.get("discount"),
        )
        if blocked:
            return blocked
        units = int(body.get("units", 0))
        sku_id = body.get("sku_id", "usage-backup-gb")
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
        payload = {
            "action": "rate_usage",
            "ok": True,
            "rated_cents": rated,
            "batch_id": batch_id,
            "recon_blocked": False,
            "sku_id": sku_id,
            "units": units,
        }
        self.history.append(payload)
        return payload

    def _active_lines(self) -> list[InvoiceLine]:
        if self.next_invoice is not None and self.invoice.state == "sent":
            return self.next_invoice.lines
        return self.invoice.lines

    def preview_invoice(self, **_: Any) -> dict[str, Any]:
        if self.invoice.state == "sent" and self.next_invoice is None:
            return {"action": "preview_invoice", "ok": False, "error": "already sent"}
        target = self.next_invoice if self.next_invoice and self.invoice.state == "sent" else self.invoice
        if target.state == "sent":
            return {"action": "preview_invoice", "ok": False, "error": "already sent"}
        usage_total = sum(ln.amount_cents for ln in target.lines if ln.line_type == "usage")
        rated_total = sum(b.rated_cents or 0 for b in self.meter_batches.values())
        variance = abs(usage_total - rated_total) if self.meter_batches or usage_total else 0
        for ln in target.lines:
            if ln.line_type == "usage" and (ln.attribution is None or not ln.attribution.complete()):
                variance = max(variance, 1)
                self.last_recon_blocked = True

        target.unexplained_variance_cents = variance
        if variance != 0:
            self.last_recon_blocked = True
            payload = {
                "action": "preview_invoice",
                "ok": False,
                "recon_blocked": True,
                "unexplained_variance_cents": variance,
                "state": target.state,
            }
            self.history.append(payload)
            return payload

        if target is self.invoice:
            self.invoice.state = "generated"
        self.last_recon_blocked = False
        self.checklist.milestones.add("preview_ok")
        self._sync_checklist()
        payload = {
            "action": "preview_invoice",
            "ok": True,
            "recon_blocked": False,
            "unexplained_variance_cents": 0,
            "state": "generated" if target is self.invoice else target.state,
            "lines": [ln.model_dump() for ln in target.lines],
            "total_cents": sum(ln.amount_cents for ln in target.lines),
            "currency": self.pricebook.currency,
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
        if self.bill_to is not None and not self.bill_to.complete():
            self.last_recon_blocked = True
            return {
                "action": "request_send",
                "ok": False,
                "recon_blocked": True,
                "error": "incomplete bill-to",
            }
        self.invoice.state = "sent"
        self.checklist.milestones.add("sent")
        self._sync_checklist()
        payload = {
            "action": "request_send",
            "ok": True,
            "state": "sent",
            "invoice_id": self.invoice.id,
            "total_cents": sum(ln.amount_cents for ln in self.invoice.lines),
            "currency": self.pricebook.currency,
        }
        self.history.append(payload)
        return payload

    def propose_credit_memo(
        self,
        sent_id: str,
        reason_code: str,
        line_refs: list[dict[str, Any]] | None = None,
        amount_cents: int | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        blocked = self._money_forbidden("propose_credit_memo", amount_cents, None, None)
        if blocked:
            return blocked
        if self.invoice.state != "sent" or self.invoice.id != sent_id:
            return {
                "action": "propose_credit_memo",
                "ok": False,
                "error": "credit memo requires matching sent invoice",
            }
        refs = list(line_refs or [])
        memo_lines: list[InvoiceLine] = []
        for ref in refs:
            sku_id = ref.get("sku_id")
            line_type = ref.get("line_type")
            match = next(
                (ln for ln in self.invoice.lines if ln.sku_id == sku_id and ln.line_type == line_type),
                None,
            )
            if match is None:
                return {
                    "action": "propose_credit_memo",
                    "ok": False,
                    "error": f"line_ref not on sent invoice: {sku_id} {line_type}",
                }
            memo_lines.append(
                InvoiceLine(
                    sku_id=match.sku_id,
                    line_type=match.line_type,
                    qty=match.qty,
                    amount_cents=match.amount_cents,
                    attribution=match.attribution,
                )
            )
        cm = Invoice(
            id=f"cm-{uuid.uuid4().hex[:8]}",
            state="credit_memo",
            parent_sent_id=sent_id,
            lines=memo_lines,
            bill_to=self.bill_to,
        )
        self.credit_memos.append(cm)
        self.next_invoice = Invoice(
            id=f"inv-{uuid.uuid4().hex[:8]}",
            state="next_invoice",
            parent_sent_id=sent_id,
            bill_to=self.bill_to,
        )
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
            "line_refs": refs,
            "reversal_cents": sum(ln.amount_cents for ln in memo_lines),
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
                tax=body.get("tax"),
                discount=body.get("discount"),
            )
        if action == "remove_line":
            return self.remove_line(sku_id=body["sku_id"], line_type=body["line_type"])
        if action == "return_to_draft":
            return self.return_to_draft()
        if action == "rate_usage":
            body = dict(body)
            batch_id = body.pop("batch_id", "batch-1")
            return self.rate_usage(batch_id=batch_id, **body)
        if action == "propose_credit_memo":
            return self.propose_credit_memo(
                sent_id=body.get("sent_id", self.invoice.id),
                reason_code=body.get("reason_code", "correction"),
                line_refs=body.get("line_refs"),
                amount_cents=body.get("amount_cents"),
            )
        if action == "load_shortlist":
            return self.load_shortlist(**body)
        if action == "preview_invoice":
            return self.preview_invoice(**body)
        if action == "request_send":
            return self.request_send(**body)
        return {"action": action, "ok": False, "error": f"unknown action {action}"}
