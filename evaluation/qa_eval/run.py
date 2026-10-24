"""Evaluate labeled claimant Q&A against isolated fictional app decisions."""
from __future__ import annotations

import csv
import importlib.util
import json
import re
import sys
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mediguard.ai import qa


QUESTION_FILE = ROOT / "evaluation" / "qa_eval" / "questions.json"
OUTPUT_DIR = QUESTION_FILE.parent
CASES = ("a_match", "b_wrongful_deduction", "c_manual_review")
DETERMINISTIC_INTENTS = {
    "why_pay", "insurer_share", "bill_and_eligible", "deductible",
    "copayment", "excluded_limited", "settlement_difference",
    "why_not_covered", "unconfirmed_term", "next_steps_appeal",
    "manual_review", "status", "patient", "hospital",
    "hypothetical", "legal_outcome", "off_topic",
}
MONEY_PATTERN = re.compile(r"INR\s+[\d,]+\.\d{2}")


def _load_app_case_runner():
    test_file = ROOT / "tests" / "integration" / "test_phase4_demo_cases.py"
    spec = importlib.util.spec_from_file_location("_qa_eval_phase4_cases", test_file)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load synthetic app fixture from {test_file}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.run_case.__wrapped__


def _claim_data(case: str, run_case) -> tuple[dict[str, Any], dict[str, Any], Any, Any, Any, Any]:
    with tempfile.TemporaryDirectory(prefix="mediguard-qa-eval-") as folder:
        monkeypatch = pytest.MonkeyPatch()
        try:
            manifest, normalized, rules, comparison, settlement = run_case(
                monkeypatch, Path(folder)
            )(case)[:5]
            return (
                manifest,
                normalized,
                rules,
                comparison,
                settlement,
                dict(rules.get("claimant_result") or {}),
            )
        finally:
            monkeypatch.undo()


def _expected_amounts(keys: list[str], facts: dict[str, Any], comparison: Any) -> list[str]:
    amounts = []
    for key in keys:
        value = comparison.possible_difference if key == "possible_difference" else facts.get(key)
        if value is not None:
            formatted = qa._money(value)
            if formatted != "unavailable":
                amounts.append(formatted)
    return sorted(set(amounts))


def _correct_refusal(kind: str | None, answer: str) -> bool | None:
    if kind == "hypothetical":
        return "can't recalculate hypothetical amounts" in answer.lower()
    if kind == "legal_outcome":
        return "can't predict an outcome" in answer.lower() and "not legal or insurance advice" in answer.lower()
    if kind == "off_topic":
        return answer == qa.OFF_TOPIC_ANSWER
    if kind == "unknown":
        return answer == qa.UNKNOWN_ANSWER
    return None


