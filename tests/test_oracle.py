from ach.discovery.catalog import load_catalog
from ach.discovery.oracle import grade_oracle
from ach.models import Checklist


def test_oracle_rejects_incompatible_service():
    cat = load_catalog()
    cl = Checklist(shortlist=["ngfw-a-2g", "svc-support-premium"])
    ok, reasons = grade_oracle(
        cat,
        cl,
        constraints={"deployment": "on_prem", "throughput_gbps": "2_5", "ha": "required"},
    )
    assert not ok
    assert any("incompatible" in r for r in reasons)


def test_oracle_accepts_compatible_bundle():
    cat = load_catalog()
    cl = Checklist(shortlist=["ngfw-a-2g", "ngfw-b-3g", "svc-mon-ngfw"])
    ok, reasons = grade_oracle(
        cat,
        cl,
        constraints={"deployment": "on_prem", "throughput_gbps": "2_5", "ha": "required"},
    )
    assert ok, reasons
