from ach.driver.curriculum import run_curriculum


def test_h1_to_h2_curriculum():
    result = run_curriculum()
    assert result["ok"], result
    handoff = result["handoff"]
    assert handoff["shortlist_ids"]
    assert handoff["quote_lines"]
    assert handoff["invoice_state"] == "sent"
    assert handoff["checkout_session_id"] is None
    assert all("amount" not in ql for ql in handoff["quote_lines"])
