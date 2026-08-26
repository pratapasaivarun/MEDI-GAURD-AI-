from policy_terms import extract_policy_terms
from rules import PolicyTerms, evaluate_claim

sample = "Annual Policy Limit: INR 100000\nDeductible: INR 10000\nCopayment: 20 percent\nRoom and Board Limit: INR 5000 per day\nWaiting period: 24 months"
parsed = extract_policy_terms(sample)
assert parsed["missing_terms"] == [], parsed
assert parsed["validation_errors"] == [], parsed
assert parsed["confidence"] >= 0.95
terms = parsed["terms"]
terms.source = parsed["terms_json"]
partial = evaluate_claim(150000, terms=terms)
assert partial["status"] == "manual_review", partial
assert partial["covered_amount"] == 100000.0
assert partial["payable_amount"] == 72000.0
missing = extract_policy_terms("Annual Policy Limit: INR 100000")
assert "deductible" in missing["missing_terms"]
review = evaluate_claim(50000, terms=missing["terms"], policy_terms_missing=missing["missing_terms"])
assert review["status"] == "manual_review", review
invalid = extract_policy_terms("Annual Policy Limit: INR 100000\nDeductible: INR 10000\nCopayment: 120 percent")
assert "copay_percent must be between 0 and 100" in invalid["validation_errors"]
print("POLICY_RULE_NEGATIVE_TEST_OK")
