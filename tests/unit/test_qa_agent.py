from copy import deepcopy

from mediguard.ai import qa


def test_qa_rejects_unsupported_numbers_and_clause_ids():
    facts = {"estimated_payment": 9000, "status": "possible_discrepancy"}
    evidence = [{"clause_id": "4.2", "page": 3, "text": "Pharmacy charges are payable."}]
    assert qa.validate_qa_output(
        {"answer": "The payment is INR 9000 and clause 9.1 supports it.", "used_clause_ids": ["9.1"]},
        facts,
        evidence,
    ) == (False, "Q&A cited a clause that was not retrieved")
    assert qa.validate_qa_output(
        {"answer": "The payment is INR 7000.", "used_clause_ids": []}, facts, evidence
    ) == (False, "Q&A used a number that was not present in the claim facts or policy evidence")


def test_qa_with_no_evidence_returns_fixed_answer_without_calling_model(monkeypatch):
    monkeypatch.setattr(qa.llm_gateway, "chat_json", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not call model")))
    assert qa.answer_with_llm("What is covered?", {"status": "approved"}, [], "claim-1") == qa.NO_EVIDENCE_ANSWER


def test_qa_deterministic_answer_wins_without_calling_model_or_mutating_claim(monkeypatch):
    result = {"status": "approved", "amount_covered": 12000}
    before = deepcopy(result)
    monkeypatch.setattr(qa.llm_gateway, "chat_json", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not call model")))
    answer = qa.answer_question("How much will insurance pay?", result, [], "claim-1")
    assert answer == "The insurer payable estimate is INR 12,000.00."
    assert result == before


def test_qa_accepts_grounded_model_answer_and_keeps_claim_read_only(monkeypatch):
    result = {"status": "possible_discrepancy", "amount_covered": 9000}
    before = deepcopy(result)

    class Response:
        ok = True
        parsed = {"answer": "The policy says pharmacy charges are payable.", "used_clause_ids": ["4.2"]}

        def finalize(self, accepted, reason, accepted_into):
            self.finalized = (accepted, reason, accepted_into)

    response = Response()
    monkeypatch.setattr(qa.llm_gateway, "chat_json", lambda *_args, **_kwargs: response)
    monkeypatch.setattr(qa.llm_gateway, "is_ollama_available", lambda **_kwargs: True)
    evidence = [{"clause_id": "4.2", "page": 3, "text": "Pharmacy charges are payable."}]
    answer = qa.answer_question("What does clause 4.2 say?", result, evidence, "claim-1")
    assert answer == response.parsed["answer"]
    assert response.finalized[0] is True
    assert result == before


def test_qa_ollama_offline_returns_safe_fallback(monkeypatch):
    result = {"status": "possible_discrepancy", "amount_covered": 9000}
    evidence = [{"clause_id": "4.2", "page": 3, "text": "Pharmacy charges are payable."}]

    class OfflineResponse:
        ok = False
        error = "Ollama offline"
        status = "unavailable"
        parsed = None

        def finalize(self, accepted, reason, accepted_into):
            pass

    monkeypatch.setattr(qa.llm_gateway, "chat_json", lambda *_args, **_kwargs: OfflineResponse())
    monkeypatch.setattr(qa.llm_gateway, "is_ollama_available", lambda **_kwargs: True)
    answer = qa.answer_question("What does clause 4.2 say?", result, evidence, "claim-1")
    assert answer == qa.NO_EVIDENCE_ANSWER
