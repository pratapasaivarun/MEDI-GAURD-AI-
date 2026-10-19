"""Comprehensive test suite covering all 22 patient-centered insurance scenarios for MediGuard AI."""
from decimal import Decimal
import pytest

from mediguard.engine.rules import (
    PolicyTerms,
    evaluate_claim,
    evaluate_line_item,
    verify_patient_name_match,
    validate_expense_date_window,
    detect_line_item_duplicates,
    validate_daycare_procedure,
)


# 1. Covered Medical / Surgical Expenses
def test_01_covered_medical_expenses():
    terms = PolicyTerms(annual_limit=Decimal("500000"), deductible=Decimal("0"), copay_percent=Decimal("0"))
    line_items = [
        {"description": "Surgeon Fee", "amount": 50000.0, "category": "surgery"},
        {"description": "OT Charges", "amount": 20000.0, "category": "surgery"},
    ]
    res = evaluate_claim(70000.0, terms=terms, line_items=line_items)
    assert res["status"] == "approved"
    assert res["covered_amount"] == 70000.0
    assert res["payable_amount"] == 70000.0


# 2. Excluded Expenses (Cosmetic / Sundries)
def test_02_excluded_expenses():
    terms = PolicyTerms(
        annual_limit=Decimal("500000"),
        deductible=Decimal("0"),
        copay_percent=Decimal("0"),
        source={"exclusions": {"value": ["toiletry kit", "cosmetic"]}},
    )
    line_items = [
        {"description": "Surgical Operation", "amount": 30000.0, "category": "surgery"},
        {"description": "Patient Toiletry Kit", "amount": 500.0, "category": "sundry"},
    ]
    res = evaluate_claim(30500.0, terms=terms, line_items=line_items)
    assert res["status"] == "partially_approved"
    assert res["line_item_results"][1]["status"] == "excluded"
    assert res["line_item_results"][1]["covered_amount"] == 0.0
    assert res["payable_amount"] == 30000.0


# 3. Non-Medical Charges (Registration, Housekeeping, TV)
def test_03_non_medical_charges():
    terms = PolicyTerms(
        annual_limit=Decimal("500000"),
        deductible=Decimal("0"),
        copay_percent=Decimal("0"),
        source={"exclusions": {"value": ["registration", "housekeeping", "television"]}},
    )
    line_items = [
        {"description": "Doctor Visit", "amount": 2000.0, "category": "consultation"},
        {"description": "Admission Registration", "amount": 500.0, "category": "admin"},
        {"description": "Television Charges", "amount": 400.0, "category": "admin"},
    ]
    res = evaluate_claim(2900.0, terms=terms, line_items=line_items)
    assert res["status"] == "partially_approved"
    assert res["covered_amount"] == 2000.0


# 4. Room-Rent Limits & Proportional Deduction
def test_04_room_rent_limits_and_proportional_deduction():
    terms = PolicyTerms(
        annual_limit=Decimal("500000"),
        deductible=Decimal("0"),
        copay_percent=Decimal("0"),
        room_limit_per_day=Decimal("5000"),
    )
    context = {
        "room_charge": 40000.0,  # Billed 10k/day for 4 days (Limit is 5k/day = 20k)
        "room_days": 4,
        "room_linked_charges": 40000.0,  # Factor = 20k / 40k = 0.5; reduction = 20k room + 20k linked = 40k total reduction
    }
    res = evaluate_claim(80000.0, terms=terms, claim_context=context)
    assert res["status"] == "partially_approved"
    assert res["covered_amount"] == 40000.0
    assert "room_limit_proportional_applied" in res["warnings"]


