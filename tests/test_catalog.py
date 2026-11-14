from ach.discovery.catalog import load_catalog


def test_catalog_has_about_24_skus():
    cat = load_catalog()
    assert 20 <= len(cat.skus) <= 30


def test_catalog_has_gold_seat_band():
    cat = load_catalog()
    band = [
        s
        for s in cat.skus
        if s.kind == "virtual"
        and s.deployment == "hybrid"
        and s.perf == "standard"
        and s.spare == "ready"
        and s.os == "windows"
        and s.family in ("northline", "harbor", "fieldkit")
    ]
    assert len(band) >= 3


def test_incompatible_service_exists():
    cat = load_catalog()
    care = cat.get("care-market")
    assert care.compatible_with == ["cd-market"]
