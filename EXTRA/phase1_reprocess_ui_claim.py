import json
import sqlite3
import app

with sqlite3.connect('data/mediguard.db') as conn:
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT claim_id,user_id,claim_number,policy_number FROM claims WHERE claim_number='CLM-UI-45821' ORDER BY created_at DESC LIMIT 1").fetchone()
assert row is not None, 'CLM-UI-45821 not found'
print('CLAIM=', dict(row))
normalized = app.process_claim_documents(row['claim_id'], row['user_id'])
summary = {key: (value.get('value') if isinstance(value, dict) else value) for key, value in normalized.items() if key in {'patient_name','hospital_name','policy_number','claim_number','admission_date','discharge_date','total_amount','missing_fields','review_fields'}}
print('NORMALIZED=', json.dumps(summary, indent=2, default=str))
rules = app.evaluate_saved_claim(row['claim_id'], row['user_id'], normalized)
print('RULES=', json.dumps({key: rules.get(key) for key in ('policy_source','status','covered_amount','deductible','copayment','payable_amount','warnings')}, indent=2, default=str))
assert summary['total_amount'] == 145000.0, summary
assert rules['payable_amount'] == 121500.0, rules
assert rules['policy_source'] == 'POL-HEALTH-45821 — 2026 Edition', rules
print('PHASE1_UI_CLAIM_REPROCESS_OK')
