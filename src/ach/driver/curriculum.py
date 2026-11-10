"""H1 → H2 curriculum driver on shared checklist / handoff (no Counter)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ach.discovery.sim import DiscoverySim
from ach.entitlements.sim import EntitlementSim
from ach.harness.runner import load_scenario, run_h1
from ach.models import Handoff, QuoteLine
from ach.paths import H1_SCENARIOS, REPO_ROOT


def handoff_from_h1(sim: DiscoverySim) -> Handoff:
    """Build handoff: appliances get setup+recurring; services get recurring."""
    quote_lines: list[QuoteLine] = []
    idx = sim.catalog.by_id()
    for sid in sim.checklist.shortlist:
        sku = idx[sid]
        if sku.is_appliance:
            quote_lines.append(QuoteLine(sku_id=sid, qty=1, line_type="setup"))
            quote_lines.append(QuoteLine(sku_id=sid, qty=1, line_type="recurring"))
        elif sku.kind == "service":
            quote_lines.append(QuoteLine(sku_id=sid, qty=1, line_type="recurring"))
    return Handoff(
        shortlist_ids=list(sim.checklist.shortlist),
        quote_lines=quote_lines,
        invoice_id=None,
        invoice_state=None,
        checkout_session_id=None,
        currency=None,
        counter_scenario_id=None,
    )


def run_curriculum(h1_scenario_path: Path | str | None = None) -> dict:
    path = Path(h1_scenario_path) if h1_scenario_path else H1_SCENARIOS / "h1_branch_ngfw.json"
    scenario = load_scenario(path)
    h1_result = run_h1(scenario)
    if not h1_result.passed:
        return {
            "ok": False,
            "stage": "h1",
            "failures": h1_result.failures,
            "handoff": None,
        }

    # Re-play H1 to obtain sim state for handoff
    sim = DiscoverySim(catalog_path=scenario.catalog)
    for step in scenario.steps:
        sim.step(step.action, step.body)

    handoff = handoff_from_h1(sim)

    # H2: load handoff and send a clean setup+recurring invoice for first appliance
    ent = EntitlementSim()
    ent.load_shortlist(
        shortlist_ids=handoff.shortlist_ids,
        quote_lines=[q.model_dump() for q in handoff.quote_lines],
    )
    for ql in handoff.quote_lines:
        if ql.line_type == "usage":
            continue
        # Skip SKUs missing from pricebook
        if ql.sku_id not in ent.pricebook.prices:
            continue
        if ql.line_type not in ent.pricebook.prices[ql.sku_id]:
            continue
        out = ent.attach_line(sku_id=ql.sku_id, line_type=ql.line_type, qty=ql.qty)
        if not out.get("ok"):
            return {
                "ok": False,
                "stage": "h2_attach",
                "failures": [out.get("error", "attach failed")],
                "handoff": handoff.model_dump(),
            }

    preview = ent.preview_invoice()
    if not preview.get("ok"):
        return {
            "ok": False,
            "stage": "h2_preview",
            "failures": [preview.get("error", "preview failed")],
            "handoff": handoff.model_dump(),
        }
    send = ent.request_send()
    if not send.get("ok"):
        return {
            "ok": False,
            "stage": "h2_send",
            "failures": [send.get("error", "send failed")],
            "handoff": handoff.model_dump(),
        }

    handoff.invoice_id = ent.invoice.id
    handoff.invoice_state = ent.invoice.state
    return {
        "ok": True,
        "stage": "complete",
        "failures": [],
        "h1_scenario": scenario.id,
        "handoff": handoff.model_dump(),
        "milestones_h1": sorted(sim.checklist.milestones),
        "milestones_h2": sorted(ent.checklist.milestones),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ach-driver")
    parser.add_argument(
        "--h1",
        default=str(H1_SCENARIOS / "h1_branch_ngfw.json"),
        help="H1 scenario path to seed the curriculum",
    )
    parser.add_argument("--out", default=None, help="Write handoff JSON")
    args = parser.parse_args(argv)
    result = run_curriculum(args.h1)
    text = json.dumps(result, indent=2)
    print(text)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