# 5. ICU Limits (Below, Exact, Above, Uncertain)
def test_05_icu_limits_below_exact_above_uncertain():
    # A. Below Limit
    terms_icu = PolicyTerms(annual_limit=Decimal("500000"), deductible=Decimal("0"), copay_percent=Decimal("0"), icu_limit_per_day=Decimal("10000"))
    item_below = {"description": "ICU Room Charge", "amount": 16000.0, "days": 2, "category": "icu"}
    res_a = evaluate_claim(16000.0, terms=terms_icu, line_items=[item_below])
    assert res_a["line_item_results"][0]["status"] == "covered"
    assert res_a["covered_amount"] == 16000.0

    # B. Exactly at Limit (10k * 2 = 20k)
    item_exact = {"description": "ICU Stay", "amount": 20000.0, "days": 2, "category": "icu"}
    res_b = evaluate_claim(20000.0, terms=terms_icu, line_items=[item_exact])
    assert res_b["line_item_results"][0]["status"] == "covered"
    assert res_b["covered_amount"] == 20000.0

    # C. Above Limit (Billed 30k for 2 days @ 10k/day = Capped at 20k)
    item_above = {"description": "ICU Stay High Rate", "amount": 30000.0, "days": 2, "category": "icu"}
    res_c = evaluate_claim(30000.0, terms=terms_icu, line_items=[item_above])
    assert res_c["line_item_results"][0]["status"] == "partial"
    assert res_c["line_item_results"][0]["covered_amount"] == 20000.0

    # D. Missing/Uncertain ICU Limit -> Manual Review
    terms_no_icu = PolicyTerms(annual_limit=Decimal("500000"), deductible=Decimal("0"), copay_percent=Decimal("0"), icu_limit_per_day=None)
    item_uncertain = {"description": "ICU Stay", "amount": 20000.0, "days": 2, "category": "icu"}
    res_d = evaluate_claim(20000.0, terms=terms_no_icu, line_items=[item_uncertain], claim_context={"icu_limit_uncertain": True})
    assert res_d["status"] == "manual_review"


# 6. Procedure / Sub-Limits
def test_06_procedure_sub_limits():
    terms = PolicyTerms(
        annual_limit=Decimal("500000"),
        deductible=Decimal("0"),
        copay_percent=Decimal("0"),
        sub_limits={"surgery": Decimal("40000")},
    )
    line_items = [{"description": "Laparoscopic Appendicectomy", "amount": 60000.0, "category": "surgery"}]
    res = evaluate_claim(60000.0, terms=terms, line_items=line_items)
    assert res["status"] == "partially_approved"
    assert res["line_item_results"][0]["covered_amount"] == 40000.0


# 7. Deductibles
def test_07_deductibles():
    terms = PolicyTerms(annual_limit=Decimal("500000"), deductible=Decimal("10000"), copay_percent=Decimal("0"))
    res = evaluate_claim(50000.0, terms=terms)
    assert res["deductible"] == 10000.0
    assert res["payable_amount"] == 40000.0


# 8. Co-Pay
def test_08_copay():
    terms = PolicyTerms(annual_limit=Decimal("500000"), deductible=Decimal("0"), copay_percent=Decimal("20"))
    res = evaluate_claim(50000.0, terms=terms)
    assert res["copayment"] == 10000.0  # 20% of 50,000 = 10,000
    assert res["payable_amount"] == 40000.0


# 9. Waiting Periods
def test_09_waiting_periods():
    terms = PolicyTerms(annual_limit=Decimal("500000"), deductible=Decimal("0"), copay_percent=Decimal("0"), waiting_period_months=24)
    line_items = [{"description": "Pre-Existing Diabetes Treatment", "amount": 20000.0, "category": "diabetes"}]
    context = {"waiting_period_satisfied": False, "waiting_period_affected_categories": ["diabetes"]}
    res = evaluate_claim(20000.0, terms=terms, line_items=line_items, claim_context=context)
    assert res["line_item_results"][0]["status"] == "excluded"
    assert res["covered_amount"] == 0.0


