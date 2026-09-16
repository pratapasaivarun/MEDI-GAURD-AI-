import json
import os
import time
from pathlib import Path
from dataclasses import asdict

ROOT = Path(__file__).parent
os.environ.setdefault('OCR_BACKEND', 'tesseract')
os.environ.setdefault('TESSERACT_CMD', r'C:\Program Files\Tesseract-OCR\tesseract.exe')
os.environ.setdefault('OLLAMA_HOST', 'http://localhost:11434')
os.environ.setdefault('OLLAMA_MODEL', 'ibm/granite4.1:8b')
os.environ.setdefault('OLLAMA_TIMEOUT_SECONDS', '120')
os.environ.setdefault('CHROMA_DIR', str(ROOT / 'data' / 'chroma_e2e'))

from extraction import extract_document, normalize_documents
from rules import evaluate_claim
from policy_index import index_policy_documents, retrieve_policy_evidence
from agents import warm_ollama, run_claim_workflow

PDF = ROOT / 'demo_assets' / 'approved_bill.pdf'
IMAGE = ROOT / 'fixtures' / 'phase4' / 'bill_clean_mobile_demo.png'
POLICY = ROOT / 'demo_assets' / 'approved_policy.pdf'


def extract(path: Path, doc_id: str):
    evidence, raw, pages = extract_document(path, doc_id, path.name)
    return {'document_id': doc_id, 'source_name': path.name, 'text': '\n'.join(raw.values()), 'evidence': [item.to_dict() for item in evidence], 'pages': pages}

print('=== 1. PDF extraction ===')
pdf_doc = extract(PDF, 'e2e-pdf')
print('pages=', pdf_doc['pages'], 'evidence=', len(pdf_doc['evidence']))
assert pdf_doc['evidence'], 'PDF extraction returned no evidence'

print('=== 2. Image extraction ===')
image_doc = extract(IMAGE, 'e2e-image')
print('pages=', image_doc['pages'], 'evidence=', len(image_doc['evidence']))
assert image_doc['evidence'], 'Image extraction returned no evidence'
assert any('total' in item['text'].lower() for item in image_doc['evidence']), 'Image OCR did not recognize total'

print('=== 3. Normalization ===')
normalized = normalize_documents([pdf_doc]).to_dict()
print(json.dumps({key: (value.get('value') if isinstance(value, dict) else value) for key, value in normalized.items() if key in ('patient_name','hospital_name','policy_number','total_amount','missing_fields','review_fields')}, indent=2))
assert normalized['patient_name']['value']
assert normalized['hospital_name']['value']
assert float(normalized['total_amount']['value']) > 0

print('=== 4. Deterministic rules ===')
rules = evaluate_claim(normalized['total_amount']['value'], review_fields=normalized.get('review_fields'), missing_fields=normalized.get('missing_fields'))
print('status=', rules['status'], 'payable=', rules.get('payable_amount'))
assert rules['status'] in {'approved', 'partially_approved', 'manual_review'}
assert rules.get('payable_amount', 0) > 0

print('=== 5. ChromaDB policy index and retrieval ===')
policy_doc = extract(POLICY, 'e2e-policy')
index = index_policy_documents([policy_doc], 'POL-HEALTH-45821-e2e')
retrieved = retrieve_policy_evidence('deductible copayment annual limit required documents', 'POL-HEALTH-45821-e2e', limit=4)
print('indexed=', index['chunks_indexed'], 'retrieved=', len(retrieved))
assert index['chunks_indexed'] > 0
assert retrieved, 'ChromaDB returned no policy evidence'

print('=== 6. Ollama warm-up ===')
started = time.time()
warm_ollama()
print('warmup_seconds=', round(time.time() - started, 2))

print('=== 7. Two-agent LangGraph workflow ===')
workflow = run_claim_workflow(normalized, policy_doc['text'], rules, policy_id='POL-HEALTH-45821-e2e')
decision = workflow.get('decision', {})
print(json.dumps({'status': decision.get('status'), 'confidence': decision.get('confidence'), 'llm_calls': workflow.get('llm_calls'), 'evidence_count': len(workflow.get('policy_evidence', []))}, indent=2))
assert workflow.get('llm_calls') == 1, workflow
assert not decision.get('_fallback'), decision
assert decision.get('status') in {'approved', 'partially_approved', 'rejected', 'manual_review'}, decision

print('E2E_TEST_OK')
