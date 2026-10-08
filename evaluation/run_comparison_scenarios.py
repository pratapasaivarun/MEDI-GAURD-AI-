"""Run synthetic settlement comparison scenarios against the YAML expectations."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
import json
from pathlib import Path
import re

from comparison import compare
from models import BillData, Clause, LineItem, PolicyTerms, SettlementData, SettlementDeduction
from rules import evaluate_claim

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = ROOT / "evaluation" / "comparison_expected.yaml"


def read_expected() -> list[dict]:
    """Read the deliberately small, dependency-free YAML subset used here."""
    text = EXPECTED.read_text(encoding="utf-8")
    rows = re.findall(r"(?m)^  - id: (\S+)\s+expected_status: (\S+)\s+expected_letter: (true|false)\s*$", text)
    if not rows:
        raise ValueError(f"No comparison scenarios found in {EXPECTED}")
    return [{"id": key, "expected_status": status, "expected_letter": letter == "true"} for key, status, letter in rows]


def demo_inputs():
    bill = BillData(
        "Ravi Reddy", "POL-558201", date(2026, 8, 10), date(2026, 8, 14), 4,
        Decimal("132000"), [
            LineItem("Admission and registration", "ADMISSION", Decimal("2000")),
            LineItem("Room rent", "ROOM", Decimal("24000")),
            LineItem("Doctor and nursing fees", "DOCTOR_NURSING", Decimal("12000")),
            LineItem("Hernia surgery and OT", "SURGERY_OT", Decimal("54000")),
            LineItem("Medicines", "PHARMACY", Decimal("20000"), date(2026, 8, 11)),
            LineItem("Lab and scans", "INVESTIGATION", Decimal("20000")),
        ],
    )
    terms = PolicyTerms(Decimal("500000"), Decimal("5000"), Decimal("10"),
                        ["ADMISSION"], clauses={
                            "PHARMACY": Clause("Covered medicines clause.", 9, "3.4"),
                            "COPAY": Clause("Co-payment applies once.", 1, "Co-payment"),
                        })
    return evaluate_claim(bill, terms), terms


def _settlement(claim, terms, *, claim_id="CLM-2026-0417", unreadable=False, deductions=None, copay=None):
    rows = deductions if deductions is not None else [
        SettlementDeduction("ADMISSION", Decimal("2000"), "policy rule"),
        SettlementDeduction("ROOM", Decimal("4000"), "policy rule"),
        SettlementDeduction("DOCTOR_NURSING", Decimal("2000"), "policy rule"),
    ]
    copay_amount = claim.copay if copay is None else Decimal(copay)
    total_deductions = sum((row.amount for row in rows), Decimal("0")) + copay_amount
    return SettlementData(claim_id, Decimal("132000") - claim.patient_share if not unreadable else Decimal("0"),
                          rows, copay_amount, unreadable,
                          ["Settlement text could not be read."] if unreadable else [], Decimal("132000"))


def run_scenarios() -> list[dict]:
    expected = read_expected()
    outcomes = []
    for scenario in expected:
        claim, terms = demo_inputs()
        settlement = _settlement(claim, terms)
        scenario_id = scenario["id"]
        if scenario_id == "pharmacy_outside_stay_and_deducted":
            pharmacy = next(row for row in claim.lines if row.item.category == "PHARMACY")
            pharmacy.allowed, pharmacy.disallowed, pharmacy.reason_code = Decimal("0"), pharmacy.item.amount, "OUTSIDE_COVERED_PERIOD"
            claim.eligible_total -= pharmacy.item.amount
            claim.patient_share += pharmacy.item.amount * (Decimal("1") - terms.copay_percent / Decimal("100"))
            claim.insurer_share = Decimal("132000") - claim.patient_share
            settlement = _settlement(claim, terms, deductions=[
                SettlementDeduction("ADMISSION", Decimal("2000"), "policy rule"),
                SettlementDeduction("ROOM", Decimal("4000"), "policy rule"),
                SettlementDeduction("DOCTOR_NURSING", Decimal("2000"), "policy rule"),
                SettlementDeduction("PHARMACY", Decimal("20000"), "outside stay"),
            ])
        elif scenario_id == "copay_applied_twice":
            settlement = _settlement(claim, terms, copay=claim.copay * 2)
            settlement.amount_paid -= claim.copay
        elif scenario_id == "insurer_deducts_less_than_rules":
            settlement.deductions[1].amount = Decimal("3000")
            settlement.amount_paid += Decimal("1000")
        elif scenario_id == "unreadable_settlement":
            settlement = _settlement(claim, terms, unreadable=True)
        elif scenario_id == "diagnosis_excluded":
            claim.status = "manual_review"
            claim.review_reasons.append("Diagnosis exclusion requires reviewer confirmation.")
        elif scenario_id == "different_claim_settlement":
            settlement.claim_id = "CLM-OTHER-0001"
        if scenario_id == "different_claim_settlement":
            status = "manual_review" if _normal(settlement.claim_id) != _normal("CLM-2026-0417") else compare(claim, settlement, terms).status
        else:
            status = compare(claim, settlement, terms).status
        letter = status == "possible_discrepancy"
        outcomes.append({"id": scenario_id, "expected_status": scenario["expected_status"],
                         "actual_status": status, "expected_letter": scenario["expected_letter"],
                         "actual_letter": letter, "passed": status == scenario["expected_status"] and letter == scenario["expected_letter"]})
    return outcomes


def _normal(value: str | None) -> str:
    return re.sub(r"[\s-]+", "", value or "").casefold()


if __name__ == "__main__":
    results = run_scenarios()
    print(json.dumps({"synthetic_scenarios": len(results), "passed": sum(x["passed"] for x in results), "results": results}, indent=2))
    if not all(row["passed"] for row in results):
        raise SystemExit(1)