# 10. Policy Exclusions (Diagnosis Match)
def test_10_policy_exclusions():
    terms = PolicyTerms(
        annual_limit=Decimal("500000"),
        deductible=Decimal("0"),
        copay_percent=Decimal("0"),
        source={"exclusions": {"value": ["cosmetic surgery", "obesity"]}},
    )
    context = {"diagnosis": "Bariatric Obesity Surgery", "exclusion_match": {"matched": True, "confidence": 0.95}}
    res = evaluate_claim(150000.0, terms=terms, claim_context=context)
    assert res["status"] == "manual_review"
    assert "DIAGNOSIS_EXCLUSION" in " ".join(res["warnings"])


# 11. Partial Approval
def test_11_partial_approval():
    terms = PolicyTerms(annual_limit=Decimal("500000"), deductible=Decimal("0"), copay_percent=Decimal("0"), sub_limits={"consultation": Decimal("3000")})
    line_items = [{"description": "Senior Specialist Consultation", "amount": 5000.0, "category": "consultation"}]
    res = evaluate_claim(5000.0, terms=terms, line_items=line_items)
    assert res["status"] == "partially_approved"
    assert res["payable_amount"] == 3000.0


# 12. Rejection (Out-of-Network Hard Denial)
def test_12_rejection():
    terms = PolicyTerms(
        annual_limit=Decimal("500000"),
        deductible=Decimal("0"),
        copay_percent=Decimal("0"),
        source={"network_required": {"value": True}},
    )
    context = {"in_network": False}
    res = evaluate_claim(50000.0, terms=terms, claim_context=context)
    assert res["status"] == "rejected"


# 13. Manual Review / Uncertain Cases
def test_13_manual_review():
    terms = PolicyTerms(annual_limit=Decimal("500000"), deductible=Decimal("0"), copay_percent=Decimal("0"))
    res = evaluate_claim(50000.0, terms=terms, missing_fields=["bill_date", "doctor_signature"])
    assert res["status"] == "manual_review"
    assert "Missing required fields: bill_date, doctor_signature" in res["warnings"]


# 14. Duplicate Charge Detection
def test_14_duplicate_charge_detection():
    # A. Exact duplicates are retained and routed to reviewer confirmation.
    items_dup = [
        {"description": "Blood Test CBC", "amount": 1500.0, "date": "10-Aug-2026", "quantity": 1},
        {"description": "Blood Test CBC", "amount": 1500.0, "date": "10-Aug-2026", "quantity": 1},
    ]
    terms = PolicyTerms(annual_limit=Decimal("500000"), deductible=Decimal("0"), copay_percent=Decimal("0"))
    res_a = evaluate_claim(3000.0, terms=terms, line_items=items_dup)
    assert res_a["line_item_results"][1]["status"] == "covered"
    assert res_a["line_item_results"][1]["possible_duplicate"] is True
    assert res_a["status"] == "manual_review"

    # B. Legitimate Repeat Service -> Covered
    items_legit = [
        {"description": "Duty Doctor Visit", "amount": 500.0, "date": "10-Aug-2026", "quantity": 1, "legitimate_repeat": True},
        {"description": "Duty Doctor Visit", "amount": 500.0, "date": "11-Aug-2026", "quantity": 1, "legitimate_repeat": True},
    ]
    res_b = evaluate_claim(1000.0, terms=terms, line_items=items_legit)
    assert res_b["line_item_results"][0]["status"] == "covered"
    assert res_b["line_item_results"][1]["status"] == "covered"

    # C. Ambiguous Duplicate -> Manual Review
    res_c = evaluate_claim(3000.0, terms=terms, line_items=items_dup, claim_context={"duplicate_suspected": True})
    assert res_c["status"] == "manual_review"


