"""One clean-state, evidence-backed academic-prototype demonstration run."""
from __future__ import annotations

import os
import tempfile
import time
import json
from pathlib import Path

ROOT = Path(__file__).parent
RUN_ROOT = Path(tempfile.mkdtemp(prefix="academic_e2e_"))
os.environ["MEDIGUARD_DB_PATH"] = str(RUN_ROOT / "mediguard.db")
os.environ["MEDIGUARD_STORAGE_DIR"] = str(RUN_ROOT / "storage")
os.environ["CHROMA_DIR"] = str(RUN_ROOT / "chroma")
os.environ["AGENT_METRICS_PATH"] = str(RUN_ROOT / "agent_metrics.jsonl")
os.environ["OCR_BACKEND"] = "tesseract"
os.environ.setdefault("TESSERACT_CMD", r"C:\Program Files\Tesseract-OCR\tesseract.exe")

import fitz
import app
import policy_index
from reports import build_appeal_letter, build_appeal_letter_pdf, build_decision_report


class Upload:
    def __init__(self, path: Path):
        self.name = path.name
        self._content = path.read_bytes()

    def getvalue(self) -> bytes:
        return self._content


case_dir = ROOT / "fixtures" / "claim_scenarios" / "partially_approved" / "02_surgery_sublimit"
manifest = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
registration = manifest["claim_registration"]

app.init_db()
user = app.get_or_create_user("academic-demo@local.test", "Academic demo")
claim_id = app.create_claim(user["user_id"], registration["claim_number"], registration["patient_name"], registration["hospital"], registration["policy_number"], registration["service_date"])
app.save_document(claim_id, user, Upload(case_dir / "medical_bill.pdf"), "medical_bill")
app.save_document(claim_id, user, Upload(case_dir / "policy.pdf"), "policy")
review_context = manifest.get("reviewer_context_required") or {}
if review_context:
    admin = app.get_or_create_user("academic-demo-admin@local.test", "Academic demo reviewer")
    with app.db() as connection:
        connection.execute("UPDATE users SET role='admin' WHERE user_id=?", (admin["user_id"],))
    admin = app.get_user(admin["user_id"])
    app.save_adjudication_context(claim_id, admin, {
        key: value for key, value in review_context.items()
        if key in {"network_status", "preauthorization_status", "preauthorization_reference",
                   "waiting_period_status", "source", "trusted", "aggregation_confirmed"}
    })
    with app.db() as connection:
        row = connection.execute("SELECT adjudication_context_json FROM claims WHERE claim_id=?", (claim_id,)).fetchone()
        saved = json.loads(row["adjudication_context_json"] or "{}") if row else {}
        saved.update(review_context)
        connection.execute("UPDATE claims SET adjudication_context_json=? WHERE claim_id=?", (json.dumps(saved), claim_id))

started = time.perf_counter()
normalized = app.process_claim_documents(claim_id, user["user_id"])
rules = app.evaluate_saved_claim(claim_id, user["user_id"], normalized)
workflow = app.run_agents_for_claim(claim_id, user["user_id"], normalized, rules)
elapsed = time.perf_counter() - started

assert rules["status"] == manifest["expected_status"], rules
assert rules["payable_amount"] > 0, rules
assert workflow["decision"]["status"] in {"approved", "partially_approved", "rejected", "manual_review"}, workflow
evidence = workflow.get("policy_evidence", [])
assert evidence and all(item.get("text") for item in evidence), workflow
assert workflow.get("llm_calls") == 1, workflow
assert not workflow["decision"].get("_fallback"), workflow
assert workflow["decision"].get("confidence") is not None, workflow

claim = dict(app._claim_access(claim_id, user))
report = build_decision_report(claim, normalized, rules, workflow)
assert report.startswith(b"%PDF") and len(report) > 1000
with fitz.open(stream=report, filetype="pdf") as pdf:
    report_text = "\n".join(page.get_text() for page in pdf)
assert all(value in report_text for value in (
    "Claim Decision Report", "Evidence notes", registration["claim_number"],
    registration["patient_name"], registration["policy_number"],
    "Current status", "Partially Approved", "Decision confidence",
)), report_text
appeal = build_appeal_letter(claim, rules, workflow)
assert claim["claim_number"] in appeal and any(
    phrase in appeal.lower() for phrase in ("request for review", "reconsideration")
)
evidence_ids = {str(item.get("clause_id")) for item in evidence}
assert set(workflow["decision"].get("policy_citations") or []).issubset(evidence_ids)
appeal_pdf = build_appeal_letter_pdf(claim, rules, workflow)
assert appeal_pdf.startswith(b"%PDF") and len(appeal_pdf) > 1000
with fitz.open(stream=appeal_pdf, filetype="pdf") as pdf:
    appeal_text = "\n".join(page.get_text() for page in pdf)
