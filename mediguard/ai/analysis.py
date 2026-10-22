"""Single background LLM explanation path with strict source grounding."""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from mediguard.ai import llm_gateway


PROMPT_VERSION = "analysis_v1"
PROMPT_PATH = Path(__file__).resolve().parents[2] / "config" / "prompts" / "analysis_v1.txt"
ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "explanation": {"type": "string"},
        "deductions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "deduction_id": {"type": "string"},
                    "assessment": {"type": "string", "enum": ["supported", "not_supported", "unclear"]},
                    "clause_id": {"type": ["string", "null"]},
                    "rationale": {"type": "string"},
                },
                "required": ["deduction_id", "assessment", "clause_id", "rationale"],
            },
        },
    },
    "required": ["explanation", "deductions"],
}


def _text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _money(value: Any) -> str:
    if value is None:
        return "not available"
    try:
        return format(Decimal(str(value)), ".2f")
    except (InvalidOperation, ValueError, TypeError):
        return "not available"


def build_analysis_payload(result: dict[str, Any]) -> dict[str, Any]:
    """Create the minimal factual payload sent to the explanation model."""
    comparison = result.get("comparison")
    categories = list(getattr(comparison, "categories", []) or []) if comparison is not None else []
    deductions: list[dict[str, Any]] = []
    clauses: list[dict[str, Any]] = []
    for index, row in enumerate(categories, start=1):
        amount = getattr(row, "insurer_deducted", None)
        if amount is None or Decimal(str(amount)) <= 0:
            continue
        deduction_id = f"deduction-{index:02d}"
        deductions.append({
            "deduction_id": deduction_id,
            "category": _text(getattr(row, "category", "")),
            "description": _text(getattr(row, "insurer_reason", "") or getattr(row, "category", "")),
            "amount": _money(amount),
            "insurer_reason": _text(getattr(row, "insurer_reason", "")),
            "python_assessment": {
                "MATCH": "supported",
                "UNEXPLAINED_DEDUCTION": "not_supported",
                "EXCESS_DEDUCTION": "not_supported",
            }.get(str(getattr(row, "status", "")), "unclear"),
        })
        clause = getattr(row, "clause", None)
        if clause is not None:
            clause_id = _text(getattr(clause, "section", None)) or f"{getattr(row, 'category', 'clause')}-page-{clause.page}"
            clauses.append({
                "deduction_id": deduction_id,
                "clause_id": clause_id,
                "page": int(clause.page),
                "text": _text(getattr(clause, "text", ""))[:400],
            })
    return {
        "verdict": _text(getattr(comparison, "status", None) or (result.get("rules") or {}).get("status") or "manual_review"),
        "estimated_payment": _money(getattr(comparison, "expected_insurer_payment", None)),
        "insurer_paid": _money(getattr(comparison, "actual_insurer_payment", None)),
        "difference": _money(getattr(comparison, "possible_difference", None)),
        "deductions": deductions,
        "clauses": clauses,
    }


def _render_prompt(payload: dict[str, Any]) -> tuple[str, str]:
    content = PROMPT_PATH.read_text(encoding="utf-8-sig")
    system, user = content.split("\nUSER\n", 1)
    system = system.removeprefix("SYSTEM\n").strip()
    deduction_lines = [
        f"{row['deduction_id']} | {row['description']} | INR {row['amount']} | {row['insurer_reason'] or 'not supplied'}"
        for row in payload["deductions"]
    ] or ["No insurer deductions were identified."]
    clause_lines = [
        f"{row['clause_id']} | page {row['page']} | {row['text']}"
        for row in payload["clauses"]
    ] or ["No supporting clauses were retrieved."]
    replacements = {
        "{verdict}": payload["verdict"],
        "{estimated_payment}": payload["estimated_payment"],
        "{insurer_paid}": payload["insurer_paid"],
        "{difference}": payload["difference"],
        "{deductions: id | description | amount | insurer_reason, one per line}": "\n".join(deduction_lines),
        "{clauses: id | page | text (max 400 chars), top 3 per deduction}": "\n".join(clause_lines),
    }
    for marker, value in replacements.items():
        user = user.replace(marker, value)
    return system, user.strip()


def _number_key(value: str) -> str | None:
    try:
        return str(Decimal(value.replace(",", "")).normalize())
    except (InvalidOperation, ValueError):
        return None


def _numeric_values(text: str) -> set[str]:
    return {key for match in re.findall(r"(?<![A-Za-z])[-+]?\d[\d,]*(?:\.\d+)?", text) if (key := _number_key(match)) is not None}


