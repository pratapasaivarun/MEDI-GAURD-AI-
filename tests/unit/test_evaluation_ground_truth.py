import json
from pathlib import Path

from evaluation.scripts.run_system_evaluation import (
    confirm_fixture_policy_terms,
    load_reviewer_confirmed_terms,
)


def test_phase4_ground_truth_contains_only_existing_fictional_bills():
    root = Path(__file__).parents[2]
    manifest = json.loads((root / "evaluation/ground_truth.json").read_text(encoding="utf-8"))
    assert manifest["synthetic_only"] is True
    assert manifest["label"] == "FICTIONAL SAMPLE"
    assert len(manifest["fixtures"]) == 3
    for fixture in manifest["fixtures"]:
        assert fixture["label"] == "FICTIONAL SAMPLE"
        assert (root / "evaluation" / fixture["file"]).is_file()
        assert set(fixture["expected"]) == {"patient_name", "hospital_name", "policy_number", "total_amount"}


def test_retrieval_labels_have_query_and_nonempty_source_clause_ids():
    root = Path(__file__).parents[2]
    annotations = json.loads((root / "evaluation/annotations.json").read_text(encoding="utf-8"))
    queries = annotations["retrieval_queries"]
    assert len(queries) >= 20
    assert all(q["query"].strip() and q["case_id"] and q["relevant_clause_ids"] for q in queries)
    assert all(q["relevant_clause_text"].strip() and q["relevant_page"] >= 1 for q in queries)
    assert len({q["case_id"] for q in queries}) >= 20
    assert len({q["query_id"].split("_")[1] for q in queries}) >= 3
    assert all(len(q["relevant_clause_ids"][0]) == 64 for q in queries)


def test_every_scenario_uses_explicit_fixture_reviewer_confirmed_terms():
    import fitz

    root = Path(__file__).parents[2]
    index = json.loads((root / "samples/claim_scenarios/case_index.json").read_text(encoding="utf-8"))
    review = json.loads((root / "evaluation/reviewer_confirmed_policy_terms.json").read_text(encoding="utf-8"))
    assert review["synthetic_only"] is True
    assert review["label"] == "FICTIONAL SAMPLE"
    assert review["reviewer"] and review["review_date"]
    assert set(review["cases"]) == {row["case_id"] for row in index}
    assert all(row["review_status"] == "confirmed" for row in review["cases"].values())
    assert all(item.get("source_page") and item.get("source_text") for row in review["cases"].values()
               for item in row["terms"].values())
    entries_by_id = {entry["case_id"]: entry for entry in index}
    for case_id, row in review["cases"].items():
        relative_case_path = entries_by_id[case_id]["path"].replace("\\", "/")
        policy_path = root / "samples/claim_scenarios" / relative_case_path / "policy.pdf"
        with fitz.open(policy_path) as policy:
            source_text = " ".join("\n".join(page.get_text() for page in policy).split()).casefold()
        for evidence in row["terms"].values():
            assert evidence["source_name"] == "policy.pdf"
            assert " ".join(evidence["source_text"].split()).casefold() in source_text


def test_rules_evaluation_submits_source_backed_terms_through_reviewer_path():
    cases = load_reviewer_confirmed_terms()

    class ReviewerForm:
        def __init__(self):
            self.call = None

        def save_policy_terms_review(self, version_id, reviewer_id, values, source_pages, sub_limits):
            self.call = (version_id, reviewer_id, values, source_pages, sub_limits)
            return "confirmed" if {"annual_limit", "deductible", "copay_percent"}.issubset(values) else "pending"

    app = ReviewerForm()
    result = confirm_fixture_policy_terms(app, "policy-1", "synthetic-reviewer", cases["01_standard_approved"])

    assert result == "confirmed"
    version_id, reviewer_id, values, pages, sub_limits = app.call
    assert (version_id, reviewer_id) == ("policy-1", "synthetic-reviewer")
    assert values == {"annual_limit": "100000", "deductible": "5000", "copay_percent": "10", "room_limit_per_day": "5000"}
    assert pages == {"annual_limit": 1, "deductible": 1, "copay_percent": 1, "room_limit_per_day": 1}
    assert sub_limits == {}


def test_evaluation_does_not_invent_policy_terms_missing_from_review():
    cases = load_reviewer_confirmed_terms()

    class ReviewerForm:
        def save_policy_terms_review(self, _version_id, _reviewer_id, values, _source_pages, _sub_limits):
            self.values = values
            return "pending" if "deductible" not in values or "copay_percent" not in values else "confirmed"

    app = ReviewerForm()
    result = confirm_fixture_policy_terms(app, "policy-2", "synthetic-reviewer", cases["02_missing_policy_terms"])

    assert app.values == {"annual_limit": "100000", "room_limit_per_day": "5000"}
    assert result == "pending"
