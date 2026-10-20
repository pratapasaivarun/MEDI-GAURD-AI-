import json
from pathlib import Path
from types import SimpleNamespace

import evaluation.run_all as evaluation
from evaluation.run_all import build_claim, eq, retrieval_metrics


ROOT = Path(__file__).resolve().parents[2]


def test_benchmark_has_30_fictional_cases_and_30_labeled_retrieval_queries():
    labels = json.loads((ROOT / "samples/evaluation_cases/ground_truth.json").read_text(encoding="utf-8"))
    queries = json.loads((ROOT / "evaluation/retrieval_queries.json").read_text(encoding="utf-8"))
    assert labels["synthetic_only"] is True
    assert len(labels["cases"]) == 30
    assert {group: sum(row["group"] == group for row in labels["cases"])
            for group in ("match", "discrepancy", "manual_review", "edge")} == {
                "match": 10, "discrepancy": 10, "manual_review": 5, "edge": 5,
            }
    assert len(queries["queries"]) == 30
    assert all(row["expected_clause"] and row["expected_page"] for row in queries["queries"])


def test_retrieval_precision_uses_k_times_query_count_as_denominator():
    score = retrieval_metrics([{"first_relevant_rank": 1}, {"first_relevant_rank": None}])
    assert score["precision_at_1"] == 0.5
    assert score["precision_at_3"] == 1 / 6
    assert score["precision_at_5"] == 0.1
    assert score["recall_at_5"] == 0.5
    assert score["mrr"] == 0.5


def test_evaluation_report_refresh_keeps_separately_measured_sections(tmp_path):
    report = tmp_path / "results.md"
    report.write_text(
        "Old generated scorecard\n\n## Supplemental measured results\n\n"
        "## Browser matrix (live Playwright run)\n8/8\n\n## Performance\n35 seconds\n",
        encoding="utf-8",
    )
    evaluation.write_evaluation_report(["New generated scorecard", "30/30"], report)
    actual = report.read_text(encoding="utf-8")
    assert "New generated scorecard" in actual
    assert "Old generated scorecard" not in actual
    assert "## Browser matrix (live Playwright run)" in actual
    assert "## Performance" in actual


def test_committed_case_expected_files_match_source_labels():
    labels = json.loads((ROOT / "samples/evaluation_cases/ground_truth.json").read_text(encoding="utf-8"))
    case_root = ROOT / "samples/evaluation_cases/cases"
    for row in labels["cases"]:
        expected = json.loads((case_root / row["case_id"] / "expected-results.json").read_text(encoding="utf-8"))
        assert expected == row
        assert all((case_root / row["case_id"] / filename).is_file()
                   for filename in ("bill.pdf", "policy.pdf", "settlement.pdf", "case.json"))


def test_hand_calculated_rule_amounts_match_direct_rule_path():
    labels = json.loads((ROOT / "samples/evaluation_cases/ground_truth.json").read_text(encoding="utf-8"))
    scored = 0
    for row in labels["cases"]:
        if row["expected_payable"] is None:
            continue
        claim, _terms = build_claim(row)
        assert eq(claim.insurer_share, row["expected_payable"]), row["case_id"]
        scored += 1
    assert scored == 24


def test_expected_manual_review_label_does_not_force_the_actual_result(monkeypatch):
    labels = json.loads((ROOT / "samples/evaluation_cases/ground_truth.json").read_text(encoding="utf-8"))
    row = dict(next(item for item in labels["cases"] if item["case_id"] == "manual_01"))
    row["expected_status"] = "no_discrepancy"
    monkeypatch.setattr(evaluation, "compare", lambda _claim, settlement, _terms: SimpleNamespace(
        status="manual_review" if settlement.needs_review else "no_discrepancy",
        possible_difference=0, review_reasons=[],
    ))
    actual = evaluation.run_case(row)
    assert actual["actual_status"] == "manual_review"
