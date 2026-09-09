import json
import time
from agents import warm_ollama, run_claim_workflow, retrieve_policy_evidence

warm_ollama()

claims = [
    {
        "name": "multiple_exclusions",
        "normalized": {"policy_number": {"value": "POL-HARD-001"}, "diagnosis": {"value": "orthopedic surgery"}, "total_amount": {"value": 185000.0}},
        "rules": {"status": "approved", "covered_amount": 185000.0, "deductible": 10000.0, "copayment": 17500.0, "payable_amount": 157500.0, "warnings": []},
        "policy": "Policy POL-HARD-001. Hospitalization is covered up to INR 500000 annual limit. Deductible is INR 10000. Copayment is 10 percent. Exclusion: cosmetic surgery. Exclusion: dental treatment unless accidental. Exclusion: experimental treatment. Network hospital required. Pre-authorization required for surgery. Room limit INR 7000 per day. Waiting period 12 months. Required documents include discharge summary and itemized bill."
    },
    {
        "name": "ambiguous_manual_review",
        "normalized": {"policy_number": {"value": "POL-HARD-002"}, "diagnosis": {"value": "hospitalization"}, "total_amount": {"value": 90000.0}, "missing_fields": ["policy_terms"]},
        "rules": {"status": "manual_review", "covered_amount": 0.0, "deductible": 0.0, "copayment": 0.0, "payable_amount": 0.0, "warnings": ["Required policy terms missing"]},
        "policy": "Policy POL-HARD-002. Hospitalization may be covered subject to plan conditions. Coverage amount and deductible are described in an unclear schedule. Copayment terms are ambiguous. Required documents may include records."
    }
]

results=[]
for item in claims:
    evidence = retrieve_policy_evidence(item["policy"], item["normalized"], limit=8)
    started=time.perf_counter()
    workflow=run_claim_workflow(item["normalized"], item["policy"], item["rules"])
    elapsed=time.perf_counter()-started
    decision=workflow.get("decision", {})
    results.append({"name":item["name"], "retrieved_before_workflow":len(evidence), "workflow_evidence":len(workflow.get("policy_evidence", [])), "llm_calls":workflow.get("llm_calls"), "status":decision.get("status"), "confidence":decision.get("confidence"), "elapsed_seconds":round(elapsed,3), "fallback":bool(decision.get("_fallback")), "decision_reasons":decision.get("reasons", [])})
print(json.dumps(results, indent=2))
open("section1_hard_claims_results.json", "w", encoding="utf-8").write(json.dumps(results, indent=2))
