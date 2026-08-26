import json
from pathlib import Path
import fitz
import app
from extraction import extract_document
from policy_terms import extract_policy_terms, terms_from_json
from rules import evaluate_claim

pdf = Path('sample_policy.pdf')
evidence, raw, pages = extract_document(pdf, 'test-policy', pdf.name)
extracted = extract_policy_terms(evidence)
assert extracted['missing_terms'] == [], extracted
assert str(extracted['terms_json']['annual_limit']['value']) == '500000'
assert str(extracted['terms_json']['deductible']['value']) == '10000'
assert str(extracted['terms_json']['copay_percent']['value']) == '10'
terms, missing, confidence = terms_from_json(extracted['terms_json'])
terms.source = extracted['terms_json']
result = evaluate_claim(145000, terms=terms, policy_terms_missing=missing)
assert result['status'] == 'manual_review', result
assert result['payable_amount'] == 121500.0, result
app.init_db()
with app.db() as conn:
    cols = [row[1] for row in conn.execute('PRAGMA table_info(policy_versions)').fetchall()]
assert 'policy_terms_json' in cols, cols
print('TERMS=', json.dumps(extracted['terms_json']))
print('RESULT=', result['status'], result['payable_amount'], 'confidence=', confidence)
print('DYNAMIC_POLICY_TERMS_TEST_OK')
