#!/usr/bin/env python3
"""Run the existing MediGuard app workflow against synthetic claim scenarios.

This isolates SQLite, uploaded documents, Chroma, and agent metrics under a
temporary directory. It uses the app's own processing, rule, agent-node, and
report functions; no production workspace data is modified.

Examples:
    .venv/Scripts/python.exe evaluation/run_system_evaluation.py --rules-only
    .venv/Scripts/python.exe evaluation/run_system_evaluation.py
    .venv/Scripts/python.exe evaluation/run_system_evaluation.py --models ibm/granite4.1:8b,org/model:3b
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, is_dataclass
import csv
import json
import os
import platform
import sqlite3
import sys
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
PENDING = "Not Evaluated — Ground Truth/Data Required"
DEFAULT_TESSERACT = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
if "TESSERACT_CMD" not in os.environ and DEFAULT_TESSERACT.exists():
    os.environ["TESSERACT_CMD"] = str(DEFAULT_TESSERACT)

from metric_calculators import decision_scores, latency_summary, retrieval_scores  # noqa: E402


class MemoryUpload:
    def __init__(self, path: Path):
        self.name = path.name
        self._content = path.read_bytes()

    def getvalue(self) -> bytes:
        return self._content


def ollama_models() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    import requests
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    try:
        response = requests.get(f"{host}/api/tags", timeout=3)
        response.raise_for_status()
        models = response.json().get("models", [])
        return models, {"available": True, "models": models}
    except Exception as exc:
        return [], {"available": False, "models": [], "error": str(exc)}


def select_models(installed: list[dict[str, Any]], requested: str | None) -> list[str]:
    if requested:
        return [model.strip() for model in requested.split(",") if model.strip()]
    selected = []
    for item in installed:
        name = str(item.get("name") or "")
        size = str((item.get("details") or {}).get("parameter_size") or "").lower()
        if "8b" in name.lower() or size.startswith("8") or "3b" in name.lower() or size.startswith("3"):
            selected.append(name)
    return selected


def load_case_entries() -> list[dict[str, Any]]:
    return json.loads((ROOT / "fixtures" / "claim_scenarios" / "case_index.json").read_text(encoding="utf-8"))


def read_case(entry: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    directory = ROOT / "fixtures" / "claim_scenarios" / entry["path"]
    return directory, json.loads((directory / "case.json").read_text(encoding="utf-8"))


def set_trusted_context(app, claim_id: str, admin, context: dict[str, Any]) -> None:
    if not context:
        return
    supported = {key: value for key, value in context.items()
                 if key in {"network_status", "preauthorization_status", "preauthorization_reference",
                            "waiting_period_status", "source", "trusted", "aggregation_confirmed"}}
    app.save_adjudication_context(claim_id, admin, supported)
    # Preserve synthetic rule inputs that the current reviewer form does not
    # expose (for example, a confirmed exclusion match) in this isolated test DB.
    with app.db() as connection:
        row = connection.execute("SELECT adjudication_context_json FROM claims WHERE claim_id=?", (claim_id,)).fetchone()
        saved = json.loads(row["adjudication_context_json"] or "{}") if row else {}
        saved.update(context)
        connection.execute("UPDATE claims SET adjudication_context_json=? WHERE claim_id=?",
                           (json.dumps(saved), claim_id))


def score_model_cases(rows: list[dict[str, Any]]) -> dict[str, Any]:
    # Count status accuracy only where the core numeric rule engine ran.
    # Fail-closed precondition outcomes remain in the case audit but are not
    # presented as evaluations of rules.evaluate_claim.
    rule_rows = [{"expected": row.get("expected_rule_status"), "actual": row.get("rule_engine_status")}
                 for row in rows if row.get("core_rule_engine_executed") is True]
    decision_rows = [{"expected": row.get("expected_decision"), "actual": row.get("final_decision")} for row in rows]
    scored_citations = [row for row in rows if row.get("policy_citations")]
    return {
        "rule_engine": decision_scores(rule_rows, "expected", "actual"),
        "decision_agent": decision_scores(decision_rows, "expected", "actual"),
        "citation_integrity": {
            "cases_with_citations": len(scored_citations),
            "all_citations_resolve_to_retrieved_evidence": sum(bool(row.get("citation_integrity")) for row in scored_citations),
            "percentage": (100 * sum(bool(row.get("citation_integrity")) for row in scored_citations) / len(scored_citations)
                           if scored_citations else PENDING),
            "note": "Mechanical citation-ID integrity only; it does not determine whether cited text supports the explanation.",
        },
        "evidence_correctness": PENDING,
        "appeal_quality": PENDING,
        "latency": {
            stage: latency_summary([float(row["timings_seconds"][stage]) for row in rows
                                   if row.get("timings_seconds", {}).get(stage) is not None])
            for stage in ("document_processing", "rule_engine", "policy_retrieval",
                          "decision_agent", "report_generation", "end_to_end")
        },
    }


def json_default(value: Any):
    from decimal import Decimal
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Path):
        return str(value)
    return str(value)


def build_timed_workflow(agents):
    """Build the same two-node graph while capturing each node's wall time."""
    stage_times: dict[str, float] = {}
    graph = agents.StateGraph(agents.ClaimWorkflowState)

    def timed_policy(state):
        started = time.perf_counter()
        result = agents.policy_agent_node(state)
        stage_times["policy_retrieval"] = time.perf_counter() - started
        return result

    def timed_decision(state):
        started = time.perf_counter()
        result = agents.decision_agent_node(state)
        stage_times["decision_agent"] = time.perf_counter() - started
        return result

    graph.add_node("policy_agent", timed_policy)
    graph.add_node("decision_agent", timed_decision)
    graph.add_edge(agents.START, "policy_agent")
    graph.add_edge("policy_agent", "decision_agent")
    graph.add_edge("decision_agent", agents.END)
    return graph.compile(), stage_times


