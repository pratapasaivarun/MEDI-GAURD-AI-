import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from mediguard.ai import qa


ROOT = Path(__file__).parents[2]
FIXTURE_CASES = (
    ("demo_cases/a_match", "expected"),
    ("demo_cases/b_wrongful_deduction", "expected"),
    ("demo_cases/c_manual_review", "expected"),
    ("claim_scenarios/partially_approved/03_room_limit_proportional", None),
    ("claim_scenarios/rejected/01_confirmed_exclusion", None),
    ("claim_scenarios/manual_review/04_incomplete_bill_fields", None),
)

SUPPORTED_QUESTIONS = (
    "Why do I have to pay?",
    "How much will insurance pay?",
    "What is the total bill and eligible amount?",
    "What is my deductible?",
    "What is my copay?",
    "What is excluded or limited?",
    "What is the settlement difference?",
    "Why is this charge not covered because of the room limit?",
    "Which policy terms are unconfirmed?",
    "Is an appeal available and what should I do next?",
    "Why was the claim sent to Manual Review?",
)


def _fixture(path: str) -> tuple[dict, dict]:
    payload = json.loads((ROOT / "samples" / path / "case.json").read_text(encoding="utf-8"))
    expected = payload.get("expected") or {}
    result = {
        "status": expected.get("expected_status", payload.get("expected_status")),
        "amount_billed": expected.get("bill_total", payload.get("expected_bill_total")),
        "amount_covered": expected.get("expected_insurer_payment"),
        "amount_claimant_pays": expected.get("expected_patient_share"),
        "covered_before_cost_sharing": expected.get("covered_before_cost_share"),
        "deductible": expected.get("deductible"),
        "copayment": expected.get("copay"),
        "amount_excluded_or_limited": expected.get("excluded_or_limited"),
        "reason": expected.get("manual_review_reason"),
    }
    calculation = payload.get("calculation") or {}
    result["rules"] = {
        "policy_terms_review_status": "preconfirmed_fictional_sample" if path.startswith("demo_cases/") else None,
        "line_item_results": calculation.get("line_item_results", []),
    }
    comparison = None
    if path.startswith("demo_cases/"):
        status = expected.get("expected_status")
        categories = []
        if path.endswith("b_wrongful_deduction"):
            categories = [SimpleNamespace(
                category="INVESTIGATION",
                status="UNEXPLAINED_DEDUCTION",
                insurer_reason=calculation["settlement_explanation"],
                clause=SimpleNamespace(section="Coverage", page=expected.get("supporting_clause_page")),
            )]
        comparison = SimpleNamespace(
            status=status,
            possible_difference=expected.get("possible_difference"),
            categories=categories,
            review_reasons=[expected["manual_review_reason"]] if expected.get("manual_review_reason") else [],
        )
    return result, {"comparison": comparison}


@pytest.mark.parametrize(("fixture_path", "_expected_key"), FIXTURE_CASES)
def test_each_saved_claim_fixture_answers_all_deterministic_intents_without_llm(
    fixture_path, _expected_key, monkeypatch,
):
    result, context = _fixture(fixture_path)
    monkeypatch.setattr(
        qa.llm_gateway, "is_ollama_available",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("deterministic intent checked Ollama")),
    )
    monkeypatch.setattr(
        qa.llm_gateway, "chat_json",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("deterministic intent called model")),
    )

    for question in SUPPORTED_QUESTIONS:
        answer = qa.answer_question(
            question, result, [], "fixture-claim", comparison=context["comparison"]
        )
        assert answer.strip()
        assert answer != qa.UNKNOWN_ANSWER
    for question, key in (
        (SUPPORTED_QUESTIONS[1], "amount_covered"),
        (SUPPORTED_QUESTIONS[3], "deductible"),
        (SUPPORTED_QUESTIONS[4], "copayment"),
        (SUPPORTED_QUESTIONS[5], "amount_excluded_or_limited"),
    ):
        answer = qa.answer_question(
            question, result, [], "fixture-claim", comparison=context["comparison"]
        )
        assert qa._money(result.get(key)) in answer

    bill = result["amount_billed"]
    eligible = result["covered_before_cost_sharing"]
    total_answer = qa.answer_question(
        SUPPORTED_QUESTIONS[2], result, [], "fixture-claim",
        comparison=context["comparison"],
    )
    assert qa._money(bill) in total_answer
    assert qa._money(eligible) in total_answer


