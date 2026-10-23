"""LangGraph workflow of five deterministic agents (Supervisor, Document, Policy, Decision, Output) with an optional on-demand LLM explanation and Q&A; Python decides every amount.

The Policy Agent retrieves policy evidence only, the Rule Engine calculates
deterministic outcomes, and the Decision Agent forwards the deterministic
rule result. An optional on-demand LLM explanation is available on the result
screen; document extraction has no automatic LLM fallback.
"""
from __future__ import annotations

import json
from decimal import Decimal
import re
import time
from pathlib import Path
from typing import Any, Callable, TypedDict

from mediguard.engine.models import ComparisonResult

from mediguard.ai import llm_gateway

try:
    from langgraph.graph import END, START, StateGraph
except ImportError:  # Keep the module importable until dependencies are installed on Windows.
    END = START = None
    StateGraph = None

OLLAMA_HOST = __import__("os").getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
# Granite is the installed CPU-only inference model for this project.
OLLAMA_MODEL = __import__("os").getenv("OLLAMA_MODEL", "ibm/granite4.1:8b")
OLLAMA_TIMEOUT = int(__import__("os").getenv("OLLAMA_TIMEOUT_SECONDS", "120"))
OLLAMA_NUM_CTX = int(__import__("os").getenv("OLLAMA_NUM_CTX", "2048"))
OLLAMA_NUM_THREAD = int(__import__("os").getenv("OLLAMA_NUM_THREAD", str(__import__("os").cpu_count() or 4)))
OLLAMA_KEEP_ALIVE = __import__("os").getenv("OLLAMA_KEEP_ALIVE", "30m")
OLLAMA_NUM_PREDICT = int(__import__("os").getenv("OLLAMA_NUM_PREDICT", "320"))
DECISION_RESPONSE_SCHEMA = {"type": "object", "properties": {"status": {"type": "string", "enum": ["approved", "partially_approved", "rejected", "manual_review"]}, "reasons": {"type": "array", "items": {"type": "string"}}, "policy_citations": {"type": "array", "items": {"type": "string"}}, "confidence": {"type": "number"}, "reviewer_note": {"type": "string"}, "line_item_notes": {"type": "array", "default": [], "items": {"type": "object", "properties": {"item_index": {"type": "integer"}, "note": {"type": "string"}}, "required": ["item_index", "note"]}}}, "required": ["status", "reasons", "policy_citations", "confidence", "reviewer_note"]}
METRICS_PATH = Path(__import__("os").getenv("AGENT_METRICS_PATH", "data/agent_metrics.jsonl"))
ESCALATION_GUIDANCE = "If your appeal is not resolved within 30 days, you can escalate to your Insurance Ombudsman or file a grievance on IRDAI's Bima Bharosa portal (https://bimabharosa.irdai.gov.in)."

def confidence_label(score: float) -> str:
    if score > 0.8: return "High confidence"
    if score >= 0.5: return "Medium confidence — recommend human review"
    return "Low confidence — please review manually"


def warm_ollama() -> None:
    """Preload Granite once before the first real agent call in a session."""
    result = llm_gateway.warmup(timeout=OLLAMA_TIMEOUT)
    if result.ok:
        result.finalize(True, "Warm-up response received", "model warm-up")


class ClaimWorkflowState(TypedDict, total=False):
    claim: dict[str, Any]
    normalized_claim: dict[str, Any]
    policy_text: str
    policy_id: str
    policy_evidence: list[dict[str, Any]]
    policy_findings: dict[str, Any]
    rule_results: dict[str, Any]
    decision: dict[str, Any]
    errors: list[str]
    llm_calls: int
    progress_callback: Callable[[str], None]


def _record_metrics(event: dict[str, Any]) -> None:
    try:
        METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with METRICS_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _missing_fields_from_warnings(warnings: list[Any]) -> list[str]:
    """Extract only explicit missing-field names from rule warning text."""
    fields: list[str] = []
    prefixes = ("Missing required fields:", "Required policy terms missing:")
    for warning in warnings:
        text = str(warning or "").strip()
        prefix = next((candidate for candidate in prefixes if text.startswith(candidate)), None)
        if not prefix:
            continue
        for field in text[len(prefix):].split(","):
            clean = field.strip().replace("_", " ")
            if clean and clean not in fields:
                fields.append(clean)
    return fields


