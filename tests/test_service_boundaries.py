from types import SimpleNamespace

from services.orchestration import assess_claim
from services.storage import validate_upload


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


def test_storage_upload_validator_keeps_file_checks_in_service_layer():
    content, name = validate_upload(Upload("bill.pdf", b"%PDF-1.4 fictional"), "medical_bill", 1)
    assert content == b"%PDF-1.4 fictional"
    assert name == "bill.pdf"
