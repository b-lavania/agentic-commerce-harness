from ach.entitlements.sim import EntitlementSim


def test_cannot_set_amount():
    sim = EntitlementSim()
    out = sim.attach_line("ngfw-a-2g", "setup", amount_cents=1)
    assert not out["ok"]
    assert out.get("forbidden")


def test_sent_immutable():
    sim = EntitlementSim()
    sim.attach_line("ngfw-a-2g", "setup")
    sim.preview_invoice()
    sim.request_send()
    out = sim.attach_line("ngfw-a-2g", "recurring")
    assert not out["ok"]
    assert out.get("forbidden")
