from agents import retrieve_policy_evidence
policy = "Policy POL-HARD-001. Hospitalization is covered up to INR 500000 annual limit. Deductible is INR 10000. Copayment is 10 percent. Exclusion: cosmetic surgery. Exclusion: dental treatment unless accidental. Exclusion: experimental treatment. Network hospital required. Pre-authorization required for surgery. Room limit INR 7000 per day. Waiting period 12 months. Required documents include discharge summary and itemized bill."
claim = {"policy_number": {"value": "POL-HARD-001"}, "diagnosis": {"value": "orthopedic surgery"}, "total_amount": {"value": 185000.0}}
for limit in (2, 4, 8):
    evidence = retrieve_policy_evidence(policy, claim, limit=limit)
    print(f"limit={limit} count={len(evidence)}")
    for item in evidence:
        print(item.get("clause_id"), item.get("text"))
