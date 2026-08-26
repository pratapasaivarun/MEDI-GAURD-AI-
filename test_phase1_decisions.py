import sqlite3
from pathlib import Path
from rules import PolicyTerms, evaluate_claim
from policy_terms import extract_policy_terms

# Decision 2: missing policy terms force Manual Review.
missing = extract_policy_terms('Hospitalization is covered subject to plan conditions.')
assert missing['missing_terms']
result = evaluate_claim(100000, terms=missing['terms'], policy_terms_missing=missing['missing_terms'])
assert result['status'] == 'manual_review'

# Decision 3: ambiguous/invalid terms force review.
ambiguous = extract_policy_terms('Annual Policy Limit: INR 100000\nDeductible: INR 10000\nCopayment: 125 percent')
assert ambiguous['validation_errors']
assert ambiguous['confidence'] == 0.0

# Decision 4: low-confidence or review-flagged fields force Manual Review.
terms = PolicyTerms(annual_limit=500000, deductible=10000, copay_percent=10)
review_result = evaluate_claim(100000, terms=terms, review_fields=['total_amount'])
assert review_result['status'] == 'manual_review'

# Decision 1: the application database must have an exact-match active policy.
# This is verified against the cleaned fixture created by Phase 0.
conn = sqlite3.connect('data/mediguard.db')
row = conn.execute("SELECT policy_number,status,policy_terms_json FROM policy_versions WHERE policy_number='POL-HEALTH-45821' AND status='active' ORDER BY created_at DESC LIMIT 1").fetchone()
conn.close()
assert row is not None
assert row[2]

# Decision 5: production retrieval remains unchanged at 2; limit=4 is an experiment only.
from pathlib import Path
agents_text = Path('agents.py').read_text(encoding='utf-8')
assert 'retrieve_policy_evidence(state.get("policy_text", ""), state.get("normalized_claim", {}), state.get("policy_id", ""), limit=2)' in agents_text
print('PHASE1_FIVE_DECISIONS_OK')
