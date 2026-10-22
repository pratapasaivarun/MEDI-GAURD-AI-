"""Application-level sequence for document extraction and deterministic rules."""
from __future__ import annotations

from typing import Any
from mediguard.ai.llm_gateway import claim_context
from mediguard.services.pipeline import run_claim_pipeline


def assess_claim(app_services: Any, claim_id: str, user_id: str, *, audit_actor_id: str | None = None) -> dict[str, Any]:
    """Thin compatibility wrapper around the deterministic claim supervisor."""
    with claim_context(claim_id):
        return run_claim_pipeline(app_services, claim_id, user_id, audit_actor_id=audit_actor_id)