def recommend_next_steps(decision: dict[str, Any], rules: dict[str, Any]) -> list[str]:
    """Return concise, deterministic claimant guidance without an LLM call."""
    status = str(decision.get("status") or rules.get("status") or "manual_review")
    warnings = rules.get("warnings") or []
    line_items = rules.get("line_item_results") or []
    billing_anomalies = rules.get("billing_anomalies") or {}
    has_billing_anomaly = bool(billing_anomalies.get("duplicates") or billing_anomalies.get("price_outliers"))
    actionable_items = [
        item for item in line_items
        if isinstance(item, dict) and item.get("status") in {"excluded", "partial", "needs_review"}
    ]
    contestable_rules = {"sub_limit", "waiting_period", "ambiguous_match", "exclusion_ambiguous"}
    contestable_items = [item for item in actionable_items if str(item.get("applied_rule") or "") in contestable_rules]

    def finalize(recommendations: list[str]) -> list[str]:
        deadline = rules.get("submission_deadline") or {}
        if deadline.get("warning"):
            recommendations = recommendations[:2] + [str(deadline["warning"])]
        citations = decision.get("policy_citations") or []
        if status in {"rejected", "partially_approved"} and citations and (status == "rejected" or actionable_items):
            recommendations.append(ESCALATION_GUIDANCE)
        if rules.get("history_flags"):
            recommendations.append("This looks similar to a past rejected claim — consider reviewing why before resubmitting, or gathering additional documentation this time.")
        # Every entry is deterministic, short, and actionable. Do not silently
        # discard deadline, escalation, or claim-history guidance.
        return recommendations

    if status == "manual_review":
        missing_fields = _missing_fields_from_warnings(warnings)
        if missing_fields:
            return finalize([f"Upload the missing document: {field}." for field in missing_fields[:3]])
        if actionable_items:
            description = str(actionable_items[0].get("description") or "this item")
            return finalize([f"Ask an authorized reviewer to check {description} and confirm the applicable policy terms before relying on this assessment."])
        return finalize(["Ask an authorized reviewer to verify the bill details and applicable policy terms before relying on this assessment."])

    if status == "rejected":
        citations = decision.get("policy_citations") or []
        if citations and contestable_items:
            citation = str(citations[0])
            if contestable_items:
                description = str(contestable_items[0].get("description") or "this item")
                return finalize([f"{description} was not covered. You can appeal this decision citing policy clause {citation}."])
            return finalize([f"You can appeal this decision citing policy clause {citation}."])
        if actionable_items:
            description = str(actionable_items[0].get("description") or "this item")
            return finalize([f"{description} was not covered. You can request a written review of this decision."])
        return finalize(["You can request a written review of this decision."])

    if status == "partially_approved":
        claimant_result = rules.get("claimant_result") or {}
        if claimant_result.get("amount_claimant_pays") is not None:
            responsibility = float(claimant_result.get("amount_claimant_pays") or 0)
        elif line_items:
            responsibility = max(0.0, sum(float(item.get("amount") or 0) for item in line_items if isinstance(item, dict)) - float(rules.get("payable_amount") or 0))
        else:
            responsibility = float(rules.get("deductible") or 0) + float(rules.get("copayment") or 0)
        item_copy = ""
        if actionable_items:
            item_copy = f" This includes the non-covered or limited item: {str(actionable_items[0].get('description') or 'a claim item')}."
        appeal_copy = " You can appeal the affected item if you believe the policy was applied incorrectly." if contestable_items else " No action is needed unless you need a written explanation of the non-covered items."
        return finalize([f"You are responsible for INR {responsibility:,.2f}.{appeal_copy}{item_copy}"])

    if status == "approved":
        if has_billing_anomaly:
            return finalize(["Review flagged billing items before proceeding."])
        return finalize(["Ask an authorized reviewer to confirm this assessment. This prototype does not submit claims or process reimbursement."])

    return finalize(["Ask an authorized reviewer to verify the claim before relying on this assessment."])


def _parse_json_response(content: str, list_key: str) -> dict[str, Any]:
    content = (content or "").strip()
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        try:
            parsed, _ = decoder.raw_decode(content)
        except json.JSONDecodeError:
            match = re.search(r"\{.*", content, flags=re.DOTALL)
            if match:
                candidate = match.group(0)
                candidate = re.sub(r",\s*([}\]])", r"\1", candidate)
                candidate += "}" * max(0, candidate.count("{") - candidate.count("}"))
                candidate += "]" * max(0, candidate.count("[") - candidate.count("]"))
                try:
                    parsed = json.loads(candidate)
                except json.JSONDecodeError as exc:
                    raise RuntimeError("Ollama returned incomplete JSON; safe fallback required.") from exc
            else:
                raise RuntimeError("Ollama returned non-JSON output.")
    if isinstance(parsed, list):
        return {list_key: parsed}
    if not isinstance(parsed, dict):
        raise RuntimeError("Ollama returned JSON that is neither an object nor an array.")
    return parsed


