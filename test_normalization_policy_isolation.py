from pathlib import Path
from extraction import extract_document, normalize_documents
from policy_terms import extract_policy_terms, terms_from_json
from rules import evaluate_claim


def doc(path: str, document_id: str, document_type: str):
    evidence, raw, pages = extract_document(Path(path), document_id, Path(path).name)
    return {"document_id": document_id, "source_name": Path(path).name, "document_type": document_type, "text": "\n".join(raw.values()), "evidence": [item.to_dict() for item in evidence], "pages": pages}

policy = doc("sample_policy.pdf", "isolation-policy", "policy")
bill = doc("sample_medical_bill.pdf", "isolation-bill", "medical_bill")
normalized = normalize_documents([policy, bill]).to_dict()
assert normalized["patient_name"]["value"] == "Jane Doe"
assert normalized["hospital_name"]["value"] == "City Care Hospital"
assert normalized["policy_number"]["value"] == "POL-HEALTH-45821"
assert normalized["total_amount"]["value"] == 145000.0, normalized["total_amount"]
terms_data = extract_policy_terms(policy["text"])
terms, missing, confidence = terms_from_json(terms_data["terms_json"])
rules = evaluate_claim(normalized["total_amount"]["value"], terms=terms, policy_terms_missing=missing)
assert rules["payable_amount"] == 121500.0, rules
print("NORMALIZATION_POLICY_ISOLATION_OK")
