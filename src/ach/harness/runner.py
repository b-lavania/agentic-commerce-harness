"""Cert scenario runner + JSONL trajectory export."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from ach.discovery.oracle import grade_oracle
from ach.discovery.sim import DiscoverySim
from ach.entitlements.sim import EntitlementSim
from ach.models import Scenario, TrajectoryRow
from ach.paths import H1_SCENARIOS, H2_SCENARIOS, REPO_ROOT


@dataclass
class ScenarioResult:
    scenario_id: str
    horizon: str
    passed: bool
    failures: list[str] = field(default_factory=list)
    milestones: list[str] = field(default_factory=list)
    trajectories: list[TrajectoryRow] = field(default_factory=list)


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
    import hashlib

    raw = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def run_h1(scenario: Scenario) -> ScenarioResult:
    sim = DiscoverySim(catalog_path=scenario.catalog)
    rows: list[TrajectoryRow] = []
    failures: list[str] = []

    if len(scenario.steps) > scenario.max_macro_steps:
        failures.append("step count exceeds max_macro_steps")

    for i, step in enumerate(scenario.steps):
        out = sim.step(step.action, step.body)
        rows.append(
            TrajectoryRow(
                scenario_id=scenario.id,
                step=i,
                action=step.action,
                observation_hash=_obs_hash(out),
                milestone_hits=sorted(sim.checklist.milestones),
                forbidden=list(sim.checklist.forbidden_hits),
                ok=bool(out.get("ok", True)) if "ok" in out else True,
                detail={"error": out.get("error"), "oracle_pass": out.get("oracle_pass")},
            )
        )
        if out.get("forbidden"):
            # Forbidden actions in the gold path are expected only when testing refusal;
            # for H1 gold paths they are failures.
            if step.action in (scenario.expect.forbidden_actions or []):
                failures.append(f"gold path used forbidden action {step.action}")

    # Terminal oracle
    cons = scenario.expect.constraints or sim.checklist.facets
    oracle_ok, reasons = grade_oracle(
        sim.catalog,
        sim.checklist,
        constraints=cons,
        had_zero_result=sim.had_zero_result,
        recovered_from_zero=sim.recovered_from_zero,
    )
    if scenario.expect.shortlist_passes_oracle is True and not oracle_ok:
        failures.extend(reasons or ["oracle failed"])
    if scenario.expect.shortlist_passes_oracle is False and oracle_ok:
        failures.append("expected oracle fail but passed")

    for m in scenario.expect.milestones:
        if m not in sim.checklist.milestones:
            failures.append(f"missing milestone {m}")

    # Reject scenario: shortlist must not contain incompatible svc-support-premium
    if scenario.id == "h1_reject_incompatible_addon":
        if "svc-support-premium" in sim.checklist.shortlist:
            failures.append("shortlist contains incompatible svc-support-premium")

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
    rows: list[TrajectoryRow] = []
    failures: list[str] = []
    saw_forbidden_rewrite = False
    sent_after_block = False

    for i, step in enumerate(scenario.steps):
        out = sim.step(step.action, step.body)
        if out.get("forbidden") and step.action == "rewrite_sent":
            saw_forbidden_rewrite = True
        if step.action == "request_send" and out.get("ok"):
            sent_after_block = True
        rows.append(
            TrajectoryRow(
                scenario_id=scenario.id,
                step=i,
                action=step.action,
                observation_hash=_obs_hash(out),
                milestone_hits=sorted(sim.checklist.milestones),
                forbidden=list(sim.checklist.forbidden_hits),
                ok=bool(out.get("ok", True)) if "ok" in out else True,
                detail={
                    "error": out.get("error"),
                    "recon_blocked": out.get("recon_blocked"),
                    "state": out.get("state") or sim.checklist.invoice_state,
                },
            )
        )

    exp = scenario.expect
    if exp.invoice_state:
        # Prefer next_invoice checklist when on credit-memo path
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
    if exp.must_refuse_sent_rewrite and not (
        saw_forbidden_rewrite or "rewrite_sent" in sim.checklist.forbidden_hits
    ):
        failures.append("expected rewrite_sent refusal")
    if exp.must_refuse_sent_rewrite and "credit_memo_only" not in sim.checklist.milestones:
        failures.append("missing credit_memo_only milestone")

    for m in exp.milestones:
        if m not in sim.checklist.milestones:
            failures.append(f"missing milestone {m}")

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
