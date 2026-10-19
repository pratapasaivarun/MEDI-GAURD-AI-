from datetime import date
from decimal import Decimal
from pathlib import Path

from mediguard.engine.comparison import compare
from mediguard.engine.models import BillData, Clause, LineItem, PolicyTerms, SettlementData, SettlementDeduction
from mediguard.engine.rules import evaluate_claim
from mediguard.ingestion.settlement import parse_settlement


def _demo_claim():
    bill = BillData(
        patient_name="Ravi Reddy",
        policy_number="POL-558201",
        admission_date=date(2026, 8, 10),
        discharge_date=date(2026, 8, 14),
        room_days=4,
        total_amount=Decimal("132000"),
        line_items=[
            LineItem("Admission and registration", "ADMISSION", Decimal("2000")),
            LineItem("Room rent", "ROOM", Decimal("24000")),
            LineItem("Doctor and nursing fees", "DOCTOR_NURSING", Decimal("12000")),
            LineItem("Hernia surgery and OT", "SURGERY_OT", Decimal("54000")),
            LineItem("Medicines", "PHARMACY", Decimal("20000"), date(2026, 8, 11)),
            LineItem("Lab and scans", "INVESTIGATION", Decimal("20000")),
        ],
    )
    terms = PolicyTerms(
        sum_insured=Decimal("500000"),
        room_rent_cap_per_day=Decimal("5000"),
        copay_percent=Decimal("10"),
        non_payable_categories=["ADMISSION"],
        clauses={"PHARMACY": Clause("Clause 3.4: Expenses incurred during the period of hospitalization, including medicines and consumables prescribed by the treating doctor, are payable subject to the sum insured and applicable co-payment.", 9, "3.4")},
    )
    return evaluate_claim(bill, terms), terms


def test_fictional_demo_comparison_finds_one_pharmacy_discrepancy():
    claim, terms = _demo_claim()
    fixture = Path(__file__).resolve().parents[1] / "fixtures" / "settlement" / "settlement_demo.txt"
    settlement = parse_settlement(fixture.read_bytes(), fixture.name)
    result = compare(claim, settlement, terms)
    assert claim.insurer_share == Decimal("111600.00")
    assert claim.patient_share == Decimal("20400.00")
    assert result.status == "possible_discrepancy"
    assert result.expected_patient_share == Decimal("20400.00")
    assert result.actual_patient_share == Decimal("29400.00")
    assert result.possible_difference == Decimal("9000.00")
    pharmacy = next(row for row in result.categories if row.category == "PHARMACY")
    assert pharmacy.status == "UNEXPLAINED_DEDUCTION"
    assert pharmacy.insurer_deducted == Decimal("10000.00")
    assert pharmacy.engine_disallowed == Decimal("0")
    assert pharmacy.payout_effect == Decimal("9000.00")
    assert pharmacy.clause.page == 9


def test_matching_settlement_has_no_discrepancy():
    claim, terms = _demo_claim()
    settlement = SettlementData(
        "CLM-2026-0417",
        Decimal("111600"),
        [
            # Matches the engine-supported exclusions.
            *[SettlementDeduction(category, amount, "policy rule") for category, amount in (("ADMISSION", Decimal("2000")), ("ROOM", Decimal("4000")), ("DOCTOR_NURSING", Decimal("2000")))],
        ],
        Decimal("12400"),
        False,
        [],
        Decimal("132000"),
    )
    result = compare(claim, settlement, terms)
    assert result.status == "no_discrepancy"
    assert result.possible_difference == Decimal("0.00")


def test_unreadable_settlement_and_claim_review_block_comparison():
    claim, terms = _demo_claim()
    settlement = SettlementData("CLM-2026-0417", Decimal("100000"), [], needs_review=True, bill_total=Decimal("132000"))
    assert compare(claim, settlement, terms).status == "manual_review"


def test_missing_paid_amount_blocks_comparison_without_inference():
    claim, terms = _demo_claim()
    settlement = SettlementData(
        "CLM-2026-0417", None, [], needs_review=True,
        review_reasons=["Settlement amount paid was not identified."],
        bill_total=Decimal("132000"),
    )

    result = compare(claim, settlement, terms)

    assert result.status == "manual_review"
    assert "Settlement amount paid was not identified." in result.review_reasons


def test_missing_clause_marks_category_for_review():
    claim, terms = _demo_claim()
    terms.clauses.clear()
    settlement = SettlementData("CLM-2026-0417", Decimal("102600"), [], Decimal("11400"), False, [], Decimal("132000"))
    result = compare(claim, settlement, terms)
    assert result.status == "manual_review"


def test_double_applied_copay_is_a_possible_discrepancy():
    claim, terms = _demo_claim()
    terms.clauses["COPAY"] = Clause("The 10 percent co-payment is applied once to eligible expenses.", 1, "Co-payment")
    settlement = SettlementData(
        "CLM-2026-0417", Decimal("99200"),
        [SettlementDeduction(category, amount, "policy calculation") for category, amount in (
            ("ADMISSION", Decimal("2000")), ("ROOM", Decimal("4000")), ("DOCTOR_NURSING", Decimal("2000")),
        )],
        Decimal("24800"), False, [], Decimal("132000"),
    )
    result = compare(claim, settlement, terms)
    assert result.status == "possible_discrepancy"
    assert result.possible_difference == claim.copay
    copay = next(row for row in result.categories if row.category == "COPAY")
    assert copay.engine_disallowed == claim.copay
    assert copay.insurer_deducted == claim.copay * 2
    assert copay.payout_effect == claim.copay


def test_deductible_is_compared_as_its_own_patient_share_category():
    bill = BillData(
        patient_name="Synthetic Patient", policy_number="POL-TEST",
        admission_date=date(2026, 8, 10), discharge_date=date(2026, 8, 14),
        room_days=4, total_amount=Decimal("41000"),
        line_items=[
            LineItem("Room charges", "ROOM", Decimal("30000")),
            LineItem("Pharmacy", "PHARMACY", Decimal("8000")),
            LineItem("Lab", "INVESTIGATION", Decimal("3000")),
        ],
    )
    terms = PolicyTerms(
        sum_insured=Decimal("500000"), room_rent_cap_per_day=Decimal("5000"),
        deductible=Decimal("10000"), copay_percent=Decimal("10"),
    )
    claim = evaluate_claim(bill, terms)
    letter = """Bill Total: INR 41000
Deductions:
Room rent | 10000 | cap
Deductible | 10000
Co-pay | 2100
Amount Paid: 18900
"""
    settlement = parse_settlement(letter.encode(), "settlement.txt")
    result = compare(claim, settlement, terms)
    assert result.status == "no_discrepancy"
    assert next(row for row in result.categories if row.category == "DEDUCTIBLE").insurer_deducted == Decimal("10000")
