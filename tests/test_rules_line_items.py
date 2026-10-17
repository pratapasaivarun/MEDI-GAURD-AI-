from decimal import Decimal

from models import BillData, LineItem, PolicyTerms as TypedPolicyTerms
from rules import PolicyTerms, evaluate_claim, verify_patient_name_match


def test_room_line_cap_and_proportionate_doctor_nursing_reduction():
    terms = PolicyTerms(annual_limit=Decimal("500000"), deductible=Decimal("0"), copay_percent=Decimal("0"), room_limit_per_day=Decimal("5000"))
    result = evaluate_claim(
        Decimal("36000"), terms,
        line_items=[
            {"description": "Room rent", "category": "ROOM", "amount": Decimal("24000")},
            {"description": "Doctor and nursing fees", "category": "DOCTOR_NURSING", "amount": Decimal("12000")},
        ],
        claim_context={"room_days": 4},
    )
    assert result["line_item_results"][0]["covered_amount"] == 20000
    assert result["line_item_results"][0]["applied_rule"] == "room_limit"
    assert result["line_item_results"][1]["covered_amount"] == 10000
    assert result["line_item_results"][1]["applied_rule"] == "proportionate_deduction"


def test_diagnosis_exclusion_always_routes_to_manual_review():
    terms = PolicyTerms(annual_limit=Decimal("500000"), deductible=Decimal("0"), copay_percent=Decimal("0"), source={"exclusions": {"value": ["cosmetic surgery"]}})
    result = evaluate_claim(Decimal("1000"), terms, line_items=[{"description": "Surgery charges", "category": "surgery", "amount": Decimal("1000")}], claim_context={"diagnosis": "cosmetic surgery"})
    assert result["status"] == "manual_review"
    assert any("DIAGNOSIS_EXCLUSION" in warning for warning in result["warnings"])


def test_duplicate_lines_are_kept_and_flagged_for_review():
    terms = PolicyTerms(annual_limit=Decimal("500000"), deductible=Decimal("0"), copay_percent=Decimal("0"))
    items = [
        {"description": "CBC blood test", "category": "investigation", "amount": Decimal("500")},
        {"description": "CBC blood test", "category": "investigation", "amount": Decimal("500")},
    ]
    result = evaluate_claim(Decimal("1000"), terms, line_items=items)
    assert len(result["line_item_results"]) == 2
    assert result["covered_amount"] == 1000
    assert result["status"] == "manual_review"
    assert any("POSSIBLE_DUPLICATE" in warning for warning in result["warnings"])


def test_item_total_mismatch_over_one_percent_requires_review():
    terms = PolicyTerms(annual_limit=Decimal("500000"), deductible=Decimal("0"), copay_percent=Decimal("0"))
    items = [{"description": "Hospital services", "category": "other", "amount": Decimal("95500")}]
    result = evaluate_claim(Decimal("100000"), terms, line_items=items)
    assert result["status"] == "manual_review"
    assert result["line_item_reconciliation_failed"] is True
    assert "TOTAL_MISMATCH" in " ".join(result["warnings"])


def test_patient_name_requires_exact_surname_and_accepts_initial():
    assert verify_patient_name_match("Anil Kumar", "Sunil Kumar")["result"] == "MISMATCH"
    assert verify_patient_name_match("A. Kumar", "Anil Kumar")["result"] == "MINOR_VARIATION"


def test_typed_contract_uses_the_same_deterministic_rule_path():
    bill = BillData(
        patient_name="Ravi Reddy",
        policy_number="POL-558201",
        admission_date=None,
        discharge_date=None,
        room_days=4,
        total_amount=Decimal("24000"),
        line_items=[LineItem("Room rent", "ROOM", Decimal("24000"))],
    )
    terms = TypedPolicyTerms(sum_insured=Decimal("500000"), room_rent_cap_per_day=Decimal("5000"), copay_percent=Decimal("0"))
    result = evaluate_claim(bill, terms)
    assert result.status == "computed"
    assert result.lines[0].allowed == Decimal("20000.00")
    assert result.lines[0].reason_code == "ROOM_CAP"


def test_missing_policy_terms_default_to_manual_review():
    result = evaluate_claim(Decimal("10000"))
    assert result["status"] == "manual_review"
    assert result["deductible"] == 0
    assert result["payable_amount"] == 0
    assert result["warnings"] == ["Required policy terms missing: annual_limit, deductible, copay_percent"]
