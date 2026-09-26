#!/usr/bin/env python3
"""Score completed human annotations against recorded MediGuard outputs."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evaluation"))
from metric_calculators import (  # noqa: E402
    PENDING,
    appeal_rubric_score,
    boolean_support_score,
    character_error_rate,
    decision_scores,
    word_error_rate,
)


def load_json(path: Path, default: Any):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--annotations", type=Path, default=ROOT / "evaluation" / "annotations.json")
    parser.add_argument("--extraction-results", type=Path, default=ROOT / "evaluation" / "results.json")
    parser.add_argument("--system-results", type=Path, default=ROOT / "evaluation" / "system_results.json")
    parser.add_argument("--output", type=Path, default=ROOT / "evaluation" / "annotation_scores.json")
    args = parser.parse_args()

    annotations = load_json(args.annotations, {})
    extraction = load_json(args.extraction_results, {}).get("extraction", {})
    system = load_json(args.system_results, {})

    ocr_actual = {row.get("document"): row.get("ocr_text", "") for row in extraction.get("ocr_documents", [])}
    ocr_rows = []
    for item in annotations.get("ocr_transcripts", []):
        reference = item.get("reference_text")
        document_id = item.get("document_id")
        hypothesis = ocr_actual.get(document_id)
        if isinstance(reference, str) and reference.strip() and isinstance(hypothesis, str):
            ocr_rows.append({"document_id": document_id,
                             "cer": character_error_rate(reference, hypothesis),
                             "wer": word_error_rate(reference, hypothesis),
                             "verified_by": item.get("verified_by")})
    ocr = {"documents_scored": len(ocr_rows), "per_document": ocr_rows,
           "mean_cer": mean([row["cer"] for row in ocr_rows]) if ocr_rows else PENDING,
           "mean_wer": mean([row["wer"] for row in ocr_rows]) if ocr_rows else PENDING}

    retrieval = system.get("retrieval_runs_by_query_id", {})
    from metric_calculators import retrieval_scores
    retrieval_result = retrieval_scores(annotations.get("retrieval_queries", []), retrieval)

    per_model = {}
    per_model_rows = {}
    for model_name, model_result in system.get("models", {}).items():
        rows = model_result.get("cases", [])
        per_model_rows[model_name] = rows
        per_model[model_name] = {
            "rule_engine": decision_scores(rows, "expected_rule_status", "rule_engine_status"),
            "decision_agent": decision_scores(rows, "expected_decision", "final_decision"),
        }

    evidence_reviews = annotations.get("evidence_reviews", [])
    appeals = annotations.get("appeal_reviews", [])
    evidence = {
        "decision_support": boolean_support_score(evidence_reviews, "evidence_supports_decision"),
        "rule_consistency": boolean_support_score(evidence_reviews, "rule_result_consistent"),
        "review_count": sum(isinstance(row.get("evidence_supports_decision"), bool) for row in evidence_reviews),
        "unsupported_claims_reported": sum(len(row.get("unsupported_claims") or []) for row in evidence_reviews),
    }
    appeal = appeal_rubric_score(appeals)
    expert_reviews = [row for row in evidence_reviews + appeals
                      if row.get("independent") is True and row.get("reviewer_qualification")]
    expert_status = {
        "status": "Reviewed" if expert_reviews else PENDING,
        "qualifying_review_count": len(expert_reviews),
        "distinct_reviewer_count": len({row.get("reviewer_id") for row in expert_reviews if row.get("reviewer_id")}),
    }
    model_names = list(per_model_rows)
    model_comparison = {}
    if len(model_names) >= 2:
        model_comparison = {
            name: {
                "decision_accuracy": per_model[name]["decision_agent"]["accuracy_percent"],
                "end_to_end_latency": model_result.get("scores", {}).get("latency", {}).get("end_to_end", PENDING),
                "evidence_support": boolean_support_score(
                    [row for row in evidence_reviews if row.get("model_name") == name],
                    "evidence_supports_decision"),
                "appeal_quality": appeal_rubric_score(
                    [row for row in appeals if row.get("model_name") == name]),
            }
            for name, model_result in system.get("models", {}).items()
        }
    else:
        model_comparison = PENDING
    result = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "synthetic_or_human_review_only": True,
        "ocr_cer_wer": ocr,
        "retrieval": retrieval_result,
        "model_case_scores": per_model,
        "evidence_correctness": evidence,
        "appeal_quality": appeal,
        "expert_validation": expert_status,
        "model_comparison": model_comparison,
        "model_comparison_reason": "A matched 8B and 3B system_results.json run is required. Human-scored quality stays pending until model-specific reviews are entered.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "ocr_documents_scored": ocr["documents_scored"],
                      "retrieval_queries_scored": retrieval_result["annotated_query_count"],
                      "evidence_reviews": evidence["review_count"], "appeal_reviews": appeal["letters_scored"],
                      "expert_review_count": expert_status["qualifying_review_count"]}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
