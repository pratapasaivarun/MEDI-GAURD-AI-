from extraction import detect_duplicate_charges, normalize_documents

text = '''MEDICAL BILL\nPatient Name: Alex Morgan\nHospital: North Star General Hospital\nPolicy Number: POL-SYN-1001\nRoom charges: INR 18000\nDoctor consultation: INR 12000\nSurgery and procedure: INR 85000\nMedicines: INR 14000\nDiagnostic tests: INR 16000\nTotal Amount: INR 145000'''
evidence = [{"document_id": "bill-1", "source_name": "bill.pdf", "page": 1, "method": "pymupdf", "text": text, "confidence": 100.0}]
doc = {"document_id": "bill-1", "source_name": "bill.pdf", "document_type": "medical_bill", "text": text, "raw_by_page": {"1": text}, "evidence": evidence}
claim = normalize_documents([doc])
assert [(x["description"], x["amount"], x["category"]) for x in claim.line_items] == [("Room charges", 18000.0, "room"), ("Doctor consultation", 12000.0, "consultation"), ("Surgery and procedure", 85000.0, "surgery"), ("Medicines", 14000.0, "pharmacy"), ("Diagnostic tests", 16000.0, "diagnostics")]
assert claim.multiple_bill_count == 1
assert claim.aggregation_requires_confirmation is False
left = claim.line_items[0]
assert len(detect_duplicate_charges([left, {**left, "evidence": []}])) == 1
second = {**doc, "document_id": "bill-2", "source_name": "bill2.pdf"}
claim_two = normalize_documents([doc, second])
assert claim_two.multiple_bill_count == 2
assert claim_two.aggregation_requires_confirmation is True
print("LINE_ITEMS_OK")
