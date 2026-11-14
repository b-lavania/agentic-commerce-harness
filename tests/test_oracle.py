from ach.discovery.catalog import load_catalog
from ach.discovery.oracle import grade_oracle
from ach.models import Checklist


def test_oracle_rejects_incompatible_service():
    cat = load_catalog()
    cl = Checklist(shortlist=["nl-14", "care-market"])
    ok, reasons = grade_oracle(
        cat,
        cl,
        constraints={"deployment": "on_prem", "perf": "standard", "spare": "required"},
    )
    assert not ok
    assert any("incompatible" in r for r in reasons)


def test_oracle_rejects_no_spare():
    cat = load_catalog()
    cons = {"deployment": "on_prem", "perf": "standard", "spare": "required"}
    for sku_id in ("nl-13", "fk-solo"):
        ok, reasons = grade_oracle(cat, Checklist(shortlist=[sku_id]), constraints=cons)
        assert not ok, reasons


def test_oracle_accepts_northline_care():
    cat = load_catalog()
    ok, reasons = grade_oracle(
        cat,
        Checklist(shortlist=["nl-14", "care-northline"]),
        constraints={"deployment": "on_prem", "perf": "standard", "spare": "required"},
    )
    assert ok, reasons


def test_preference_grades_commit_not_shortlist():
    cat = load_catalog()
    cons = {"deployment": "on_prem", "perf": "standard", "spare": "required"}
    prefs = [{"minimize_recurring": True}]
    decoy = Checklist(shortlist=["fk-mini"], committed=["nl-14"], facets=cons)
    ok, reasons = grade_oracle(cat, decoy, constraints=cons, preferences=prefs)
    assert not ok, reasons
    winner = Checklist(
        shortlist=["nl-14", "hb-16", "fk-mini"],
        committed=["fk-mini"],
        facets=cons,
    )
    ok, reasons = grade_oracle(cat, winner, constraints=cons, preferences=prefs)
    assert ok, reasons


def test_oracle_accepts_compatible_bundle():
    cat = load_catalog()
    cl = Checklist(shortlist=["nl-14", "hb-16", "care-desk"])
    ok, reasons = grade_oracle(
        cat,
        cl,
        constraints={"deployment": "on_prem", "perf": "standard", "spare": "required"},
    )
    assert ok, reasons
