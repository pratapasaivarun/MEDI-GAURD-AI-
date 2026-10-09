from datetime import date
from decimal import Decimal

import pytest

from comparison import compare
from models import ClaimResult, Clause, LineItem, LineResult, PolicyTerms, SettlementData, SettlementDeduction
from reports import build_comparison_appeal_letter_text


def _suresh_case(pharmacy_dates):
    amount = Decimal("100000")
    lines = [
        LineResult(
            LineItem(f"Medicine item {index + 1}", "PHARMACY", Decimal("5000"), item_date),
            Decimal("5000"), Decimal("0"), "OK",
        )
        for index, item_date in enumerate(pharmacy_dates)
    ]
    claim = ClaimResult(
        lines=lines,
        eligible_total=amount,
        copay=Decimal("0"),
        patient_share=Decimal("0"),
        insurer_share=amount,
        status="computed",
        admission_date=date(2026, 8, 10),
        discharge_date=date(2026, 8, 14),
    )
    terms = PolicyTerms(
        sum_insured=Decimal("500000"),
        clauses={"PHARMACY": Clause("Clause 3.4: Medicines are payable during hospitalization.", 9, "3.4")},
    )
    settlement = SettlementData(
        "CLM-2026-0417", Decimal("90000"),
        [SettlementDeduction("PHARMACY", Decimal("10000"), "Medicines outside hospitalization window")],
        bill_total=amount,
    )
    return claim, settlement, terms


def test_suresh_fictional_case_dates_inside_stay_are_flagged_in_letter():
    claim, settlement, terms = _suresh_case([date(2026, 8, 10), date(2026, 8, 14)])
    result = compare(claim, settlement, terms)

    assert result.status == "possible_discrepancy"
    assert result.expected_patient_share == Decimal("0")
    assert result.possible_difference == Decimal("10000.00")
    pharmacy = next(row for row in result.categories if row.category == "PHARMACY")
    assert pharmacy.status == "UNEXPLAINED_DEDUCTION"
    assert pharmacy.review_note == "all dated entries fall inside the stay"

    letter = build_comparison_appeal_letter_text(
        {"claim_number": "CLM-2026-0417", "patient_name": "Suresh Fictional"},
        result,
        settlement,
    )
    assert "all dated entries fall inside the stay" in letter


@pytest.mark.parametrize("dates", [[date(2026, 8, 15)], [None]])
def test_missing_or_outside_pharmacy_dates_require_manual_review(dates):
    claim, settlement, terms = _suresh_case(dates)
    result = compare(claim, settlement, terms)

    assert result.status == "manual_review"
    pharmacy = next(row for row in result.categories if row.category == "PHARMACY")
    assert pharmacy.status == "REVIEW"
    assert pharmacy.review_note
