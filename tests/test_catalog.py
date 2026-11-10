from ach.discovery.catalog import load_catalog


def test_catalog_has_about_24_skus():
    cat = load_catalog()
    assert 20 <= len(cat.skus) <= 30


def test_catalog_has_gold_ngfw_band():
    cat = load_catalog()
    band = [
        s
        for s in cat.skus
        if s.kind == "physical"
        and s.deployment == "on_prem"
        and s.throughput_gbps == "2_5"
        and s.ha == "required_capable"
        and s.family.startswith("ngfw")
    ]
    assert len(band) >= 3


def test_incompatible_service_exists():
    cat = load_catalog()
    sky = cat.get("svc-support-premium")
    assert "ngfw-a" not in sky.compatible_with
