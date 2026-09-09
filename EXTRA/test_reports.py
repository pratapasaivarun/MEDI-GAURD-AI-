from reports import build_appeal_letter, build_decision_report

claim = {"claim_number": "CLM-REPORT-001", "patient_name": "Jane Doe", "hospital_name": "City Care Hospital", "policy_number": "POL-HEALTH-45821"}
normalized = {"total_amount": {"value": 145000.0}}
rules = {"status": "approved", "covered_amount": 145000.0, "deductible": 10000.0, "copayment": 13500.0, "payable_amount": 121500.0, "warnings": []}
workflow = {"policy_source": "POL-HEALTH-45821 — 2026 Edition", "policy_findings": {"retrieved_evidence": [{"text": "Annual Policy Limit: INR 500000"}]}, "decision": {"status": "approved", "reasons": ["Policy evidence supports coverage."]}}
pdf = build_decision_report(claim, normalized, rules, workflow)
assert pdf.startswith(b"%PDF"), pdf[:20]
letter = build_appeal_letter(claim, rules, workflow)
assert "CLM-REPORT-001" in letter
assert "121,500.00" in letter
print("REPORT_EXPORT_TEST_OK")
