from decimal import Decimal
from pathlib import Path

import pytest

from settlement import parse_settlement


FIXTURE = Path(__file__).parent / "fixtures" / "settlement" / "settlement_demo.txt"


def test_fictional_text_settlement_parses_amounts_and_deductions():
    result = parse_settlement(FIXTURE.read_bytes(), FIXTURE.name)
    assert result.claim_id == "CLM-2026-0417"
    assert result.amount_paid == Decimal("102600.00")
    assert result.bill_total == Decimal("132000.00")
    assert result.copay_applied == Decimal("11400.00")
    assert [(row.category, row.amount) for row in result.deductions] == [
        ("ADMISSION", Decimal("2000.00")),
        ("ROOM", Decimal("4000.00")),
        ("DOCTOR_NURSING", Decimal("2000.00")),
        ("PHARMACY", Decimal("10000.00")),
    ]
    assert result.deductions[-1].reason_text == "Medicines outside hospitalization window"
    assert result.needs_review is False


def test_fictional_pdf_settlement_parses_using_pdf_text_reader():
    fixture = FIXTURE.with_suffix(".pdf")
    result = parse_settlement(fixture.read_bytes(), fixture.name)
    assert result.amount_paid == Decimal("102600.00")
    assert len(result.deductions) == 4


def test_settlement_reconciliation_failure_requires_review():
    text = FIXTURE.read_text(encoding="utf-8").replace("102600", "101600")
    result = parse_settlement(text.encode(), "settlement.txt")
    assert result.needs_review is True
    assert any("do not reconcile" in reason for reason in result.review_reasons)


def test_total_deductions_summary_row_is_not_a_deduction():
    text = """Bill Total: INR 41000
Deductions:
Room rent | 10000 | cap
Total deductions | 10000
Amount Paid: INR 31000
"""
    result = parse_settlement(text.encode(), "settlement.txt")
    assert len(result.deductions) == 1
    assert result.deductions[0].category == "ROOM"
    assert not any("do not reconcile" in reason for reason in result.review_reasons)


def test_total_amount_deducted_summary_row_is_not_a_deduction():
    text = """Bill Total: INR 41000
Deductions:
Room rent | 10000 | cap
Total Amount Deducted | 10000
Amount Paid: INR 31000
"""
    result = parse_settlement(text.encode(), "settlement.txt")
    assert len(result.deductions) == 1
    assert result.deductions[0].category == "ROOM"
    assert not any("do not reconcile" in reason for reason in result.review_reasons)


def test_patient_payable_is_not_extracted_as_amount_paid(monkeypatch):
    monkeypatch.setattr("settlement.requests.post", lambda *_args, **_kwargs: type("Response", (), {"status_code": 503})())
    for patient_label in ("Amount payable by patient: INR 13100", "Patient payable to hospital: INR 13100"):
        text = f"{patient_label}\nAmount paid to hospital: INR 27900"
        result = parse_settlement(text.encode(), "settlement.txt")
        assert result.amount_paid == Decimal("27900.00")


@pytest.mark.parametrize(
    ("filename", "content"),
    [("settlement.pdf", b"not a pdf"), ("settlement.exe", b"%PDF-1.4")],
)
def test_settlement_rejects_invalid_extension_or_magic_bytes(filename, content):
    with pytest.raises(ValueError):
        parse_settlement(content, filename)
