from datetime import date
import hashlib
import sys

import pymupdf
from PIL import Image, ImageDraw

import mediguard.ingestion.extraction as extraction
from mediguard.ingestion.extraction import Evidence, _extract_line_items, _infer_line_category, normalize_documents


def test_tabular_line_uses_last_number_as_amount_and_does_not_invent_code():
    evidence = [Evidence("bill", "bill.pdf", 1, "pymupdf", "Room charges 2 5,000 10,000", 100)]
    items = _extract_line_items("Room charges 2 5,000 10,000", evidence)
    assert len(items) == 1
    assert items[0]["amount"] == 10000
    assert items[0]["cpt_codes"] == []


def test_table_bill_amount_column_and_header_handling():
    text = "Description Qty Rate Amount\nRoom charges 4 5000 20000\nPharmacy 1 8000 8000"
    items = _extract_line_items(text, [Evidence("bill", "bill.pdf", 1, "pymupdf", text, 100)])
    assert [(item["description"], item["amount"]) for item in items] == [
        ("Room charges", 20000),
        ("Pharmacy", 8000),
    ]


def test_repeated_table_headers_are_skipped_between_item_rows():
    header = "Description Qty Rate Amount"
    text = f"{header}\nRoom charges 4 5000 20000\n{header}\nPharmacy 1 8000 8000"
    items = _extract_line_items(text, [Evidence("bill", "bill.pdf", 1, "pymupdf", text, 100)])
    assert [(item["description"], item["amount"]) for item in items] == [
        ("Room charges", 20000), ("Pharmacy", 8000),
    ]


def test_low_confidence_ocr_line_item_is_flagged_for_review():
    text = "Pharmacy 1 8000 8000"
    items = _extract_line_items(text, [Evidence("bill", "bill.pdf", 2, "tesseract", text, 45)])
    assert len(items) == 1
    assert items[0]["amount"] == 8000
    assert items[0]["confidence"] == 45
    assert items[0]["needs_review"] is True


def test_tabular_rows_with_days_column_use_final_amount():
    rows = (
        "Room charges | 4 days | 5000 | 20000",
        "Room charges 4 days 5000 20000",
    )
    for row in rows:
        items = _extract_line_items(row, [Evidence("bill", "bill.pdf", 1, "pymupdf", row, 100)])
        assert len(items) == 1
        assert items[0]["amount"] == 20000


def test_five_digit_bill_total_is_not_a_procedure_code():
    text = "Room charges 4 5000 10000"
    items = _extract_line_items(text, [Evidence("bill", "bill.pdf", 1, "pymupdf", text, 100)])
    assert items[0]["cpt_codes"] == []


def test_digit_in_service_description_is_preserved_before_amount_column():
    text = "Vitamin B12 injection 500"
    items = _extract_line_items(text, [Evidence("bill", "bill.pdf", 1, "pymupdf", text, 100)])
    assert len(items) == 1
    assert items[0]["description"] == "Vitamin B12 injection"
    assert items[0]["amount"] == 500


def test_explicit_grand_total_wins_over_subtotal(monkeypatch):
    monkeypatch.setattr(extraction, "_llm_extract_claim_fallback", lambda _text: None)
    claim = normalize_documents([{"text": "Subtotal: Rs. 5,000/-\nGrand Total: Rs. 6,000/-"}])
    assert claim.total_amount.value == 6000


def test_grand_total_or_net_payable_beats_subtotal_and_discount(monkeypatch):
    monkeypatch.setattr(extraction, "_llm_extract_claim_fallback", lambda _text: None)
    grand_total_bill = normalize_documents([{"text": "Subtotal 31000\nDiscount 1000\nGrand Total 30000"}])
    net_payable_bill = normalize_documents([{"text": "Subtotal 31000\nNet Payable 30000"}])
    assert grand_total_bill.total_amount.value == 30000
    assert net_payable_bill.total_amount.value == 30000


def test_total_label_priority_and_last_same_priority_value(monkeypatch):
    monkeypatch.setattr(extraction, "_llm_extract_claim_fallback", lambda _text: None)
    cases = (
        ("Sub Total 31000\nTax 1550\nTotal 32550", 32550),
        ("Sub Total 31000\nDiscount 1000\nNet Amount 30000", 30000),
        ("Gross Bill Amount 31000\nNet Bill Amount 30000", 30000),
        ("Total Amount 31000\nTotal Amount 30000", 30000),
    )
    for text, expected in cases:
        claim = normalize_documents([{"text": text}])
        assert claim.total_amount.value == expected


def test_extracted_line_item_keeps_its_date():
    text = "Room charges 2 5,000 10,000 05-Mar-2026"
    items = _extract_line_items(text, [Evidence("bill", "bill.pdf", 1, "pymupdf", text, 100)])
    assert items[0]["amount"] == 10000
    assert items[0]["date"] == "2026-03-05"


