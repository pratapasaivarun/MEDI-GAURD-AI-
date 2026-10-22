"""Read-only, evidence-bounded fallback for claimant questions."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from mediguard.ai import llm_gateway
from mediguard.ai.analysis import _numeric_values

PROMPT_VERSION = "qa_v1"
PROMPT_PATH = Path(__file__).resolve().parents[2] / "config" / "prompts" / "qa_v1.txt"
NO_EVIDENCE_ANSWER = "I can't find that in this claim's documents."
QA_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "used_clause_ids": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["answer", "used_clause_ids"],
}


def _claim_facts(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "verdict": result.get("status", "not available"),
        "estimated_payment": result.get("amount_covered"),
        "claimant_responsibility": result.get("amount_claimant_pays"),
        "insurer_paid": result.get("insurer_paid", "not available"),
        "difference": result.get("possible_difference", "not available"),
        "deductible": result.get("deductible"),
        "copayment": result.get("copayment"),
        "reason": result.get("reason", ""),
    }


def _render_prompt(question: str, facts: dict[str, Any], evidence: list[dict[str, Any]]) -> tuple[str, str]:
    content = PROMPT_PATH.read_text(encoding="utf-8-sig")
    system, user = content.split("\nUSER\n", 1)
    system = system.removeprefix("SYSTEM\n").strip()
    clauses = [
        f"{item.get('clause_id') or item.get('section') or 'clause'} | page {item.get('page', 'unknown')} | {' '.join(str(item.get('text') or '').split())[:500]}"
        for item in evidence
        if str(item.get("text") or "").strip()
    ]
    replacements = {
        "{verdict, estimated_payment, insurer_paid, difference, deductions with reasons}": json.dumps(facts, ensure_ascii=False, sort_keys=True),
        "{clauses: id | page | text, top 3 by similarity to the question}": "\n".join(clauses) or "No policy clauses were retrieved.",
        "{question}": question.strip(),
    }
    for marker, value in replacements.items():
        user = user.replace(marker, value)
    return system, user.strip()


def validate_qa_output(output: Any, facts: dict[str, Any], evidence: list[dict[str, Any]]) -> tuple[bool, str]:
    if not isinstance(output, dict):
        return False, "Q&A response was not an object"
    answer = output.get("answer")
    if not isinstance(answer, str) or not answer.strip() or len(answer.split()) > 80:
        return False, "Q&A answer must contain 1 to 80 words"
    allowed_ids = {
        str(item.get("clause_id") or item.get("section"))
        for item in evidence if item.get("clause_id") or item.get("section")
    }
    used_ids = output.get("used_clause_ids")
    if not isinstance(used_ids, list) or any(not isinstance(value, str) or value not in allowed_ids for value in used_ids):
        return False, "Q&A cited a clause that was not retrieved"
    allowed_numbers = set().union(
        _numeric_values(json.dumps(facts, ensure_ascii=False)),
        *(_numeric_values(str(item.get("text") or "")) for item in evidence),
        *(_numeric_values(str(item.get("page") or "")) for item in evidence),
    )
    if any(number not in allowed_numbers for number in _numeric_values(answer)):
        return False, "Q&A used a number that was not present in the claim facts or policy evidence"
    for citation in re.findall(r"\b(?:clause|section)\s+([A-Za-z0-9][A-Za-z0-9._:-]*)", answer, re.I):
        if citation not in allowed_ids:
            return False, "Q&A cited a clause that was not retrieved"
    return True, "Q&A answer grounded in supplied claim facts and retrieved clauses"


def answer_with_llm(question: str, result: dict[str, Any], evidence: list[dict[str, Any]], claim_id: str) -> str:
    """Use the model only as a read-only fallback; return safe wording on any failure."""
    usable_evidence = [item for item in (evidence or []) if isinstance(item, dict) and str(item.get("text") or "").strip()]
    if not usable_evidence:
        return NO_EVIDENCE_ANSWER
    facts = _claim_facts(result)
    system, prompt = _render_prompt(question, facts, usable_evidence[:3])
    response = llm_gateway.chat_json(
        system, prompt, caller="claim_pages.py:_render_claim_assistant_chat",
        prompt_version=PROMPT_VERSION, schema=QA_SCHEMA, claim_id=claim_id,
        temperature=0.0,
    )
    if not response.ok:
        return NO_EVIDENCE_ANSWER
    valid, reason = validate_qa_output(response.parsed, facts, usable_evidence[:3])
    response.finalize(valid, reason, "claimant Q&A" if valid else "none")
    return str(response.parsed["answer"]).strip() if valid else NO_EVIDENCE_ANSWER


def answer_question(question: str, deterministic_answer: str | None, result: dict[str, Any], evidence: list[dict[str, Any]], claim_id: str) -> str:
    """Preserve deterministic-first behavior and avoid LLM calls when it answered."""
    if deterministic_answer is not None:
        return deterministic_answer
    return answer_with_llm(question, result, evidence, claim_id)
