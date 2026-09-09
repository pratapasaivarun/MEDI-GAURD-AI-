import json
import app

claim_id = '45932a17-4b26-40bb-b1d4-5b82f1d3f98c'
user_id = '06b5a593e3cb063aaa41ae03'
normalized = app.process_claim_documents(claim_id, user_id)
summary = {key: (value.get('value') if isinstance(value, dict) else value) for key, value in normalized.items() if key in {'patient_name','hospital_name','policy_number','claim_number','admission_date','discharge_date','diagnosis','total_amount','missing_fields','review_fields'}}
print('NORMALIZED=', json.dumps(summary, indent=2, default=str))
rules = app.evaluate_saved_claim(claim_id, user_id, normalized)
print('RULES=', json.dumps({key: rules.get(key) for key in ('policy_source','status','covered_amount','deductible','copayment','payable_amount','warnings')}, indent=2, default=str))
assert summary['patient_name'] == 'Jane Doe', summary
assert summary['hospital_name'] == 'City Care Hospital', summary
assert summary['policy_number'] == 'POL-HEALTH-45821', summary
assert summary['claim_number'] == 'CLM-2026-0001', summary
assert summary['diagnosis'] == 'Acute appendicitis', summary
assert summary['total_amount'] == 145000.0, summary
assert rules['payable_amount'] == 121500.0, rules
print('IMAGE_CLAIM_FULL_NORMALIZATION_OK')