def _comparison_money_values(comparison: ComparisonResult) -> set[str]:
    values = {
        comparison.expected_patient_share,
        comparison.actual_patient_share,
        comparison.possible_difference,
        comparison.billed_total,
        comparison.actual_insurer_payment,
        comparison.expected_insurer_payment,
    }
    for row in comparison.categories:
        values.update({row.insurer_deducted, row.engine_disallowed, row.difference, row.payout_effect})
    return {str(value.quantize(Decimal("0.01"))) for value in values if value is not None}


def comparison_template_explanation(comparison: ComparisonResult) -> str:
    """Stable explanation used when the model is offline or fails validation."""
    if comparison.status == "manual_review":
        return "An authorized reviewer must confirm the settlement values and supporting policy evidence before this comparison can be relied on."
    disputed = [row for row in comparison.categories if row.status in {"UNEXPLAINED_DEDUCTION", "EXCESS_DEDUCTION"}]
    if not disputed:
        return "The insurer deductions match the deterministic policy calculation based on the documents provided. This remains an estimate for reviewer confirmation."
    row = disputed[0]
    clause = f" The supporting clause is on page {row.clause.page}." if row.clause else ""
    return (
        f"The documents show a possible difference of INR {comparison.possible_difference:,.2f}. "
        f"The {row.category.lower()} deduction of INR {row.insurer_deducted:,.2f} is greater than the amount supported by the deterministic rules."
        f"{clause} Please ask an authorized reviewer to confirm the documents and calculation."
    )


def validate_comparison_explanation(text: str, comparison: ComparisonResult) -> bool:
    if not isinstance(text, str) or not text.strip() or len(text.split()) > 120:
        return False
    allowed = _comparison_money_values(comparison)
    # Validate every numeric literal, not only currency-prefixed amounts. This
    # blocks fabricated percentages, counts, years, and other figures too.
    allowed_numbers = set(allowed)
    for row in comparison.categories:
        if row.clause:
            allowed_numbers.add(str(Decimal(row.clause.page).quantize(Decimal("0.01"))))
            for section_number in re.findall(r"\d+(?:\.\d+)?", str(row.clause.section or "")):
                allowed_numbers.add(str(Decimal(section_number).quantize(Decimal("0.01"))))
    for match in re.finditer(r"(?<![A-Za-z])\d[\d,]*(?:\.\d+)?", text):
        try:
            amount = Decimal(match.group(0).replace(",", "")).quantize(Decimal("0.01"))
        except Exception:
            return False
        if str(amount) not in allowed_numbers:
            return False
    clauses = [row.clause.text for row in comparison.categories if row.clause]
    quoted = re.findall(r"[\"“](.+?)[\"”]", text)
    if any(not any(quote in clause for clause in clauses) for quote in quoted):
        return False
    allowed_citations = {row.clause.section for row in comparison.categories if row.clause and row.clause.section}
    # Require a citation token beginning with a letter prefix plus a digit or
    # with a digit. Otherwise ordinary prose such as "the clause is on page 9"
    # is misread as a citation named "is" and incorrectly rejected.
    for citation in re.findall(r"\bClause\s+([A-Z]?\d[A-Za-z0-9.]*|[A-Z]\.\d[A-Za-z0-9.]*)", text, re.I):
        if citation not in allowed_citations:
            return False
    return True


def explain_comparison(comparison: ComparisonResult, use_llm: bool = True, claim_id: str | None = None) -> str:
    """Explain fixed comparison facts; invalid model text is discarded."""
    fallback = comparison_template_explanation(comparison)
    if not use_llm or comparison.status == "manual_review":
        return fallback
    categories = [
        {
            "category": row.category,
            "insurer_deducted": str(row.insurer_deducted),
            "engine_disallowed": str(row.engine_disallowed),
            "difference": str(row.difference),
            "status": row.status,
            "payout_effect": str(row.payout_effect),
            "clause": row.clause.text if row.clause else None,
            "page": row.clause.page if row.clause else None,
        }
        for row in comparison.categories
    ]
    prompt = {
        "status": comparison.status,
        "expected_patient_share": str(comparison.expected_patient_share),
        "actual_patient_share": str(comparison.actual_patient_share),
        "possible_difference": str(comparison.possible_difference),
        "categories": categories,
    }
    schema = {"type": "object", "properties": {"explanation": {"type": "string"}}, "required": ["explanation"]}
    explain_timeout = getattr(llm_gateway, "OLLAMA_EXPLAIN_TIMEOUT", 120.0)
    try:
        data = _ollama_json(
            "Explain this health insurance settlement comparison concisely. State the difference if any, the reason from the policy clauses provided, and whether the policyholder should appeal. Never contradict the numbers in the prompt.",
            json.dumps(prompt),
            list_key="explanation",
            agent_name="comparison_explainer",
            response_schema=schema,
            claim_id=claim_id,
            timeout=explain_timeout,
            acceptance_validator=lambda parsed: (
                validate_comparison_explanation(str(parsed.get("explanation") or ""), comparison),
                "Explanation numbers and citations validated",
            ),
        )
        explanation = str(data.get("explanation") or "").strip()
        if validate_comparison_explanation(explanation, comparison):
            return explanation
    except Exception:
        pass
    return fallback