def test_indian_grouping_and_rupee_suffix_amounts():
    assert extraction.parse_amount("Rs. 5,000/-") == 5000.0
    assert extraction.parse_amount("1,23,456.00") == 123456.0


def test_category_matches_whole_words():
    assert _infer_line_category("Particular charges") == "OTHER"
    assert _infer_line_category("ICU charges") == "ICU"


def test_consultation_and_diagnostic_test_category_keywords():
    assert _infer_line_category("Consultation - Dr Rao") == "DOCTOR_NURSING"
    assert _infer_line_category("ECG") == "INVESTIGATION"
    assert _infer_line_category("Pathology") == "INVESTIGATION"


def test_mixed_pdf_uses_text_layer_and_ocr_for_scanned_pages(tmp_path, monkeypatch):
    path = tmp_path / "mixed.pdf"
    doc = pymupdf.open()
    text_page = doc.new_page()
    text_page.insert_text((72, 72), "Text layer page")
    image_path = tmp_path / "page.png"
    image = Image.new("RGB", (600, 800), "white")
    ImageDraw.Draw(image).text((50, 50), "scanned content", fill="black")
    image.save(image_path)
    scanned_page = doc.new_page()
    scanned_page.insert_image(scanned_page.rect, filename=str(image_path))
    doc.save(path)
    doc.close()

    class FakeOCR:
        def predict(self, _path):
            return [{"rec_texts": ["OCR scanned page"], "rec_scores": [0.95]}]

    monkeypatch.setattr(extraction, "_get_ocr", lambda: FakeOCR())
    evidence, raw, page_count = extraction.extract_document(path, "mixed", "mixed.pdf")
    assert page_count == 2
    assert [(item.page, item.method) for item in evidence] == [(1, "pymupdf"), (2, "tesseract")]
    assert raw["1"].strip() == "Text layer page"
    assert raw["2"] == "OCR scanned page"


def test_scanned_pdf_page_is_flagged_for_review_when_ocr_is_unavailable(tmp_path, monkeypatch):
    path = tmp_path / "mixed-no-ocr.pdf"
    doc = pymupdf.open()
    first = doc.new_page()
    first.insert_text((72, 72), "Text layer page")
    image_path = tmp_path / "scanned.png"
    Image.new("RGB", (300, 400), "white").save(image_path)
    second = doc.new_page()
    second.insert_image(second.rect, filename=str(image_path))
    doc.save(path)
    doc.close()

    class UnavailableOCR:
        def predict(self, _path):
            raise RuntimeError("Tesseract is unavailable")

    monkeypatch.setattr(extraction, "_get_ocr", lambda: UnavailableOCR())
    evidence, raw, page_count = extraction.extract_document(path, "no-ocr", "mixed-no-ocr.pdf")
    assert page_count == 2
    assert [(item.page, item.method) for item in evidence] == [(1, "pymupdf"), (2, "ocr_unavailable")]
    assert raw["2"] == ""
    normalized = normalize_documents([{
        "document_type": "medical_bill", "text": "\n".join(item.text for item in evidence),
        "evidence": [item.to_dict() for item in evidence], "raw_by_page": raw,
    }])
    assert "scanned_page_ocr" in normalized.review_fields


def test_supported_line_item_date_formats():
    assert extraction.parse_bill_date("05-Mar-2026") == date(2026, 3, 5)


def test_reviewer_saved_line_item_keeps_confirmed_date(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIGUARD_DB_PATH", str(tmp_path / "review.sqlite"))
    monkeypatch.setenv("MEDIGUARD_STORAGE_DIR", str(tmp_path / "storage"))
    monkeypatch.setenv("CHROMA_DIR", str(tmp_path / "chroma"))
    sys.path.insert(0, str(extraction.Path(__file__).resolve().parents[2]))
    import mediguard.services.application as app

    app.init_db()
    user = app.get_or_create_user("phase1-reviewer@example.test", "Phase 1 Reviewer")
    with app.db() as conn:
        conn.execute("UPDATE users SET role='admin' WHERE user_id=?", (user["user_id"],))
    claim_id = app.create_claim(user["user_id"], "CLM-PHASE1", "Synthetic Patient", "Example Hospital", "POL-TEST", "2026-03-05")
    document_id = "phase1-bill"
    with app.db() as conn:
        conn.execute(
            "INSERT INTO documents(document_id,claim_id,original_name,stored_path,document_type,size_bytes,sha256,page_count,processing_status,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (document_id, claim_id, "bill.pdf", "", "medical_bill", 10, hashlib.sha256(b"bill").hexdigest(), 1, "uploaded", app.utc_now()),
        )
    app.save_claim_extraction_review(claim_id, user["user_id"], {
        "line_items": {"value": [{"description": "Room charges", "amount": 5000, "date": "05-Mar-2026", "source_page": 1}], "page": 1, "document_id": document_id},
    })
    reviewed = app.apply_claim_extraction_reviews(claim_id, {"line_items": []})
    assert reviewed["line_items"][0]["date"] == "2026-03-05"
