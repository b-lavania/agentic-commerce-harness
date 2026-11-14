from ach.harness.runner import run_all, run_scenario
from ach.paths import H1_SCENARIOS, H2_SCENARIOS


def test_all_scenarios_pass():
    results = run_all()
    failed = [r for r in results if not r.passed]
    assert not failed, [(r.scenario_id, r.failures) for r in failed]
    assert len(results) == 15


def test_h1_office_laptop(tmp_path):
    r = run_scenario(H1_SCENARIOS / "h1_office_laptop.json")
    assert r.passed, r.failures


def test_h2_preview_send():
    r = run_scenario(H2_SCENARIOS / "h2_preview_send.json")
    assert r.passed, r.failures
    assert r.trajectories[-1].delegate == {
        "partner_id": "p-100",
        "smb_id": "smb-9",
        "subscription_id": "sub-77",
    }
    assert r.trajectories[-1].detail["total_cents"] == 207000


def test_mandate_refusal_is_a_pass():
    r = run_scenario(H1_SCENARIOS / "h1_mandate_over_cap.json")
    assert r.passed, r.failures
    assert any(row.mandate_violation for row in r.trajectories)


def test_jsonl_export(tmp_path):
    out = tmp_path / "t.jsonl"
    results = run_all(jsonl_path=out)
    assert out.exists()
    assert out.read_text(encoding="utf-8").strip()
    assert all(r.passed for r in results)