def validate_analysis_output(output: Any, payload: dict[str, Any]) -> tuple[bool, str]:
    if not isinstance(output, dict):
        return False, "Analysis response was not an object"
    explanation = output.get("explanation")
    if not isinstance(explanation, str) or not explanation.strip() or len(explanation) > 1200 or len(explanation.split()) > 80:
        return False, "Explanation must contain 1 to 80 words"
    expected = {row["deduction_id"] for row in payload["deductions"]}
    rows = output.get("deductions")
    if not isinstance(rows, list) or len(rows) != len(expected):
        return False, "Analysis must assess every supplied deduction exactly once"
    seen: set[str] = set()
    clauses_by_deduction: dict[str, set[str]] = {}
    for clause in payload["clauses"]:
        clauses_by_deduction.setdefault(clause["deduction_id"], set()).add(clause["clause_id"])
    for row in rows:
        if not isinstance(row, dict):
            return False, "A deduction assessment was malformed"
        deduction_id = row.get("deduction_id")
        if deduction_id not in expected or deduction_id in seen:
            return False, "A deduction assessment used an unknown or duplicate id"
        seen.add(deduction_id)
        if row.get("assessment") not in {"supported", "not_supported", "unclear"}:
            return False, "A deduction assessment used an invalid label"
        clause_id = row.get("clause_id")
        if clause_id is not None and clause_id not in clauses_by_deduction.get(deduction_id, set()):
            return False, "Analysis cited a clause that was not supplied"
        rationale = row.get("rationale")
        if not isinstance(rationale, str) or len(rationale) > 500 or len(rationale.split()) > 25:
            return False, "A deduction rationale must contain at most 25 words"
    source_numbers = [payload["estimated_payment"], payload["insurer_paid"], payload["difference"]]
    for deduction in payload["deductions"]:
        source_numbers.extend((deduction["amount"], deduction["description"], deduction["insurer_reason"]))
    source_numbers.extend(clause["text"] for clause in payload["clauses"])
    allowed_numbers = set().union(*(_numeric_values(value) for value in source_numbers))
    for clause in payload["clauses"]:
        allowed_numbers.add(str(clause["page"]))
    for text in [explanation, *(str(row["rationale"]) for row in rows)]:
        for number in _numeric_values(text):
            if number not in allowed_numbers:
                return False, f"Analysis used an unsupported number: {number}"
    expected_by_id = {row["deduction_id"]: row.get("python_assessment") for row in payload["deductions"]}
    if any(row["assessment"] != expected_by_id.get(row["deduction_id"]) for row in rows):
        return False, "Analysis deduction assessment disagrees with the Python comparison"
    verdict = payload["verdict"]
    lower_explanation = explanation.casefold()
    if re.search(
        r"\b(?:claim\s+(?:was\s+)?(?:approved|denied|accepted|rejected)|(?:approved|denied|accepted|rejected)\s+(?:the\s+)?claim)\b",
        lower_explanation,
    ):
        return False, "Analysis must not make an insurer or claim decision"
    if verdict == "manual_review":
        if re.search(
            r"\b(?:approved|resolved|no\s+discrepanc(?:y|ies)|no\s+difference|matches?\s+(?:the\s+)?(?:estimate|policy|exactly)|paid\s+the\s+full\s+estimated\s+payment)\b",
            lower_explanation,
        ):
            return False, "Analysis explanation disagrees with the Python comparison"
        if not re.search(r"\b(?:manual\s+review|reviewer|authorized\s+review)\b", lower_explanation):
            return False, "Manual-review comparison must remain explicitly unresolved"
    if verdict == "possible_discrepancy" and re.search(r"\bno\s+discrepanc(?:y|ies)\b|\bmatches?\s+the\s+policy\b", lower_explanation):
        return False, "Analysis explanation disagrees with the Python comparison"
    if verdict == "no_discrepancy" and re.search(r"\bpossible\s+discrepanc|\bunsupported\s+deduction|\bwrongful\s+deduction", lower_explanation):
        return False, "Analysis explanation disagrees with the Python comparison"
    return True, "Explanation amounts and clause references passed grounding checks"


def _safe_deductions(rows: Any) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        return []
    return [{key: row.get(key) for key in ("deduction_id", "assessment", "clause_id", "rationale")}
            for row in rows if isinstance(row, dict)]


def analyze_payload(payload: dict[str, Any], claim_id: str, fallback: str) -> dict[str, Any]:
    """Make one bounded gateway request; return a template on any fault."""
    system, prompt = _render_prompt(payload)
    response = llm_gateway.chat_json(
        system, prompt, caller="analysis.py:analyze_payload", prompt_version=PROMPT_VERSION,
        schema=ANALYSIS_SCHEMA, temperature=0.0, max_retries=0, claim_id=claim_id,
    )
    if not response.ok:
        return {"accepted": False, "reason": response.error or response.status, "explanation": fallback, "deductions": []}
    accepted, reason = validate_analysis_output(response.parsed, payload)
    response.finalize(accepted, reason, "claim explanation and deduction assessments" if accepted else "none")
    if not accepted:
        reviewer_candidate = None
        if reason.endswith("disagrees with the Python comparison") and isinstance(response.parsed, dict):
            reviewer_candidate = {
                "explanation": str(response.parsed.get("explanation") or ""),
                "deductions": _safe_deductions(response.parsed.get("deductions", [])),
            }
        return {"accepted": False, "reason": reason, "explanation": fallback, "deductions": [],
                "reviewer_candidate": reviewer_candidate}
    # Statuses, payment values, and appeal eligibility are never returned from
    # this module. Only the validated explanation and per-deduction commentary
    # may be displayed.
    return {"accepted": True, "reason": reason, "explanation": response.parsed["explanation"].strip(),
            "deductions": _safe_deductions(response.parsed["deductions"])}
