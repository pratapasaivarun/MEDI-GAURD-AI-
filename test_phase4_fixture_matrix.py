import json
from pathlib import Path
from extraction import extract_document, normalize_documents
from policy_terms import extract_policy_terms

ROOT = Path(__file__).parent / "fixtures" / "phase4"
manifest = json.loads((ROOT / "ground_truth.json").read_text(encoding="utf-8"))
assert manifest["synthetic_only"] is True
results = []
for item in manifest["fixtures"]:
    path = ROOT / item["file"]
    evidence, raw, pages = extract_document(path, f"phase4-{item['file']}", path.name)
    assert pages == item["pages"], (item["file"], pages)
    if item["type"] == "medical_bill":
        normalized = normalize_documents([{"document_id": f"phase4-{item['file']}", "source_name": path.name, "document_type": item["type"], "text": "\\n".join(e.text for e in evidence), "evidence": [e.to_dict() for e in evidence], "raw_by_page": raw}]).to_dict()
        expected = item["expected"]
        values = {key: (normalized.get(key) or {}).get("value") for key in expected}
        if item.get("expected_behavior") == "correct_or_manual_review":
            assert values["total_amount"] == expected["total_amount"] or normalized["review_fields"] or normalized["missing_fields"], (item["file"], values, normalized)
        else:
            assert values["total_amount"] == expected["total_amount"], (item["file"], values)
        results.append((item["file"], normalized["review_fields"], normalized["missing_fields"]))
    else:
        assert evidence, item["file"]
        policy_text = "\\n".join(e.text for e in evidence)
        terms = extract_policy_terms(policy_text)
        if item["file"] == "policy_standard.pdf":
            for expected_term in item["expected_terms"]:
                assert expected_term not in terms["missing_terms"], (item["file"], expected_term, terms)
        else:
            assert terms["terms_json"] or terms["missing_terms"], (item["file"], terms)
        results.append((item["file"], len(evidence), terms["terms_json"], terms["missing_terms"]))
print("PHASE4_FIXTURE_MATRIX_OK", len(results), "synthetic_only=True")
