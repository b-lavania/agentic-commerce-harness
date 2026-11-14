"""Cert scenario runner + JSONL trajectory export."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from ach.discovery.oracle import grade_oracle
from ach.discovery.sim import DiscoverySim
from ach.entitlements.sim import EntitlementSim
from ach.models import Scenario, ScenarioStep, ScenarioStepExpect, TrajectoryRow
from ach.paths import H1_SCENARIOS, H2_SCENARIOS, REPO_ROOT


_HIDDEN_OBSERVATION_KEYS = frozenset(
    {"amount_cents", "total_cents", "rated_cents", "recurring_cents", "tax", "discount"}
)


@dataclass
class ScenarioResult:
    scenario_id: str
    horizon: str
    passed: bool
    failures: list[str] = field(default_factory=list)
    milestones: list[str] = field(default_factory=list)
    trajectories: list[TrajectoryRow] = field(default_factory=list)


class ScriptedPolicy:
    """Gold-script policy. Observation is accepted and not read."""

    def __init__(self, steps: list[ScenarioStep]):
        self._steps = steps
        self._i = 0

    def next_action(self, observation: dict[str, Any]) -> dict[str, Any] | None:
        del observation
        if self._i >= len(self._steps):
            return None
        step = self._steps[self._i]
        self._i += 1
        return {"action": step.action, "body": step.body, "expect": step.expect}


def load_scenario(path: Path | str) -> Scenario:
    p = Path(path)
    if not p.is_absolute():
        p = REPO_ROOT / p
    return Scenario.model_validate(json.loads(p.read_text(encoding="utf-8")))


def iter_scenario_paths() -> Iterator[Path]:
    for folder in (H1_SCENARIOS, H2_SCENARIOS):
        if not folder.exists():
            continue
        yield from sorted(folder.glob("*.json"))


def _obs_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _redact(item)
            for key, item in value.items()
            if key not in _HIDDEN_OBSERVATION_KEYS
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def _observation(sim: DiscoverySim | EntitlementSim, out: dict[str, Any]) -> dict[str, Any]:
    checklist = sim.checklist
    return {
        "tool": _redact(out),
        "checklist": {
            "intent": checklist.intent,
            "facets": checklist.facets,
            "compared_ids": list(checklist.compared_ids),
            "shortlist": list(checklist.shortlist),
            "committed": list(checklist.committed),
            "quote_lines": [line.model_dump() for line in checklist.quote_lines],
            "invoice_id": checklist.invoice_id,
            "invoice_state": checklist.invoice_state,
            "milestones": sorted(checklist.milestones),
        },
    }


def _delegate(sim: DiscoverySim | EntitlementSim) -> dict[str, str] | None:
    bill = getattr(sim, "bill_to", None)
    if bill is not None and bill.complete():
        return {
            "partner_id": bill.partner_id,
            "smb_id": bill.smb_id,
            "subscription_id": bill.subscription_id,
        }
    return None


def grade_step(expect: ScenarioStepExpect | dict[str, Any] | None, out: dict[str, Any]) -> list[str]:
    if expect is None:
        return []
    parsed = expect if isinstance(expect, ScenarioStepExpect) else ScenarioStepExpect.model_validate(expect)
    if not parsed.model_fields_set and not any(
        getattr(parsed, name) is not None for name in ("ok", "error", "forbidden", "oracle_pass", "recon_blocked")
    ):
        return []
    failures: list[str] = []
    if parsed.ok is not None:
        actual = bool(out["ok"]) if "ok" in out else True
        if actual != parsed.ok:
            failures.append(f"step ok {actual} != {parsed.ok}")
    if parsed.error is not None and out.get("error") != parsed.error:
        failures.append(f"step error {out.get('error')!r} != {parsed.error!r}")
    if parsed.forbidden is not None and bool(out.get("forbidden")) != parsed.forbidden:
        failures.append(f"step forbidden {bool(out.get('forbidden'))} != {parsed.forbidden}")
    if parsed.oracle_pass is not None and out.get("oracle_pass") != parsed.oracle_pass:
        failures.append(f"step oracle_pass {out.get('oracle_pass')!r} != {parsed.oracle_pass}")
    if parsed.recon_blocked is not None and bool(out.get("recon_blocked")) != parsed.recon_blocked:
        failures.append(
            f"step recon_blocked {bool(out.get('recon_blocked'))} != {parsed.recon_blocked}"
        )
    return failures


def _detail(out: dict[str, Any], sim: DiscoverySim | EntitlementSim) -> dict[str, Any]:
    detail: dict[str, Any] = {
        "error": out.get("error"),
        "oracle_pass": out.get("oracle_pass"),
        "recon_blocked": out.get("recon_blocked"),
        "forbidden": bool(out.get("forbidden")),
        "state": out.get("state") or sim.checklist.invoice_state,
    }
    if "total_cents" in out:
        detail["total_cents"] = out["total_cents"]
        detail["currency"] = out.get("currency")
    if "quote_lines" in out:
        detail["quote_lines"] = out["quote_lines"]
    if out.get("mandate_violation"):
        detail["mandate_violation"] = out["mandate_violation"]
    return detail


def _row(
    scenario: Scenario,
    index: int,
    action: str,
    sim: DiscoverySim | EntitlementSim,
    out: dict[str, Any],
) -> TrajectoryRow:
    return TrajectoryRow(
        scenario_id=scenario.id,
        step=index,
        action=action,
        observation_hash=_obs_hash(out),
        milestone_hits=sorted(sim.checklist.milestones),
        forbidden=list(sim.checklist.forbidden_hits),
        ok=bool(out["ok"]) if "ok" in out else True,
        detail=_detail(out, sim),
        horizon=scenario.horizon,
        delegate=_delegate(sim),
        mandate_violation=getattr(sim, "mandate_violation", None),
    )


def _play(
    scenario: Scenario,
    sim: DiscoverySim | EntitlementSim,
) -> tuple[list[TrajectoryRow], list[str], bool]:
    rows: list[TrajectoryRow] = []
    failures: list[str] = []
    saw_send = False
    if len(scenario.steps) > scenario.max_macro_steps:
        failures.append("step count exceeds max_macro_steps")
    policy = ScriptedPolicy(scenario.steps)
    observation: dict[str, Any] = {}
    index = 0
    while True:
        nxt = policy.next_action(observation)
        if nxt is None:
            break
        out = sim.step(nxt["action"], nxt["body"])
        failures.extend(grade_step(nxt["expect"], out))
        if out.get("forbidden") and nxt["action"] in (scenario.expect.forbidden_actions or []):
            if scenario.horizon == "h1":
                failures.append(f"gold path used forbidden action {nxt['action']}")
        if nxt["action"] == "request_send" and out.get("ok"):
            saw_send = True
        rows.append(_row(scenario, index, nxt["action"], sim, out))
        observation = _observation(sim, out)
        index += 1
    return rows, failures, saw_send


def run_h1(scenario: Scenario) -> ScenarioResult:
    sim = DiscoverySim(catalog_path=scenario.catalog)
    sim.task = scenario.task
    rows, failures, _saw_send = _play(scenario, sim)

    cons = scenario.expect.constraints or sim.checklist.facets
    prefs = scenario.task.preferences if scenario.task else None
    oracle_ok, reasons = grade_oracle(
        sim.catalog,
        sim.checklist,
        constraints=cons,
        had_zero_result=sim.had_zero_result,
        recovered_from_zero=sim.recovered_from_zero,
        preferences=prefs or None,
        pricebook=sim.pricebook,
    )
    if scenario.expect.shortlist_passes_oracle is True and not oracle_ok:
        failures.extend(reasons or ["oracle failed"])
    if scenario.expect.shortlist_passes_oracle is False and oracle_ok:
        failures.append("expected oracle fail but passed")

    for milestone in scenario.expect.milestones:
        if milestone not in sim.checklist.milestones:
            failures.append(f"missing milestone {milestone}")

    if scenario.task and scenario.task.must_consider_addon:
        if "addon_in_path" not in sim.checklist.milestones:
            failures.append("missing addon consideration")

    return ScenarioResult(
        scenario_id=scenario.id,
        horizon="h1",
        passed=len(failures) == 0,
        failures=failures,
        milestones=sorted(sim.checklist.milestones),
        trajectories=rows,
    )


def run_h2(scenario: Scenario) -> ScenarioResult:
    sim = EntitlementSim(pricebook_path=scenario.pricebook)
    rows, failures, sent_after_block = _play(scenario, sim)
    saw_forbidden_rewrite = "rewrite_sent" in sim.checklist.forbidden_hits

    exp = scenario.expect
    if exp.invoice_state:
        state = sim.checklist.invoice_state
        if exp.invoice_state == "sent" and sim.invoice.state != "sent":
            failures.append(f"expected invoice_state sent, got {sim.invoice.state}")
        elif exp.invoice_state == "draft" and sim.invoice.state != "draft":
            failures.append(f"expected invoice_state draft, got {sim.invoice.state}")
        elif exp.invoice_state not in ("sent", "draft") and state != exp.invoice_state:
            failures.append(f"expected invoice_state {exp.invoice_state}, got {state}")

    if exp.recon_blocked is True and not sim.last_recon_blocked:
        failures.append("expected recon_blocked")
    if exp.must_not_send and (sim.invoice.state == "sent" or sent_after_block):
        failures.append("must_not_send violated")
    if exp.must_refuse_sent_rewrite and not saw_forbidden_rewrite:
        failures.append("expected rewrite_sent refusal")
    if exp.must_refuse_sent_rewrite and "credit_memo_only" not in sim.checklist.milestones:
        failures.append("missing credit_memo_only milestone")

    for milestone in exp.milestones:
        if milestone not in sim.checklist.milestones:
            failures.append(f"missing milestone {milestone}")

    return ScenarioResult(
        scenario_id=scenario.id,
        horizon="h2",
        passed=len(failures) == 0,
        failures=failures,
        milestones=sorted(sim.checklist.milestones),
        trajectories=rows,
    )


def run_scenario(path: Path | str) -> ScenarioResult:
    scenario = load_scenario(path)
    if scenario.horizon == "h1":
        return run_h1(scenario)
    return run_h2(scenario)


def run_all(jsonl_path: Path | str | None = None) -> list[ScenarioResult]:
    results: list[ScenarioResult] = []
    traj_file = Path(jsonl_path) if jsonl_path else None
    if traj_file:
        traj_file.parent.mkdir(parents=True, exist_ok=True)
        fh = traj_file.open("w", encoding="utf-8")
    else:
        fh = None
    try:
        for path in iter_scenario_paths():
            result = run_scenario(path)
            results.append(result)
            if fh:
                for row in result.trajectories:
                    fh.write(row.model_dump_json() + "\n")
                fh.write(
                    json.dumps(
                        {
                            "type": "scenario_result",
                            "scenario_id": result.scenario_id,
                            "passed": result.passed,
                            "failures": result.failures,
                        }
                    )
                    + "\n"
                )
    finally:
        if fh:
            fh.close()
    return results
