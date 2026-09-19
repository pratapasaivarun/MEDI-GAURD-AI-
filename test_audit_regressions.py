"""Isolated failure-path checks for the end-to-end audit."""
import os
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).parent
RUN = Path(tempfile.mkdtemp(prefix="audit_regression_", dir=ROOT / "data"))
os.environ["MEDIGUARD_DB_PATH"] = str(RUN / "claims.db")
os.environ["MEDIGUARD_STORAGE_DIR"] = str(RUN)

import requests
import app
import agents

state = {"policy_evidence": [{"clause_id": "p1", "text": "Coverage"}], "rule_results": {"status": "approved"}}
with patch.object(agents, "_ollama_json", side_effect=requests.ConnectionError("offline")):
    decision = agents.decision_agent_node(state)["decision"]
    assert decision["status"] == "manual_review" and decision["_fallback"]
    assert decision["line_item_notes"] == []

app.init_db()
user = app.get_or_create_user("audit@local.test", "Audit")
claim_id = app.create_claim(user["user_id"], "AUDIT-1", "Test", "Test", "TEST-POL", "2026-09-16")
documents = [{"document_id": "failed-policy", "document_type": "policy"},
             {"document_id": "good-bill", "document_type": "medical_bill", "original_name": "bill.pdf"}]
with patch.object(app, "claim_documents", return_value=documents), patch.object(app, "_extract_one", side_effect=[ValueError("bad PDF"), ([], {}, 1)]), patch.object(app, "run_extraction", return_value={"review_fields": [], "missing_fields": []}), patch.object(app, "index_policy_documents") as index:
    normalized = app.process_claim_documents(claim_id, user["user_id"])
    assert "document_extraction" in normalized["review_fields"]
    index.assert_not_called()

with patch.object(app, "active_policy_for_claim", return_value=None), patch.object(app, "saved_policy_text", return_value="Coverage applies."), patch.object(app, "warm_ollama", side_effect=requests.ConnectionError("offline")), patch.object(agents, "_ollama_json", side_effect=requests.ConnectionError("offline")), patch.object(agents, "retrieve_policy_evidence", return_value=state["policy_evidence"]):
    result = app.run_agents_for_claim(claim_id, user["user_id"], {}, {"status": "approved"})
    assert result["decision"]["status"] == "manual_review"
    assert app._claim_access(claim_id, user)["status"] == "manual_review"

# A fresh session must show the persisted fallback and subsequent reviewer
# determination instead of reverting to the older deterministic approval.
with app.db() as conn:
    conn.execute("INSERT INTO rule_evaluations VALUES (?,?,?,?,?,?)", ("audit-rule", claim_id, "test", "approved", json.dumps({"status": "approved", "payable_amount": 100}), app.utc_now()))
assert app._claimant_result_for_claim(claim_id, user)["status"] == "manual_review"
admin = app._core_demo_user()
app.save_reviewer_decision(claim_id, admin["user_id"], "manual_review", "rejected", "Verified exclusion")
assert app._claimant_result_for_claim(claim_id, user)["status"] == "rejected"

with patch.object(app.requests, "get") as get:
    get.return_value.ok = True
    get.return_value.json.return_value = {"models": []}
    assert app.ollama_status()[0] is False

# Payment questions must remain answerable from saved claim data even when the
# model or retrieval service is unavailable.
assistant_answer = app._claim_answer_from_saved_data(
    "HOW MUCH CLAIM THE USER GOT",
    {"amount_covered": 67500, "amount_billed": 80000, "amount_claimant_pays": 12500},
    {},
    [],
)
assert assistant_answer and "INR 67,500.00" in assistant_answer
print("AUDIT_REGRESSIONS_OK")
