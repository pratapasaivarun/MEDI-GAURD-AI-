import json
from pathlib import Path

from mediguard.ingestion.extraction import extract_document, run_extraction
from mediguard.ingestion.settlement import parse_settlement


ROOT = Path(__file__).resolve().parents[2]
CASE_ROOT = ROOT / "samples" / "adversarial_cases" / "cases"


def bill(case_id):
    path = CASE_ROOT / case_id / "bill.pdf"
    evidence, raw_by_page, _ = extract_document(path, case_id, path.name)
    text = "\n".join(item.text for item in evidence)
    return run_extraction([{
        "document_id": case_id,
        "document_type": "medical_bill",
        "source_name": path.name,
        "text": text,
        "evidence": [item.to_dict() for item in evidence],
        "raw_by_page": raw_by_page,
    }])


def settlement(case_id):
    path = CASE_ROOT / case_id / "settlement.pdf"
    return parse_settlement(path.read_bytes(), path.name)


def test_pipe_delimited_grand_total_is_read_as_the_bill_total():
    assert bill("adv_01_split_columns")["total_amount"]["value"] == 21800


def test_paid_to_hospital_label_is_a_paid_amount_and_reconciles():
    parsed = settlement("adv_02_noisy_ocr")
    assert parsed.amount_paid == 3000
    assert parsed.needs_review is False


def test_bill_claim_reference_accepts_claim_ref_wording():
    assert bill("adv_02_noisy_ocr")["claim_number"]["value"] == "ADV-1002"


def test_room_description_keeps_embedded_four_day_duration():
    lines = bill("adv_06_one_rupee_over_cap")["line_items"]
    assert lines == [
        {**lines[0], "description": "Room charges for 4 days", "amount": 20001.0}
    ]


def test_explicit_nonmedical_exclusion_reason_is_not_other_review():
    parsed = settlement("adv_07_multiple_deductions")
    assert parsed.needs_review is False
    assert any(row.category == "EXCLUSION" and row.amount == 1000 for row in parsed.deductions)


def test_standalone_room_rent_above_limit_is_parsed_and_reconciles():
    parsed = settlement("adv_06_one_rupee_over_cap")
    assert [(row.category, float(row.amount)) for row in parsed.deductions] == [("ROOM", 1.0)]
    assert parsed.needs_review is False


def test_missing_settlement_claim_reference_is_flagged_for_review():
    parsed = settlement("adv_08_missing_claim_reference")
    assert parsed.claim_id is None
    assert parsed.needs_review is True


def test_matching_bill_total_and_payment_proves_no_unlisted_deduction():
    parsed = settlement("adv_09_subtotal_tax_grand_total")
    assert parsed.amount_paid == parsed.bill_total == 32550
    assert parsed.deductions == []
    assert parsed.needs_review is False


def test_adversarial_casebook_labels_remain_unchanged():
    casebook = json.loads((ROOT / "samples/adversarial_cases/casebook.json").read_text(encoding="utf-8"))
    assert casebook["label"].startswith("FICTIONAL SAMPLE")
    assert len(casebook["cases"]) == 10
    for case in casebook["cases"]:
        label = json.loads((CASE_ROOT / case["case_id"] / "expected-results.json").read_text(encoding="utf-8"))
        assert label["expected"] == case["expected"]
