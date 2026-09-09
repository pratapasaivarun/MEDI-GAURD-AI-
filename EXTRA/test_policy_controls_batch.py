from rules import PolicyTerms, evaluate_claim
from policy_terms import extract_policy_terms

policy = '''Annual Policy Limit: INR 500000
Deductible: INR 10000
Copayment: 10 percent
Room and Board Limit: INR 5000 per day
Waiting period: 24 months
Pre-authorization required for surgery.
Network provider required.
Surgery sub-limit: INR 100000
Exclusion: cosmetic surgery.'''
extracted = extract_policy_terms(policy)
assert extracted['terms'].waiting_period_months == 24, extracted
assert extracted['terms'].sub_limits.get('surgery') == 100000, extracted
assert extracted['terms_json']['preauthorization_required']['value'] is True, extracted
assert extracted['terms_json']['network_required']['value'] is True, extracted
assert 'exclusions' in extracted['terms_json'], extracted

base = extracted['terms']
source = extracted['terms_json']
base.source = source
manual = evaluate_claim(150000, base, claim_context={'diagnosis': 'cosmetic surgery', 'coverage_category': 'surgery'})
assert manual['status'] == 'manual_review', manual
assert any('waiting period' in warning.lower() for warning in manual['warnings']), manual
assert any('pre-authorization' in warning.lower() for warning in manual['warnings']), manual
assert any('network' in warning.lower() for warning in manual['warnings']), manual
assert any('exclusion' in warning.lower() for warning in manual['warnings']), manual
assert 'sub_limit_applied:surgery' in manual['warnings'], manual

approved = evaluate_claim(145000, PolicyTerms(annual_limit=500000, deductible=10000, copay_percent=10, room_limit_per_day=5000))
assert approved['status'] == 'approved', approved
assert approved['payable_amount'] == 121500.0, approved
print('POLICY_CONTROLS_BATCH_OK')
