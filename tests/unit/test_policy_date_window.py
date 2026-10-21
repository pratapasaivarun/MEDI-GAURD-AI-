from datetime import date
from decimal import Decimal

from mediguard.engine.rules import PolicyTerms, evaluate_claim
from mediguard.policy.policy_terms import extract_policy_terms, terms_from_json


def test_policy_pdf_wording_extracts_both_date_windows():
    extracted = extract_policy_terms([{
        "text": "Pre-hospitalization expenses are covered up to 30 days before admission; "
                "post-hospitalization expenses are covered up to 60 days after discharge.",
        "page": 3,
        "source_name": "fictional-policy.pdf",
    }])
    pre = extracted["terms_json"]["pre_hospitalization_days"]
    post = extracted["terms_json"]["post_hospitalization_days"]
    assert (pre["value"], pre["source_page"]) == (30, 3)
    assert (post["value"], post["source_page"]) == (60, 3)
    terms, _, _ = terms_from_json(extracted["terms_json"])
    assert terms.pre_hospitalization_days == 30
    assert terms.post_hospitalization_days == 60


def test_date_window_excludes_a_line_outside_the_policy_window():
    result = evaluate_claim(
        Decimal("10000"),
        PolicyTerms(annual_limit=Decimal("10000"), deductible=Decimal("0"), copay_percent=Decimal("10"), pre_hospitalization_days=30),
        line_items=[{"description": "Eligible treatment", "category": "other", "amount": Decimal("10000"), "date": "2026-06-01", "confidence": 0.95}],
        claim_context={"admission_date": date(2026, 8, 10), "discharge_date": date(2026, 8, 14)},
    )
    assert result["line_item_results"][0]["covered_amount"] == 0
    assert result["line_item_results"][0]["applied_rule"] == "pre_hospitalization"
    assert result["payable_amount"] == 0


def test_missing_line_date_with_policy_window_is_explicitly_unverified():
    result = evaluate_claim(
        Decimal("10000"),
        PolicyTerms(annual_limit=Decimal("10000"), deductible=Decimal("0"), copay_percent=Decimal("10"), pre_hospitalization_days=30),
        line_items=[{"description": "Eligible treatment", "category": "other", "amount": Decimal("10000"), "confidence": 0.95}],
        claim_context={"admission_date": date(2026, 8, 10), "discharge_date": date(2026, 8, 14)},
    )
    assert result["status"] == "manual_review"
    assert result["line_item_results"][0]["status"] == "needs_review"
    assert "date-window check could not be done" in result["line_item_results"][0]["calculation"]
