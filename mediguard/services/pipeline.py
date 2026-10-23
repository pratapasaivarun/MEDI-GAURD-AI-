"""Deterministic LangGraph supervisor for the claim assessment workflow.

The graph carries claim ids and compact stage results. Application services
are captured by the node functions, so database handles and document bytes do
not become graph state.
"""
from __future__ import annotations

from functools import lru_cache
import logging
import time
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

logger = logging.getLogger(__name__)


class ClaimPipelineState(TypedDict, total=False):
    claim_id: str
    user_id: str
    audit_actor_id: str
    normalized: dict[str, Any]
    rules: dict[str, Any]
    comparison: Any
    settlement: Any
    appeal_eligible: bool
    analysis_job: str
    node_timings: dict[str, float]
    result: dict[str, Any]


def _build_graph(app_services: Any):
    def document_node(state: ClaimPipelineState) -> dict[str, Any]:
        started = time.perf_counter()
        normalized = app_services.process_claim_documents(state["claim_id"], state["user_id"])
        elapsed = round(time.perf_counter() - started, 4)
        logger.info("Pipeline node 'document' completed in %.4fs", elapsed)
        timings = dict(state.get("node_timings") or {})
        timings["document"] = elapsed
        return {"normalized": normalized, "node_timings": timings}

    def policy_node(state: ClaimPipelineState) -> dict[str, Any]:
        started = time.perf_counter()
        audit_actor_id = state.get("audit_actor_id")
        if audit_actor_id:
            rules = app_services.evaluate_saved_claim(
                state["claim_id"], state["user_id"], state["normalized"], audit_actor_id=audit_actor_id
            )
        else:
            rules = app_services.evaluate_saved_claim(state["claim_id"], state["user_id"], state["normalized"])
        elapsed = round(time.perf_counter() - started, 4)
        logger.info("Pipeline node 'policy' completed in %.4fs", elapsed)
        timings = dict(state.get("node_timings") or {})
        timings["policy"] = elapsed
        return {"rules": rules, "node_timings": timings}

    def decision_node(state: ClaimPipelineState) -> dict[str, Any]:
        started = time.perf_counter()
        claim = app_services.get_user(state["user_id"])
        documents = app_services.claim_documents(state["claim_id"], claim)
        timings = dict(state.get("node_timings") or {})
        if not any(document["document_type"] == "settlement" for document in documents):
            elapsed = round(time.perf_counter() - started, 4)
            logger.info("Pipeline node 'decision' skipped (no settlement letter) in %.4fs", elapsed)
            timings["decision"] = elapsed
            return {"node_timings": timings}
        comparison, settlement = app_services.run_settlement_comparison(
            state["claim_id"], state["user_id"], state["normalized"], state["rules"]
        )
        elapsed = round(time.perf_counter() - started, 4)
        logger.info("Pipeline node 'decision' completed in %.4fs", elapsed)
        timings["decision"] = elapsed
        return {"comparison": comparison, "settlement": settlement, "node_timings": timings}

    def output_node(state: ClaimPipelineState) -> dict[str, Any]:
        started = time.perf_counter()
        comparison = state.get("comparison")
        appeal_check = getattr(app_services, "appeal_draft_available", None)
        appeal_eligible = bool(comparison is not None and callable(appeal_check) and appeal_check(comparison))
        result: dict[str, Any] = {"normalized": state["normalized"], "rules": state["rules"]}
        if comparison is not None:
            result.update(comparison=comparison, settlement=state.get("settlement"))
        elapsed = round(time.perf_counter() - started, 4)
        logger.info("Pipeline node 'output' completed in %.4fs", elapsed)
        timings = dict(state.get("node_timings") or {})
        timings["output"] = elapsed
        return {"appeal_eligible": appeal_eligible, "result": result, "node_timings": timings}

    def enqueue_analysis_node(state: ClaimPipelineState) -> dict[str, Any]:
        # Phase 4 supplies this optional queue hook. Until then the pipeline
        # records that analysis is deferred and never starts a model call here.
        started = time.perf_counter()
        enqueue = getattr(app_services, "enqueue_analysis_job", None)
        timings = dict(state.get("node_timings") or {})
        if not callable(enqueue):
            elapsed = round(time.perf_counter() - started, 4)
            timings["enqueue_analysis"] = elapsed
            return {"analysis_job": "deferred", "node_timings": timings}
        job_id = enqueue(state["claim_id"], state["user_id"], state["result"])
        elapsed = round(time.perf_counter() - started, 4)
        logger.info("Pipeline node 'enqueue_analysis' completed in %.4fs", elapsed)
        timings["enqueue_analysis"] = elapsed
        return {"analysis_job": str(job_id or "queued"), "node_timings": timings}

    graph = StateGraph(ClaimPipelineState)
    graph.add_node("document", document_node)
    graph.add_node("policy", policy_node)
    graph.add_node("decision", decision_node)
    graph.add_node("output", output_node)
    graph.add_node("enqueue_analysis", enqueue_analysis_node)
    graph.set_entry_point("document")
    graph.add_edge("document", "policy")
    graph.add_edge("policy", "decision")
    graph.add_edge("decision", "output")
    graph.add_edge("output", "enqueue_analysis")
    graph.add_edge("enqueue_analysis", END)
    return graph.compile()


@lru_cache(maxsize=8)
def _cached_graph(app_services: Any):
    return _build_graph(app_services)


def run_claim_pipeline(app_services: Any, claim_id: str, user_id: str, *, audit_actor_id: str | None = None) -> dict[str, Any]:
    """Run the automatic document, policy, decision and output stages."""
    try:
        graph = _cached_graph(app_services)
    except TypeError:
        # Unhashable test doubles can still use the exact same graph.
        graph = _build_graph(app_services)
    initial = {"claim_id": str(claim_id), "user_id": str(user_id)}
    if audit_actor_id:
        initial["audit_actor_id"] = str(audit_actor_id)
    state = graph.invoke(initial)
    return state["result"]
