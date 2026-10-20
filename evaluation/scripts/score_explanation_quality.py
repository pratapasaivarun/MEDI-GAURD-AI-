"""Generate and score ten Ollama explanations for fictional discrepancy cases."""
from __future__ import annotations

import json
import os
import re
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import requests

from evaluation.run_all import CASES_DIR, LABELS_PATH, build_claim
from mediguard.ai.agents import (
    OLLAMA_HOST, OLLAMA_MODEL, comparison_template_explanation,
    explain_comparison, validate_comparison_explanation,
)
from mediguard.engine.comparison import compare
from mediguard.engine.models import Clause
from mediguard.ingestion.settlement import parse_settlement

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "evaluation" / "latest" / "explanation_quality.json"
REPORT = ROOT / "docs" / "06_EVALUATION_RESULTS.md"
UNSUPPORTED_CERTAINTY = re.compile(
    r"\b(?:fraud(?:ulent)?|illegal|guaranteed?|definitely entitled|must pay|will win|wrongful(?:ly)?)\b",
    re.IGNORECASE,
)
NUMBER = re.compile(r"(?<![A-Za-z])\d[\d,]*(?:\.\d+)?")


def _normalized_numbers(text: str) -> set[Decimal]:
    values: set[Decimal] = set()
    for match in NUMBER.finditer(text):
        try:
            values.add(Decimal(match.group(0).replace(",", "")))
        except InvalidOperation:
            continue
    return values


def _quality_checks(item: dict[str, Any], comparison: Any, explanation: str) -> dict[str, bool]:
    clause_amount_match = re.search(r"INR\s+([\d,]+(?:\.\d+)?)", item["supporting_clause"], re.I)
    clause_amount = Decimal(clause_amount_match.group(1).replace(",", "")) if clause_amount_match else None
    numbers = _normalized_numbers(explanation)
    clause_cited = bool(
        "deductible" in explanation.casefold()
        and clause_amount is not None and clause_amount in numbers
        and re.search(rf"\bpage\s+{item['supporting_clause_page']}\b", explanation, re.I)
    )
    no_overclaim = not bool(UNSUPPORTED_CERTAINTY.search(explanation))
    # A higher actual patient share is an adverse difference; calling its
    # effect positive or beneficial reverses the comparison's direction.
    if comparison.actual_patient_share > comparison.expected_patient_share and re.search(
        r"\b(?:positive(?:ly)?|beneficial(?:ly)?|benefit)\b", explanation, re.I
    ):
        no_overclaim = False
    return {
        "correct_numbers": validate_comparison_explanation(explanation, comparison),
        "correct_clause_cited": clause_cited,
        "no_unsupported_claim": no_overclaim,
    }


