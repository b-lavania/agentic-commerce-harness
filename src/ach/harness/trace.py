"""Write a self-contained replay page for one cert run."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ach.harness.runner import ScenarioResult


_TEMPLATE = Path(__file__).with_name("trace_view.html")


def write_trace(path: Path | str, document: dict[str, Any]) -> None:
    raw = json.dumps(document, indent=2, default=str).replace("<", "\\u003c")
    html = _TEMPLATE.read_text(encoding="utf-8").replace("__ACH_TRACE_JSON__", raw)
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(html, encoding="utf-8")


def document_from_results(results: list[ScenarioResult], title: str = "ach-harness") -> dict[str, Any]:
    steps: list[dict[str, Any]] = []
    for result in results:
        for row in result.trajectories:
            lane = "payments" if result.horizon == "h2" else "commerce"
            if row.action == "compose_quote":
                lane = "handoff"
            step: dict[str, Any] = {
                "scenario_id": result.scenario_id,
                "lane": lane,
                "action": row.action,
                "ok": row.ok,
                "horizon": row.horizon,
                "delegate": row.delegate,
                "mandate_violation": row.mandate_violation,
                "detail": row.detail,
            }
            if "total_cents" in row.detail:
                step["total_cents"] = row.detail["total_cents"]
                step["currency"] = row.detail.get("currency")
            if row.action == "compose_quote" and row.detail.get("quote_lines"):
                step["handoff"] = {
                    "quote_lines": row.detail["quote_lines"],
                    "checkout_session_id": None,
                    "currency": None,
                    "counter_scenario_id": None,
                }
            steps.append(step)
    return {
        "title": title,
        "journey": ["discover", "quote", "bill", "sent"],
        "steps": steps,
    }
