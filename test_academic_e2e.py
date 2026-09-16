"""One clean-state, evidence-backed academic-prototype demonstration run."""
from __future__ import annotations

import os
import tempfile
import time
import json
from pathlib import Path

ROOT = Path(__file__).parent
RUN_ROOT = Path(tempfile.mkdtemp(prefix="academic_e2e_", dir=ROOT / "data"))
os.environ["MEDIGUARD_DB_PATH"] = str(RUN_ROOT / "mediguard.db")
os.environ["MEDIGUARD_STORAGE_DIR"] = str(RUN_ROOT / "storage")
os.environ["CHROMA_DIR"] = str(RUN_ROOT / "chroma")
os.environ["AGENT_METRICS_PATH"] = str(RUN_ROOT / "agent_metrics.jsonl")
os.environ["OCR_BACKEND"] = "tesseract"
os.environ.setdefault("TESSERACT_CMD", r"C:\Program Files\Tesseract-OCR\tesseract.exe")

import fitz
import app
from reports import build_appeal_letter, build_decision_report


class Upload:
    def __init__(self, path: Path):
        self.name = path.name
        self._content = path.read_bytes()

    def getvalue(self) -> bytes:
        return self._content


app.init_db()
user = app.get_or_create_user("academic-demo@local.test", "Academic demo")
claim_id = app.create_claim(user["user_id"], "CLM-DEMO-APPROVED-001", "Jane Doe", "City Care Hospital", "POL-DEMO-APPROVED-2026", "2026-09-08")
app.save_document(claim_id, user, Upload(ROOT / "demo_assets" / "approved_bill.pdf"), "medical_bill")
app.save_document(claim_id, user, Upload(ROOT / "demo_assets" / "approved_policy.pdf"), "policy")

started = time.perf_counter()
normalized = app.process_claim_documents(claim_id, user["user_id"])
rules = app.evaluate_saved_claim(claim_id, user["user_id"], normalized)
workflow = app.run_agents_for_claim(claim_id, user["user_id"], normalized, rules)
elapsed = time.perf_counter() - started

assert rules["payable_amount"] > 0, rules
assert workflow["decision"]["status"] in {"approved", "partially_approved", "rejected", "manual_review"}, workflow
evidence = workflow.get("policy_evidence", [])
assert evidence and all(item.get("text") for item in evidence), workflow
assert workflow.get("llm_calls") == 1, workflow
assert not workflow["decision"].get("_fallback"), workflow

claim = dict(app._claim_access(claim_id, user))
report = build_decision_report(claim, normalized, rules, workflow)
assert report.startswith(b"%PDF") and len(report) > 1000
with fitz.open(stream=report, filetype="pdf") as pdf:
    report_text = "\n".join(page.get_text() for page in pdf)
assert "Claim Decision Report" in report_text and "Evidence items:" in report_text
appeal = build_appeal_letter(claim, rules, workflow)
assert claim["claim_number"] in appeal and "cited policy evidence" in appeal

summary = {
    "elapsed_seconds": round(elapsed, 2),
    "rule_status": rules["status"],
    "payable_amount": rules["payable_amount"],
    "decision_status": workflow["decision"]["status"],
    "evidence_count": len(evidence),
    "llm_calls": workflow["llm_calls"],
    "reportlab_pdf_bytes": len(report),
    "appeal_letter_ok": True,
}
(RUN_ROOT / "result.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

print(f"CLEAN_RUN_ROOT={RUN_ROOT}")
print(f"E2E_SECONDS={elapsed:.2f}")
print(f"RULE_STATUS={rules['status']} PAYABLE={rules['payable_amount']:.2f}")
print(f"DECISION_STATUS={workflow['decision']['status']} EVIDENCE_COUNT={len(evidence)} LLM_CALLS={workflow['llm_calls']}")
print("REPORTLAB_PDF_OK")
print("APPEAL_LETTER_OK")