# 15. Bill <-> Policy Patient Name Mismatch
def test_15_bill_policy_name_mismatch():
    # Exact Match
    assert verify_patient_name_match("Arun Kumar", "ARUN KUMAR")["result"] == "MATCH"
    # Case & Spacing Variation -> MATCH
    assert verify_patient_name_match("Arun  Kumar", "ARUN KUMAR")["result"] == "MATCH"
    # A shortened surname is not accepted as an identity match.
    assert verify_patient_name_match("Arun K.", "ARUN KUMAR")["result"] == "MISMATCH"
    # Genuine Mismatch -> MISMATCH
    mismatch = verify_patient_name_match("Rahul Kumar", "ARUN KUMAR")
    assert mismatch["result"] == "MISMATCH"

    terms = PolicyTerms(annual_limit=Decimal("500000"), deductible=Decimal("0"), copay_percent=Decimal("0"))
    res_mismatch = evaluate_claim(10000.0, terms=terms, claim_context={"bill_patient_name": "Rahul Kumar", "policy_holder_name": "Arun Kumar"})
    assert res_mismatch["status"] == "manual_review"


# 16. Seemingly Covered Items Excluded
def test_16_seemingly_covered_items_excluded():
    terms = PolicyTerms(
        annual_limit=Decimal("500000"),
        deductible=Decimal("0"),
        copay_percent=Decimal("0"),
        source={"exclusions": {"value": ["endo-gia stapler", "harmonic scalpel"]}},
    )
    line_items = [
        {"description": "Laparoscopic OT", "amount": 18000.0, "category": "surgery"},
        {"description": "Endo-GIA Stapler with reload", "amount": 9800.0, "category": "surgery"},
    ]
    res = evaluate_claim(27800.0, terms=terms, line_items=line_items)
    assert res["line_item_results"][1]["status"] == "excluded"
    assert res["line_item_results"][1]["applied_rule"] == "exclusion"


# 17. Policy-Clause Verification
def test_17_policy_clause_verification():
    from mediguard.ai.agents import policy_agent_node
    state = {
        "policy_text": "Section 4.1 Exclusions: Endo-GIA staplers and harmonic scalpels are non-payable items under this policy.",
        "policy_id": "policy-101",
        "normalized_claim": {"diagnosis": "Appendicitis"},
        "rule_results": {
            "line_item_results": [
                {"description": "Endo-GIA Stapler", "status": "excluded", "applied_rule": "exclusion", "category": "surgery"}
            ]
        },
    }
    node_res = policy_agent_node(state)
    assert len(node_res["policy_evidence"]) > 0
    assert "policy_findings" in node_res


# 18. Itemized Multi-Line Bill Processing
def test_18_itemized_multi_line_bill_processing():
    terms = PolicyTerms(annual_limit=Decimal("500000"), deductible=Decimal("0"), copay_percent=Decimal("0"))
    line_items = [
        {"description": "Item A", "amount": 1000.0},
        {"description": "Item B", "amount": 2000.0},
        {"description": "Item C", "amount": 3000.0},
    ]
    res = evaluate_claim(6000.0, terms=terms, line_items=line_items)
    assert len(res["line_item_results"]) == 3
    assert res["covered_amount"] == 6000.0


# 19. Annual Sum Insured Capping
def test_19_annual_sum_insured_capping():
    terms = PolicyTerms(annual_limit=Decimal("50000"), deductible=Decimal("0"), copay_percent=Decimal("0"))
    line_items = [{"description": "Major Cardiac Surgery", "amount": 120000.0, "category": "surgery"}]
    res = evaluate_claim(120000.0, terms=terms, line_items=line_items)
    assert res["status"] == "partially_approved"
    assert res["covered_amount"] == 50000.0


# 20. Multi-Claim / Cumulative Sum Insured Exhaustion
def test_20_multi_claim_cumulative_sum_insured_exhaustion():
    # Annual Limit 5 Lakhs, Previous Approved Claims = 4 Lakhs -> Remaining Sum Insured = 1 Lakh
    terms = PolicyTerms(annual_limit=Decimal("500000"), deductible=Decimal("0"), copay_percent=Decimal("0"), previous_claims_total=Decimal("400000"))
    line_items = [{"description": "Second Hospitalization Bill", "amount": 150000.0, "category": "surgery"}]
    res = evaluate_claim(150000.0, terms=terms, line_items=line_items)
    assert res["status"] == "partially_approved"
    assert res["covered_amount"] == 100000.0  # Capped at remaining 1 Lakh balance

    # Previous claims already 5 Lakhs -> Fully Exhausted Rejection
    terms_exhausted = PolicyTerms(annual_limit=Decimal("500000"), deductible=Decimal("0"), copay_percent=Decimal("0"), previous_claims_total=Decimal("500000"))
    res_exhausted = evaluate_claim(50000.0, terms=terms_exhausted)
    assert res_exhausted["status"] == "rejected"
    assert "Annual sum insured is fully exhausted by previous claims." in res_exhausted["warnings"]


