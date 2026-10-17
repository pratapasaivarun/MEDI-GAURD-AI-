from decimal import Decimal

import policy_terms


def test_llm_policy_term_is_unverified_with_reduced_confidence(monkeypatch):
    monkeypatch.setattr(
        policy_terms,
        "_llm_extract_policy_terms_fallback",
        lambda _rows: {"annual_limit": 500000},
    )
    result = policy_terms.extract_policy_terms([{"text": "Policy benefit provisions", "page": 7}])
    term = result["terms_json"]["annual_limit"]
    assert term["value"] == "500000"
    assert term["confidence"] == 0.60
    assert term["method"] == "llm_fallback"
    assert term["needs_review"] is True
    assert term["source_text"] == "extracted via LLM (unverified)"
    assert term["source_page"] == 7


def test_excluded_sentence_yields_short_unverified_policy_term(monkeypatch):
    monkeypatch.setattr(policy_terms, "_llm_extract_policy_terms_fallback", lambda _rows: None)
    result = policy_terms.extract_policy_terms([
        {"text": "Cosmetic surgery is excluded from coverage.", "page": 4}
    ])
    exclusion = result["terms_json"]["exclusions"]
    assert exclusion["value"] == ["cosmetic surgery"]
    assert exclusion["needs_review"] is True
    assert exclusion["source_page"] == 4
