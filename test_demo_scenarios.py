"""Three reproducible prototype outcomes using synthetic documents."""
import json
import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent
RUN = Path(tempfile.mkdtemp(prefix='demo_scenarios_', dir=ROOT / 'data'))
os.environ['MEDIGUARD_DB_PATH'] = str(RUN / 'claims.db')
os.environ['MEDIGUARD_STORAGE_DIR'] = str(RUN)
os.environ['CHROMA_DIR'] = str(RUN / 'chroma')
import app
from reports import build_appeal_letter

class Upload:
    def __init__(self, path):
        self.name = path.name
        self.content = path.read_bytes()
    def getvalue(self):
        return self.content

app.init_db()
user = app.get_or_create_user('scenarios@local.test', 'Synthetic scenarios')
results = []
for number, label, patient, expected in [(1, 'APPROVED', 'Ananya Rao', 'approved'), (2, 'PARTIAL', 'Rahul Verma', 'partially_approved'), (1, 'MANUAL', 'Ananya Rao', 'manual_review')]:
    source_label = 'APPROVED' if number == 1 else 'PARTIAL'
    # The approved bill uses an alphanumeric fixture policy identifier so the
    # line-item extractor cannot mistake a trailing identifier segment for a charge.
    policy = 'POLDEMOAPPROVEDX' if source_label == 'APPROVED' else f'POL-DEMO-{source_label}-2026'
    registered_policy = 'POL-MISMATCH-DEMO' if label == 'MANUAL' else policy
    claim = app.create_claim(user['user_id'], f'DEMO-{label}', patient, 'Demo Hospital', registered_policy, '2026-08-20')
    files = {
        'APPROVED': {'medical_bill': 'approved_bill.pdf', 'policy': 'approved_policy.pdf'},
        'PARTIAL': {'medical_bill': 'partial_bill.pdf', 'policy': 'partial_policy.pdf'},
        'MANUAL': {'medical_bill': 'approved_bill.pdf', 'policy': 'approved_policy.pdf'},
    }
    for kind, filename in files[label].items():
        path = ROOT / 'demo_assets' / filename
        app.save_document(claim, user, Upload(path), kind)
    normalized = app.process_claim_documents(claim, user['user_id'])
    assert normalized['policy_terms']['terms_json']['room_limit_per_day']['value'] == '5000', normalized['policy_terms']
    rules = app.evaluate_saved_claim(claim, user['user_id'], normalized)
    assert rules['status'] == expected, (label, rules)
    if label == 'APPROVED':
        assert rules['payable_amount'] == 67500
    if label == 'PARTIAL':
        assert rules['payable_amount'] == 81000
    result = {'scenario': label, 'status': rules['status'], 'payable': rules['payable_amount'], 'warnings': rules.get('warnings', [])}
    results.append(result)
    print(json.dumps(result))
(RUN / 'results.json').write_text(json.dumps(results, indent=2), encoding='utf-8')

# The deterministic appeal letter must explain the disputed item rows and cite
# retained policy evidence without making an additional LLM call.
appeal_claim = {
    'claim_number': 'DEMO-APPEAL',
    'patient_name': 'Appeal Patient',
}
appeal_rules = {
    'status': 'partially_approved',
    'payable_amount': 45000,
    'warnings': [],
    'line_item_results': [
        {'description': 'Cosmetic procedure', 'amount': 20000, 'covered_amount': 0, 'status': 'excluded', 'applied_rule': 'exclusion'},
        {'description': 'Surgery', 'amount': 80000, 'covered_amount': 50000, 'status': 'partial', 'applied_rule': 'sub_limit'},
        {'description': 'Consultation', 'amount': 10000, 'covered_amount': 10000, 'status': 'covered', 'applied_rule': 'standard'},
    ],
}
appeal_workflow = {
    'normalized_claim': {
        'line_items': [
            {'description': 'Cosmetic procedure', 'amount': 20000},
            {'description': 'Surgery', 'amount': 80000},
            {'description': 'Consultation', 'amount': 10000},
        ],
    },
    'decision': {
        'reasons': ['The surgery charge is above the applicable sub-limit.'],
        'policy_citations': ['CL-EXCLUSION', 'CL-SURGERY-LIMIT'],
        'line_item_notes': [
            {'item_index': 0, 'note': 'This procedure was excluded.'},
            {'item_index': 1, 'note': 'This charge was capped.'},
        ],
    },
    'policy_findings': {
        'findings': [
            {'clause_id': 'CL-EXCLUSION', 'text': 'Cosmetic procedures are excluded unless medically necessary.'},
            {'clause_id': 'CL-SURGERY-LIMIT', 'text': 'Surgery is subject to an INR 50,000 sub-limit.'},
        ],
    },
}
appeal_letter = build_appeal_letter(appeal_claim, appeal_rules, appeal_workflow)
assert 'Cosmetic procedure' in appeal_letter and 'Surgery' in appeal_letter
assert 'INR 50,000.00' in appeal_letter
assert 'CL-SURGERY-LIMIT' in appeal_letter

fallback_letter = build_appeal_letter(appeal_claim, {**appeal_rules, 'line_item_results': []}, appeal_workflow)
assert fallback_letter == (
    'Subject: Request for review of claim DEMO-APPEAL\n\n'
    'Dear Claims Review Team,\n\n'
    'I request a human review of claim DEMO-APPEAL for Appeal Patient. '
    'The current assessment is Partially Approved, with an estimated insurer payment of INR 45,000.00.\n\n'
    'Please review the attached medical documents, the applicable policy edition, cited policy evidence, and the recorded calculation. '
    'Please provide the final determination and supporting reasons in writing.\n\n'
    'Key points for review:\n'
    '- The surgery charge is above the applicable sub-limit.\n\n'
    'Sincerely,\n'
    'Claimant or authorized representative\n'
)
print('DEMO_SCENARIOS_OK', RUN)
