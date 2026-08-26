import os
from pathlib import Path
os.environ['OCR_BACKEND'] = 'tesseract'
from extraction import extract_document

image = Path('sample_documents/sample_medical_bill_image.png')
evidence, raw, pages = extract_document(image, 'ocr-test', image.name)
print('pages=', pages)
print('evidence_count=', len(evidence))
for item in evidence:
    print('confidence=', item.confidence)
    print(item.text)
assert evidence, 'No OCR evidence returned'
assert any('Jane' in item.text or 'Total' in item.text or 'Hospital' in item.text for item in evidence), 'Expected sample bill text was not recognized'
print('TESSERACT_IMAGE_OCR_TEST_OK')
