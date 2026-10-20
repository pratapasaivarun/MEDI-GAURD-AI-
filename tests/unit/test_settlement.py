from decimal import Decimal
from pathlib import Path
import random

import pytest
import pymupdf

from mediguard.ingestion.settlement import parse_settlement


FIXTURE = Path(__file__).resolve().parents[2] / "samples" / "test_documents" / "settlement" / "settlement_demo.txt"


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


def test_image_only_settlement_pdf_routes_to_manual_review_without_ocr(monkeypatch, tmp_path):
    monkeypatch.setattr("mediguard.ingestion.settlement.requests.post", lambda *_args, **_kwargs: type("Response", (), {"status_code": 503})())
    image_path = tmp_path / "settlement-page.png"
    from PIL import Image
    Image.new("RGB", (300, 400), "white").save(image_path)
    document = pymupdf.open()
    page = document.new_page()
    page.insert_image(page.rect, filename=str(image_path))
    pdf_path = tmp_path / "image-only.pdf"
    document.save(pdf_path)
    document.close()

    result = parse_settlement(pdf_path.read_bytes(), "image-only.pdf")

    assert result.amount_paid is None
    assert result.deductions == []
    assert result.needs_review is True
    assert any("could not be read" in reason for reason in result.review_reasons)


def test_parser_handles_two_hundred_deterministic_malformed_rows(monkeypatch):
    rng = random.Random(41)
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 |:/-.,\t"
    monkeypatch.setattr("mediguard.ingestion.settlement.requests.post", lambda *_args, **_kwargs: type("Response", (), {"status_code": 503})())

    for index in range(200):
        noise = "".join(rng.choice(alphabet) for _ in range(rng.randrange(0, 500)))
        payload = (
            f"Claim ID: CLM-{index:04d}\nBill Total: INR 41000\n"
            f"Deductions:\n{noise}\nAmount Paid: INR 30000"
        ).encode("utf-8")
        parsed = parse_settlement(payload, "fuzz.txt")
        assert parsed.amount_paid == Decimal("30000.00")
        assert parsed.needs_review is True


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


def test_explicit_no_deductions_is_valid_without_llm_fallback(monkeypatch):
    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("An explicit no-deductions statement must not call the LLM")
    monkeypatch.setattr("mediguard.ingestion.settlement._llm_deductions", fail_if_called)
    result = parse_settlement(
        b"Bill Total: INR 10000\nAmount Paid: INR 10000\nDeductions: none\n",
        "settlement.txt",
    )
    assert result.deductions == []
    assert result.amount_paid == Decimal("10000.00")
    assert result.needs_review is False


def test_single_space_aligned_deduction_rows_are_parsed():
    result = parse_settlement(
        b"Bill Total: INR 10000\nDeductions\nDeductible INR 1000 Policy deductible\nAmount Paid: INR 9000\n",
        "settlement.txt",
    )
    assert [(row.category, row.amount) for row in result.deductions] == [
        ("DEDUCTIBLE", Decimal("1000.00")),
    ]
    assert result.needs_review is False


def test_exclusion_deduction_has_a_distinct_category():
    result = parse_settlement(
        b"Bill Total: INR 10000\nDeductions\nExclusion | INR 5000 | not covered\nAmount Paid: INR 5000\n",
        "settlement.txt",
    )
    assert result.deductions[0].category == "EXCLUSION"
    assert result.deductions[0].needs_review is False


def test_conflicting_paid_amounts_are_not_arbitrarily_selected():
    result = parse_settlement(
        b"Bill Total: INR 30000\nAmount Paid: INR 25000\nAmount Paid: INR 24000\nDeductions: none\n",
        "settlement.txt",
    )
    assert result.amount_paid is None
    assert result.needs_review is True
    assert any("Conflicting" in reason for reason in result.review_reasons)


def test_patient_payable_is_not_extracted_as_amount_paid(monkeypatch):
    monkeypatch.setattr("mediguard.ingestion.settlement.requests.post", lambda *_args, **_kwargs: type("Response", (), {"status_code": 503})())
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
