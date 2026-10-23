from __future__ import annotations

import json
import threading
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import pytest

from mediguard.services import application as app
from mediguard.services.orchestration import assess_claim
from mediguard.ai.agents import explain_comparison
from mediguard.ai import qa, llm_gateway
from mediguard.engine.models import CategoryComparison, Clause, ComparisonResult


class FakeOllamaServer:
    def __init__(self):
        self.requests: list[dict] = []
        self._server = None
        self._thread = None
        self.port = 0

    def start(self):
        server_self = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                server_self.requests.append({"method": "GET", "path": self.path})
                payload = json.dumps({"models": [{"name": "ibm/granite4.1:8b"}]}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("Content-Length", "0"))
                body_bytes = self.rfile.read(length) if length > 0 else b"{}"
                try:
                    body = json.loads(body_bytes.decode("utf-8"))
                except Exception:
                    body = {}
                server_self.requests.append({"method": "POST", "path": self.path, "body": body})

                # Distinguish Explain vs QA from prompt content or format
                user_msg = ""
                for msg in body.get("messages", []):
                    if msg.get("role") == "user":
                        user_msg = msg.get("content", "")

                if "Explain this health insurance" in user_msg or "ROOM_RENT" in user_msg:
                    content = json.dumps({"explanation": "The settlement differs by INR 1000.00."})
                else:
                    content = json.dumps({
                        "answer": "Pharmacy charges are payable under the policy.",
                        "used_clause_ids": ["4.2"],
                    })

                resp = {
                    "message": {"role": "assistant", "content": content},
                    "done": True,
                    "prompt_eval_count": 20,
                    "eval_count": 15,
                }
                raw = json.dumps(resp).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def log_message(self, *_args):
                pass

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self._server.server_port
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self):
        if self._server:
            self._server.shutdown()
            self._server.server_close()
        if self._thread:
            self._thread.join(timeout=2)


@pytest.fixture
def fake_ollama_service(monkeypatch, tmp_path):
    server = FakeOllamaServer()
    server.start()
    host = f"http://127.0.0.1:{server.port}"
    monkeypatch.setenv("OLLAMA_HOST", host)
    monkeypatch.setattr(llm_gateway, "OLLAMA_HOST", host)
    monkeypatch.setattr(llm_gateway, "OLLAMA_TIMEOUT", 2.0)
    monkeypatch.setattr(llm_gateway, "OLLAMA_EXPLAIN_TIMEOUT", 2.0)
    from mediguard.ai import agents
    monkeypatch.setattr(agents, "OLLAMA_HOST", host)
    monkeypatch.setenv("MEDIGUARD_DB_PATH", str(tmp_path / "zero-calls.db"))
    monkeypatch.setenv("MEDIGUARD_STORAGE_DIR", str(tmp_path / "storage"))
    # Clear any gateway caches
    llm_gateway.clear_cache()
    try:
        yield server
    finally:
        server.stop()


def _sample_comparison():
    clause = Clause(page=2, section="Clause 4.1", text="Room rent limit is capped.")
    category = CategoryComparison(
        category="ROOM_RENT",
        insurer_deducted=Decimal("2000.00"),
        engine_disallowed=Decimal("1000.00"),
        difference=Decimal("1000.00"),
        status="EXCESS_DEDUCTION",
        insurer_reason="Exceeded limit",
        engine_reason="Room rent capped at 1000.00",
        clause=clause,
        payout_effect=Decimal("1000.00"),
    )
    return ComparisonResult(
        status="possible_discrepancy",
        expected_insurer_payment=Decimal("8000.00"),
        actual_insurer_payment=Decimal("7000.00"),
        possible_difference=Decimal("1000.00"),
        expected_patient_share=Decimal("2000.00"),
        actual_patient_share=Decimal("3000.00"),
        billed_total=Decimal("10000.00"),
        categories=[category],
        review_reasons=[],
    )


class DummyUpload:
    def __init__(self, filename: str, content: bytes):
        self.name = filename
        self._content = content

    def getvalue(self) -> bytes:
        return self._content


