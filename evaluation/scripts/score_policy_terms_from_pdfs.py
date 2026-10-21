"""Score term extraction against independently labeled fictional policy PDFs."""
from __future__ import annotations

import json
from pathlib import Path
from decimal import Decimal

ROOT = Path(__file__).resolve().parents[2]
LABELS = ROOT / "samples/evaluation_cases/policy_pdf_term_labels.json"
CASES = ROOT / "samples/evaluation_cases/cases"
OUTPUT = ROOT / "evaluation/latest/policy_pdf_term_scores.json"


def _same(actual, expected) -> bool:
    if actual is None or expected is None:
        return actual is expected
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(_same(actual.get(key), value) for key, value in expected.items())
    if isinstance(expected, list):
        return isinstance(actual, list) and [str(v).casefold() for v in actual] == [str(v).casefold() for v in expected]
    try:
        return Decimal(str(actual)) == Decimal(str(expected))
    except Exception:
        return str(actual).strip().casefold() == str(expected).strip().casefold()


def run(*, emit: bool = True) -> dict:
    from mediguard.ingestion.extraction import extract_document
    from mediguard.policy.policy_terms import extract_policy_terms

    labels = json.loads(LABELS.read_text(encoding="utf-8"))
    term_fields = (
        "deductible", "copay_percent", "room_limit_per_day", "icu_limit_per_day",
        "exclusions", "date_window", "annual_limit",
    )
    rows_by_term = {name: [] for name in term_fields}
    for case in labels["cases"]:
        path = CASES / case["case_id"] / "policy.pdf"
        evidence, _raw_pages, _page_count = extract_document(path, path.name, path.name)
        extracted = extract_policy_terms(evidence)["terms_json"]
        actuals = {
            "deductible": (extracted.get("deductible") or {}).get("value"),
            "copay_percent": (extracted.get("copay_percent") or {}).get("value"),
            "room_limit_per_day": (extracted.get("room_limit_per_day") or {}).get("value"),
            "icu_limit_per_day": (extracted.get("icu_limit_per_day") or {}).get("value"),
            "exclusions": (extracted.get("exclusions") or {}).get("value"),
            "date_window": {
                "pre_hospitalization_days": (extracted.get("pre_hospitalization_days") or {}).get("value"),
                "post_hospitalization_days": (extracted.get("post_hospitalization_days") or {}).get("value"),
            },
            "annual_limit": (extracted.get("annual_limit") or {}).get("value"),
        }
        for field in term_fields:
            expected = case.get(field)
            actual = actuals[field]
            if field == "date_window":
                expected = expected or {"pre_hospitalization_days": None, "post_hospitalization_days": None}
                if actual == {"pre_hospitalization_days": None, "post_hospitalization_days": None}:
                    actual = expected if expected == actual else actual
            rows_by_term[field].append({"case_id": case["case_id"], "expected": expected, "actual": actual, "match": _same(actual, expected)})

    scores = {}
    failures = []
    for field, rows in rows_by_term.items():
        correct = sum(row["match"] for row in rows)
        scores[field] = {"numerator": correct, "denominator": len(rows), "score": correct / len(rows) if rows else None}
        failures.extend({"term": field, **row} for row in rows if not row["match"])
    result = {"basis": "extract_policy_terms(policy.pdf) compared with separately committed source-PDF labels; no reviewer-confirmed JSON was read", "cases": len(labels["cases"]), "scores": scores, "case_rows": rows_by_term, "failures": failures}
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if emit:
        print(json.dumps({"basis": result["basis"], "scores": scores, "failures": failures, "output": str(OUTPUT)}, indent=2, ensure_ascii=False))
    return result


if __name__ == "__main__":
    run()
