from datetime import date
from decimal import Decimal

import pytest

from mediguard.engine.comparison import compare
from mediguard.engine.models import ClaimResult, Clause, LineItem, LineResult, PolicyTerms, SettlementData, SettlementDeduction
from mediguard.reporting.reports import build_comparison_appeal_letter_text


def _suresh_case(pharmacy_dates):
    lines = [
        LineResult(LineItem("Admission registration", "ADMISSION", Decimal("2000")), Decimal("0"), Decimal("2000"), "NON_PAYABLE"),
        LineResult(LineItem("Room rent", "ROOM", Decimal("24000")), Decimal("20000"), Decimal("4000"), "ROOM_CAP"),
        LineResult(LineItem("Doctor nursing fees", "DOCTOR_NURSING", Decimal("12000")), Decimal("10000"), Decimal("2000"), "PROPORTIONATE"),
        *[
            LineResult(
                LineItem(f"Medicine item {index + 1}", "PHARMACY", Decimal("10000"), item_date),
                Decimal("10000"), Decimal("0"), "OK",
                Clause("Clause 3.4: Medicines are payable during hospitalization.", 9, "3.4"),
            )
            for index, item_date in enumerate(pharmacy_dates)
        ],
        LineResult(LineItem("Surgery and OT", "SURGERY_OT", Decimal("54000")), Decimal("54000"), Decimal("0"), "OK"),
        LineResult(LineItem("Investigations", "INVESTIGATION", Decimal("20000")), Decimal("20000"), Decimal("0"), "OK"),
    ]
    claim = ClaimResult(
        lines=lines,
        eligible_total=Decimal("124000"),
        copay=Decimal("12400"),
        patient_share=Decimal("20400"),
        insurer_share=Decimal("111600"),
        status="computed",
        admission_date=date(2026, 8, 10),
        discharge_date=date(2026, 8, 14),
    )
    terms = PolicyTerms(
        sum_insured=Decimal("500000"),
        copay_percent=Decimal("10"),
        clauses={"PHARMACY": Clause("Clause 3.4: Medicines are payable during hospitalization.", 9, "3.4")},
    )
    settlement = SettlementData(
        "CLM-2026-0417", Decimal("102600"),
        [
            SettlementDeduction("ADMISSION", Decimal("2000"), "Non-payable"),
            SettlementDeduction("ROOM", Decimal("4000"), "Room limit"),
            SettlementDeduction("DOCTOR_NURSING", Decimal("2000"), "Proportionate deduction"),
            SettlementDeduction("PHARMACY", Decimal("10000"), "Medicines outside hospitalization window"),
        ],
        copay_applied=Decimal("11400"),
        bill_total=Decimal("132000"),
    )
    return claim, settlement, terms


def test_suresh_fictional_case_dates_inside_stay_are_flagged_in_letter():
    claim, settlement, terms = _suresh_case([date(2026, 8, 10), date(2026, 8, 14)])
    result = compare(claim, settlement, terms)

    assert result.status == "possible_discrepancy"
    assert result.expected_patient_share == Decimal("20400")
    assert result.possible_difference == Decimal("9000.00")
    pharmacy = next(row for row in result.categories if row.category == "PHARMACY")
    assert pharmacy.status == "UNEXPLAINED_DEDUCTION"
    assert pharmacy.review_note == "all dated entries fall inside the stay"
    assert pharmacy.clause.page == 9

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
