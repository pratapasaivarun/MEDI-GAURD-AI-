import requests
import agents

normalized = {
    'policy_number': {'value': 'POL-TEST'},
    'patient_name': {'value': 'Jane Doe'},
    'hospital_name': {'value': 'City Care Hospital'},
    'diagnosis': {'value': 'Acute appendicitis'},
    'total_amount': {'value': 145000.0},
}
rules = {
    'status': 'approved', 'covered_amount': 145000.0, 'deductible': 10000.0,
    'copayment': 13500.0, 'payable_amount': 121500.0, 'warnings': []
}
policy = 'Hospitalization covered up to INR 500000. Deductible INR 10000. Copayment 10 percent.'

# Policy-agent failure must stop the second LLM call and produce Manual Review.
original_json = agents._ollama_json
try:
    agents._ollama_json = lambda *args, **kwargs: (_ for _ in ()).throw(requests.Timeout('simulated policy timeout'))
    result = agents.run_claim_workflow(normalized, policy, rules)
finally:
    agents._ollama_json = original_json
assert result['decision']['status'] == 'manual_review', result
assert result['decision'].get('_fallback') is True, result
assert result.get('llm_calls') == 1, result

# Decision-agent failure must produce Manual Review after exactly two attempted calls.
count = {'value': 0}
def fail_decision(*args, **kwargs):
    count['value'] += 1
    if count['value'] == 1:
        return {'findings': [{'clause_id': 'policy-clause-1', 'interpretation': 'Coverage applies', 'applicability': 'Claim matches', 'citation': 'page 1'}], 'missing_evidence': [], 'confidence': 0.9}
    raise requests.RequestException('simulated decision outage')
try:
    agents._ollama_json = fail_decision
    result = agents.run_claim_workflow(normalized, policy, rules)
finally:
    agents._ollama_json = original_json
assert result['decision']['status'] == 'manual_review', result
assert result['decision'].get('_fallback') is True, result
assert result.get('llm_calls') == 2, result

# Malformed JSON must be rejected safely; a JSON list is normalized safely to the configured list key.
for content in ('not json', '{"status":'):
    try:
        agents._parse_json_response(content, 'reasons')
    except RuntimeError:
        pass
    else:
        raise AssertionError(f'Malformed response was accepted: {content!r}')
assert agents._parse_json_response('[]', 'reasons') == {'reasons': []}

print('PHASE2_AGENT_FAILURES_OK')