def _ollama_json(system: str, prompt: str, list_key: str = "items", agent_name: str = "unknown", response_schema: dict[str, Any] | None = None, *, caller: str | None = None, prompt_version: str | None = None, acceptance_validator: Callable[[dict[str, Any]], tuple[bool, str]] | None = None, claim_id: str | None = None, timeout: Any = None) -> dict[str, Any]:
    started = time.perf_counter()
    prompt_chars = len(system) + len(prompt)
    prompt_token_estimate = max(1, round(prompt_chars / 4))
    result = llm_gateway.chat_json(
        system, prompt, caller=caller or f"agents.py:{agent_name}",
        prompt_version=prompt_version or f"{agent_name}_v1", schema=response_schema,
        model=OLLAMA_MODEL, timeout=timeout or (5, OLLAMA_TIMEOUT), num_predict=OLLAMA_NUM_PREDICT,
        num_ctx=OLLAMA_NUM_CTX, num_thread=OLLAMA_NUM_THREAD, keep_alive=OLLAMA_KEEP_ALIVE,
        temperature=0.0, claim_id=claim_id,
    )
    elapsed = time.perf_counter() - started
    response_payload = result.payload
    _record_metrics({"agent": agent_name, "elapsed_seconds": round(elapsed, 3), "prompt_chars": prompt_chars, "prompt_token_estimate": prompt_token_estimate, "keep_alive": OLLAMA_KEEP_ALIVE, "num_predict": OLLAMA_NUM_PREDICT, "load_duration_ns": response_payload.get("load_duration"), "prompt_eval_count": response_payload.get("prompt_eval_count"), "eval_count": response_payload.get("eval_count"), "timestamp": time.time()})
    if not result.ok:
        raise RuntimeError(result.error or f"Ollama request failed: {result.status}")
    try:
        content = result.text or json.dumps(result.parsed, ensure_ascii=False)
        parsed = _parse_json_response(content, list_key)
        accepted, reason = (True, "Valid response JSON accepted")
        if acceptance_validator is not None:
            try:
                accepted, reason = acceptance_validator(parsed)
            except Exception as exc:
                accepted, reason = False, f"Acceptance validator failed: {type(exc).__name__}"
    except Exception as exc:
        result.finalize(False, f"Response parsing failed: {type(exc).__name__}", agent_name)
        raise
    result.finalize(bool(accepted), reason, agent_name)
    return parsed


def retrieve_policy_evidence(policy_text: str, normalized_claim: dict[str, Any], policy_id: str = "", limit: int = 8, query: str = "") -> list[dict[str, Any]]:
    """Use persistent ChromaDB retrieval when indexed; fall back to lexical retrieval."""
    query_parts = []
    for value in normalized_claim.values():
        if isinstance(value, dict):
            candidate = value.get("value")
        elif isinstance(value, (list, tuple, set)):
            continue
        else:
            candidate = value
        if candidate not in (None, ""):
            query_parts.append(str(candidate))
    claim_query = " ".join(query_parts)
    retrieval_query = " ".join(part for part in (query.strip(), claim_query) if part)
    if policy_id:
        try:
            from mediguard.policy.policy_index import retrieve_policy_evidence as chroma_retrieve
            semantic = chroma_retrieve(retrieval_query or "coverage deductible copayment limits required documents", policy_id, limit)
            if semantic:
                return semantic
        except Exception:
            pass
    query_terms = set()
    for key in ("diagnosis", "hospital_name", "total_amount", "admission_date"):
        value = normalized_claim.get(key, {})
        if isinstance(value, dict):
            value = value.get("value")
        if value:
            query_terms.update(str(value).lower().split())
    query_terms.update({"coverage", "deductible", "copayment", "limit", "required", "documents", "waiting"})
    query_terms.update(term for term in query.lower().split() if len(term) > 2)
    chunks = re.split(r"(?<=[.!?])\s+|\n+", policy_text or "")
    scored: list[tuple[int, int, str]] = []
    for index, chunk in enumerate(chunks, start=1):
        clean = chunk.strip()
        if not clean:
            continue
        score = sum(1 for term in query_terms if term and term in clean.lower())
        if score:
            scored.append((score, index, clean))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [{"clause_id": f"policy-clause-{source_index}", "page": 1, "text": text, "relevance_score": score} for score, source_index, text in scored[:limit]]