# 21. Pre- & Post-Hospitalization Expenses
def test_21_pre_post_hospitalization_expenses():
    terms = PolicyTerms(
        annual_limit=Decimal("500000"),
        deductible=Decimal("0"),
        copay_percent=Decimal("0"),
        pre_hospitalization_days=30,
        post_hospitalization_days=60,
    )
    context = {"admission_date": "10-Jan-2026", "discharge_date": "15-Jan-2026"}

    # A. Valid Pre-Hosp (15-Dec-2025 is within 30 days of 10-Jan-2026)
    valid_pre = validate_expense_date_window("15-Dec-2025", context["admission_date"], context["discharge_date"], 30, 60, "pre_hospitalization")
    assert valid_pre["status"] == "covered"

    # B. Pre-Hosp Outside Window (01-Nov-2025 is outside 30 days)
    invalid_pre = validate_expense_date_window("01-Nov-2025", context["admission_date"], context["discharge_date"], 30, 60, "pre_hospitalization")
    assert invalid_pre["status"] == "excluded"

    # C. Valid Post-Hosp (10-Feb-2026 is within 60 days of 15-Jan-2026)
    valid_post = validate_expense_date_window("10-Feb-2026", context["admission_date"], context["discharge_date"], 30, 60, "post_hospitalization")
    assert valid_post["status"] == "covered"

    # D. Post-Hosp Outside Window (20-Apr-2026 is outside 60 days)
    invalid_post = validate_expense_date_window("20-Apr-2026", context["admission_date"], context["discharge_date"], 30, 60, "post_hospitalization")
    assert invalid_post["status"] == "excluded"

    # E. Line Item Integration Test
    items = [
        {"description": "Pre-Op OPD Consult", "amount": 2000.0, "date": "01-Nov-2025", "category": "pre_hospitalization"},
        {"description": "Hospital Surgery", "amount": 50000.0, "date": "12-Jan-2026", "category": "surgery"},
    ]
    res = evaluate_claim(52000.0, terms=terms, line_items=items, claim_context=context)
    assert res["line_item_results"][0]["status"] == "excluded"
    assert res["line_item_results"][1]["status"] == "covered"
    assert res["covered_amount"] == 50000.0


# 22. Day-Care Procedures
def test_22_daycare_procedures():
    terms = PolicyTerms(
        annual_limit=Decimal("500000"),
        deductible=Decimal("0"),
        copay_percent=Decimal("0"),
        daycare_procedures=["Cataract Surgery", "Chemotherapy", "Dialysis"],
    )

    # A. Included Daycare Procedure (0-night stay) -> Covered
    res_included = validate_daycare_procedure("Cataract Surgery", terms.daycare_procedures, length_of_stay_nights=0)
    assert res_included["status"] == "covered"

    # B. Procedure Not Included in Whitelist -> Excluded
    res_unlisted = validate_daycare_procedure("Cosmetic Laser", terms.daycare_procedures, length_of_stay_nights=0)
    assert res_unlisted["status"] == "excluded"

    # C. Claim Evaluation Integration
    context_daycare = {"procedure": "Cataract Surgery", "length_of_stay_nights": 0, "is_daycare": True}
    res_claim = evaluate_claim(25000.0, terms=terms, claim_context=context_daycare)
    assert res_claim["status"] == "approved"
