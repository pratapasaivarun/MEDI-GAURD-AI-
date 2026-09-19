"""One-call LangGraph workflow: retrieval/routing are deterministic; only decision uses the LLM."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Callable, TypedDict

import requests

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
    response = requests.post(
        f"{OLLAMA_HOST}/api/generate",
        json={"model": OLLAMA_MODEL, "prompt": "Return only OK.", "stream": False, "keep_alive": OLLAMA_KEEP_ALIVE, "options": {"num_predict": 4, "num_ctx": OLLAMA_NUM_CTX, "num_thread": OLLAMA_NUM_THREAD}},
        timeout=(5, OLLAMA_TIMEOUT),
    )
    response.raise_for_status()


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
            return finalize([f"Your claim needs manual review for {description}; our team will contact you."])
        return finalize(["Your claim needs manual review; our team will contact you."])

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
        return finalize(["No action needed — reimbursement is being processed."])

    return finalize(["Your claim needs manual review; our team will contact you."])


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


def _ollama_json(system: str, prompt: str, list_key: str = "items", agent_name: str = "unknown", response_schema: dict[str, Any] | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    prompt_chars = len(system) + len(prompt)
    prompt_token_estimate = max(1, round(prompt_chars / 4))
    request_payload = {
        "model": OLLAMA_MODEL,
        "stream": False,
        "format": response_schema or "json",
        "keep_alive": OLLAMA_KEEP_ALIVE,
        # A mixed claim can require several grounded item notes. 192 tokens
        # truncated valid JSON at the configured generation boundary, so leave
        # sufficient room for the complete structured response.
        "options": {"temperature": 0.0, "num_predict": OLLAMA_NUM_PREDICT, "num_ctx": OLLAMA_NUM_CTX, "num_thread": OLLAMA_NUM_THREAD},
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
    }
    response = requests.post(
        f"{OLLAMA_HOST}/api/chat",
        json=request_payload,
        timeout=(5, OLLAMA_TIMEOUT),
    )
    response.raise_for_status()
    response_payload = response.json()
    elapsed = time.perf_counter() - started
    _record_metrics({"agent": agent_name, "elapsed_seconds": round(elapsed, 3), "prompt_chars": prompt_chars, "prompt_token_estimate": prompt_token_estimate, "keep_alive": request_payload.get("keep_alive"), "num_predict": request_payload.get("options", {}).get("num_predict"), "load_duration_ns": response_payload.get("load_duration"), "prompt_eval_count": response_payload.get("prompt_eval_count"), "eval_count": response_payload.get("eval_count"), "timestamp": time.time()})
    content = response_payload.get("message", {}).get("content", "{}")
    return _parse_json_response(content, list_key)


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
            from policy_index import retrieve_policy_evidence as chroma_retrieve
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
    progress = state.get("progress_callback")
    if not state.get("policy_evidence"):
        decision = {"status": "manual_review", "reasons": ["No policy evidence was retrieved; an authorized reviewer must verify coverage."], "policy_citations": [], "confidence": 0, "reviewer_note": "Automatic decision was blocked because policy evidence was unavailable.", "line_item_notes": [], "_fallback": True}
        if progress:
            progress("No policy evidence was retrieved. Safe Manual Review result created; Decision Agent was not called.")
        return {**state, "decision": decision}
    if progress:
        progress("Decision Agent: generating final structured decision...")
    normalized = state.get("normalized_claim", {})
    compact_claim = {key: value.get("value") for key, value in normalized.items() if isinstance(value, dict) and value.get("value") is not None and key in {"patient_name", "hospital_name", "policy_number", "diagnosis", "total_amount"}}
    policy_findings = state.get("policy_findings", {})
    compact_policy = {"evidence": policy_findings.get("findings", [])[:2], "missing_evidence": policy_findings.get("missing_evidence", [])[:3]}
    rules = state.get("rule_results", {})
    compact_rules = {key: rules.get(key) for key in ("status", "covered_amount", "deductible", "copayment", "payable_amount", "warnings") if key in rules}
    line_item_results = rules.get("line_item_results") or []
    if line_item_results:
        compact_rules["line_item_results"] = [
            {
                "item_index": index,
                "status": item.get("status"),
                "covered_amount": item.get("covered_amount"),
                "applied_rule": item.get("applied_rule"),
                "category": item.get("category"),
            }
            for index, item in enumerate(line_item_results)
        ]
    prompt = json.dumps({"claim": compact_claim, "policy": compact_policy, "rules": compact_rules}, ensure_ascii=False, separators=(",", ":"))
    try:
        decision = _ollama_json(
            "You are the Medi Gaurd Decision Agent. Use only supplied facts. Return compact JSON with status, reasons, policy_citations, confidence, reviewer_note, and optional line_item_notes. Use at most 3 short reasons and one short reviewer_note. Each line_item_notes entry must be {item_index: int, note: str}; provide at most one short sentence only for an item whose status is not covered. Only reference item_index values that appear in the line_item_results you were given below. If no line_item_results were provided, return an empty line_item_notes list and explain the decision only at the claim level, exactly as before. Never change calculated amounts; use manual_review when evidence is missing or low-confidence.",
            prompt,
            list_key="reasons",
            agent_name="decision_agent",
            response_schema=DECISION_RESPONSE_SCHEMA,
        )
    except (RuntimeError, requests.RequestException) as exc:
        decision = {"status": "manual_review", "reasons": ["Decision Agent response was unavailable or invalid."], "policy_citations": [], "confidence": 0, "reviewer_note": "An authorized reviewer must confirm the determination.", "line_item_notes": [], "_fallback": True, "_error": str(exc)}
    allowed = {"approved", "partially_approved", "rejected", "manual_review"}
    rule_status = state.get("rule_results", {}).get("status", "manual_review")
    # The LLM explains the deterministic result; it never adjudicates around
    # coverage arithmetic, exclusions, or safety gates computed by rules.py.
    decision["status"] = "manual_review" if decision.get("_fallback") else (rule_status if rule_status in allowed else "manual_review")
    evidence_ids = {str(item.get("clause_id")) for item in state.get("policy_evidence", [])}
    raw_citations = decision.get("policy_citations") or []
    raw_citations = raw_citations if isinstance(raw_citations, list) else []
    citations = [str(item) for item in raw_citations if str(item) in evidence_ids]
    decision["policy_citations"] = citations or sorted(evidence_ids)[:2]
    allowed_item_indices = {
        index for index, item in enumerate(line_item_results)
        if str(item.get("status") or "covered") != "covered"
    }
    line_item_notes = []
    seen_indices: set[int] = set()
    raw_line_item_notes = decision.get("line_item_notes") or []
    raw_line_item_notes = raw_line_item_notes if isinstance(raw_line_item_notes, list) else []
    for item in raw_line_item_notes:
        if not isinstance(item, dict):
            continue
        index = item.get("item_index")
        note = str(item.get("note") or "").strip()
        if isinstance(index, bool) or not isinstance(index, int) or index not in allowed_item_indices or index in seen_indices or not note:
            continue
        line_item_notes.append({"item_index": index, "note": note[:240]})
        seen_indices.add(index)
    decision["line_item_notes"] = line_item_notes
    _record_metrics({
        "agent": "decision_agent_groundedness",
        "policy_citations_received": len(raw_citations),
        "policy_citations_dropped": len(raw_citations) - len(citations),
        "line_item_notes_received": len(raw_line_item_notes),
        "line_item_notes_dropped": len(raw_line_item_notes) - len(line_item_notes),
        "timestamp": time.time(),
    })
    if progress:
        progress("Decision Agent complete. Rendering evidence-backed result...")
    return {**state, "decision": decision, "llm_calls": state.get("llm_calls", 0) + 1}


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
