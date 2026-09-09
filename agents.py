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
DECISION_RESPONSE_SCHEMA = {"type": "object", "properties": {"status": {"type": "string", "enum": ["approved", "partially_approved", "rejected", "manual_review"]}, "reasons": {"type": "array", "items": {"type": "string"}}, "policy_citations": {"type": "array", "items": {"type": "string"}}, "confidence": {"type": "number"}, "reviewer_note": {"type": "string"}}, "required": ["status", "reasons", "policy_citations", "confidence", "reviewer_note"]}
METRICS_PATH = Path(__import__("os").getenv("AGENT_METRICS_PATH", "data/agent_metrics.jsonl"))


def warm_ollama() -> None:
    """Preload Granite once before the first real agent call in a session."""
    response = requests.post(
        f"{OLLAMA_HOST}/api/generate",
        json={"model": OLLAMA_MODEL, "prompt": "Return only OK.", "stream": False, "keep_alive": OLLAMA_KEEP_ALIVE, "options": {"num_predict": 4}},
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
        "options": {"temperature": 0.0, "num_predict": 192, "num_ctx": OLLAMA_NUM_CTX, "num_thread": OLLAMA_NUM_THREAD},
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


def retrieve_policy_evidence(policy_text: str, normalized_claim: dict[str, Any], policy_id: str = "", limit: int = 8) -> list[dict[str, Any]]:
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
    query = " ".join(query_parts)
    if policy_id:
        try:
            from policy_index import retrieve_policy_evidence as chroma_retrieve
            semantic = chroma_retrieve(query or "coverage deductible copayment limits required documents", policy_id, limit)
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
    chunks = re.split(r"(?<=[.!?])\s+|\n+", policy_text or "")
    scored: list[tuple[int, str]] = []
    for index, chunk in enumerate(chunks, start=1):
        clean = chunk.strip()
        if not clean:
            continue
        score = sum(1 for term in query_terms if term and term in clean.lower())
        if score:
            scored.append((score, clean))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [{"clause_id": f"policy-clause-{index}", "page": 1, "text": text, "relevance_score": score} for index, (score, text) in enumerate(scored[:limit], start=1)]


def policy_agent_node(state: ClaimWorkflowState) -> ClaimWorkflowState:
    progress = state.get("progress_callback")
    if progress:
        progress("Policy Agent: retrieving relevant policy evidence...")
    evidence = retrieve_policy_evidence(state.get("policy_text", ""), state.get("normalized_claim", {}), state.get("policy_id", ""), limit=2)
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
        decision = {"status": "manual_review", "reasons": ["No policy evidence was retrieved; an authorized reviewer must verify coverage."], "policy_citations": [], "confidence": 0, "reviewer_note": "Automatic decision was blocked because policy evidence was unavailable.", "_fallback": True}
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
    prompt = json.dumps({"claim": compact_claim, "policy": compact_policy, "rules": compact_rules}, ensure_ascii=False, separators=(",", ":"))
    try:
        decision = _ollama_json(
            "You are the Medi Gaurd Decision Agent. Use only supplied facts. Return compact JSON with status, reasons, policy_citations, confidence, reviewer_note. Use at most 3 short reasons and one short reviewer_note. Never change calculated amounts; use manual_review when evidence is missing or low-confidence.",
            prompt,
            list_key="reasons",
            agent_name="decision_agent",
            response_schema=DECISION_RESPONSE_SCHEMA,
        )
    except (RuntimeError, requests.RequestException) as exc:
        decision = {"status": "manual_review", "reasons": ["Decision Agent response was unavailable or invalid."], "policy_citations": [], "confidence": 0, "reviewer_note": "An authorized reviewer must confirm the determination.", "_fallback": True, "_error": str(exc)}
    allowed = {"approved", "partially_approved", "rejected", "manual_review"}
    rule_status = state.get("rule_results", {}).get("status", "manual_review")
    # The LLM explains the deterministic result; it never adjudicates around
    # coverage arithmetic, exclusions, or safety gates computed by rules.py.
    decision["status"] = rule_status if rule_status in allowed else "manual_review"
    evidence_ids = {str(item.get("clause_id")) for item in state.get("policy_evidence", [])}
    citations = [str(item) for item in decision.get("policy_citations", []) if str(item) in evidence_ids]
    decision["policy_citations"] = citations or sorted(evidence_ids)[:2]
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