def test_wrongful_deduction_payable_breakdown_and_noisy_question_use_saved_values(monkeypatch):
    result, context = _fixture("demo_cases/b_wrongful_deduction")
    result.update({
        "amount_claimant_pays": 24500,
        "amount_excluded_or_limited": 12000,
        "amount_covered": 22500,
        "covered_before_cost_sharing": 35000,
        "deductible": 10000,
        "copayment": 2500,
        "amount_billed": 47000,
    })
    monkeypatch.setattr(
        qa.llm_gateway, "is_ollama_available",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("deterministic intent checked Ollama")),
    )
    question = (
        "Why do I have to pay INR 24,500 when the hospital bill is 47,000 "
        "and I have insurance? Pasted note: please see the attached statement."
    )
    answer = qa.answer_question(question, result, [], "b_wrongful_deduction", comparison=context["comparison"])
    for amount in (24500, 10000, 2500, 12000, 35000, 22500):
        assert qa._money(amount) in answer
    assert "cost-sharing, not rejected charges" in answer


def test_component_values_are_individual_and_missing_values_are_not_zero(monkeypatch):
    result = {"status": "manual_review", "amount_billed": 1200, "deductible": None, "copayment": None}
    monkeypatch.setattr(qa.llm_gateway, "is_ollama_available", lambda **_kwargs: False)
    for question in ("What is my deductible?", "What is my copay?", "What amount was excluded?"):
        answer = qa.answer_question(question, result, [], "missing-values")
        assert "unavailable" in answer
        assert "INR 0.00" not in answer


def test_room_limit_and_related_charge_answers_use_saved_calculation_notes(monkeypatch):
    monkeypatch.setattr(
        qa.llm_gateway, "is_ollama_available",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("saved calculation notes must not check Ollama")),
    )
    result = {
        "status": "partially_approved",
        "rules": {
            "line_item_results": [
                {
                    "description": "Room charge",
                    "status": "partial",
                    "applied_rule": "room_limit",
                    "calculation": "Room charge capped at INR 15,000 for 3 days.",
                },
                {
                    "description": "Doctor and nursing charges",
                    "status": "partial",
                    "applied_rule": "proportionate_deduction",
                    "calculation": "Room-linked charges scaled by 0.5 because the room cap was exceeded.",
                },
            ],
        },
    }
    answer = qa.answer_question("Why were room and related charges limited?", result, [], "room-limit")
    assert "Room charge: Room charge capped at INR 15,000 for 3 days." in answer
    assert "Doctor and nursing charges: Room-linked charges scaled by 0.5" in answer


def test_no_appeal_without_discrepancy_or_comparison(monkeypatch):
    monkeypatch.setattr(qa.llm_gateway, "is_ollama_available", lambda **_kwargs: False)
    result, context = _fixture("demo_cases/a_match")
    answer = qa.answer_question("Is an appeal available?", result, [], "a_match", comparison=context["comparison"])
    assert "No appeal draft is offered" in answer
    assert "no possible discrepancy" in answer
    missing = qa.answer_question("What is the settlement difference?", result, [], "a_match")
    assert "No saved settlement comparison" in missing
    discrepant, comparison_context = _fixture("demo_cases/b_wrongful_deduction")
    offered = qa.answer_question(
        "What are my next steps, and can I appeal?",
        discrepant, [], "b_wrongful_deduction",
        comparison=comparison_context["comparison"],
    )
    assert "appeal draft is available" in offered


