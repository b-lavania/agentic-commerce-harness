from ach.entitlements.sim import EntitlementSim


def test_cannot_set_amount():
    sim = EntitlementSim()
    out = sim.attach_line("nl-14", "setup", amount_cents=1)
    assert not out["ok"]
    assert out.get("forbidden")


def test_sent_immutable():
    sim = EntitlementSim()
    sim.attach_line("nl-14", "setup")
    sim.preview_invoice()
    sim.request_send()
    out = sim.attach_line("nl-14", "recurring")
    assert not out["ok"]
    assert out.get("forbidden")


def test_send_from_draft_refused():
    sim = EntitlementSim()
    sim.attach_line("nl-14", "setup")
    out = sim.request_send()
    assert not out["ok"]
    assert sim.invoice.state == "draft"


def test_incomplete_bill_to_blocks_send():
    sim = EntitlementSim()
    sim.load_shortlist(bill_to={"partner_id": "p-100"})
    sim.attach_line("nl-14", "setup")
    sim.preview_invoice()
    out = sim.request_send()
    assert out.get("recon_blocked")
    assert sim.invoice.state == "generated"


def test_rate_usage_does_not_attach():
    sim = EntitlementSim()
    out = sim.rate_usage(
        "b1",
        units=10,
        sku_id="usage-backup-gb",
        attribution={"partner_id": "p-100", "smb_id": "smb-9", "subscription_id": "sub-77"},
    )
    assert out["ok"]
    assert out["rated_cents"] == 1000
    assert sim.invoice.lines == []


def test_usage_qty_mismatch_blocks_preview():
    sim = EntitlementSim()
    attr = {"partner_id": "p-100", "smb_id": "smb-9", "subscription_id": "sub-77"}
    sim.rate_usage("b1", units=4, sku_id="usage-backup-gb", attribution=attr)
    sim.attach_line("usage-backup-gb", "usage", qty=5, attribution=attr)
    out = sim.preview_invoice()
    assert out.get("recon_blocked")
    assert sim.invoice.state == "draft"


def test_return_to_draft_then_remove():
    sim = EntitlementSim()
    sim.attach_line("nl-14", "setup")
    sim.preview_invoice()
    blocked = sim.attach_line("nl-14", "recurring")
    assert blocked["error"] == "return to draft before editing lines"
    back = sim.return_to_draft()
    assert back["ok"]
    assert "preview_ok" not in sim.checklist.milestones
    removed = sim.remove_line("nl-14", "setup")
    assert removed["ok"]
    assert sim.invoice.lines == []


def test_credit_memo_copies_cents_and_leaves_sent():
    sim = EntitlementSim()
    sim.attach_line("nl-14", "setup")
    sim.preview_invoice()
    sim.request_send()
    before = sim.invoice.model_dump()
    out = sim.propose_credit_memo(
        sim.invoice.id,
        "correction",
        line_refs=[{"sku_id": "nl-14", "line_type": "setup"}],
    )
    assert out["ok"]
    assert sim.invoice.model_dump() == before
    assert sim.credit_memos[0].lines[0].amount_cents == 150000
    attr = {"partner_id": "p-100", "smb_id": "smb-9", "subscription_id": "sub-77"}
    sim.rate_usage("b1", units=2, sku_id="usage-backup-gb", attribution=attr)
    attached = sim.attach_line("usage-backup-gb", "usage", qty=2, attribution=attr)
    assert attached["ok"]
    assert sim.invoice.lines == [before_line for before_line in sim.invoice.lines]
    assert sim.next_invoice.lines[0].line_type == "usage"
    assert sim.invoice.model_dump() == before


def test_checkout_does_not_open_session():
    sim = EntitlementSim()
    out = sim.step("checkout", {})
    assert out["forbidden"]
    assert sim.checkout_session_id is None


def test_unpriced_line_fails():
    sim = EntitlementSim()
    out = sim.attach_line("pl-display", "setup")
    assert not out["ok"]
