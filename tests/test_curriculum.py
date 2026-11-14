import json

from ach.discovery.sim import DiscoverySim
from ach.driver.curriculum import run_curriculum
from ach.harness.runner import load_scenario
from ach.harness.trace import write_trace
from ach.paths import H1_SCENARIOS


def test_h1_to_h2_curriculum():
    result = run_curriculum()
    assert result["ok"], result
    handoff = result["handoff"]
    assert handoff["shortlist_ids"] == ["nl-14", "care-desk"]
    assert [(q["sku_id"], q["line_type"]) for q in handoff["quote_lines"]] == [
        ("nl-14", "setup"),
        ("nl-14", "recurring"),
        ("care-desk", "recurring"),
    ]
    assert all(set(q) == {"sku_id", "qty", "line_type"} for q in handoff["quote_lines"])
    assert handoff["invoice_state"] == "sent"
    assert handoff["checkout_session_id"] is None
    assert handoff["currency"] is None
    assert handoff["counter_scenario_id"] is None
    assert result["total_cents"] == 207000
    lanes = {step["lane"] for step in result["trace"]["steps"]}
    assert lanes == {"commerce", "handoff", "payments"}
    handoff_steps = [step for step in result["trace"]["steps"] if step["lane"] == "handoff"]
    assert "amount" not in json.dumps(handoff_steps)
    preview = [step for step in result["trace"]["steps"] if step.get("total_cents") == 207000]
    assert preview


def test_unpriced_commit_stops_before_handoff(tmp_path):
    path = tmp_path / "unpriced.json"
    path.write_text(
        json.dumps(
            {
                "id": "tmp_unpriced",
                "horizon": "h1",
                "steps": [
                    {
                        "action": "set_facets",
                        "body": {
                            "deployment": "on_prem",
                            "perf": "standard",
                            "spare": "required",
                        },
                    },
                    {"action": "save_shortlist", "body": {"ids": ["pl-display"]}},
                    {"action": "commit_shortlist", "body": {"ids": ["pl-display"]}},
                    {"action": "compose_quote", "body": {}},
                ],
                "expect": {"shortlist_passes_oracle": True},
            }
        ),
        encoding="utf-8",
    )
    result = run_curriculum(path)
    assert not result["ok"]
    assert result["stage"] == "compose"


def test_position_decoy_commits_winner_not_rank_one():
    scenario = load_scenario(H1_SCENARIOS / "h1_position_decoy.json")
    sim = DiscoverySim(catalog_path=scenario.catalog)
    sim.task = scenario.task
    ranked = None
    for step in scenario.steps:
        out = sim.step(step.action, step.body)
        if step.action == "set_facets":
            ranked = out["results"]
    assert ranked[0]["id"] == "nl-14"
    assert ranked[0]["sponsored"] is True
    assert ranked[0]["rank"] == 1
    assert sim.checklist.committed == ["fk-mini"]
    for line in sim.checklist.quote_lines:
        assert set(line.model_dump()) == {"sku_id", "qty", "line_type"}
        assert line.sku_id == "fk-mini"


def test_compose_refuses_amount():
    sim = DiscoverySim()
    sim.checklist.facets = {"deployment": "on_prem", "perf": "standard", "spare": "required"}
    sim.checklist.committed = ["fk-mini"]
    sim.checklist.shortlist = ["fk-mini"]
    out = sim.compose_quote(amount_cents=1)
    assert out["forbidden"]
    assert sim.checklist.quote_lines == []


def test_attach_addon_refuses_incompatible():
    sim = DiscoverySim()
    sim.compare(ids=["nl-14", "hb-16"])
    out = sim.attach_addon("care-market")
    assert out["error"] == "incompatible"
    assert "care-market" not in sim.checklist.attached_addons


def test_view_page_embeds_trace(tmp_path):
    result = run_curriculum()
    page = tmp_path / "out.html"
    write_trace(page, result["trace"])
    text = page.read_text(encoding="utf-8")
    assert 'id="ach-trace"' in text
    assert "nl-14" in text
    assert "207000" in text