def test_settlement_difference_names_flagged_line_and_policy_reference_only_for_discrepancy(monkeypatch):
    result, context = _fixture("demo_cases/b_wrongful_deduction")
    monkeypatch.setattr(qa.llm_gateway, "is_ollama_available", lambda **_kwargs: False)
    answer = qa.answer_question(
        "How much is the settlement payment below the estimate?",
        result, [], "b_wrongful_deduction", comparison=context["comparison"],
    )
    assert qa._money(2700) in answer
    assert "investigation" in answer
    assert "page 1" in answer
    no_difference = qa.answer_question(
        "What is the settlement difference?", result, [], "a_match",
        comparison=SimpleNamespace(status="no_discrepancy", possible_difference=0, categories=[]),
    )
    assert "no possible discrepancy" in no_difference
    assert "page" not in no_difference


def test_unconfirmed_terms_are_not_applied_and_provisional_notice_is_always_shown(monkeypatch):
    monkeypatch.setattr(qa.llm_gateway, "is_ollama_available", lambda **_kwargs: False)
    result = {
        "status": "provisional",
        "policy_terms_review_status": "provisional",
        "policy_terms_issues": [{
            "term": "deductible",
            "reason": "Deductible: page 2; low-confidence candidate was not applied until review.",
        }],
        "amount_covered": 10000,
    }
    answer = qa.answer_question("Why was the deductible not applied?", result, [], "provisional-claim")
    assert "not applied until review" in answer
    assert "may change after authorized review" in answer
    general = qa.answer_question("How much will insurance pay?", result, [], "provisional-claim")
    assert qa.PROVISIONAL_NOTICE in general


def test_hypothetical_legal_off_topic_and_unknown_questions_are_safe(monkeypatch):
    monkeypatch.setattr(
        qa.llm_gateway, "is_ollama_available",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("special responses must not check Ollama")),
    )
    monkeypatch.setattr(
        qa.llm_gateway, "chat_json",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("special responses must not call model")),
    )
    result = {"status": "approved", "deductible": 10000}
    hypothetical = qa.answer_question("What if my deductible was INR 5,000?", result, [], "claim-1")
    assert "can't recalculate hypothetical amounts" in hypothetical
    assert "INR 5,000" not in hypothetical
    legal = qa.answer_question("Will I win if I complain to the ombudsman?", result, [], "claim-1")
    assert "can't predict an outcome" in legal
    assert "not legal or insurance advice" in legal
    off_topic = qa.answer_question("What is the weather tomorrow?", result, [], "claim-1")
    assert off_topic == qa.OFF_TOPIC_ANSWER
    monkeypatch.setattr(qa.llm_gateway, "is_ollama_available", lambda **_kwargs: False)
    unknown = qa.answer_question("What is the claim's internal case category?", result, [], "claim-1")
    assert unknown == qa.UNKNOWN_ANSWER
    assert "How much will the insurer pay?" in unknown
    assert "Manual Review" in unknown


def test_question_normalization_handles_currency_commas_quotes_and_pasted_text():
    question = '"Why do I have to pay Rs. 24,500 when the hospital bill is INR 47,000?" copied below'
    assert qa.classify_intent(question) == "why_pay"
    assert "24500" in qa.normalize_question(question)
    assert "47000" in qa.normalize_question(question)


def test_unknown_question_uses_existing_llm_path_only_when_available(monkeypatch):
    result = {"status": "approved"}
    evidence = [{"clause_id": "4.2", "page": 3, "text": "Policy language."}]
    monkeypatch.setattr(qa.llm_gateway, "is_ollama_available", lambda **_kwargs: True)
    monkeypatch.setattr(qa, "answer_with_llm", lambda *_args: "Saved-facts fallback.")
    assert qa.answer_question(
        "What is the claim's internal case category?", result, evidence, "claim-1"
    ) == "Saved-facts fallback."
