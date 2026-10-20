"""Score the committed synthetic adversarial casebook without editing labels."""
from __future__ import annotations

import json
import re
from decimal import Decimal
from pathlib import Path
from typing import Any

from mediguard.ingestion.extraction import extract_document, run_extraction
from mediguard.ingestion.settlement import parse_settlement

ROOT = Path(__file__).resolve().parents[2]
CASEBOOK = ROOT / "samples" / "adversarial_cases" / "casebook.json"
RESULTS = ROOT / "evaluation" / "latest" / "adversarial_results.json"


def _field(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict) and "value" in value:
        return value["value"]
    return value


def _norm(text: Any) -> str:
    return re.sub(r"\W+", " ", str(text or "").casefold()).strip()


def _score_one(case: dict[str, Any]) -> dict[str, Any]:
    case_dir = ROOT / "samples" / "adversarial_cases" / "cases" / case["case_id"]
    bill_path = case_dir / "bill.pdf"
    evidence, raw_by_page, page_count = extract_document(bill_path, case["case_id"], bill_path.name)
    bill_text = "\n".join(item.text for item in evidence)
    normalized = run_extraction([{
        "document_id": case["case_id"], "document_type": "medical_bill", "source_name": bill_path.name,
        "text": bill_text, "evidence": [item.to_dict() for item in evidence], "raw_by_page": raw_by_page,
    }])
    settlement_path = case_dir / "settlement.pdf"
    settlement = parse_settlement(settlement_path.read_bytes(), settlement_path.name)
    expected = case["expected"]
    actual_lines = [{"description": row["description"], "amount": float(row["amount"])} for row in normalized.get("line_items", [])]
    expected_lines = expected.get("line_items", [])
    actual_line_pairs = {(_norm(row["description"]), round(float(row["amount"]), 2)) for row in actual_lines}
    expected_line_pairs = {(_norm(row["description"]), round(float(row["amount"]), 2)) for row in expected_lines}
    line_item_precision = len(actual_line_pairs & expected_line_pairs) / len(actual_line_pairs) if actual_line_pairs else (1.0 if not expected_line_pairs else 0.0)
    line_item_recall = len(actual_line_pairs & expected_line_pairs) / len(expected_line_pairs) if expected_line_pairs else 1.0
    actual_total = _field(normalized.get("total_amount"))
    actual_claim = _field(normalized.get("claim_number"))
    actual_paid = float(settlement.amount_paid) if settlement.amount_paid is not None else None
    actual_settlement_claim = settlement.claim_id
    actual_deductions = [{"description": row.reason_text or row.category, "amount": float(row.amount), "category": row.category} for row in settlement.deductions]
    actual = {
        "bill_total": actual_total,
        "line_items": actual_lines,
        "claim_reference": actual_claim,
        "amount_paid": actual_paid,
        "settlement_claim_reference": actual_settlement_claim,
        "deductions": actual_deductions,
        "copay_applied": float(settlement.copay_applied) if settlement.copay_applied is not None else None,
        "needs_review": settlement.needs_review,
        "review_reasons": settlement.review_reasons,
        "page_count": page_count,
        "evidence_methods": [item.method for item in evidence],
    }
    field_matches = {
        "bill_total": actual_total == expected.get("bill_total"),
        "line_items": actual_line_pairs == expected_line_pairs,
        "bill_claim_reference": actual_claim == expected.get("claim_reference"),
        "paid_amount": actual_paid == expected.get("amount_paid"),
        "settlement_claim_reference": actual_settlement_claim == expected.get("settlement_claim_reference", expected.get("claim_reference")),
        "review_routing": settlement.needs_review == expected.get("needs_review"),
    }
    if "deductions" in expected:
        expected_total = sum(float(row["amount"]) for row in expected["deductions"])
        parsed_total = sum(float(row.amount) for row in settlement.deductions) + float(settlement.copay_applied or 0)
        field_matches["deduction_total"] = round(parsed_total, 2) == round(expected_total, 2)
    return {
        "case_id": case["case_id"], "challenge": case["challenge"], "expected": expected,
        "actual": actual, "field_matches": field_matches,
        "line_item_precision": line_item_precision, "line_item_recall": line_item_recall,
        "match": all(field_matches.values()),
    }


def main() -> int:
    casebook = json.loads(CASEBOOK.read_text(encoding="utf-8"))
    rows = [_score_one(case) for case in casebook["cases"]]
    checks = [(case_id, match) for row in rows for case_id, match in row["field_matches"].items()]
    output = {
        "dataset": str(CASEBOOK.relative_to(ROOT)).replace("\\", "/"),
        "labels_committed_before_scoring": True,
        "cases": rows,
        "case_match": {"numerator": sum(row["match"] for row in rows), "denominator": len(rows)},
        "field_match": {"numerator": sum(value for _, value in checks), "denominator": len(checks)},
        "line_item_precision": sum(row["line_item_precision"] for row in rows) / len(rows),
        "line_item_recall": sum(row["line_item_recall"] for row in rows) / len(rows),
    }
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
