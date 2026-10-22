import mediguard.ingestion.extraction as extraction
import mediguard.ingestion.settlement as settlement
import mediguard.policy.policy_terms as policy_terms


def _fail_if_called(*_args, **_kwargs):
    raise AssertionError("LLM extraction fallback must be opt-in")


def test_bill_field_fallback_is_off_by_default(monkeypatch):
    monkeypatch.delenv("MEDIGUARD_LLM_EXTRACTION_FALLBACK", raising=False)
    monkeypatch.setattr(extraction, "_llm_extract_claim_fallback", _fail_if_called)
    result = extraction.normalize_documents([{"text": "Unstructured fictional bill text."}])
    assert result.total_amount is None


def test_policy_term_fallback_is_off_by_default(monkeypatch):
    monkeypatch.delenv("MEDIGUARD_LLM_EXTRACTION_FALLBACK", raising=False)
    monkeypatch.setattr(policy_terms, "_llm_extract_policy_terms_fallback", _fail_if_called)
    result = policy_terms.extract_policy_terms([{"text": "Policy benefit provisions", "page": 1}])
    assert result["terms_json"].get("annual_limit") is None


def test_settlement_deduction_fallback_is_off_by_default(monkeypatch):
    monkeypatch.delenv("MEDIGUARD_LLM_EXTRACTION_FALLBACK", raising=False)
    monkeypatch.setattr(settlement, "_llm_deductions", _fail_if_called)
    result = settlement.parse_settlement(
        b"Claim Ref: CLM-FICT-001\nAmount paid: INR 8,000\nSome deductions were applied.",
        "settlement.txt",
    )
    assert result.amount_paid == 8000
    assert result.deductions == []
    assert "Settlement deductions could not be read from the letter." in result.review_reasons
