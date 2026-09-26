#!/usr/bin/env python3
"""Run reproducible synthetic-fixture evaluations for MediGuard AI.

Run from the repository root with:
    .venv/Scripts/python.exe evaluation/run_evaluation.py --repeats 3

No external claim decisions are inferred here. Metrics without suitable
ground-truth annotations are emitted as Not Evaluated — Ground Truth/Data Required.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DEFAULT_TESSERACT = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
if "TESSERACT_CMD" not in os.environ and DEFAULT_TESSERACT.exists():
    os.environ["TESSERACT_CMD"] = str(DEFAULT_TESSERACT)

from extraction import extract_document, run_extraction  # noqa: E402
from metric_calculators import character_error_rate, word_error_rate  # noqa: E402

PENDING = "Not Evaluated — Ground Truth/Data Required"
FIELDS = ("patient_name", "hospital_name", "policy_number", "total_amount")


def field_value(claim: dict[str, Any], name: str) -> Any:
    value = claim.get(name)
    return value.get("value") if isinstance(value, dict) else value


def equal(actual: Any, expected: Any) -> bool:
    if isinstance(expected, (float, int)) and not isinstance(expected, bool):
        try:
            return abs(float(actual) - float(expected)) <= 0.01
        except (TypeError, ValueError):
            return False
    return str(actual or "").strip().casefold() == str(expected or "").strip().casefold()


def timing_summary(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"mean_seconds": None, "median_seconds": None, "min_seconds": None, "max_seconds": None}
    return {
        "mean_seconds": round(statistics.mean(values), 6),
        "median_seconds": round(statistics.median(values), 6),
        "min_seconds": round(min(values), 6),
        "max_seconds": round(max(values), 6),
    }


def evaluate_extraction(repeats: int, annotations: dict[str, Any] | None = None) -> dict[str, Any]:
    manifest_path = ROOT / "fixtures" / "phase4" / "ground_truth.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    details: list[dict[str, Any]] = []
    durations: list[float] = []
    correct = total = 0
    ocr_correct = ocr_total = 0
    digital_correct = digital_total = 0
    ocr_documents = 0
    ocr_durations: list[float] = []
    ocr_rows: list[dict[str, Any]] = []
    for fixture in manifest["fixtures"]:
        if fixture.get("type") != "medical_bill":
            continue
        path = ROOT / "fixtures" / "phase4" / fixture["file"]
        expected = fixture.get("expected", {})
        latest: dict[str, Any] = {}
        raw_by_page: dict[str, str] = {}
        methods: list[str] = []
        run_times: list[float] = []
        for _ in range(repeats):
            started = time.perf_counter()
            evidence, raw_by_page, _page_count = extract_document(path, fixture["file"], fixture["file"])
            elapsed = time.perf_counter() - started
            run_times.append(elapsed)
            methods = sorted({item.method for item in evidence})
            document = {
                "document_id": fixture["file"], "source_name": fixture["file"],
                "document_type": "medical_bill",
                "text": "\n".join(item.text for item in evidence),
                "evidence": [item.to_dict() for item in evidence],
                "raw_by_page": raw_by_page,
            }
            latest = run_extraction([document])
        durations.extend(run_times)
        # Count OCR attempts even when the OCR engine returns no usable text.
        is_ocr = ("tesseract" in methods or path.suffix.lower() in {".png", ".jpg", ".jpeg"}
                  or fixture["file"] == "bill_scanned_image_only.pdf")
        ocr_documents += int(is_ocr)
        if is_ocr:
            ocr_durations.extend(run_times)
        if is_ocr:
            ocr_rows.append({"document": fixture["file"], "ground_truth_text": None,
                             "ocr_text": "\n".join(raw_by_page.values()), "cer": None, "wer": None,
                             "status": PENDING})
        field_results = {}
        for name, expected_value in expected.items():
            actual = field_value(latest, name)
            match = equal(actual, expected_value)
            total += 1
            correct += int(match)
            if is_ocr:
                ocr_total += 1
                ocr_correct += int(match)
            else:
                digital_total += 1
                digital_correct += int(match)
            field_results[name] = {"expected": expected_value, "actual": actual, "correct": match}
        details.append({"document": fixture["file"], "extraction_methods": methods,
                        "ocr_attempted": is_ocr,
                        "field_results": field_results, "field_count": len(expected),
                        "correct_fields": sum(item["correct"] for item in field_results.values()),
                        "timing": timing_summary(run_times)})
    transcript_by_document = {str(item.get("document_id")): item.get("reference_text")
                              for item in (annotations or {}).get("ocr_transcripts", [])}
    for row in ocr_rows:
        reference = transcript_by_document.get(row["document"])
        if isinstance(reference, str) and reference.strip():
            row["ground_truth_text"] = reference
            row["cer"] = character_error_rate(reference, row["ocr_text"])
            row["wer"] = word_error_rate(reference, row["ocr_text"])
            row["status"] = "scored"
    scored_cer = [row["cer"] for row in ocr_rows if isinstance(row.get("cer"), (float, int))]
    scored_wer = [row["wer"] for row in ocr_rows if isinstance(row.get("wer"), (float, int))]
    return {
        "dataset": "fixtures/phase4/ground_truth.json (synthetic_only=true)",
        "documents_tested": len(details), "fields_evaluated": total,
        "correct_fields": correct, "incorrect_or_missing_fields": total - correct,
        "accuracy": correct / total if total else None,
        "accuracy_percent": round(100 * correct / total, 2) if total else None,
        "ocr_field_accuracy": {"correct_fields": ocr_correct, "fields_evaluated": ocr_total,
                               "accuracy_percent": round(100 * ocr_correct / ocr_total, 2) if ocr_total else None},
        "digital_pdf_field_accuracy": {"correct_fields": digital_correct, "fields_evaluated": digital_total,
                                       "accuracy_percent": round(100 * digital_correct / digital_total, 2) if digital_total else None},
        "field_scope": list(FIELDS), "field_details": details,
        "document_processing_timing": timing_summary(durations),
        "ocr_document_count": ocr_documents,
        "ocr_timing": timing_summary(ocr_durations),
        "ocr_cer": mean(scored_cer) if scored_cer else PENDING,
        "ocr_wer": mean(scored_wer) if scored_wer else PENDING,
        "ocr_documents_scored_for_text": len(scored_cer),
        "ocr_metric_normalization": "Unicode NFC; whitespace collapsed; CER is case-sensitive; WER tokenization is case-insensitive.",
        "ocr_note": "CER/WER are scored only when annotations.json contains a manually verified reference_text for that document.",
        "ocr_documents": ocr_rows,
    }


def scenario_inventory() -> dict[str, Any]:
    index_path = ROOT / "fixtures" / "claim_scenarios" / "case_index.json"
    entries = json.loads(index_path.read_text(encoding="utf-8"))
    categories: dict[str, int] = {}
    cases = []
    for entry in entries:
        manifest = json.loads((ROOT / "fixtures" / "claim_scenarios" / entry["path"] / "case.json").read_text(encoding="utf-8"))
        categories[entry["category"]] = categories.get(entry["category"], 0) + 1
        cases.append({"case_id": manifest["case_id"], "expected_decision": manifest["expected_status"],
                      "expected_bill_total": manifest.get("expected_bill_total"),
                      "reviewer_context_required": manifest.get("reviewer_context_required", {}),
                      "case_manifest": str(Path("fixtures/claim_scenarios") / entry["path"] / "case.json")})
    return {"synthetic_only": True, "source": "fixtures/claim_scenarios/case_index.json",
            "scenario_count": len(cases), "category_counts": categories, "cases": cases}


def evaluate_rule_statuses() -> dict[str, Any]:
    """Compare deterministic rule output to scenario outcome labels.

    Cases that explicitly require trusted reviewer context are listed but not
    scored because the repository does not contain those verified inputs.
    """
    from policy_terms import extract_policy_terms
    from rules import evaluate_claim

    index = json.loads((ROOT / "fixtures" / "claim_scenarios" / "case_index.json").read_text(encoding="utf-8"))
    rows = []
    scored = correct = 0
    for entry in index:
        case_dir = ROOT / "fixtures" / "claim_scenarios" / entry["path"]
        manifest = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
        bill_paths = sorted(case_dir.glob("medical_bill*.pdf"))
        policy_path = case_dir / "policy.pdf"
        if not bill_paths or not policy_path.exists():
            rows.append({"case_id": manifest["case_id"], "status": "not_run", "reason": "Required fixture PDF missing"})
            continue
        bill_docs = []
        for path in bill_paths:
            evidence, raw, _ = extract_document(path, path.name, path.name)
            bill_docs.append({"document_id": path.name, "source_name": path.name,
                              "document_type": "medical_bill", "text": "\n".join(item.text for item in evidence),
                              "evidence": [item.to_dict() for item in evidence], "raw_by_page": raw})
        policy_evidence, _, _ = extract_document(policy_path, policy_path.name, policy_path.name)
        policy = extract_policy_terms(policy_evidence)
        normalized = run_extraction(bill_docs)
        policy["terms"].source = policy["terms_json"]
        multiple_unconfirmed = len(bill_docs) > 1
        context = {"multiple_bills": multiple_unconfirmed, "aggregation_confirmed": False}
        required_missing_terms = [name for name in ("annual_limit", "deductible", "copay_percent")
                                  if name not in policy["terms_json"]]
        required_missing_terms.extend(f"invalid_{name}" for name in policy["validation_errors"])
        actual = evaluate_claim(
            field_value(normalized, "total_amount"), terms=policy["terms"],
            review_fields=normalized.get("review_fields"), missing_fields=normalized.get("missing_fields"),
            policy_terms_missing=required_missing_terms, claim_context=context,
            line_items=normalized.get("line_items"),
        )
        expected = manifest["expected_status"]
        missing_context = manifest.get("reviewer_context_required") or {}
        # This harness does not yet mirror all app-level safety gates (saved
        # policy-number matching, selected-upload behavior, trusted context).
        eligible = False
        is_correct = actual.get("status") == expected
        if eligible:
            scored += 1
            correct += int(is_correct)
        rows.append({"case_id": manifest["case_id"], "expected_decision": expected,
                     "rule_engine_status": actual.get("status"), "correct": is_correct if eligible else None,
                     "scored": eligible, "reviewer_context_required": missing_context,
                     "rule_warnings": actual.get("warnings", [])})
    return {"status_accuracy": correct / scored if scored else None,
            "status_accuracy_percent": round(100 * correct / scored, 2) if scored else None,
            "scored_cases": scored, "correct_cases": correct,
            "excluded_context_required_cases": len(rows) - scored, "case_results": rows,
            "note": "Rule-engine status only; not Decision Agent accuracy. All scenario statuses remain unscored until the harness mirrors app-level policy matching, upload selection, and trusted reviewer context."}


def ollama_inventory() -> dict[str, Any]:
    try:
        import requests
        response = requests.get(f"{os.getenv('OLLAMA_HOST', 'http://localhost:11434').rstrip('/')}/api/tags", timeout=3)
        response.raise_for_status()
        models = [item.get("name") for item in response.json().get("models", [])]
        return {"available": True, "models": models}
    except Exception as exc:
        return {"available": False, "models": [], "error": str(exc)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=3, help="Repeated extraction runs per document (default: 3)")
    parser.add_argument("--output", type=Path, default=ROOT / "evaluation" / "results.json")
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be at least 1")

    annotation_path = ROOT / "evaluation" / "annotations.json"
    annotations = json.loads(annotation_path.read_text(encoding="utf-8")) if annotation_path.exists() else {}
    extraction = evaluate_extraction(args.repeats, annotations)
    cases = scenario_inventory()
    rule_evaluation = evaluate_rule_statuses()
    ollama = ollama_inventory()
    result = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "evaluation_type": "synthetic prototype evaluation; not real-world performance",
        "environment": {"python": platform.python_version(), "platform": platform.platform(),
                        "configured_ollama_model": os.getenv("OLLAMA_MODEL", "ibm/granite4.1:8b"),
                        "ollama": ollama, "tesseract_cmd": os.getenv("TESSERACT_CMD")},
        "dataset": cases,
        "annotations_file": str(annotation_path.relative_to(ROOT)) if annotation_path.exists() else None,
        "extraction": extraction,
        "retrieval": {"precision_at_1": PENDING, "precision_at_3": PENDING,
                      "precision_at_5": PENDING, "recall_at_3": PENDING,
                      "recall_at_5": PENDING,
                      "reason": "No case has manually annotated relevant policy clause/chunk IDs; retrieval scores would be unsupported."},
        "decision": {"test_cases": cases["scenario_count"], "expected_decisions_available": True,
                     "rule_engine": {**rule_evaluation, "status_accuracy": PENDING,
                                     "status_accuracy_percent": None,
                                     "scored_cases": 0, "correct_cases": None,
                                     "reason": "A direct rule-call prototype did not mirror the application's policy-number, upload-selection, and reviewer-context gates; case accuracy is therefore not reported."},
                     "decision_agent_accuracy": PENDING,
                     "confusion_matrix": PENDING,
                     "reason": "Scenario manifests label expected status, but they lack complete annotated rule inputs, expected rule traces, and per-run decision outputs."},
        "evidence_support": PENDING,
        "appeal_quality": {"score": PENDING, "rubric": {"0": "Incorrect", "1": "Partially correct", "2": "Correct"},
                           "reason": "Requires case-level factual/policy answer keys and expert review; no expert annotations are present."},
        "latency": {"document_processing": extraction["document_processing_timing"],
                    "ocr": extraction["ocr_timing"], "retrieval": PENDING, "rule_engine": PENDING,
                    "decision_agent": PENDING, "report_generation": PENDING,
                    "end_to_end": PENDING,
                    "reason": "Only extraction/document-processing timing is measured by this runner; no isolated reproducible full workflow harness is in the repository."},
        "model_comparison": {"8b": PENDING, "3b": PENDING,
                             "reason": "Only the configured 8B model is present in Ollama; matched 8B/3B scoring requires both models and quality annotations."},
        "expert_validation": PENDING,
        "limitations": ["synthetic dataset", "limited claim scenarios", "OCR sensitivity to document quality",
                        "policy wording varies across insurers", "CPU-only target configuration",
                        "no large-scale expert validation", "3B model unavailable for matched comparison",
                        "sentence-transformers unavailable; BGE retrieval evaluation not run"],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "documents": extraction["documents_tested"],
                      "fields": extraction["fields_evaluated"], "correct": extraction["correct_fields"],
                      "accuracy_percent": extraction["accuracy_percent"], "ocr_documents": extraction["ocr_document_count"],
                      "scenarios": cases["scenario_count"], "ollama": ollama}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
