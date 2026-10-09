from decimal import Decimal
from pathlib import Path

import pytest

from settlement import parse_settlement


FIXTURES = Path(__file__).parents[1] / "fixtures" / "settlements"
EXPECTED_DEDUCTIONS = [
    ("ADMISSION", Decimal("2000.00")),
    ("ROOM", Decimal("4000.00")),
    ("DOCTOR_NURSING", Decimal("2000.00")),
    ("PHARMACY", Decimal("10000.00")),
]


@pytest.mark.parametrize(
    ("filename", "expected_total"),
    [
        ("pipe_table.txt", Decimal("132000.00")),
        ("tab_table.txt", Decimal("132000.00")),
        ("colon_list.txt", Decimal("132000.00")),
        ("claimed_amount_labels.txt", Decimal("132000.00")),
        ("no_bill_total.txt", None),
        ("indian_grouping.txt", Decimal("132000.00")),
    ],
)
def test_six_fictional_settlement_layouts_parse_without_external_services(monkeypatch, filename, expected_total):
    monkeypatch.setattr("settlement._llm_deductions", lambda _text: [])
    result = parse_settlement((FIXTURES / filename).read_bytes(), filename)

    assert result.claim_id == "CLM-2026-0417"
    assert result.amount_paid == Decimal("102600.00")
    assert result.bill_total == expected_total
    assert result.copay_applied == Decimal("11400.00")
    assert [(row.category, row.amount) for row in result.deductions] == EXPECTED_DEDUCTIONS


def test_claim_number_does_not_capture_the_date_and_narrative_is_not_an_id(monkeypatch):
    monkeypatch.setattr("settlement._llm_deductions", lambda _text: [])
    result = parse_settlement(
        b"Your claim has been processed. Claim Number: CLM-2026-0417 dated 12 Aug 2026\nAmount paid: 102600\nBill total: 132000",
        "claim-id.txt",
    )
    assert result.claim_id == "CLM-2026-0417"


def test_spaced_numeric_claim_id_remains_supported(monkeypatch):
    monkeypatch.setattr("settlement._llm_deductions", lambda _text: [])
    result = parse_settlement(
        b"Claim No: clm 2026 0417\nBill Total: 132000\nAmount Paid: 102600",
        "spaced-claim-id.txt",
    )
    assert result.claim_id == "clm 2026 0417"