def test_zero_automatic_llm_calls_end_to_end(fake_ollama_service, monkeypatch):
    """Decisive test proving default settings produce ZERO automatic LLM requests.

    Requests occur ONLY upon deliberate user clicks:
    - Click 'Explain with AI': exactly 1 request
    - Unanswered Q&A question: exactly 1 request
    """
    server = fake_ollama_service

    # Verify default environment variables (analysis and warmup disabled by default)
    assert not app.is_analysis_enabled() if hasattr(app, "is_analysis_enabled") else True

    # 1. App start: warmup and pending job resumption
    warmup_ran = app.start_ollama_warmup_background()
    assert warmup_ran is False  # Warmup is off by default
    resumed = app.resume_pending_analysis_jobs()
    assert resumed is False
    assert len(server.requests) == 0, "App start must make 0 LLM requests"

    # Initialize database and user
    app.init_db()
    user = app.get_or_create_user("zero-caller@fictional.test", "Zero Call User")
    user_id = user["user_id"]
    claim_id = app.create_claim(user_id, "CLM-ZERO-001", "A Patient", "A Hospital", "POL-001", "2026-08-10")

    # 2. Upload completion & assessment
    demo_dir = Path("samples/demo_cases/b_wrongful_deduction")
    bill_bytes = (demo_dir / "bill.pdf").read_bytes()
    policy_bytes = (demo_dir / "policy.pdf").read_bytes()
    settlement_bytes = (demo_dir / "settlement.pdf").read_bytes()
    app.save_document(claim_id, user, DummyUpload("bill.pdf", bill_bytes), "medical_bill")
    app.save_document(claim_id, user, DummyUpload("policy.pdf", policy_bytes), "policy")
    app.save_document(claim_id, user, DummyUpload("settlement.pdf", settlement_bytes), "settlement")

    # Run claim assessment pipeline (simulating upload completion)
    result = assess_claim(app, claim_id, user_id)
    assert result is not None
    assert len(server.requests) == 0, f"Upload and claim assessment must make 0 LLM requests (got {len(server.requests)})"

    # 3. Reviewer confirmation
    reviewer = app.get_or_create_user("zero-reviewer@fictional.test", "Zero Reviewer")
    with app.db() as conn:
        conn.execute("UPDATE users SET role='admin' WHERE user_id=?", (reviewer["user_id"],))
    reviewer = app.get_user(reviewer["user_id"])
    docs = app.claim_documents(claim_id, reviewer)
    bill_doc_id = next(d["document_id"] for d in docs if d["document_type"] == "medical_bill")
    app.save_claim_extraction_review(
        claim_id,
        reviewer["user_id"],
        {"patient_name": {"value": "Confirmed Patient", "page": 1, "document_id": bill_doc_id}},
    )
    re_result = assess_claim(app, claim_id, user_id, audit_actor_id=reviewer["user_id"])
    assert re_result is not None
    assert len(server.requests) == 0, f"Reviewer confirmation must make 0 LLM requests (got {len(server.requests)})"

    # 4. Result screen rendering
    # Rendering uses template explanation and checks for reviewer deductions
    comparison = _sample_comparison()
    default_text = explain_comparison(comparison, use_llm=False)
    assert "1,000.00" in default_text
    job = app.claim_analysis_job(claim_id, user_id)
    # Deductions should be empty or safe, no error
    assert (job or {}).get("deductions", []) == []
    assert len(server.requests) == 0, f"Result screen rendering must make 0 LLM requests (got {len(server.requests)})"

    # 5. User clicks 'Explain with AI': exactly 1 request
    ai_text = explain_comparison(comparison, use_llm=True, claim_id=claim_id)
    assert ai_text is not None
    post_explain_requests = [r for r in server.requests if r["method"] == "POST"]
    assert len(post_explain_requests) == 1, f"Clicking 'Explain with AI' must make exactly 1 LLM request (got {len(post_explain_requests)})"

    # 6. Q&A: deterministic question causes 0 LLM calls
    det_ans = qa.answer_question("What is the status?", {"status": "possible_discrepancy"}, [], claim_id)
    assert "possible_discrepancy" in det_ans
    assert len([r for r in server.requests if r["method"] == "POST"]) == 1, "Deterministic Q&A must make 0 additional LLM calls"

    # Q&A: unmatched question uses the model only when it is available
    evidence = [{"clause_id": "4.2", "page": 3, "text": "Pharmacy charges are payable under the policy."}]
    qa_ans = qa.answer_question("What does clause 4.2 say?", {"status": "possible_discrepancy"}, evidence, claim_id)
    assert "Pharmacy charges are payable" in qa_ans
    post_qa_requests = [r for r in server.requests if r["method"] == "POST"]
    assert len(post_qa_requests) == 2, f"Fallback Q&A must make exactly 1 additional LLM request (total 2, got {len(post_qa_requests)})"
