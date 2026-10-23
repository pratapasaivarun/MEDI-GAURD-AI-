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
UNKNOWN_ANSWER = (
    "I can't answer that from this claim's saved facts. You can ask: "
    "How much will the insurer pay? What are my deductible and copayment? "
    "Why was my claim sent to Manual Review?"
)
OFF_TOPIC_ANSWER = "I can only help with this claim's saved decision data, policy terms, and settlement comparison."
PROVISIONAL_NOTICE = "Provisional notice: policy terms are unconfirmed; this result may change after authorized review."
QA_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "used_clause_ids": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["answer", "used_clause_ids"],
}


def _object_value(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _saved_rules(result: dict[str, Any]) -> dict[str, Any]:
    rules = result.get("rules")
    return rules if isinstance(rules, dict) else result


def _claimant_facts(result: dict[str, Any]) -> dict[str, Any]:
    claimant = result.get("claimant_result")
    return claimant if isinstance(claimant, dict) else result


def normalize_question(question: str) -> str:
    """Normalize pasted questions without interpreting or parsing claim amounts."""
    normalized = question.lower().replace(",", "")
    normalized = re.sub(r"[\"'`“”‘’]", " ", normalized)
    normalized = re.sub(r"\b(?:inr|rs\.?|rupees?)\b", " ", normalized)
    normalized = re.split(
        r"\b(?:pasted note|pasted text|copied below|forwarded message|begin pasted text)\b",
        normalized,
        maxsplit=1,
    )[0]
    return " ".join(normalized.split())


def classify_intent(question: str) -> str | None:
    """Classify supported claimant questions before any model availability check."""
    asked = normalize_question(question)
    if re.search(
        r"\b(?:ombudsman|will i win|can i win|could i win|win this|"
        r"is this fair|was this fair|unfair|fair chance|legal advice|"
        r"likely outcome|chance of winning|predict the outcome|"
        r"guarantee.{0,20}(?:win|success|outcome)|sue|lawsuit|court)\b",
        asked,
    ):
        return "legal_outcome"
    if re.search(
        r"\bwhat if\b|\bassuming\b|\bhypothetical\b|"
        r"\bif\s+(?:(?:my|the|a)\s+)?(?:deductible|copay|co-pay|bill|eligible amount|"
        r"coverage|limit|insurer payment)\b.{0,60}\b(?:was|were|would|changed|changes|became)\b",
        asked,
    ):
        return "hypothetical"
    if re.search(
        r"\b(?:unconfirmed|not confirmed|not reviewer[- ]confirmed|"
        r"low[- ]confidence|not applied|uncertain term|provisional(?: term)?|"
        r"needs confirmation)\b",
        asked,
    ):
        return "unconfirmed_term"
    if "manual review" in asked or "manual_review" in asked or re.search(r"\bunder review\b|\bsent to review\b", asked):
        return "manual_review"
    if any(term in asked for term in (
        "settlement difference", "settlement payment", "settlement vs",
        "settlement versus", "difference between", "why is the settlement",
        "what caused the difference", "which line caused",
    )) or (("vs estimate" in asked or "versus estimate" in asked) and any(word in asked for word in ("payment", "settlement"))):
        return "settlement_difference"
    if any(term in asked for term in ("appeal", "next step", "what should i do", "what can i do next")):
        return "next_steps_appeal"
    if re.search(r"\bwhy\b.{0,90}\b(?:pay|owe|responsib|out of pocket)\b|\b(?:breakdown|break it down)\b", asked):
        return "why_pay"
    if any(term in asked for term in ("how much will insurance pay", "how much does insurance pay", "how much will the insurer pay", "insurer share", "insurance share", "insurance payable", "insurer payable", "insurance pay", "insurer pay")):
        return "insurer_share"
    if any(term in asked for term in ("eligible amount", "eligible total", "bill total", "total bill", "amount billed", "total amount")):
        return "bill_and_eligible"
    if "deductible" in asked:
        return "deductible"
    if "copay" in asked or "co-pay" in asked or "co pay" in asked or "copayment" in asked:
        return "copayment"
    if any(term in asked for term in ("excluded amount", "excluded", "not covered amount", "not covered", "limited amount", "policy-limited", "policy limited")):
        return "excluded_limited"
    if any(term in asked for term in ("why", "room limit", "room rent", "proportionate", "not covered", "excluded", "charge", "limit")):
        return "why_not_covered"
    if any(term in asked for term in ("status", "approved", "decision", "result")):
        return "status"
    if re.search(r"\bpatient\b", asked):
        return "patient"
    if any(term in asked for term in ("hospital", "provider")):
        return "hospital"
    if any(term in asked for term in ("policy", "coverage", "waiting period", "clause")):
        return None
    claim_terms = ("claim", "insurance", "insurer", "policy", "bill", "hospital", "deduct", "copay", "cover", "settle", "appeal", "review", "payment", "eligible", "room", "charge", "benefit", "paid")
    if not any(term in asked for term in claim_terms):
        return "off_topic"
    return None


def _money(value: Any) -> str:
    if value is None:
        return "unavailable"
    try:
        return f"INR {float(value):,.2f}"
    except (TypeError, ValueError):
        return "unavailable"


def _provisional_notice(result: dict[str, Any]) -> str | None:
    rules = _saved_rules(result)
    status = str(result.get("policy_terms_review_status") or rules.get("policy_terms_review_status") or "").lower()
    issues = result.get("policy_terms_issues") or rules.get("policy_terms_issues") or []
    if status in {"provisional", "not_available", "pending"} or issues:
        return PROVISIONAL_NOTICE
    return None


def _build_why_pay(result: dict[str, Any], _context: dict[str, Any]) -> str:
    facts = _claimant_facts(result)
    return (
        f"Your estimated responsibility is {_money(facts.get('amount_claimant_pays'))}: "
        f"deductible {_money(facts.get('deductible'))}, copayment {_money(facts.get('copayment'))}, "
        f"and excluded or policy-limited charges {_money(facts.get('amount_excluded_or_limited'))}. "
        f"The eligible amount before cost-sharing is {_money(facts.get('covered_before_cost_sharing'))}; "
        f"the insurer payable estimate is {_money(facts.get('amount_covered'))}. "
        "The deductible and copayment are cost-sharing, not rejected charges."
    )


def _build_insurer_share(result: dict[str, Any], _context: dict[str, Any]) -> str:
    facts = _claimant_facts(result)
    return f"The insurer payable estimate is {_money(facts.get('amount_covered'))}."


def _build_bill_and_eligible(result: dict[str, Any], _context: dict[str, Any]) -> str:
    facts = _claimant_facts(result)
    return (
        f"The total bill is {_money(facts.get('amount_billed'))}; "
        f"the eligible amount before deductible and copayment is {_money(facts.get('covered_before_cost_sharing'))}."
    )


def _build_deductible(result: dict[str, Any], _context: dict[str, Any]) -> str:
    return f"The saved deductible amount is {_money(_claimant_facts(result).get('deductible'))}."


def _build_copayment(result: dict[str, Any], _context: dict[str, Any]) -> str:
    return f"The saved copayment amount is {_money(_claimant_facts(result).get('copayment'))}."


def _build_excluded_limited(result: dict[str, Any], _context: dict[str, Any]) -> str:
    return f"The saved excluded or policy-limited amount is {_money(_claimant_facts(result).get('amount_excluded_or_limited'))}."


def _build_settlement_difference(_result: dict[str, Any], context: dict[str, Any]) -> str:
    comparison = context.get("comparison")
    if comparison is None:
        return "No saved settlement comparison is available, so a settlement difference cannot be stated."
    status = str(_object_value(comparison, "status", ""))
    if status != "possible_discrepancy":
        if status == "manual_review":
            return "The saved settlement comparison is under Manual Review, so no settlement difference is confirmed."
        return "The saved settlement comparison found no possible discrepancy, so no settlement difference is identified."
    difference = _object_value(comparison, "possible_difference")
    if difference is None:
        return "The saved comparison identifies a possible discrepancy, but its amount is unavailable."
    categories = _object_value(comparison, "categories", []) or []
    cause = next((
        item for item in categories
        if _object_value(item, "status") in {"UNEXPLAINED_DEDUCTION", "EXCESS_DEDUCTION"}
    ), None)
    if cause is None:
        return f"The saved comparison shows a possible settlement difference of {_money(difference)}, but does not identify a causing line."
    line = str(_object_value(cause, "category") or "Unidentified settlement line").replace("_", " ").lower()
    reason = str(_object_value(cause, "insurer_reason") or "No settlement reason was saved.")
    clause = _object_value(cause, "clause")
    citation = ""
    if clause is not None:
        section = _object_value(clause, "section")
        page = _object_value(clause, "page")
        parts = [str(part) for part in (section, f"page {page}" if page is not None else None) if part]
        if parts:
            citation = f" Supporting policy reference: {', '.join(parts)}."
    elif _object_value(cause, "clause") is None:
        citation = " Supporting policy clause/page: unavailable in the saved comparison."
    return f"The saved comparison shows a possible difference of {_money(difference)}. The flagged line is {line}: {reason}.{citation}"


def _build_why_not_covered(result: dict[str, Any], _context: dict[str, Any]) -> str:
    rules = _saved_rules(result)
    lines = rules.get("line_item_results") or []
    notes = []
    for line in lines:
        if not isinstance(line, dict):
            continue
        status = str(line.get("status") or "").lower()
        rule = str(line.get("applied_rule") or "").lower()
        if status in {"partial", "excluded", "needs_review", "fail"} or any(word in rule for word in ("room", "limit", "exclude", "sub_limit")):
            calculation = str(line.get("calculation") or "").strip()
            if calculation:
                description = str(line.get("description") or line.get("category") or "Unidentified bill line")
                notes.append(f"{description}: {calculation}")
    if notes:
        return "The saved calculation notes say: " + " ".join(notes)
    return "The saved decision data has no line-level calculation note identifying why a charge was limited or not covered."


def _build_unconfirmed_term(result: dict[str, Any], _context: dict[str, Any]) -> str:
    rules = _saved_rules(result)
    issues = result.get("policy_terms_issues") or rules.get("policy_terms_issues") or []
    details = []
    for issue in issues:
        if isinstance(issue, dict):
            reason = str(issue.get("reason") or "").strip()
            if reason:
                details.append(reason)
    if details:
        return "The following policy term(s) were not applied because they are unconfirmed: " + " ".join(details) + " The result may change after authorized review."
    missing = rules.get("policy_terms_missing") or []
    if missing:
        terms = ", ".join(str(term).replace("_", " ") for term in missing)
        return f"The saved decision lists these unconfirmed terms as not applied: {terms}. The result may change after authorized review."
    return "No specific unconfirmed term is listed in the saved decision data. If a term remains unconfirmed, it was not applied and the result may change after authorized review."


def _build_next_steps_appeal(_result: dict[str, Any], context: dict[str, Any]) -> str:
    comparison = context.get("comparison")
    if comparison is None:
        return "No appeal draft is offered because no saved settlement comparison is available."
    status = str(_object_value(comparison, "status", ""))
    if status == "possible_discrepancy":
        return "A possible discrepancy is recorded and an appeal draft is available for review. Check the flagged settlement line and policy reference with an authorized reviewer before using it."
    if status == "manual_review":
        return "No appeal draft is offered because the settlement comparison is still under Manual Review."
    return "No appeal draft is offered because the saved settlement comparison found no possible discrepancy."


def _build_manual_review(result: dict[str, Any], context: dict[str, Any]) -> str:
    reasons = []
    rules = _saved_rules(result)
    claimant_reason = result.get("reason") or _claimant_facts(result).get("reason")
    if claimant_reason and claimant_reason not in reasons:
        reasons.append(str(claimant_reason))
    for issue in result.get("policy_terms_issues") or rules.get("policy_terms_issues") or []:
        if isinstance(issue, dict) and issue.get("reason") and issue["reason"] not in reasons:
            reasons.append(str(issue["reason"]))
    for warning in rules.get("warnings") or []:
        if warning and str(warning) not in reasons:
            reasons.append(str(warning))
    comparison = context.get("comparison")
    for reason in _object_value(comparison, "review_reasons", []) or []:
        if reason and str(reason) not in reasons:
            reasons.append(str(reason))
    if reasons:
        return "The claim was sent to Manual Review because the saved decision records: " + " ".join(reasons) + " An authorized reviewer must resolve this before the result is final."
    return "The saved decision marks this claim for Manual Review but does not record a specific reason. An authorized reviewer must check the source documents."


def _build_status(result: dict[str, Any], _context: dict[str, Any]) -> str:
    return f"The current claim status in the saved decision is {result.get('status') or 'unavailable'}."


def _build_patient(result: dict[str, Any], context: dict[str, Any]) -> str:
    patient = context.get("normalized", {}).get("patient_name", {})
    patient = patient.get("value") if isinstance(patient, dict) else patient
    return f"The patient listed in the saved claim is {patient}." if patient else "The patient name is unavailable in the saved claim data."


def _build_hospital(result: dict[str, Any], context: dict[str, Any]) -> str:
    hospital = context.get("normalized", {}).get("hospital_name", {})
    hospital = hospital.get("value") if isinstance(hospital, dict) else hospital
    return f"The hospital listed in the saved claim is {hospital}." if hospital else "The hospital name is unavailable in the saved claim data."


ANSWER_BUILDERS = {
    "why_pay": _build_why_pay,
    "insurer_share": _build_insurer_share,
    "bill_and_eligible": _build_bill_and_eligible,
    "deductible": _build_deductible,
    "copayment": _build_copayment,
    "excluded_limited": _build_excluded_limited,
    "settlement_difference": _build_settlement_difference,
    "why_not_covered": _build_why_not_covered,
    "unconfirmed_term": _build_unconfirmed_term,
    "next_steps_appeal": _build_next_steps_appeal,
    "manual_review": _build_manual_review,
    "status": _build_status,
    "patient": _build_patient,
    "hospital": _build_hospital,
}


def _claim_facts(result: dict[str, Any]) -> dict[str, Any]:
    claimant = _claimant_facts(result)
    return {
        "verdict": result.get("status", "not available"),
        "estimated_payment": claimant.get("amount_covered"),
        "bill_total": claimant.get("amount_billed"),
        "eligible_amount": claimant.get("covered_before_cost_sharing"),
        "claimant_responsibility": claimant.get("amount_claimant_pays"),
        "insurer_paid": result.get("insurer_paid", "not available"),
        "difference": result.get("possible_difference", "not available"),
        "deductible": claimant.get("deductible"),
        "copayment": claimant.get("copayment"),
        "excluded_or_limited": claimant.get("amount_excluded_or_limited"),
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


def answer_question(
    question: str,
    result: dict[str, Any],
    evidence: list[dict[str, Any]],
    claim_id: str,
    *,
    normalized: dict[str, Any] | None = None,
    comparison: Any = None,
    settlement: Any = None,
) -> str:
    """Answer supported claim intents from saved data before considering Ollama."""
    intent = classify_intent(question)
    context = {
        "normalized": normalized or {},
        "comparison": comparison,
        "settlement": settlement,
    }
    if intent == "legal_outcome":
        answer = (
            "I can't predict an outcome or determine whether a decision is fair. "
            "This tool provides decision support, not legal or insurance advice. "
            "Review the appeal draft, if available, with an authorized reviewer."
        )
    elif intent == "hypothetical":
        answer = "I can't recalculate hypothetical amounts. I can answer only from this claim's saved decision data."
    elif intent == "off_topic":
        answer = OFF_TOPIC_ANSWER
    elif intent in ANSWER_BUILDERS:
        answer = ANSWER_BUILDERS[intent](result, context)
    else:
        if evidence and llm_gateway.is_ollama_available(timeout=0.5):
            answer = answer_with_llm(question, result, evidence, claim_id)
        else:
            answer = UNKNOWN_ANSWER
    notice = _provisional_notice(result)
    return f"{answer} {notice}" if notice else answer
