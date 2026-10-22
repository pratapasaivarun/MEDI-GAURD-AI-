from decimal import Decimal

import mediguard.ai.analysis as analysis
from test_comparison_reports import _comparison


class _Response:
    ok = True
    status = "ok"
    error = None

    def __init__(self, parsed):
        self.parsed = parsed
        self.finalized = None

    def finalize(self, accepted, reason, accepted_into):
        self.finalized = (accepted, reason, accepted_into)


def _payload():
    comparison = _comparison()
    return analysis.build_analysis_payload({"comparison": comparison, "rules": {"status": comparison.status}})


def test_analysis_payload_has_only_supplied_claim_facts_and_source_clause():
    payload = _payload()
    assert payload["verdict"] == "possible_discrepancy"
    assert payload["estimated_payment"] == "111600.00"
    assert payload["insurer_paid"] == "102600.00"
    assert payload["difference"] == "9000.00"
    assert payload["deductions"] == [{
        "deduction_id": "deduction-01", "category": "PHARMACY",
        "description": "Medicines outside the hospitalization window",
        "amount": "10000.00", "insurer_reason": "Medicines outside the hospitalization window",
        "python_assessment": "not_supported",
    }]
    assert payload["clauses"][0]["clause_id"] == "3.4"
    assert payload["clauses"][0]["page"] == 9


def test_analysis_accepts_grounded_explanation_and_ignores_candidate_decision(monkeypatch):
    payload = _payload()
    fake = _Response({
        "status": "rejected", "amount": 1,
        "explanation": "The possible difference is INR 9,000.00; see page 9.",
        "deductions": [{"deduction_id": "deduction-01", "assessment": "not_supported", "clause_id": "3.4", "rationale": "The cited text discusses payable medicines."}],
    })
    monkeypatch.setattr(analysis.llm_gateway, "chat_json", lambda *args, **kwargs: fake)
    result = analysis.analyze_payload(payload, "claim-1", "rules template")
    assert fake.finalized[0] is True
    assert result["accepted"] is True
    assert result["explanation"] == fake.parsed["explanation"]
    assert "status" not in result and "amount" not in result


def test_analysis_rejects_hallucinated_amount_and_uses_template(monkeypatch):
    payload = _payload()
    fake = _Response({
        "explanation": "The difference is INR 9,999.00.",
        "deductions": [{"deduction_id": "deduction-01", "assessment": "not_supported", "clause_id": None, "rationale": "No clause was found."}],
    })
    monkeypatch.setattr(analysis.llm_gateway, "chat_json", lambda *args, **kwargs: fake)
    result = analysis.analyze_payload(payload, "claim-2", "rules-based fallback")
    assert fake.finalized[0] is False
    assert "unsupported number" in fake.finalized[1]
    assert result["accepted"] is False
    assert result["explanation"] == "rules-based fallback"


def test_analysis_rejects_citation_for_another_deduction(monkeypatch):
    payload = _payload()
    payload["deductions"].append({"deduction_id": "deduction-02", "category": "ROOM", "description": "Room rent", "amount": "500.00", "insurer_reason": "Room cap"})
    fake = _Response({
        "explanation": "The insurer paid INR 102,600.00.",
        "deductions": [
            {"deduction_id": "deduction-01", "assessment": "not_supported", "clause_id": "not-supplied", "rationale": "The clause supports this."},
            {"deduction_id": "deduction-02", "assessment": "unclear", "clause_id": None, "rationale": "No clause was found."},
        ],
    })
    monkeypatch.setattr(analysis.llm_gateway, "chat_json", lambda *args, **kwargs: fake)
    result = analysis.analyze_payload(payload, "claim-3", "fallback")
    assert result["accepted"] is False
    assert "clause" in result["reason"]


def test_analysis_requires_every_deduction_and_limits_word_counts():
    payload = _payload()
    valid = {"explanation": "A short explanation.", "deductions": []}
    assert analysis.validate_analysis_output(valid, payload) == (False, "Analysis must assess every supplied deduction exactly once")
    too_long = {"explanation": "word " * 81, "deductions": []}
    assert analysis.validate_analysis_output(too_long, {**payload, "deductions": []})[0] is False


def test_python_disagreement_is_returned_only_as_reviewer_candidate(monkeypatch):
    payload = _payload()
    fake = _Response({
        "explanation": "There is no discrepancy; the insurer deduction matches the policy.",
        "deductions": [{"deduction_id": "deduction-01", "assessment": "supported", "clause_id": "3.4", "rationale": "The supplied clause describes payable medicines."}],
    })
    monkeypatch.setattr(analysis.llm_gateway, "chat_json", lambda *args, **kwargs: fake)
    result = analysis.analyze_payload(payload, "claim-4", "Python template")
    assert result["accepted"] is False
    assert result["explanation"] == "Python template"
    assert result["reviewer_candidate"]["explanation"] == fake.parsed["explanation"]
    assert result["reviewer_candidate"]["deductions"][0]["assessment"] == "supported"


def test_manual_review_analysis_cannot_claim_the_case_is_resolved(monkeypatch):
    payload = {**_payload(), "verdict": "manual_review", "deductions": [], "clauses": []}
    fake = _Response({
        "explanation": (
            "The insurer paid the full estimated payment of INR 111,600.00. "
            "The difference is zero, so the payment matches exactly."
        ),
        "deductions": [],
    })
    monkeypatch.setattr(analysis.llm_gateway, "chat_json", lambda *args, **kwargs: fake)
    result = analysis.analyze_payload(payload, "claim-manual-review", "An authorized reviewer must confirm the inputs.")
    assert fake.finalized[0] is False
    assert "disagrees with the Python comparison" in fake.finalized[1]
    assert result["accepted"] is False
    assert result["explanation"] == "An authorized reviewer must confirm the inputs."


def test_analysis_cannot_say_python_approved_or_denied_a_claim():
    payload = {**_payload(), "verdict": "no_discrepancy", "deductions": [], "clauses": []}
    output = {
        "explanation": "The claim was approved with no discrepancies.",
        "deductions": [],
    }
    accepted, reason = analysis.validate_analysis_output(output, payload)
    assert accepted is False
    assert reason == "Analysis must not make an insurer or claim decision"
