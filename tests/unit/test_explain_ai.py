from __future__ import annotations

from decimal import Decimal
import json
from types import SimpleNamespace

from mediguard.ai.agents import (
    comparison_template_explanation,
    explain_comparison,
    validate_comparison_explanation,
)
from mediguard.engine.models import CategoryComparison, Clause, ComparisonResult


def _sample_comparison(status="possible_discrepancy"):
    clause = Clause(page=2, section="Clause 4.1", text="Room rent limit is 1% of sum insured.")
    category = CategoryComparison(
        category="ROOM_RENT",
        insurer_deducted=Decimal("2000.00"),
        engine_disallowed=Decimal("1000.00"),
        difference=Decimal("1000.00"),
        status="EXCESS_DEDUCTION",
        insurer_reason="Exceeded room rent limit",
        engine_reason="Room rent capped at 1000.00",
        clause=clause,
        payout_effect=Decimal("1000.00"),
    )
    return ComparisonResult(
        status=status,
        expected_insurer_payment=Decimal("8000.00"),
        actual_insurer_payment=Decimal("7000.00"),
        possible_difference=Decimal("1000.00"),
        expected_patient_share=Decimal("2000.00"),
        actual_patient_share=Decimal("3000.00"),
        billed_total=Decimal("10000.00"),
        categories=[category],
        review_reasons=[],
    )


def test_explain_comparison_use_llm_false_returns_template():
    comp = _sample_comparison()
    res = explain_comparison(comp, use_llm=False)
    assert res == comparison_template_explanation(comp)
    assert "1,000.00" in res


def test_explain_comparison_ollama_offline_returns_template_safely(monkeypatch):
    from mediguard.ai import llm_gateway

    def offline(*_args, **_kwargs):
        raise ConnectionError("Ollama offline")

    monkeypatch.setattr(llm_gateway.requests, "post", offline)
    comp = _sample_comparison()
    # Must never crash, must return template
    res = explain_comparison(comp, use_llm=True, claim_id="claim-offline-test")
    assert res == comparison_template_explanation(comp)


def test_explain_comparison_validates_and_rejects_hallucinated_numbers(monkeypatch):
    from mediguard.ai import llm_gateway
    comp = _sample_comparison()

    # Model returns an invented number (e.g. INR 99,999.00)
    def fake_chat(*_args, **_kwargs):
        return llm_gateway.GatewayResult(
            request_id="id",
            status="ok",
            caller="test",
            prompt_version="test",
            endpoint="/api/chat",
            model="test",
            elapsed_seconds=0.05,
            claim_id="claim-test",
            text='{"explanation": "The insurer owes you INR 99999.00 under Clause 4.1."}',
            parsed={"explanation": "The insurer owes you INR 99999.00 under Clause 4.1."},
        )

    monkeypatch.setattr(llm_gateway, "chat_json", fake_chat)
    res = explain_comparison(comp, use_llm=True, claim_id="claim-hallucination-test")
    # Must reject and fall back to template!
    assert res == comparison_template_explanation(comp)
    assert "99999" not in res


def test_explain_comparison_accepts_grounded_explanation(monkeypatch):
    from mediguard.ai import llm_gateway
    comp = _sample_comparison()

    grounded_text = "The difference is INR 1,000.00. The supporting clause is on page 2."
    assert validate_comparison_explanation(grounded_text, comp)

    def fake_chat(*_args, **_kwargs):
        return llm_gateway.GatewayResult(
            request_id="id",
            status="ok",
            caller="test",
            prompt_version="test",
            endpoint="/api/chat",
            model="test",
            elapsed_seconds=0.05,
            claim_id="claim-test",
            text=json.dumps({"explanation": grounded_text}),
            parsed={"explanation": grounded_text},
        )

    monkeypatch.setattr(llm_gateway, "chat_json", fake_chat)
    res = explain_comparison(comp, use_llm=True, claim_id="claim-grounded-test")
    assert res == grounded_text