def policy_agent_node(state: ClaimWorkflowState) -> ClaimWorkflowState:
    progress = state.get("progress_callback")
    if progress:
        progress("Policy Agent: retrieving relevant policy evidence...")
    policy_text = state.get("policy_text", "")
    normalized_claim = state.get("normalized_claim", {})
    policy_id = state.get("policy_id", "")
    rules = state.get("rule_results", {})
    # Appeal-worthy rows need the clause which actually produced their result,
    # not merely the most common claim-level terms such as deductible.
    rule_queries: list[str] = []
    for item in rules.get("line_item_results") or []:
        if not isinstance(item, dict) or item.get("status") not in {"excluded", "partial"}:
            continue
        description = str(item.get("description") or item.get("category") or "").strip()
        applied_rule = str(item.get("applied_rule") or "").replace("_", " ")
        if description or applied_rule:
            rule_queries.append(f"{description} {applied_rule}".strip())

    evidence: list[dict[str, Any]] = []
    seen_evidence: set[tuple[str, str]] = set()
    for query in rule_queries + [""]:
        candidates = retrieve_policy_evidence(policy_text, normalized_claim, policy_id, limit=2, query=query)
        for candidate in candidates:
            key = (str(candidate.get("clause_id") or ""), str(candidate.get("text") or ""))
            if key not in seen_evidence:
                seen_evidence.add(key)
                evidence.append(candidate)
    evidence = evidence[:6]
    # The Policy Agent is intentionally retrieval-only on CPU-only hardware.
    # It passes source clauses to the Decision Agent without LLM interpretation.
    findings = {
        "findings": [{"clause_id": item.get("clause_id"), "citation": item.get("clause_id"), "page": item.get("page"), "text": str(item.get("text", ""))[:350]} for item in evidence],
        "missing_evidence": [] if evidence else ["No policy evidence was retrieved."],
        "confidence": 1.0 if evidence else 0.0,
        "retrieved_evidence": evidence,
    }
    if progress:
        progress("Policy Agent complete. Decision Agent: evaluating claim and rule results...")
    return {**state, "policy_evidence": evidence, "policy_findings": findings}


def decision_agent_node(state: ClaimWorkflowState) -> ClaimWorkflowState:
    """Legacy graph adapter: forward only Python's deterministic rule result."""
    rules = state.get("rule_results", {})
    decision = {
        "status": rules.get("status", "manual_review"),
        "reasons": list(rules.get("warnings") or []),
        "policy_citations": [],
        "confidence": 1.0,
        "reviewer_note": "The estimate and status come from deterministic Python rules.",
        "line_item_notes": [],
    }
    progress = state.get("progress_callback")
    if progress:
        progress("Deterministic decision stage complete. Optional analysis runs separately.")
    return {**state, "decision": decision, "llm_calls": state.get("llm_calls", 0)}


def build_claim_graph():
    if StateGraph is None:
        raise RuntimeError("LangGraph is not installed. Run pip install -r requirements.txt.")
    graph = StateGraph(ClaimWorkflowState)
    graph.add_node("policy_agent", policy_agent_node)
    graph.add_node("decision_agent", decision_agent_node)
    graph.add_edge(START, "policy_agent")
    graph.add_edge("policy_agent", "decision_agent")
    graph.add_edge("decision_agent", END)
    return graph.compile()


def run_claim_workflow(normalized_claim: dict[str, Any], policy_text: str, rule_results: dict[str, Any], claim: dict[str, Any] | None = None, policy_id: str = "", progress_callback: Callable[[str], None] | None = None) -> dict[str, Any]:
    workflow = build_claim_graph()
    result = workflow.invoke({"claim": claim or {}, "normalized_claim": normalized_claim, "policy_text": policy_text, "policy_id": policy_id, "rule_results": rule_results, "errors": [], "llm_calls": 0, "progress_callback": progress_callback})
    return dict(result)
