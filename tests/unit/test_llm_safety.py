from decimal import Decimal

import pytest
import requests

import mediguard.ai.agents as agents
from test_comparison_reports import _comparison


@pytest.mark.parametrize("failure", [
    requests.ConnectionError("model is down"),
    requests.Timeout("model timed out"),
    RuntimeError("malformed model output"),
])
def test_explanation_uses_template_when_model_is_down_timed_out_or_malformed(monkeypatch, failure):
    comparison = _comparison()
    fallback = agents.comparison_template_explanation(comparison)
    def fail(*_args, **_kwargs):
        raise failure
    monkeypatch.setattr(agents, "_ollama_json", fail)
    assert agents.explain_comparison(comparison, use_llm=True) == fallback
    assert comparison.status == "possible_discrepancy"
    assert comparison.possible_difference == Decimal("9000")


def test_explanation_rejects_any_number_not_in_rules_or_clause_output():
    comparison = _comparison()
    assert not agents.validate_comparison_explanation("The claim has 2 issues.", comparison)
    assert not agents.validate_comparison_explanation("The co-pay is 10 percent.", comparison)
    assert agents.validate_comparison_explanation("The difference is INR 9,000.00; see page 9.", comparison)


def test_grounding_validator_accepts_clause_prose_with_a_supported_page():
    comparison = _comparison()
    text = "The difference is INR 9,000.00. The supporting clause is on page 9."
    assert agents.validate_comparison_explanation(text, comparison)


def test_valid_model_explanation_does_not_change_claim_comparison(monkeypatch):
    comparison = _comparison()
    original = (comparison.status, comparison.possible_difference, comparison.expected_patient_share)
    monkeypatch.setattr(agents, "_ollama_json", lambda *_args, **_kwargs: {"explanation": "The difference is INR 9,000.00; see page 9."})
    explanation = agents.explain_comparison(comparison, use_llm=True)
    assert explanation == "The difference is INR 9,000.00; see page 9."
    assert (comparison.status, comparison.possible_difference, comparison.expected_patient_share) == original
