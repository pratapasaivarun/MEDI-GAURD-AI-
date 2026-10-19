"""Application-level sequence for document extraction and deterministic rules."""
from __future__ import annotations

from typing import Any


def assess_claim(app_services: Any, claim_id: str, user_id: str) -> dict[str, Any]:
    """Run the same extraction/rules/comparison steps used by the claimant UI."""
    normalized = app_services.process_claim_documents(claim_id, user_id)
    rules = app_services.evaluate_saved_claim(claim_id, user_id, normalized)
    result: dict[str, Any] = {"normalized": normalized, "rules": rules}
    documents = app_services.claim_documents(claim_id, app_services.get_user(user_id))
    if any(document["document_type"] == "settlement" for document in documents):
        comparison, settlement = app_services.run_settlement_comparison(claim_id, user_id, normalized, rules)
        result.update(comparison=comparison, settlement=settlement)
    return result
