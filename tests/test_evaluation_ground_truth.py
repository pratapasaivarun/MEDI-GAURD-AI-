import json
from pathlib import Path


def test_phase4_ground_truth_contains_only_existing_fictional_bills():
    root = Path(__file__).parents[1]
    manifest = json.loads((root / "fixtures/phase4/ground_truth.json").read_text(encoding="utf-8"))
    assert manifest["synthetic_only"] is True
    assert manifest["label"] == "FICTIONAL SAMPLE"
    assert len(manifest["fixtures"]) == 3
    for fixture in manifest["fixtures"]:
        assert fixture["label"] == "FICTIONAL SAMPLE"
        assert (root / "fixtures/phase4" / fixture["file"]).is_file()
        assert set(fixture["expected"]) == {"patient_name", "hospital_name", "policy_number", "total_amount"}


def test_retrieval_labels_have_query_and_nonempty_source_clause_ids():
    root = Path(__file__).parents[1]
    annotations = json.loads((root / "evaluation/annotations.json").read_text(encoding="utf-8"))
    queries = annotations["retrieval_queries"]
    assert len(queries) >= 20
    assert all(q["query"].strip() and q["case_id"] and q["relevant_clause_ids"] for q in queries)
    assert all(q["relevant_clause_text"].strip() and q["relevant_page"] >= 1 for q in queries)
    assert len({q["case_id"] for q in queries}) >= 20
    assert len({q["query_id"].split("_")[1] for q in queries}) >= 3
    assert all(len(q["relevant_clause_ids"][0]) == 64 for q in queries)


def test_every_scenario_uses_explicit_fixture_reviewer_confirmed_terms():
    root = Path(__file__).parents[1]
    index = json.loads((root / "fixtures/claim_scenarios/case_index.json").read_text(encoding="utf-8"))
    review = json.loads((root / "evaluation/reviewer_confirmed_policy_terms.json").read_text(encoding="utf-8"))
    assert review["synthetic_only"] is True
    assert review["label"] == "FICTIONAL SAMPLE"
    assert review["reviewer"] and review["review_date"]
    assert set(review["cases"]) == {row["case_id"] for row in index}
    assert all(row["review_status"] == "confirmed" for row in review["cases"].values())
    assert all(item.get("source_page") and item.get("source_text") for row in review["cases"].values()
               for item in row["terms"].values())
