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
    policy = f'POL-DEMO-{source_label}-2026'
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
print('DEMO_SCENARIOS_OK', RUN)