assert "Appeal and Review Request" in appeal_text and claim["claim_number"] in appeal_text

report_path = RUN_ROOT / "decision_report.pdf"
appeal_path = RUN_ROOT / "appeal_draft.pdf"
report_path.write_bytes(report)
appeal_path.write_bytes(appeal_pdf)

# Exercise the same evidence-bounded answer helper used by the claim Q&A UI.
question = "What policy coverage applies to this inpatient treatment?"
qa_answer = app._claim_answer_from_saved_data(question, {
    "status": workflow["decision"]["status"],
    "reason": (workflow["decision"].get("reasons") or [""])[0],
}, normalized, evidence)
evidence_text = " ".join(str(evidence[0]["text"]).split())
answer_text = " ".join(str(qa_answer or "").split())
assert answer_text and evidence_text[:100] in answer_text

# Verify the existing missing-terms case fails closed as a visible Manual Review.
manual_dir = ROOT / "fixtures" / "claim_scenarios" / "manual_review" / "02_missing_policy_terms"
manual_manifest = json.loads((manual_dir / "case.json").read_text(encoding="utf-8"))
manual_registration = manual_manifest["claim_registration"]
manual_claim_id = app.create_claim(user["user_id"], manual_registration["claim_number"], manual_registration["patient_name"], manual_registration["hospital"], manual_registration["policy_number"], manual_registration["service_date"])
app.save_document(manual_claim_id, user, Upload(manual_dir / "medical_bill.pdf"), "medical_bill")
app.save_document(manual_claim_id, user, Upload(manual_dir / "policy.pdf"), "policy")
manual_normalized = app.process_claim_documents(manual_claim_id, user["user_id"])
manual_rules = app.evaluate_saved_claim(manual_claim_id, user["user_id"], manual_normalized)
assert manual_rules["status"] == "manual_review", manual_rules
assert app._status_badge(manual_rules["status"]) == "Manual Review"
assert manual_rules.get("warnings") or manual_rules.get("policy_terms_missing"), manual_rules

summary = {
    "elapsed_seconds": round(elapsed, 2),
    "rule_status": rules["status"],
    "payable_amount": rules["payable_amount"],
    "decision_status": workflow["decision"]["status"],
    "evidence_count": len(evidence),
    "llm_calls": workflow["llm_calls"],
    "reportlab_pdf_bytes": len(report),
    "appeal_pdf_bytes": len(appeal_pdf),
    "appeal_letter_ok": True,
    "case_id": manifest["case_id"],
    "extracted_bill_fields": {key: (normalized.get(key) or {}).get("value") for key in ("patient_name", "hospital_name", "policy_number", "total_amount")},
    "retrieved_policy_evidence": evidence,
    "decision_reasons": workflow["decision"].get("reasons", []),
    "confidence": workflow["decision"].get("confidence"),
    "embedding_backend": policy_index.embedding_backend_status(),
    "decision_report_path": str(report_path),
    "appeal_pdf_path": str(appeal_path),
    "q_and_a_question": question,
    "q_and_a_answer": qa_answer,
    "manual_review_case_id": manual_manifest["case_id"],
    "manual_review_status": manual_rules["status"],
    "manual_review_reason": manual_rules.get("warnings") or manual_rules.get("policy_terms_missing"),
    "workflow_complete": True,
}
(RUN_ROOT / "result.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
(ROOT / "evaluation" / "final_workflow_verification.json").write_text(
    json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
)

print(f"CLEAN_RUN_ROOT={RUN_ROOT}")
print(f"E2E_SECONDS={elapsed:.2f}")
print(f"RULE_STATUS={rules['status']} PAYABLE={rules['payable_amount']:.2f}")
print(f"DECISION_STATUS={workflow['decision']['status']} EVIDENCE_COUNT={len(evidence)} LLM_CALLS={workflow['llm_calls']}")
print("REPORTLAB_PDF_OK")
print("APPEAL_LETTER_OK")
