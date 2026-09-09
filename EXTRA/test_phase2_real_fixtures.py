from pathlib import Path
from extraction import extract_document, normalize_documents

image = Path('sample_medical_bill_image.png')
pdf = Path('sample_medical_bill.pdf')
assert image.exists(), image
assert pdf.exists(), pdf

image_evidence, image_raw, image_pages = extract_document(image, 'real-image', image.name)
image_claim = normalize_documents([{
    'document_id': 'real-image', 'original_name': image.name, 'document_type': 'medical_bill',
    'text': '\n'.join(item.text for item in image_evidence),
    'evidence': [item.to_dict() for item in image_evidence], 'raw_by_page': image_raw,
}]).to_dict()
assert image_pages == 1
assert image_claim['total_amount']['value'] == 145000.0, image_claim
assert image_claim['patient_name']['value'] == 'Jane Doe', image_claim
assert image_claim['hospital_name']['value'] == 'City Care Hospital', image_claim
assert image_claim['diagnosis']['value'] == 'Acute appendicitis', image_claim

pdf_evidence, pdf_raw, pdf_pages = extract_document(pdf, 'real-pdf', pdf.name)
pdf_claim = normalize_documents([{
    'document_id': 'real-pdf', 'original_name': pdf.name, 'document_type': 'medical_bill',
    'text': '\n'.join(item.text for item in pdf_evidence),
    'evidence': [item.to_dict() for item in pdf_evidence], 'raw_by_page': pdf_raw,
}]).to_dict()
assert pdf_pages >= 1
# If the PDF fixture does not expose an explicit total, never infer one from line items.
if pdf_claim['total_amount'] is None:
    assert 'total_amount' in pdf_claim['missing_fields'], pdf_claim
else:
    assert pdf_claim['total_amount']['value'] == 145000.0, pdf_claim

print('PHASE2_REAL_FIXTURES_OK')
