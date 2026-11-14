"""H1 → H2 curriculum driver on shared checklist / handoff (no Counter)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from ach.discovery.sim import DiscoverySim
from ach.entitlements.sim import EntitlementSim
from ach.harness.runner import load_scenario, run_h1
from ach.harness.trace import write_trace
from ach.models import Handoff
from ach.paths import H1_SCENARIOS


BILL_TO = {
    "partner_id": "p-100",
    "smb_id": "smb-9",
    "subscription_id": "sub-77",
}


def handoff_from_h1(sim: DiscoverySim) -> Handoff | None:
    """Handoff is compose_quote output. No invented lines and no cents."""
    if not sim.checklist.quote_lines:
        return None
    ids = list(sim.checklist.committed or sim.checklist.shortlist)
    return Handoff(
        shortlist_ids=ids,
        quote_lines=list(sim.checklist.quote_lines),
        invoice_id=None,
        invoice_state=None,
        checkout_session_id=None,
        currency=None,
        counter_scenario_id=None,
    )


def _snap(sim: DiscoverySim | EntitlementSim) -> dict[str, Any]:
    checklist = sim.checklist
    return {
        "intent": checklist.intent,
        "facets": checklist.facets,
        "compared_ids": list(checklist.compared_ids),
        "shortlist": list(checklist.shortlist),
        "committed": list(checklist.committed),
        "quote_lines": [line.model_dump() for line in checklist.quote_lines],
        "invoice_id": checklist.invoice_id,
        "invoice_state": checklist.invoice_state,
        "milestones": sorted(checklist.milestones),
    }


def _hits(out: dict[str, Any]) -> list[dict[str, Any]]:
    hits = []
    for row in out.get("results") or []:
        if not isinstance(row, dict) or "id" not in row:
            continue
        hits.append(
            {
                "id": row.get("id"),
                "rank": row.get("rank"),
                "sponsored": bool(row.get("sponsored")),
                "platform_pick": bool(row.get("platform_pick")),
                "seller_text": row.get("seller_text"),
                "not_in_handoff": True,
            }
        )
    return hits


def _trace_step(
    *,
    lane: str,
    action: str,
    out: dict[str, Any],
    sim: DiscoverySim | EntitlementSim,
    horizon: str,
    handoff: dict[str, Any] | None = None,
) -> dict[str, Any]:
    step: dict[str, Any] = {
        "lane": lane,
        "action": action,
        "ok": bool(out["ok"]) if "ok" in out else True,
        "error": out.get("error"),
        "forbidden": bool(out.get("forbidden")),
        "oracle_pass": out.get("oracle_pass"),
        "recon_blocked": out.get("recon_blocked"),
        "horizon": horizon,
        "delegate": None,
        "mandate_violation": getattr(sim, "mandate_violation", None),
        "checklist": _snap(sim),
        "handoff": handoff,
        "counter": {
            "checkout_session_id": None,
            "currency": None,
            "counter_scenario_id": None,
        },
    }
    bill = getattr(sim, "bill_to", None)
    if bill is not None and bill.complete():
        step["delegate"] = bill.model_dump()
    if lane == "commerce":
        hits = _hits(out)
        if hits:
            step["hits"] = hits
    if "quote_lines" in out:
        step["quote_lines"] = out["quote_lines"]
    if "total_cents" in out:
        step["total_cents"] = out["total_cents"]
        step["currency"] = out.get("currency")
    return step


def run_curriculum(h1_scenario_path: Path | str | None = None) -> dict:
    path = Path(h1_scenario_path) if h1_scenario_path else H1_SCENARIOS / "h1_office_laptop.json"
    scenario = load_scenario(path)
    h1_result = run_h1(scenario)
    if not h1_result.passed:
        return {
            "ok": False,
            "stage": "h1",
            "failures": h1_result.failures,
            "handoff": None,
        }

    sim = DiscoverySim(catalog_path=scenario.catalog)
    sim.task = scenario.task
    trace_steps: list[dict[str, Any]] = []
    for step in scenario.steps:
        out = sim.step(step.action, step.body)
        lane = "handoff" if step.action == "compose_quote" else "commerce"
        handoff_payload = None
        if step.action == "compose_quote" and out.get("quote_lines"):
            handoff_payload = {
                "shortlist_ids": list(sim.checklist.committed or sim.checklist.shortlist),
                "quote_lines": out["quote_lines"],
                "checkout_session_id": None,
                "currency": None,
                "counter_scenario_id": None,
            }
        trace_steps.append(
            _trace_step(
                lane=lane,
                action=step.action,
                out=out,
                sim=sim,
                horizon="h1",
                handoff=handoff_payload,
            )
        )

    handoff = handoff_from_h1(sim)
    if handoff is None:
        return {
            "ok": False,
            "stage": "compose",
            "failures": ["compose_quote produced no quote lines"],
            "handoff": None,
            "trace": {"title": scenario.id, "journey": ["discover", "quote", "bill", "sent"], "steps": trace_steps},
        }

    ent = EntitlementSim()
    loaded = ent.load_shortlist(
        shortlist_ids=handoff.shortlist_ids,
        quote_lines=[q.model_dump() for q in handoff.quote_lines],
        bill_to=BILL_TO,
    )
    trace_steps.append(
        _trace_step(lane="payments", action="load_shortlist", out=loaded, sim=ent, horizon="h2")
    )
    for ql in handoff.quote_lines:
        if ql.line_type == "usage":
            continue
        out = ent.attach_line(sku_id=ql.sku_id, line_type=ql.line_type, qty=ql.qty)
        trace_steps.append(
            _trace_step(lane="payments", action="attach_line", out=out, sim=ent, horizon="h2")
        )
        if not out.get("ok"):
            return {
                "ok": False,
                "stage": "h2_attach",
                "failures": [out.get("error", "attach failed")],
                "handoff": handoff.model_dump(),
                "trace": _trace_doc(scenario.id, trace_steps),
            }

    preview = ent.preview_invoice()
    trace_steps.append(
        _trace_step(lane="payments", action="preview_invoice", out=preview, sim=ent, horizon="h2")
    )
    if not preview.get("ok"):
        return {
            "ok": False,
            "stage": "h2_preview",
            "failures": [preview.get("error", "preview failed")],
            "handoff": handoff.model_dump(),
            "trace": _trace_doc(scenario.id, trace_steps),
        }
    send = ent.request_send()
    trace_steps.append(
        _trace_step(lane="payments", action="request_send", out=send, sim=ent, horizon="h2")
    )
    if not send.get("ok"):
        return {
            "ok": False,
            "stage": "h2_send",
            "failures": [send.get("error", "send failed")],
            "handoff": handoff.model_dump(),
            "trace": _trace_doc(scenario.id, trace_steps),
        }

    handoff.invoice_id = ent.invoice.id
    handoff.invoice_state = ent.invoice.state
    return {
        "ok": True,
        "stage": "complete",
        "failures": [],
        "h1_scenario": scenario.id,
        "handoff": handoff.model_dump(),
        "total_cents": preview.get("total_cents"),
        "currency": preview.get("currency"),
        "milestones_h1": sorted(sim.checklist.milestones),
        "milestones_h2": sorted(ent.checklist.milestones),
        "trace": _trace_doc(scenario.id, trace_steps),
    }


def _trace_doc(title: str, steps: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "title": title,
        "journey": ["discover", "quote", "bill", "sent"],
        "steps": steps,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ach-driver")
    parser.add_argument(
        "--h1",
        default=str(H1_SCENARIOS / "h1_office_laptop.json"),
        help="H1 scenario path to seed the curriculum",
    )
    parser.add_argument("--out", default=None, help="Write handoff JSON")
    parser.add_argument("--view", default=None, help="Write a three-lane replay HTML page")
    args = parser.parse_args(argv)
    result = run_curriculum(args.h1)
    text = json.dumps(result, indent=2)
    print(text)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    if args.view and result.get("trace"):
        write_trace(args.view, result["trace"])
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
