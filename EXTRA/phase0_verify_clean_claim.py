import json
import sqlite3
from pathlib import Path
from extraction import extract_document, normalize_documents
from policy_terms import terms_from_json
from rules import evaluate_claim

DB = Path('data/mediguard.db')
with sqlite3.connect(DB) as conn:
    conn.row_factory = sqlite3.Row
    policy = conn.execute("SELECT * FROM policy_versions WHERE policy_number=? AND status='active' ORDER BY effective_date DESC, created_at DESC LIMIT 1", ('POL-HEALTH-45821',)).fetchone()
assert policy is not None, 'No active exact-match POL-HEALTH-45821 policy'
assert policy['policy_terms_json'], 'Active exact-match policy has no terms'
terms_payload = json.loads(policy['policy_terms_json'])
terms, missing, confidence = terms_from_json(terms_payload)
terms.source = terms_payload
assert not missing, missing
assert confidence >= 0.70, confidence

def doc(path, doc_id):
    evidence, raw, pages = extract_document(path, doc_id, path.name)
    return {'document_id': doc_id, 'source_name': path.name, 'text': '\n'.join(raw.values()), 'evidence': [x.to_dict() for x in evidence], 'pages': pages}

bill = doc(Path('sample_medical_bill.pdf'), 'phase0-bill')
normalized = normalize_documents([bill]).to_dict()
assert normalized['policy_number']['value'] == 'POL-HEALTH-45821', normalized['policy_number']
assert not normalized['missing_fields'], normalized['missing_fields']
rules = evaluate_claim(normalized['total_amount']['value'], terms=terms, review_fields=normalized.get('review_fields'), missing_fields=normalized.get('missing_fields'), policy_terms_missing=missing)
result = {'policy_number': policy['policy_number'], 'policy_version': policy['version_label'], 'policy_status': policy['status'], 'term_keys': sorted(terms_payload), 'confidence': confidence, 'claim_policy_number': normalized['policy_number']['value'], 'bill_amount': normalized['total_amount']['value'], 'status': rules['status'], 'payable_amount': rules['payable_amount'], 'warnings': rules['warnings']}
print(json.dumps(result, indent=2, default=str))
assert result['payable_amount'] == 121500.0, result
assert result['status'] == 'approved', result
print('PHASE0_CLEAN_CLAIM_OK')
