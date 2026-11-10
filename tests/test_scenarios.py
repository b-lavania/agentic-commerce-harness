from ach.harness.runner import run_all, run_scenario
from ach.paths import H1_SCENARIOS, H2_SCENARIOS


def test_all_scenarios_pass():
    results = run_all()
    failed = [r for r in results if not r.passed]
    assert not failed, [(r.scenario_id, r.failures) for r in failed]
    assert len(results) == 6


def test_h1_branch(tmp_path):
    r = run_scenario(H1_SCENARIOS / "h1_branch_ngfw.json")
    assert r.passed, r.failures


def test_h2_preview_send():
    r = run_scenario(H2_SCENARIOS / "h2_preview_send.json")
    assert r.passed, r.failures


def test_jsonl_export(tmp_path):
    out = tmp_path / "t.jsonl"
    results = run_all(jsonl_path=out)
    assert out.exists()
    assert out.read_text(encoding="utf-8").strip()
    assert all(r.passed for r in results)
