from decimal import Decimal

from extraction import _infer_line_category
from models import BillData, LineItem, PolicyTerms as TypedPolicyTerms
from rules import evaluate_claim
from policy_terms import extract_policy_terms, terms_from_json


def test_icu_is_a_distinct_category_from_general_room_rent():
    assert _infer_line_category("ICU intensive care daily charges") == "ICU"
    assert _infer_line_category("Private room rent") == "ROOM"


def test_typed_policy_icu_limit_caps_daily_and_marks_rule():
    bill = BillData(
        patient_name="Fictional Patient", policy_number="POL-TEST",
        admission_date=None, discharge_date=None, room_days=2,
        total_amount=Decimal("30000"),
        line_items=[LineItem("ICU intensive care charges", "ICU", Decimal("30000"))],
    )
    terms = TypedPolicyTerms(
        sum_insured=Decimal("500000"), room_rent_cap_per_day=Decimal("5000"),
        icu_limit_per_day=Decimal("10000"), copay_percent=Decimal("0"),
    )
    result = evaluate_claim(bill, terms)
    assert result.lines[0].allowed == Decimal("20000.00")
    assert result.lines[0].reason_code == "ICU_CAP"


def test_icu_without_stated_policy_cap_requires_manual_review():
    bill = BillData(
        patient_name="Fictional Patient", policy_number="POL-TEST",
        admission_date=None, discharge_date=None, room_days=2,
        total_amount=Decimal("30000"),
        line_items=[LineItem("ICU intensive care charges", "ICU", Decimal("30000"))],
    )
    result = evaluate_claim(
        bill,
        TypedPolicyTerms(sum_insured=Decimal("500000"), room_rent_cap_per_day=Decimal("5000")),
    )
    assert result.status == "manual_review"
    assert result.lines[0].reason_code == "ICU_LIMIT_NOT_STATED"


def test_policy_icu_daily_cap_is_extracted_and_loaded_from_reviewed_json():
    extracted = extract_policy_terms("Annual limit INR 500000. Deductible: 0. Copay: 0%. ICU limit per day: INR 12000.")
    assert extracted["terms"].icu_limit_per_day == Decimal("12000")
    reviewed, _missing, _confidence = terms_from_json({
        "annual_limit": {"value": "500000", "confidence": 1},
        "deductible": {"value": "0", "confidence": 1},
        "copay_percent": {"value": "0", "confidence": 1},
        "sub_limits": {"value": {"ICU": "9000"}, "confidence": 1},
    })
    assert reviewed.icu_limit_per_day == Decimal("9000")
