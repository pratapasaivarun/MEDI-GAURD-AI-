from datetime import date
from decimal import Decimal

from mediguard.engine.comparison import compare
from mediguard.engine.models import ClaimResult, Clause, LineItem, LineResult, PolicyTerms, SettlementData, SettlementDeduction


def test_matching_settlement_agrees_with_rules_golden_case():
    claim = ClaimResult(
        lines=[LineResult(LineItem("Lab", "INVESTIGATION", Decimal("10000")), Decimal("10000"), Decimal("0"), "OK")],
        eligible_total=Decimal("10000"), copay=Decimal("1000"), patient_share=Decimal("1000"), insurer_share=Decimal("9000"), status="computed",
    )
    settlement = SettlementData("FIC-001", Decimal("9000"), [SettlementDeduction("COPAY", Decimal("1000"), "Co-pay")], bill_total=Decimal("10000"))
    result = compare(claim, settlement, PolicyTerms(Decimal("500000"), copay_percent=Decimal("10")))
    assert result.status == "no_discrepancy"
    assert result.possible_difference == Decimal("0")


def test_supported_extra_investigation_deduction_golden_case():
    claim = ClaimResult(
        lines=[LineResult(LineItem("Lab", "INVESTIGATION", Decimal("10000")), Decimal("10000"), Decimal("0"), "OK")],
        eligible_total=Decimal("10000"), copay=Decimal("0"), patient_share=Decimal("0"), insurer_share=Decimal("10000"), status="computed",
        admission_date=date(2026, 8, 10), discharge_date=date(2026, 8, 12),
    )
    clause = Clause("Diagnostic investigations are payable during hospitalization.", 3)
    settlement = SettlementData("FIC-002", Decimal("9000"), [SettlementDeduction("INVESTIGATION", Decimal("1000"), "Not payable")], bill_total=Decimal("10000"))
    result = compare(claim, settlement, PolicyTerms(Decimal("500000"), clauses={"INVESTIGATION": clause}))
    assert result.status == "possible_discrepancy"
    assert result.possible_difference == Decimal("1000")
    assert result.categories[0].clause.page == 3
