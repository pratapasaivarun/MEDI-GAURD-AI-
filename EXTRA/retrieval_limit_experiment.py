import json
import time
import agents
from agents import warm_ollama, retrieve_policy_evidence, run_claim_workflow

policy = ('Policy POL-HARD-001. Hospitalization is covered up to INR 500000 annual limit. '
          'Deductible is INR 10000. Copayment is 10 percent. Exclusion: cosmetic surgery. '
          'Exclusion: dental treatment unless accidental. Exclusion: experimental treatment. '
          'Network hospital required. Pre-authorization required for surgery. Room limit INR 7000 per day. '
          'Waiting period 12 months. Required documents include discharge summary and itemized bill.')
normalized = {'policy_number': {'value': 'POL-HARD-001'}, 'diagnosis': {'value': 'orthopedic surgery'}, 'total_amount': {'value': 185000.0}}
rules = {'status': 'approved', 'covered_amount': 185000.0, 'deductible': 10000.0, 'copayment': 17500.0, 'payable_amount': 157500.0, 'warnings': []}

warm_ollama()
results = []
for limit in (2, 4):
    evidence = retrieve_policy_evidence(policy, normalized, limit=limit)
    started = time.perf_counter()
    # Verification-only injection: production code and default retrieval stay unchanged.
    original_retriever = agents.retrieve_policy_evidence
    agents.retrieve_policy_evidence = lambda *args, **kwargs: evidence
    try:
        workflow = run_claim_workflow(normalized, policy, rules)
    finally:
        agents.retrieve_policy_evidence = original_retriever
    elapsed = time.perf_counter() - started
    decision = workflow.get('decision', {})
    results.append({'limit': limit, 'evidence_count': len(evidence), 'evidence': evidence, 'workflow_evidence_count': len(workflow.get('policy_evidence', [])), 'elapsed_seconds': round(elapsed, 3), 'llm_calls': workflow.get('llm_calls'), 'status': decision.get('status'), 'confidence': decision.get('confidence'), 'fallback': bool(decision.get('_fallback')), 'reasons': decision.get('reasons', [])})
print(json.dumps(results, indent=2, default=str))
with open('retrieval_limit_experiment_results.json', 'w', encoding='utf-8') as handle:
    json.dump(results, handle, indent=2, default=str)
print('RETRIEVAL_LIMIT_EXPERIMENT_OK')
