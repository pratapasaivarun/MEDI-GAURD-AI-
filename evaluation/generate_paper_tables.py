#!/usr/bin/env python3
"""Generate paper-ready result tables from recorded metrics and annotations."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EVAL = ROOT / "evaluation"
PENDING = "Not Evaluated — Ground Truth/Data Required"


def read(name: str) -> dict[str, Any]:
    path = EVAL / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def show(value: Any, suffix="") -> str:
    if value in (None, PENDING):
        return PENDING
    if isinstance(value, int) and not isinstance(value, bool):
        return f"{value}{suffix}"
    if isinstance(value, (float, int)):
        return f"{value:.2f}{suffix}"
    return str(value)


def show_seconds(value: Any) -> str:
    if value is None:
        return PENDING
    return f"{value:.3f} s"


def model_named(models: dict[str, Any], needle: str):
    return next((name for name in models if needle in name.lower()), None)


def make_table() -> str:
    extraction = read("results.json").get("extraction", {})
    system = read("system_results.json")
    rule_system = read("system_rules_only.json")
    annotations = read("annotation_scores.json")
    models = system.get("models", {})
    retrieval = annotations.get("retrieval", system.get("retrieval_annotation_scores", {}))
    extraction_timing = extraction.get("document_processing_timing", {})
    ocr_timing = extraction.get("ocr_timing", {})
    rule_latency = rule_system.get("models", {}).get("rules-only", {}).get("scores", {}).get("latency", {})
    env = rule_system.get("environment", {})
    embedding = env.get("embedding_backend", {})
    ollama_models = [item.get("name") for item in env.get("ollama_inventory", {}).get("models", [])]
    extraction_run_time = read("results.json").get("timestamp_utc", "not recorded")
    rule_run_time = rule_system.get("timestamp_utc", "not recorded")

    def get_model_score(model_name: str | None, group: str, key: str):
        if not model_name:
            return None
        score = models.get(model_name, {}).get("scores", {}).get(group, {})
        if group == "latency":
            return score.get(key, {}).get("mean_seconds")
        return score.get(key)

    rule_scores = (rule_system.get("models", {}).get("rules-only", {}).get("scores", {})
                   if rule_system else {})
    rule_engine_score = rule_scores.get("rule_engine", {})
    rules_only_rows = rule_system.get("models", {}).get("rules-only", {}).get("cases", [])
    rule_cases_scored = rule_engine_score.get("cases_scored", 0)
    rule_correct = rule_engine_score.get("correct", 0)
    rule_excluded = max(0, len(rules_only_rows) - rule_cases_scored)

    model8 = model_named(models, "8b")
    model3 = model_named(models, "3b")
    evidence_by_model = {}
    appeal_by_model = {}
    for model_name in (model8, model3):
        if model_name:
            evidence_reviews = [row for row in read("annotations.json").get("evidence_reviews", [])
                                if row.get("model_name") == model_name]
            appeal_reviews = [row for row in read("annotations.json").get("appeal_reviews", [])
                              if row.get("model_name") == model_name]
            from sys import path as sys_path
            sys_path.insert(0, str(EVAL))
            from metric_calculators import appeal_rubric_score, boolean_support_score
            evidence_by_model[model_name] = boolean_support_score(evidence_reviews, "evidence_supports_decision")["percentage"]
            appeal_by_model[model_name] = appeal_rubric_score(appeal_reviews)["mean_overall"]

    lines = [
        "# Paper-ready quantitative results",
        "",
        "These results use fictional synthetic fixtures. They do not establish real-world, clinical, or insurer performance.",
        "",
        "## Evaluation scope and method",
        "",
        f"Two isolated evaluations were completed on Windows 11 with Python 3.13.1. Extraction run: {extraction_run_time}; six synthetic bill fixtures repeated three times (18 document-processing observations). Rules run: {rule_run_time}; app document processing and deterministic rules over 24 synthetic claim scenarios. The latter used isolated temporary SQLite, storage, and Chroma locations and supplied each case's trusted reviewer context. The case labels are synthetic expected statuses, not independently reviewed insurance outcomes.",
        "",
        "The extraction score covers four labeled fields per bill: patient name, hospital name, policy number, and total amount. It does not cover bill number, dates, procedure codes, quantities, line-item charges, or all requested structured fields. OCR field accuracy is the same field-match score restricted to the four OCR-path documents; it is not CER/WER.",
        "",
        "## Table A — Extraction evaluation",
        "",
        "| Metric | Result |",
        "| --- | ---: |",
        f"| Documents tested | {show(extraction.get('documents_tested'))} |",
        f"| Fields evaluated | {show(extraction.get('fields_evaluated'))} |",
        f"| Correct fields | {show(extraction.get('correct_fields'))} |",
        f"| Incorrect or missing fields | {show(extraction.get('incorrect_or_missing_fields'))} |",
        f"| Extraction accuracy | {show(extraction.get('accuracy_percent'), '%')} |",
        f"| OCR field accuracy | {show((extraction.get('ocr_field_accuracy') or {}).get('accuracy_percent'), '%')} |",
        f"| OCR CER | {show(annotations.get('ocr_cer_wer', {}).get('mean_cer'))} |",
        f"| OCR WER | {show(annotations.get('ocr_cer_wer', {}).get('mean_wer'))} |",
        "",
        "Field-level extraction currently scores patient name, hospital name, policy number, and total amount. The additional bill fields requested in the paper require more labeled fixtures. The four OCR-path fixtures contain 16 scored field values; the two selectable-text PDFs contain 8.",
        "",
        "Per-document extraction results:",
        "",
        "| Fixture | Input path | Correct fields / evaluated | Accuracy |",
        "| --- | --- | ---: | ---: |",
    ]
    for item in extraction.get("field_details", []):
        methods = ", ".join(item.get("extraction_methods") or []) or "No extraction output"
        correct, total = item.get("correct_fields", 0), item.get("field_count", 0)
        lines.append(f"| {item.get('document', 'unknown')} | {methods} | {correct}/{total} | "
                     f"{show(100 * correct / total if total else None, '%')} |")
    lines += [
        "",
        "## Table B — Retrieval evaluation",
        "",
        "| Metric | Result |",
        "| --- | ---: |",
        f"| Precision@1 | {show(retrieval.get('precision_at_1'))} |",
        f"| Precision@3 | {show(retrieval.get('precision_at_3'))} |",
        f"| Precision@5 | {show(retrieval.get('precision_at_5'))} |",
        f"| Recall@3 | {show(retrieval.get('recall_at_3'))} |",
        f"| Recall@5 | {show(retrieval.get('recall_at_5'))} |",
        "",
        f"The rules-only evaluation file recorded configured embeddings `{embedding.get('configured', 'unknown')}` and active backend `{embedding.get('active', 'unknown')}`. A separate controlled smoke test subsequently indexed the synthetic policy into 3 chunks and confirmed Chroma retrieval plus Policy Agent evidence handoff with zero Policy Agent LLM calls while using `{embedding.get('configured', 'unknown')}`. This is a functionality check, not a quality score; retrieval metrics still need manually annotated relevant clause IDs for each query.",
        "",
        "## Table C — Decision evaluation",
        "",
        "| Metric | Rule engine | Decision Agent |",
        "| --- | ---: | ---: |",
        f"| Cases scored | {show(rule_engine_score.get('cases_scored'))} | {show(get_model_score(model8, 'decision_agent', 'cases_scored'))} |",
        f"| Correct outcomes | {show(rule_engine_score.get('correct'))} | {show(get_model_score(model8, 'decision_agent', 'correct'))} |",
        f"| Accuracy | {show(rule_engine_score.get('accuracy_percent'), '%')} | {show(get_model_score(model8, 'decision_agent', 'accuracy_percent'), '%')} |",
        "",
        "Rule-engine confusion matrix (expected rows × predicted columns):",
        "",
        "| Expected \\ Predicted | Approved | Partially approved | Rejected | Manual review |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    confusion = rule_engine_score.get("confusion_matrix_expected_rows_actual_columns", {})
    for label in ("approved", "partially_approved", "rejected", "manual_review"):
        row = confusion.get(label, {})
        lines.append(f"| {label.replace('_', ' ').title()} | {show(row.get('approved', 0))} | "
                     f"{show(row.get('partially_approved', 0))} | {show(row.get('rejected', 0))} | "
                     f"{show(row.get('manual_review', 0))} |")
    lines += [
        "",
        f"Core rule-engine status agreement is {rule_correct}/{rule_cases_scored} on cases that reached the core rules.evaluate_claim calculation. {rule_excluded} scenarios returned a fail-closed status from policy/bill precondition checks before that calculation; their actual outcomes remain in the case audit but are excluded from core-engine accuracy. The score uses synthetic fixture labels and does not establish expert validation, full financial-rule correctness, Decision Agent accuracy, or real-world accuracy.",
        "",
        "## Table D — Model comparison",
        "",
        "| Metric | 8B model | 3B model |",
        "| --- | ---: | ---: |",
        f"| Decision accuracy | {show(get_model_score(model8, 'decision_agent', 'accuracy_percent'), '%')} | {show(get_model_score(model3, 'decision_agent', 'accuracy_percent'), '%')} |",
        f"| Evidence support (human review) | {show(evidence_by_model.get(model8))} | {show(evidence_by_model.get(model3))} |",
        f"| Appeal quality (mean 0–2) | {show(appeal_by_model.get(model8))} | {show(appeal_by_model.get(model3))} |",
        f"| Mean end-to-end latency | {show(get_model_score(model8, 'latency', 'end_to_end'), ' s')} | {show(get_model_score(model3, 'latency', 'end_to_end'), ' s')} |",
        "",
        f"The local Ollama inventory contained: {', '.join(ollama_models) if ollama_models else 'no model reported'}. The full 8B model batch did not complete, and no 3B model was installed; thus no model accuracy/quality comparison is reported.",
        "",
        "## Evidence and latency",
        "",
        "| Stage | Runs | Mean (s) | Median (s) | Min (s) | Max (s) |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
        f"| Bill document processing (extraction run) | {show(extraction.get('documents_tested', 0) * 3)} | {show_seconds(extraction_timing.get('mean_seconds'))} | {show_seconds(extraction_timing.get('median_seconds'))} | {show_seconds(extraction_timing.get('min_seconds'))} | {show_seconds(extraction_timing.get('max_seconds'))} |",
        f"| OCR-path document processing | {show(extraction.get('ocr_document_count', 0) * 3)} | {show_seconds(ocr_timing.get('mean_seconds'))} | {show_seconds(ocr_timing.get('median_seconds'))} | {show_seconds(ocr_timing.get('min_seconds'))} | {show_seconds(ocr_timing.get('max_seconds'))} |",
        f"| App document processing (rules-only run) | {show(rule_latency.get('document_processing', {}).get('runs'))} | {show_seconds(rule_latency.get('document_processing', {}).get('mean_seconds'))} | {show_seconds(rule_latency.get('document_processing', {}).get('median_seconds'))} | {show_seconds(rule_latency.get('document_processing', {}).get('min_seconds'))} | {show_seconds(rule_latency.get('document_processing', {}).get('max_seconds'))} |",
        f"| Rule engine | {show(rule_latency.get('rule_engine', {}).get('runs'))} | {show_seconds(rule_latency.get('rule_engine', {}).get('mean_seconds'))} | {show_seconds(rule_latency.get('rule_engine', {}).get('median_seconds'))} | {show_seconds(rule_latency.get('rule_engine', {}).get('min_seconds'))} | {show_seconds(rule_latency.get('rule_engine', {}).get('max_seconds'))} |",
        f"| Report/appeal PDF generation (rules-only run) | {show(rule_latency.get('report_generation', {}).get('runs'))} | {show_seconds(rule_latency.get('report_generation', {}).get('mean_seconds'))} | {show_seconds(rule_latency.get('report_generation', {}).get('median_seconds'))} | {show_seconds(rule_latency.get('report_generation', {}).get('min_seconds'))} | {show_seconds(rule_latency.get('report_generation', {}).get('max_seconds'))} |",
        f"| Full app end-to-end | {show(rule_latency.get('end_to_end', {}).get('runs'))} | {show_seconds(rule_latency.get('end_to_end', {}).get('mean_seconds'))} | {show_seconds(rule_latency.get('end_to_end', {}).get('median_seconds'))} | {show_seconds(rule_latency.get('end_to_end', {}).get('min_seconds'))} | {show_seconds(rule_latency.get('end_to_end', {}).get('max_seconds'))} |",
        "",
        f"Evidence-support percentage: {show(annotations.get('evidence_correctness', {}).get('decision_support', {}).get('percentage'), '%')}",
        "",
        "The rules-only measurements omit policy retrieval and Decision Agent inference. The extraction-run and app-run stages are separate experiments and must not be added to estimate total latency. Full end-to-end latency is not available. The full workflow clock, when captured by the model runner, starts after file bytes are staged and ends after decision plus appeal/report PDF generation; warm-up is recorded separately.",
        "",
        "## Expert validation",
        "",
        show((annotations.get('expert_validation') or {}).get('status')),
        "",
        "## Limitations",
        "",
        "Synthetic cases only and limited sample sizes; expected statuses are fixture labels rather than independent domain judgments; OCR quality varies with image quality; insurer and policy wording vary; CPU-only local execution; no expert or human evidence/appeal reviews; OCR CER/WER and retrieval relevance labels are absent; the configured BGE backend was active for the rules-only run, but retrieval relevance was not evaluated; the full 8B workflow did not complete; 3B is unavailable; and no real-world or production evaluation was conducted. No performance or quality claim should be generalized beyond these fixtures.",
        "",
        "## Recommended Results wording for the paper",
        "",
        f"An exploratory evaluation of a synthetic prototype measured {show(extraction.get('documents_tested'))} bill documents and {show(extraction.get('fields_evaluated'))} annotated field values across patient name, hospital name, policy number, and total amount. The extractor matched {show(extraction.get('correct_fields'))}/{show(extraction.get('fields_evaluated'))} fields ({show(extraction.get('accuracy_percent'), '%')}). On four OCR-path fixtures, field accuracy was {show((extraction.get('ocr_field_accuracy') or {}).get('correct_fields'))}/{show((extraction.get('ocr_field_accuracy') or {}).get('fields_evaluated'))} ({show((extraction.get('ocr_field_accuracy') or {}).get('accuracy_percent'), '%')}); this is field accuracy, not character or word error rate. In a separate rules-only run across 24 scenarios, {rule_excluded} fail-closed precondition cases were excluded because the core rules.evaluate_claim calculation did not run; on the remaining cases, deterministic rule statuses agreed with the expected synthetic labels in {rule_correct}/{rule_cases_scored} cases ({show(rule_engine_score.get('accuracy_percent'), '%')}). These measurements are limited to synthetic fixtures and do not establish real-world performance. OCR CER/WER, policy retrieval relevance, final Decision Agent accuracy, human evidence/appeal ratings, end-to-end latency, matched 8B/3B performance, and expert validation were not evaluated.",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    target = EVAL / "PAPER_RESULTS.md"
    target.write_text(make_table(), encoding="utf-8")
    print(f"Wrote {target}")
