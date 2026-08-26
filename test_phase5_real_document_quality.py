import json
from pathlib import Path
from extraction import extract_document, normalize_documents
from rules import evaluate_claim

ROOT = Path(__file__).parent / "fixtures" / "phase4"
manifest = json.loads((ROOT / "ground_truth.json").read_text(encoding="utf-8"))
quality = []
for item in manifest["fixtures"]:
    if item["type"] != "medical_bill":
        continue
    path = ROOT / item["file"]
    evidence, raw, pages = extract_document(path, f"phase5-{item['file']}", path.name)
    normalized_obj = normalize_documents([{"document_id": f"phase5-{item['file']}", "source_name": path.name, "document_type": item["type"], "text": "\n".join(e.text for e in evidence), "evidence": [e.to_dict() for e in evidence], "raw_by_page": raw}])
    normalized = normalized_obj.to_dict()
    expected = item["expected"]
    field_results = {}
    for field, expected_value in expected.items():
        extracted = normalized.get(field) or {}
        field_results[field] = {
            "expected": expected_value,
            "actual": extracted.get("value"),
            "confidence": extracted.get("confidence"),
            "needs_review": extracted.get("needs_review"),
            "provenance": [{"source_name": ev.get("source_name"), "page": ev.get("page"), "method": ev.get("method")} for ev in extracted.get("evidence", [])],
        }
    exact_count = sum(1 for f in field_results.values() if f["actual"] == f["expected"])
    review_required = bool(normalized["review_fields"] or normalized["missing_fields"])
    if review_required:
        rules = evaluate_claim((normalized.get("total_amount") or {}).get("value"), missing_fields=normalized["missing_fields"], review_fields=normalized["review_fields"])
        assert rules["status"] == "manual_review", (item["file"], rules)
    if item.get("expected_behavior") == "correct_or_manual_review":
        assert exact_count == len(field_results) or review_required, (item["file"], field_results, normalized)
    else:
        assert exact_count == len(field_results), (item["file"], field_results)
        assert not review_required, (item["file"], normalized)
    quality.append({"file": item["file"], "pages": pages, "exact_fields": exact_count, "field_count": len(field_results), "review_fields": normalized["review_fields"], "missing_fields": normalized["missing_fields"], "fields": field_results})
report = {"synthetic_only": True, "fixtures": quality}
(Path(__file__).parent / "fixtures" / "phase4" / "phase5_quality_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print("PHASE5_REAL_DOCUMENT_QUALITY_OK", len(quality), "synthetic_only=True")
for row in quality:
    print(row["file"], f"exact={row['exact_fields']}/{row['field_count']}", f"review={row['review_fields']}", f"missing={row['missing_fields']}")