def run() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", help="Comma-separated local Ollama model tags; defaults to installed 8B/3B models")
    parser.add_argument("--rules-only", action="store_true", help="Run app document processing and deterministic rules without LLM/report stages")
    parser.add_argument("--limit", type=int, help="Run the first N synthetic cases; omit for all 24")
    parser.add_argument("--annotations", type=Path, default=ROOT / "evaluation" / "annotations.json")
    parser.add_argument("--output", type=Path, default=ROOT / "evaluation" / "system_results.json")
    args = parser.parse_args()

    installed, inventory = ollama_models()
    selected_models = [] if args.rules_only else select_models(installed, args.models)
    installed_names = [str(item.get("name") or "") for item in installed]
    missing_requested = [model for model in selected_models if model not in installed_names]
    models = [model for model in selected_models if model in installed_names]
    entries = load_case_entries()
    if args.limit is not None:
        entries = entries[:max(0, args.limit)]
    annotations = {}
    if args.annotations.exists():
        annotations = json.loads(args.annotations.read_text(encoding="utf-8"))

    all_model_results = {}
    temp_root = tempfile.TemporaryDirectory(prefix="mediguard-evaluation-")
    isolated = Path(temp_root.name)
    os.environ["MEDIGUARD_DB_PATH"] = str(isolated / "claims.sqlite3")
    os.environ["MEDIGUARD_STORAGE_DIR"] = str(isolated / "private-storage")
    os.environ["CHROMA_DIR"] = str(isolated / "chroma")
    os.environ["AGENT_METRICS_PATH"] = str(isolated / "agent_metrics.jsonl")

    import app  # noqa: E402
    import agents  # noqa: E402
    import policy_index  # noqa: E402
    from reports import build_appeal_letter, build_appeal_letter_pdf, build_decision_report  # noqa: E402

    @contextmanager
    def closing_db():
        connection = sqlite3.connect(app.get_db_path())
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    # app.db uses SQLite's transaction context, which commits but does not
    # close connections. The isolated runner closes each test connection so
    # its temporary database can be safely removed on Windows.
    app.db = closing_db
    app.init_db()
    claimant = app.get_or_create_user("synthetic-evaluation-claimant@mediguard.local", "Synthetic Evaluation Claimant")
    admin = app.get_or_create_user("synthetic-evaluation-admin@mediguard.local", "Synthetic Evaluation Admin")
    with app.db() as connection:
        connection.execute("UPDATE users SET role='admin' WHERE user_id=?", (admin["user_id"],))
    admin = app.get_user(admin["user_id"])

    missing_3b = not any("3b" in str(item.get("name", "")).lower()
                         or str((item.get("details") or {}).get("parameter_size", "")).lower().startswith("3")
                         for item in installed)
    retrieval_queries = annotations.get("retrieval_queries", [])
    benchmark_policies: dict[str, dict[str, Any]] = {}
    retrieval_runs: dict[str, list[str]] = {}
    per_case_by_model: dict[str, list[dict[str, Any]]] = {}

    for model in models or ([None] if args.rules_only else []):
        if model:
            agents.OLLAMA_MODEL = model
            os.environ["OLLAMA_MODEL"] = model
        graph, graph_timings = build_timed_workflow(agents) if model else (None, {})
        model_rows = []
        warmup_seconds = None
        for entry in entries:
            case_dir, manifest = read_case(entry)
            registration = manifest["claim_registration"]
            claim_id = app.create_claim(
                claimant["user_id"], registration["claim_number"], registration["patient_name"],
                registration["hospital"], registration["policy_number"], registration["service_date"],
            )
            for filename in manifest.get("upload_files", []):
                file_path = case_dir / filename
                if not file_path.exists():
                    continue
                kind = "policy" if "policy" in filename.lower() else "medical_bill"
                app.save_document(claim_id, claimant, MemoryUpload(file_path), kind)

            started_e2e = time.perf_counter()
            started = time.perf_counter()
            normalized = app.process_claim_documents(claim_id, claimant["user_id"])
            document_seconds = time.perf_counter() - started
            set_trusted_context(app, claim_id, admin, manifest.get("reviewer_context_required") or {})

            started = time.perf_counter()
            rules = app.evaluate_saved_claim(claim_id, claimant["user_id"], normalized)
            rules_seconds = time.perf_counter() - started

            workflow = {"policy_evidence": [], "decision": {"status": rules.get("status"), "reasons": [], "policy_citations": []},
                        "policy_findings": {"findings": []}, "llm_calls": 0}
            if model:
                active_policy = app.active_policy_for_claim(claim_id, normalized)
                if active_policy:
                    policy_text = active_policy["content_text"]
                    policy_id = active_policy["version_id"]
                else:
                    policy_text = app.saved_policy_text(claim_id)
                    policy_id = str(((normalized.get("policy_number") or {}).get("value")) or claim_id)
                if warmup_seconds is None:
                    warm_started = time.perf_counter()
                    try:
                        agents.warm_ollama()
                        warmup_seconds = time.perf_counter() - warm_started
                    except Exception as exc:
                        warmup_seconds = time.perf_counter() - warm_started
                        warmup_error = str(exc)
                    else:
                        warmup_error = None
                else:
                    warmup_error = None
                workflow = graph.invoke({
                    "claim": registration, "normalized_claim": normalized,
                    "policy_text": policy_text, "policy_id": policy_id,
                    "rule_results": rules, "errors": [], "llm_calls": 0,
                })
                workflow["stage_timings_seconds"] = dict(graph_timings)
            else:
                warmup_error = None

            decision = workflow.get("decision") or {}
            claim_record = {**registration, "claim_number": registration.get("claim_number"),
                            "patient_name": registration.get("patient_name")}
            started = time.perf_counter()
            appeal_text = build_appeal_letter(claim_record, rules, workflow)
            appeal_pdf = build_appeal_letter_pdf(claim_record, rules, workflow)
            report_pdf = build_decision_report(claim_record, normalized, rules, workflow)
            report_seconds = time.perf_counter() - started
            e2e_seconds = time.perf_counter() - started_e2e

            final_decision = decision.get("status") if model else None
            expected = manifest.get("expected_status")
            retrieved = workflow.get("policy_evidence") or []
            evidence_ids = {str(item.get("clause_id")) for item in retrieved}
            citations = decision.get("policy_citations") or []
            citation_integrity = all(str(item) in evidence_ids for item in citations)
            stage_times = {
                "document_processing": document_seconds,
                "rule_engine": rules_seconds,
                "policy_retrieval": workflow.get("stage_timings_seconds", {}).get("policy_retrieval"),
                "decision_agent": workflow.get("stage_timings_seconds", {}).get("decision_agent"),
                "report_generation": report_seconds,
                "end_to_end": e2e_seconds,
            }
            row = {
                "case_id": manifest["case_id"], "model_name": model or "rules-only",
                "expected_rule_status": expected, "rule_engine_status": rules.get("status"),
                "rule_engine_correct": rules.get("status") == expected,
                "core_rule_engine_executed": rules.get("rule_version") == "mvp-1.0",
                "rule_version": rules.get("rule_version"),
                "expected_decision": expected, "final_decision": final_decision,
                "decision_correct": final_decision == expected if final_decision else None,
                "decision_fallback": bool(decision.get("_fallback")),
                "llm_calls": workflow.get("llm_calls", 0), "reasons": decision.get("reasons", []),
                "policy_citations": citations, "citation_integrity": citation_integrity,
                "retrieved_evidence": retrieved, "rule_result": rules,
                "normalized_claim": normalized,
                "appeal_letter_text": appeal_text,
                "appeal_pdf_bytes": len(appeal_pdf), "decision_report_pdf_bytes": len(report_pdf),
                "timings_seconds": stage_times if model else {**stage_times, "policy_retrieval": None,
                    "decision_agent": None, "end_to_end": None},
                "warmup_seconds_once_per_model": warmup_seconds,
                "warmup_error": warmup_error,
                "evidence_support_human_review": PENDING,
                "appeal_quality_human_review": PENDING,
            }
            model_rows.append(row)

            # Build a stable case-scoped corpus for future clause annotations.
            policy_file = case_dir / "policy.pdf"
            if policy_file.exists() and manifest["case_id"] not in benchmark_policies:
                from extraction import extract_document
                evidence, raw, _ = extract_document(policy_file, policy_file.name, policy_file.name)
                payload = {"document_id": policy_file.name, "source_name": policy_file.name,
                           "text": "\n".join(raw.values()), "evidence": [item.to_dict() for item in evidence]}
                benchmark_policies[manifest["case_id"]] = payload
                try:
                    policy_index.index_policy_documents([payload], manifest["case_id"])
                except Exception as exc:
                    benchmark_policies[manifest["case_id"]]["index_error"] = str(exc)

        per_case_by_model[model or "rules-only"] = model_rows
        scores = score_model_cases(model_rows)
        all_model_results[model or "rules-only"] = {"case_count": len(model_rows), "scores": scores, "cases": model_rows}

    # Run only explicitly annotated queries. Blank template entries are ignored.
    for query in retrieval_queries:
        query_id = str(query.get("query_id") or "")
        case_id = str(query.get("case_id") or "")
        text = str(query.get("query") or "").strip()
        if not query_id or not case_id or not text:
            continue
        try:
            hits = policy_index.retrieve_policy_evidence(text, case_id, limit=5)
            retrieval_runs[query_id] = [str(hit["clause_id"]) for hit in hits]
        except Exception as exc:
            retrieval_runs[query_id] = []
            query["run_error"] = str(exc)
    retrieval_metric = retrieval_scores(retrieval_queries, retrieval_runs) if retrieval_queries else {
        "annotated_query_count": 0, "precision_at_1": PENDING, "precision_at_3": PENDING,
        "precision_at_5": PENDING, "recall_at_3": PENDING, "recall_at_5": PENDING,
        "reason": "Fill retrieval_queries in annotations.json with manually labeled relevant_clause_ids.",
    }

    result = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "dataset": "fixtures/claim_scenarios (synthetic-only)",
        "run_scope": "full workflow" if models else "app document processing and rule engine only",
        "environment": {"python": platform.python_version(), "ollama_inventory": inventory,
                        "requested_models_missing": missing_requested,
                        "three_billion_parameter_model_installed": not missing_3b,
                        "embedding_backend": policy_index.embedding_backend_status(),
                        "cpu_only_target": True},
        "models": all_model_results,
        "retrieval_annotation_scores": retrieval_metric,
        "retrieval_runs_by_query_id": retrieval_runs,
        "retrieval_quality": PENDING if not retrieval_runs else "Scored only on explicitly annotated queries",
        "evidence_support": PENDING,
        "appeal_quality": PENDING,
        "expert_validation": PENDING,
        "model_comparison": PENDING if missing_3b or len(models) < 2 else "Matched models evaluated; human quality review remains pending",
        "model_comparison_reason": "A 3B parameter model is not installed." if missing_3b else None,
        "method_note": "The application workflow is isolated in temporary storage. End-to-end latency starts at document processing (file bytes are already staged) and ends after decision and appeal PDFs are built. Model warm-up is recorded separately once per model.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=json_default) + "\n", encoding="utf-8")
    csv_path = args.output.with_suffix(".csv")
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["case_id", "model_name", "expected_rule_status",
            "rule_engine_status", "rule_engine_correct", "core_rule_engine_executed", "rule_version",
            "expected_decision", "final_decision",
            "decision_correct", "decision_fallback", "llm_calls", "citation_integrity",
            "document_processing_seconds", "policy_retrieval_seconds", "rule_engine_seconds",
            "decision_agent_seconds", "report_generation_seconds", "end_to_end_seconds"])
        writer.writeheader()
        for rows in per_case_by_model.values():
            for item in rows:
                writer.writerow({**{key: item.get(key) for key in ("case_id", "model_name", "expected_rule_status",
                    "rule_engine_status", "rule_engine_correct", "core_rule_engine_executed", "rule_version",
                    "expected_decision", "final_decision",
                    "decision_correct", "decision_fallback", "llm_calls", "citation_integrity")},
                    **{f"{stage}_seconds": item.get("timings_seconds", {}).get(stage)
                       for stage in ("document_processing", "policy_retrieval", "rule_engine",
                                     "decision_agent", "report_generation", "end_to_end")}})
    print(json.dumps({"output": str(args.output), "csv": str(csv_path), "case_count": len(entries),
                      "models_run": list(all_model_results), "embedding_backend": result["environment"]["embedding_backend"],
                      "rule_accuracy": {name: model["scores"]["rule_engine"]["accuracy_percent"]
                                        for name, model in all_model_results.items()},
                      "decision_accuracy": {name: model["scores"]["decision_agent"]["accuracy_percent"]
                                            for name, model in all_model_results.items()},
                      "3b_installed": not missing_3b}, indent=2, ensure_ascii=False))
    policy_index.close_policy_index()
    temp_root.cleanup()
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
