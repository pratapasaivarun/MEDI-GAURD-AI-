from pathlib import Path
from extraction import extract_document, normalize_documents
from policy_terms import extract_policy_terms

root = Path('fixtures/phase4')
bill = root / 'bill_clean_mobile_demo.png'
policy = root / 'policy_clean_mobile_demo.pdf'

def extract(path, kind, doc_id):
    evidence, raw, pages = extract_document(path, doc_id, path.name)
    return {'document_id': doc_id, 'source_name': path.name, 'document_type': kind, 'text': '\n'.join(item.text for item in evidence), 'raw_by_page': raw, 'evidence': [item.to_dict() for item in evidence], 'pages': pages}

bill_doc = extract(bill, 'medical_bill', 'clean-bill')
Path('clean_mobile_bill_ocr.txt').write_text(bill_doc['text'], encoding='utf-8')
policy_doc = extract(policy, 'policy', 'clean-policy')
claim = normalize_documents([bill_doc])
policy_parsed = extract_policy_terms(policy_doc['evidence'])
print('BILL_PAGES=', bill_doc['pages'])
print('BILL_FIELDS=', {key: (getattr(claim, key).value if getattr(claim, key) else None) for key in ('patient_name','hospital_name','policy_number','claim_number','admission_date','discharge_date','diagnosis','total_amount')})
print('BILL_MISSING=', claim.missing_fields)
print('BILL_LINE_ITEMS=', [(item['description'], item['amount'], item['category']) for item in claim.line_items])
print('POLICY_PAGES=', policy_doc['pages'])
terms = policy_parsed['terms']
print('POLICY_TERMS=', {'annual_limit': str(terms.annual_limit), 'deductible': str(terms.deductible), 'copay_percent': str(terms.copay_percent), 'room_limit_per_day': str(terms.room_limit_per_day), 'waiting_period_months': terms.waiting_period_months})
print('POLICY_MISSING=', policy_parsed['missing_terms'])
