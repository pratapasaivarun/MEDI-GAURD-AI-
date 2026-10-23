from types import SimpleNamespace

from mediguard.services.orchestration import assess_claim
from mediguard.services.storage import validate_upload
from mediguard.ui import claim_pages
import pytest


class Upload:
    def __init__(self, name, data):
        self.name = name
        self.data = data

    def getvalue(self):
        return self.data


def test_orchestration_runs_extraction_rules_then_comparison():
    calls = []
    services = SimpleNamespace(
        process_claim_documents=lambda claim_id, user_id: calls.append(("extract", claim_id, user_id)) or {"bill": 1},
        evaluate_saved_claim=lambda claim_id, user_id, normalized: calls.append(("rules", normalized)) or {"status": "approved"},
        get_user=lambda user_id: {"user_id": user_id},
        claim_documents=lambda claim_id, user: [{"document_type": "settlement"}],
        run_settlement_comparison=lambda claim_id, user_id, normalized, rules: calls.append(("compare", rules)) or ("comparison", "settlement"),
    )
    result = assess_claim(services, "claim-id", "user-id")
    assert calls == [("extract", "claim-id", "user-id"), ("rules", {"bill": 1}), ("compare", {"status": "approved"})]
    assert result == {"normalized": {"bill": 1}, "rules": {"status": "approved"}, "comparison": "comparison", "settlement": "settlement"}


def test_orchestration_keeps_missing_settlement_out_of_comparison():
    calls = []
    services = SimpleNamespace(
        process_claim_documents=lambda *_args: {"bill": 1},
        evaluate_saved_claim=lambda *_args: {"status": "manual_review"},
        get_user=lambda user_id: {"user_id": user_id},
        claim_documents=lambda *_args: [{"document_type": "policy"}, {"document_type": "medical_bill"}],
        run_settlement_comparison=lambda *_args: calls.append("comparison"),
    )
    result = assess_claim(services, "claim-id", "user-id")
    assert "comparison" not in result
    assert calls == []


def test_claimant_submission_returns_rules_result_without_waiting_for_llm(monkeypatch):
    result = {"normalized": {"total_amount": {"value": 1000}}, "rules": {"status": "approved"}}
    monkeypatch.setattr(claim_pages, "assess_claim", lambda *_args: result)
    monkeypatch.setattr(
        claim_pages, "run_agents_for_claim",
        lambda *_args, **_kwargs: pytest.fail("The claimant submit action must not wait for an LLM explanation."),
    )

    assert claim_pages._assess_claimant_submission("claim-id", "user-id") == result


def test_policy_reviewer_panel_lists_missing_terms_and_requires_source_pages():
    rows = claim_pages._policy_term_review_rows({
        "annual_limit": {"value": "100000", "source_page": 2, "confidence": 0.95, "method": "deterministic_regex"},
    })
    by_term = {row["Term"]: row for row in rows}
    assert by_term["Annual Limit"]["Candidate value"] == "100000"
    assert by_term["Annual Limit"]["Source page"] == "2"
    assert by_term["Deductible"]["Candidate value"] == "Not identified"
    assert by_term["Deductible"]["Source page"] == "Not identified"
    assert "source page" in by_term["Deductible"]["Evidence"]
    assert "Co-Payment Percentage" in by_term
    assert "Non-Payable Categories" in by_term


def test_claim_assistant_names_the_specific_manual_review_reason():
    answer = claim_pages._claim_answer_from_saved_data(
        "Why is my claim under review?",
        {"status": "manual_review", "reason": "Co-payment percentage: page not identified; no reliable value is available."},
        {}, [],
    )
    assert "Co-payment percentage" in answer
    assert "page not identified" in answer
    assert "source value or document issue" in answer
    assert "confirm the bill details and applicable policy terms first" not in answer


def test_reviewer_workspace_remembers_the_active_step_after_a_rerun(monkeypatch):
    state = {}
    monkeypatch.setattr(claim_pages, "st", SimpleNamespace(session_state=state))
    claim_pages._remember_claim_review_tab("claim-1", 4)
    assert claim_pages._claim_review_tab_default("claim-1") == "5 · Compare settlement & draft letters"


def test_reviewer_tabs_track_selection_across_streamlit_reruns(monkeypatch):
    captured = {}
    tabs = [object() for _ in range(5)]
    monkeypatch.setattr(claim_pages, "st", SimpleNamespace(
        session_state={},
        tabs=lambda labels, **kwargs: captured.update(labels=labels, kwargs=kwargs) or tabs,
    ))
    assert claim_pages._claim_review_tabs("claim-1") is tabs
    assert captured["kwargs"]["key"] == "claim_review_tabs_claim-1"
    assert captured["kwargs"]["on_change"] == "rerun"


def test_policy_link_picker_prefers_confirmed_matching_edition_when_none_linked():
    editions = [
        {"version_id": "claim-upload", "policy_number": "POL-FICT-001", "terms_review_status": "pending"},
        {"version_id": "reviewed", "policy_number": "POL-FICT-001", "terms_review_status": "confirmed"},
        {"version_id": "other", "policy_number": "POL-OTHER", "terms_review_status": "confirmed"},
    ]
    assert claim_pages._policy_edition_default_index(editions, None, "POL-FICT-001") == 1
    assert claim_pages._policy_edition_default_index(editions, "claim-upload", "POL-FICT-001") == 0


def test_storage_upload_validator_keeps_file_checks_in_service_layer():
    content, name = validate_upload(Upload("bill.pdf", b"%PDF-1.4 fictional"), "medical_bill", 1)
    assert content == b"%PDF-1.4 fictional"
    assert name == "bill.pdf"