def _evaluate() -> dict[str, Any]:
    source = json.loads(QUESTION_FILE.read_text(encoding="utf-8"))
    questions = source["questions"]
    if len(questions) < 40:
        raise ValueError("The labeled Q&A set must contain at least 40 questions.")
    run_case = _load_app_case_runner()
    case_data = {case: _claim_data(case, run_case) for case in CASES}
    llm_requests = 0

    def count_chat_request(*_args, **_kwargs):
        nonlocal llm_requests
        llm_requests += 1
        raise AssertionError("The Q&A evaluation must not make an LLM request.")

    rows = []
    by_intent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in questions:
        case = item["case"]
        if case not in case_data:
            raise ValueError(f"Unknown fictional case in {item['id']}: {case}")
        manifest, normalized, rules, comparison, settlement, facts = case_data[case]
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(qa.llm_gateway, "chat_json", count_chat_request)
        predicted_intent = qa.classify_intent(item["question"])
        answer = qa.answer_question(
            item["question"],
            rules,
            [],
            manifest["case_id"],
            normalized=normalized,
            comparison=comparison,
            settlement=settlement,
        )
        monkeypatch.undo()

        expected_intent = item.get("expected_intent")
        intent_correct = predicted_intent == expected_intent
        expected_amounts = _expected_amounts(
            item.get("amount_fact_keys", []), facts, comparison
        )
        actual_amounts = sorted(set(MONEY_PATTERN.findall(answer)))
        amount_applicable = bool(expected_amounts)
        exact_amount_match = (
            actual_amounts == expected_amounts if amount_applicable else None
        )
        refusal_correct = _correct_refusal(item.get("refusal_type"), answer)
        row = {
            "id": item["id"],
            "case": case,
            "question": item["question"],
            "expected_intent": expected_intent or "unknown",
            "predicted_intent": predicted_intent or "unknown",
            "intent_correct": intent_correct,
            "expected_amounts": expected_amounts,
            "actual_amounts": actual_amounts,
            "amount_applicable": amount_applicable,
            "exact_amount_match": exact_amount_match,
            "refusal_type": item.get("refusal_type", ""),
            "correct_refusal": refusal_correct,
            "llm_request_count": llm_requests,
            "answer": answer,
        }
        rows.append(row)
        by_intent[row["expected_intent"]].append(row)

    deterministic_rows = [
        row for row in rows if row["expected_intent"] in DETERMINISTIC_INTENTS
    ]
    amount_rows = [row for row in rows if row["amount_applicable"]]
    refusal_rows = [
        row for row in rows
        if row["refusal_type"] in {"hypothetical", "legal_outcome", "off_topic"}
    ]
    per_intent = []
    for intent, intent_rows in sorted(by_intent.items()):
        numeric = [row for row in intent_rows if row["amount_applicable"]]
        refusals = [
            row for row in intent_rows if row["correct_refusal"] is not None
        ]
        per_intent.append({
            "intent": intent,
            "questions": len(intent_rows),
            "intent_correct": sum(row["intent_correct"] for row in intent_rows),
            "intent_accuracy": sum(row["intent_correct"] for row in intent_rows) / len(intent_rows),
            "numeric_questions": len(numeric),
            "exact_amount_matches": sum(bool(row["exact_amount_match"]) for row in numeric),
            "exact_amount_match_rate": (
                sum(bool(row["exact_amount_match"]) for row in numeric) / len(numeric)
                if numeric else None
            ),
            "refusal_questions": len(refusals),
            "correct_refusals": sum(bool(row["correct_refusal"]) for row in refusals),
            "correct_refusal_rate": (
                sum(bool(row["correct_refusal"]) for row in refusals) / len(refusals)
                if refusals else None
            ),
            "llm_request_count": sum(row["llm_request_count"] for row in intent_rows),
        })

    result = {
        "label": source["label"],
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "question_count": len(rows),
        "case_count": len(case_data),
        "deterministic_intent_count": len(deterministic_rows),
        "intent_accuracy": {
            "numerator": sum(row["intent_correct"] for row in rows),
            "denominator": len(rows),
        },
        "exact_amount_match_rate": {
            "numerator": sum(bool(row["exact_amount_match"]) for row in amount_rows),
            "denominator": len(amount_rows),
        },
        "correct_refusal_rate": {
            "numerator": sum(bool(row["correct_refusal"]) for row in refusal_rows),
            "denominator": len(refusal_rows),
            "refusal_types": ["hypothetical", "legal_outcome", "off_topic"],
        },
        "llm_request_count_for_deterministic_intents": sum(
            row["llm_request_count"] for row in deterministic_rows
        ),
        "unknown_refusal_rate": {
            "numerator": sum(
                bool(row["correct_refusal"])
                for row in rows if row["refusal_type"] == "unknown"
            ),
            "denominator": sum(row["refusal_type"] == "unknown" for row in rows),
        },
        "per_intent": per_intent,
        "results": rows,
    }
    return result


def main() -> int:
    result = _evaluate()
    (OUTPUT_DIR / "results.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    columns = [
        "id", "case", "question", "expected_intent", "predicted_intent",
        "intent_correct", "expected_amounts", "actual_amounts",
        "amount_applicable", "exact_amount_match", "refusal_type",
        "correct_refusal", "llm_request_count", "answer",
    ]
    with (OUTPUT_DIR / "results.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in result["results"]:
            writer.writerow({
                **row,
                "expected_amounts": " | ".join(row["expected_amounts"]),
                "actual_amounts": " | ".join(row["actual_amounts"]),
            })
    print(json.dumps({
        "question_count": result["question_count"],
        "intent_accuracy": result["intent_accuracy"],
        "exact_amount_match_rate": result["exact_amount_match_rate"],
        "correct_refusal_rate": result["correct_refusal_rate"],
        "llm_request_count_for_deterministic_intents": result["llm_request_count_for_deterministic_intents"],
        "unknown_refusal_rate": result["unknown_refusal_rate"],
        "per_intent": result["per_intent"],
        "results_json": str(OUTPUT_DIR / "results.json"),
        "results_csv": str(OUTPUT_DIR / "results.csv"),
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
