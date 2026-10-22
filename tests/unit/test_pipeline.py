from types import SimpleNamespace

from mediguard.services.orchestration import assess_claim


def test_assess_claim_runs_deterministic_stages_in_graph_order():
    events = []
    normalized = {"total_amount": {"value": 12000}}
    rules = {"status": "possible_discrepancy", "payable_amount": 8000}
    comparison = SimpleNamespace(status="possible_discrepancy")
    settlement = SimpleNamespace(amount_paid=7000)

    class Services:
        def process_claim_documents(self, claim_id, user_id):
            events.append("document")
            assert (claim_id, user_id) == ("claim-1", "user-1")
            return normalized

        def evaluate_saved_claim(self, claim_id, user_id, value):
            events.append("policy")
            assert value is normalized
            return rules

        def get_user(self, user_id):
            events.append("get_user")
            return {"user_id": user_id}

        def claim_documents(self, claim_id, user):
            events.append("documents")
            return [{"document_type": "settlement"}]

        def run_settlement_comparison(self, claim_id, user_id, value, rules_value):
            events.append("decision")
            assert value is normalized and rules_value is rules
            return comparison, settlement

        @staticmethod
        def appeal_draft_available(value):
            events.append("output")
            return value.status == "possible_discrepancy"

        def enqueue_analysis_job(self, claim_id, user_id, result):
            events.append("enqueue_analysis")
            assert result["comparison"] is comparison
            return "job-1"

    result = assess_claim(Services(), "claim-1", "user-1")

    assert events == ["document", "policy", "get_user", "documents", "decision", "output", "enqueue_analysis"]
    assert result == {
        "normalized": normalized,
        "rules": rules,
        "comparison": comparison,
        "settlement": settlement,
    }


def test_graph_skips_settlement_stage_when_no_letter_is_uploaded():
    events = []

    class Services:
        def process_claim_documents(self, *_args):
            events.append("document")
            return {}

        def evaluate_saved_claim(self, *_args):
            events.append("policy")
            return {"status": "manual_review"}

        def get_user(self, *_args):
            return {"user_id": "user-1"}

        def claim_documents(self, *_args):
            return [{"document_type": "medical_bill"}]

        @staticmethod
        def appeal_draft_available(_comparison):
            return False

    result = assess_claim(Services(), "claim-2", "user-1")

    assert events == ["document", "policy"]
    assert result == {"normalized": {}, "rules": {"status": "manual_review"}}
