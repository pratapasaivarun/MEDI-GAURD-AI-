from decimal import Decimal
from rules import PolicyTerms, evaluate_claim

base = PolicyTerms(annual_limit=Decimal('500000'), deductible=Decimal('10000'), copay_percent=Decimal('10'), room_limit_per_day=Decimal('5000'))

partial = evaluate_claim(100000, terms=PolicyTerms(**{**base.__dict__, 'sub_limits': {'surgery': Decimal('50000')} }), claim_context={'coverage_category': 'surgery'})
assert partial['status'] == 'partially_approved', partial
assert partial['covered_amount'] == 50000.0 and partial['payable_amount'] == 36000.0, partial

room = evaluate_claim(200000, terms=base, claim_context={'room_charge': 40000, 'room_days': 5, 'room_linked_charges': 80000})
assert room['status'] == 'partially_approved', room
assert room['covered_amount'] == 155000.0 and room['payable_amount'] == 130500.0, room
assert any('proportional' in warning for warning in room['warnings']), room

excluded_terms = PolicyTerms(**{**base.__dict__, 'source': {'exclusions': {'value': ['cosmetic surgery']}}})
clear_exclusion = evaluate_claim(100000, terms=excluded_terms, claim_context={'diagnosis': 'cosmetic surgery', 'exclusion_match': {'matched': True, 'confidence': 0.99}})
assert clear_exclusion['status'] == 'rejected', clear_exclusion
uncertain_exclusion = evaluate_claim(100000, terms=excluded_terms, claim_context={'diagnosis': 'cosmetic surgery'})
assert uncertain_exclusion['status'] == 'manual_review', uncertain_exclusion

waiting_terms = PolicyTerms(**{**base.__dict__, 'waiting_period_months': 12})
waiting = evaluate_claim(100000, terms=waiting_terms, claim_context={'waiting_period_satisfied': False, 'waiting_period_affected_amount': 40000, 'unrelated_eligible_amount': 60000})
assert waiting['status'] == 'partially_approved', waiting
assert waiting['payable_amount'] == 45000.0, waiting

network_terms = PolicyTerms(**{**base.__dict__, 'source': {'network_required': {'value': True}}})
out_of_network = evaluate_claim(100000, terms=network_terms, claim_context={'in_network': False})
assert out_of_network['status'] == 'rejected', out_of_network
network_unknown = evaluate_claim(100000, terms=network_terms, claim_context={})
assert network_unknown['status'] == 'manual_review', network_unknown

preauth_terms = PolicyTerms(**{**base.__dict__, 'source': {'preauthorization_required': {'value': True}}})
assert evaluate_claim(100000, terms=preauth_terms, claim_context={})['status'] == 'manual_review'
assert evaluate_claim(100000, terms=base, claim_context={'duplicate_suspected': True})['status'] == 'manual_review'
assert evaluate_claim(100000, terms=base, claim_context={'multiple_bills': True, 'aggregation_confirmed': False})['status'] == 'manual_review'

net = evaluate_claim(160000, terms=base, claim_context={'net_amount': 140000})
assert net['status'] == 'approved' and net['payable_amount'] == 117000.0, net

print('PHASE6_BUSINESS_RULES_OK')