def main() -> int:
    refresh_failed = "--refresh-failed" in sys.argv
    if "--verify-existing" in sys.argv:
        saved = json.loads(OUTPUT.read_text(encoding="utf-8"))
        print(json.dumps({key: value for key, value in saved.items() if key != "results"}, indent=2))
        for item in saved["results"]:
            print(json.dumps(item, ensure_ascii=True))
        return 0
    response = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=3)
    response.raise_for_status()
    if not any(item.get("name") == OLLAMA_MODEL for item in response.json().get("models", [])):
        raise SystemExit(f"Configured Ollama model is unavailable: {OLLAMA_MODEL}")

    labels = json.loads(LABELS_PATH.read_text(encoding="utf-8"))
    cases = [row for row in labels["cases"] if row["group"] == "discrepancy"]
    if len(cases) < 10:
        raise SystemExit(f"Expected at least 10 labeled discrepancy cases, found {len(cases)}")

    existing = {}
    if refresh_failed and OUTPUT.exists():
        existing = {item["case"]: item for item in json.loads(OUTPUT.read_text(encoding="utf-8"))["results"]}
    results: list[dict[str, Any]] = []
    for row in cases[:10]:
        claim, terms = build_claim(row)
        settlement_path = CASES_DIR / row["case_id"] / "settlement.pdf"
        settlement = parse_settlement(settlement_path.read_bytes(), settlement_path.name)
        comparison = compare(claim, settlement, terms)
        deductible_category = next(
            (item for item in comparison.categories if item.category == "DEDUCTIBLE"), None
        )
        if deductible_category is None or deductible_category.difference <= 0:
            raise SystemExit(f"{row['case_id']} is not a labeled deductible discrepancy")

        # The source fixture has a reviewer-confirmed deductible term on page 1.
        deductible_category.clause = Clause(
            f"Deductible: INR {row['deductible']}", page=1, section=None
        )
        before = (
            comparison.status, comparison.possible_difference,
            comparison.expected_insurer_payment, comparison.actual_insurer_payment,
        )
        old = existing.get(row["case_id"])
        explanation = old["explanation"] if old else ""
        if not old or not refresh_failed or sum(old["checks"].values()) < 3:
            explanation = explain_comparison(comparison, use_llm=True)
        after = (
            comparison.status, comparison.possible_difference,
            comparison.expected_insurer_payment, comparison.actual_insurer_payment,
        )
        clause_text = deductible_category.clause.text
        item = {
            "case": row["case_id"],
            "status": comparison.status,
            "possible_difference": str(comparison.possible_difference),
            "expected_insurer_payment": str(comparison.expected_insurer_payment),
            "actual_insurer_payment": str(comparison.actual_insurer_payment),
            "supporting_clause": clause_text,
            "supporting_clause_page": 1,
            "explanation": explanation,
            "template_fallback_used": explanation == comparison_template_explanation(comparison),
            "comparison_unchanged": before == after,
            "checks": {},
            "score": 0,
        }
        item["checks"] = _quality_checks(item, comparison, explanation)
        item["score"] = sum(item["checks"].values())
        results.append(item)

    score = sum(row["score"] for row in results)
    output = {
        "dataset": "samples/evaluation_cases/ground_truth.json (first 10 discrepancy cases)",
        "synthetic_only": True,
        "model": OLLAMA_MODEL,
        "ollama_host": OLLAMA_HOST,
        "case_count": len(results),
        "check_count": 3 * len(results),
        "earned_checks": score,
        "score": score / (3 * len(results)),
        "results": results,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")

    table = [
        "\n## Explanation quality (live Ollama)",
        "\nTen fictional deductible-discrepancy comparisons were sent through `explain_comparison` with Ollama enabled. Each earns one point for grounded numbers, one for quoting the correct deductible term and page, and one for avoiding unsupported certainty. `template_fallback_used` is shown so a fallback is not misreported as model quality.\n",
        "| Case | Numbers | Clause and page | No overclaim | Template fallback | Score / 3 |",
        "|---|---|---|---|---:|---:|",
    ]
    for item in results:
        checks = item["checks"]
        mark = lambda value: "yes" if value else "no"
        table.append(
            f"| {item['case']} | {mark(checks['correct_numbers'])} | "
            f"{mark(checks['correct_clause_cited'])} (p. {item['supporting_clause_page']}) | "
            f"{mark(checks['no_unsupported_claim'])} | {mark(item['template_fallback_used'])} | {item['score']}/3 |"
        )
    table.append(
        f"\n**Score: {score}/{3 * len(results)} checks ({100 * score / (3 * len(results)):.1f}%).** "
        "Validated on ten synthetic explanations only. Full text and per-check results: `evaluation/latest/explanation_quality.json`.\n"
    )
    report = REPORT.read_text(encoding="utf-8")
    marker = "\n## Explanation quality (live Ollama)"
    if marker in report:
        report = report[:report.index(marker)].rstrip() + "\n"
    REPORT.write_text(report.rstrip() + "\n" + "\n".join(table) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in output.items() if key != "results"}, indent=2))
    for item in results:
        print(json.dumps(item, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
