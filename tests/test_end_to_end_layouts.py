from decimal import Decimal
from pathlib import Path

from mediguard.services import application as app
from mediguard.reporting.reports import build_comparison_appeal_letter_text
from test_end_to_end import _run_demo_pipeline


FIXTURE_DIR = Path(__file__).parents[1] / "fixtures" / "settlements"
LAYOUTS = (
    ("pipe_table.txt", Decimal("132000")),
    ("tab_table.txt", Decimal("132000")),
    ("colon_list.txt", Decimal("132000")),
    ("claimed_amount_labels.txt", Decimal("132000")),
    ("no_bill_total.txt", None),
    ("indian_grouping.txt", Decimal("132000")),
)


def test_all_six_settlement_layouts_use_demo_claim_policy_and_gate_letters(monkeypatch, tmp_path):
    for filename, expected_total in LAYOUTS:
        normalized, rules, comparison, settlement, claim = _run_demo_pipeline(
            monkeypatch,
            tmp_path / Path(filename).stem,
            (FIXTURE_DIR / filename).read_bytes(),
            include_pharmacy_date=True,
        )
        if expected_total is None:
            assert comparison.status == "manual_review"
            assert settlement.bill_total == Decimal("132000")
            assert "proposed; user confirmation required" in " ".join(settlement.review_reasons)
            comparison, settlement = app.run_settlement_comparison(
                claim["claim_id"], claim["user_id"], normalized, rules,
                confirm_inferred_bill_total=True,
            )

        assert settlement.claim_id == "CLM-2026-0417"
        assert settlement.bill_total == Decimal("132000")
        assert comparison.status == "possible_discrepancy", (filename, comparison.review_reasons)
        assert comparison.expected_patient_share == Decimal("20400")
        assert comparison.possible_difference == Decimal("9000")
        pharmacy = next(row for row in comparison.categories if row.category == "PHARMACY")
        assert pharmacy.clause is not None and pharmacy.clause.page == 9
        letter = build_comparison_appeal_letter_text(claim, comparison, settlement)
        assert "possible difference is ₹9,000" in letter
        assert "please provide a written explanation" in letter.lower()
        if filename in {"pipe_table.txt", "tab_table.txt", "claimed_amount_labels.txt"}:
            assert pharmacy.status == "UNEXPLAINED_DEDUCTION"
            assert pharmacy.review_note == "all dated entries fall inside the stay"
            assert "all dated entries fall inside the stay" in letter
