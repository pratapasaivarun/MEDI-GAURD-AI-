from decimal import Decimal

import mediguard.policy.policy_terms as policy_terms
from mediguard.services import application as app


def test_llm_policy_term_is_unverified_with_reduced_confidence(monkeypatch):
    monkeypatch.setenv("MEDIGUARD_LLM_EXTRACTION_FALLBACK", "true")
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


def test_exclusions_header_splits_multiple_items_into_short_terms(monkeypatch):
    monkeypatch.setattr(policy_terms, "_llm_extract_policy_terms_fallback", lambda _rows: None)
    result = policy_terms.extract_policy_terms([
        {"text": "Exclusions: Cosmetic surgery; dental treatment; infertility treatment.", "page": 8}
    ])
    exclusion = result["terms_json"]["exclusions"]
    assert exclusion["value"] == ["cosmetic surgery", "dental treatment", "infertility treatment"]
    assert exclusion["needs_review"] is True
    assert exclusion["source_page"] == 8


def test_annual_limit_exclusion_is_not_misread_as_an_item_exclusion(monkeypatch):
    monkeypatch.setattr(policy_terms, "_llm_extract_policy_terms_fallback", lambda _rows: None)
    result = policy_terms.extract_policy_terms([
        {"text": "Expenses exceeding the annual limit are not covered.", "page": 3}
    ])
    assert "exclusions" not in result["terms_json"]

    mixed = policy_terms.extract_policy_terms([
        {"text": "Exclusions: Cosmetic surgery; expenses above annual limit.", "page": 3}
    ])
    assert mixed["terms_json"]["exclusions"]["value"] == ["cosmetic surgery"]


def test_policy_review_labels_distinguish_llm_estimates_from_other_candidates():
    assert app._policy_term_verification_label({"method": "llm_fallback", "needs_review": True}) == "UNVERIFIED LLM estimate"
    assert app._policy_term_verification_label({"method": "deterministic_keyword", "needs_review": True}) == "UNVERIFIED policy candidate"
