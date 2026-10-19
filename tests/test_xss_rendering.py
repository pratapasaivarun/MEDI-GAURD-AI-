from mediguard.services import application as app


PAYLOAD = "<script>alert(1)</script>"


def _assert_escaped(markup):
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in markup
    assert "<script>" not in markup


def test_page_header_escapes_untrusted_title():
    _assert_escaped(app.page_header_html("EYE", PAYLOAD, "safe", "icon"))


def test_auth_portal_markup_escapes_interpolated_values():
    _assert_escaped(app.auth_portal_html("USER", PAYLOAD, "safe"))


def test_claimant_claim_context_rendering_escapes_claim_values():
    _assert_escaped(app.claim_context_html({"claim_number": PAYLOAD, "patient_name": PAYLOAD, "policy_number": "POL-1"}, "approved"))


def test_review_queue_claim_row_rendering_escapes_claim_values():
    _assert_escaped(app.claim_row_html({"claim_number": PAYLOAD, "patient_name": PAYLOAD, "hospital_name": "Hospital", "status": "draft"}))


def test_reviewer_claim_context_rendering_escapes_claim_values():
    _assert_escaped(app.claim_context_html({"claim_number": "CLM-1", "patient_name": PAYLOAD, "policy_number": "POL-1"}, "manual_review"))


def test_deterministic_status_markup_uses_allowlisted_status():
    markup = app.deterministic_result_header_html(PAYLOAD)
    assert "&lt;script&gt;" not in markup
    assert "<script>" not in markup
    assert "manual_review" in markup


def test_agent_status_markup_uses_allowlisted_status():
    markup = app.evidence_recommendation_header_html(PAYLOAD)
    assert "&lt;script&gt;" not in markup
    assert "<script>" not in markup
    assert "manual_review" in markup
