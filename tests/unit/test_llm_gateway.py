from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
import threading
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from mediguard.ai import llm_gateway


def test_extraction_fallback_is_opt_in(monkeypatch):
    monkeypatch.delenv("MEDIGUARD_LLM_EXTRACTION_FALLBACK", raising=False)
    assert llm_gateway.extraction_fallback_enabled() is False
    monkeypatch.setenv("MEDIGUARD_LLM_EXTRACTION_FALLBACK", "TRUE")
    assert llm_gateway.extraction_fallback_enabled() is True


@contextmanager
def fake_ollama(response_factory):
    state = {"calls": 0}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802 - stdlib protocol method name
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length) or b"{}")
            state["calls"] += 1
            status, payload, delay = response_factory(body, state["calls"])
            if delay:
                time.sleep(delay)
            raw = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            try:
                self.wfile.write(raw)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass

        def log_message(self, *_args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", state
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)


def _generate_response(value: str):
    return lambda _body, _count: (200, {"response": value}, 0)


def test_gateway_fake_server_success_is_schema_checked_and_attributed(tmp_path, monkeypatch):
    with fake_ollama(_generate_response('{"total_amount": 1250}')) as (host, _state):
        monkeypatch.setattr(llm_gateway, "OLLAMA_HOST", host)
        monkeypatch.setattr(llm_gateway, "METRICS_PATH", tmp_path / "metrics.jsonl")
        with llm_gateway.claim_context("claim-17"):
            result = llm_gateway.generate_text(
                "extract fictional total", caller="extraction.py:extract", prompt_version="bill_v1",
                timeout=2, schema={"type": "object", "required": ["total_amount"],
                                  "properties": {"total_amount": {"type": "number"}}},
            )
            assert result.ok
            assert result.parsed == {"total_amount": 1250}
            result.finalize(True, "total field validated", "bill fields")
        event = json.loads((tmp_path / "metrics.jsonl").read_text(encoding="utf-8"))
        assert event["claim_id"] == "claim-17"
        assert event["caller"] == "extraction.py:extract"
        assert event["prompt_version"] == "bill_v1"
        assert event["status"] == "ok"
        assert event["accepted"] is True
        assert event["acceptance_reason"] == "total field validated"
        assert event["duration_seconds"] >= 0


def test_gateway_timeout_is_a_clean_result_and_logged(tmp_path, monkeypatch):
    with fake_ollama(lambda *_args: (200, {"response": "{}"}, 0.2)) as (host, _state):
        monkeypatch.setattr(llm_gateway, "OLLAMA_HOST", host)
        monkeypatch.setattr(llm_gateway, "METRICS_PATH", tmp_path / "metrics.jsonl")
        result = llm_gateway.generate_text("slow", caller="test.py:timeout", prompt_version="timeout_v1", timeout=0.03)
        assert result.status == "timeout"
        row = json.loads((tmp_path / "metrics.jsonl").read_text(encoding="utf-8"))
        assert row["status"] == "timeout"
        assert row["accepted"] is False
        assert row["acceptance_reason"] == "ReadTimeout"


def test_gateway_invalid_json_is_rejected_and_logged(tmp_path, monkeypatch):
    with fake_ollama(_generate_response("not-json")) as (host, _state):
        monkeypatch.setattr(llm_gateway, "OLLAMA_HOST", host)
        monkeypatch.setattr(llm_gateway, "METRICS_PATH", tmp_path / "metrics.jsonl")
        result = llm_gateway.generate_text("malformed", caller="test.py:invalid_json", prompt_version="bad_json_v1", timeout=2)
        assert result.status == "invalid_json"
        row = json.loads((tmp_path / "metrics.jsonl").read_text(encoding="utf-8"))
        assert row["accepted"] is False
        assert row["acceptance_reason"] == "Response was not valid JSON"


def test_gateway_rejects_schema_mismatch(tmp_path, monkeypatch):
    with fake_ollama(_generate_response('{"answer":12}')) as (host, _state):
        monkeypatch.setattr(llm_gateway, "OLLAMA_HOST", host)
        monkeypatch.setattr(llm_gateway, "METRICS_PATH", tmp_path / "metrics.jsonl")
        result = llm_gateway.generate_text(
            "answer", caller="test.py:schema", prompt_version="schema_v1", timeout=2,
            schema={"type": "object", "required": ["answer"], "properties": {"answer": {"type": "string"}}},
        )
        assert result.status == "schema_rejected"
        event = json.loads((tmp_path / "metrics.jsonl").read_text(encoding="utf-8"))
        assert event["accepted"] is False
        assert event["acceptance_reason"] == "$.answer must be string"


def test_gateway_unavailable_is_clean_and_logged(tmp_path, monkeypatch):
    monkeypatch.setattr(llm_gateway, "METRICS_PATH", tmp_path / "metrics.jsonl")
    def offline(*_args, **_kwargs):
        import requests
        raise requests.ConnectionError("Ollama is not running")
    monkeypatch.setattr(llm_gateway.requests, "post", offline)
    result = llm_gateway.generate_text("offline", caller="test.py:offline", prompt_version="offline_v1", timeout=0.1)
    assert result.status == "unavailable"
    row = json.loads((tmp_path / "metrics.jsonl").read_text(encoding="utf-8"))
    assert row["accepted"] is False
    assert row["acceptance_reason"].startswith("ConnectionError:")


def test_gateway_cache_deduplicates_facts_within_one_claim(tmp_path, monkeypatch):
    llm_gateway.clear_cache()
    with fake_ollama(_generate_response('{"answer":"Supported."}')) as (host, state):
        monkeypatch.setattr(llm_gateway, "OLLAMA_HOST", host)
        monkeypatch.setattr(llm_gateway, "METRICS_PATH", tmp_path / "metrics.jsonl")
        with llm_gateway.claim_context("claim-cache"):
            first = llm_gateway.generate_text("same facts", caller="test.py:first", prompt_version="qa_v1", timeout=2)
            first.finalize(True, "response accepted", "answer")
            second = llm_gateway.generate_text("same facts", caller="test.py:second", prompt_version="qa_v1", timeout=2)
            second.finalize(True, "cached response revalidated", "answer")
        assert state["calls"] == 1
        assert second.cache_hit is True
        rows = [json.loads(line) for line in (tmp_path / "metrics.jsonl").read_text(encoding="utf-8").splitlines()]
        assert len(rows) == 2
        assert rows[1]["cache_hit"] is True


def test_gateway_cache_deduplicates_simultaneous_identical_claim_calls(monkeypatch):
    llm_gateway.clear_cache()
    with fake_ollama(lambda *_args: (200, {"response": "{\"answer\":\"ok\"}"}, 0.1)) as (host, state):
        monkeypatch.setattr(llm_gateway, "OLLAMA_HOST", host)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(llm_gateway.generate_text, "same facts",
                                   caller="test.py:parallel", prompt_version="qa_v1",
                                   timeout=2, claim_id="claim-parallel") for _ in range(2)]
            results = [future.result() for future in futures]
        assert state["calls"] == 1
        assert sum(result.cache_hit for result in results) == 1
        for result in results:
            result.finalize(True, "response revalidated", "answer")


def test_gateway_retries_transient_failure_at_most_once(tmp_path, monkeypatch):
    def response(_body, call):
        if call == 1:
            return 503, {"error": "busy"}, 0
        return 200, {"response": "{\"ok\":true}"}, 0

    with fake_ollama(response) as (host, state):
        monkeypatch.setattr(llm_gateway, "OLLAMA_HOST", host)
        monkeypatch.setattr(llm_gateway, "METRICS_PATH", tmp_path / "metrics.jsonl")
        result = llm_gateway.generate_text("retry", caller="test.py:retry", prompt_version="retry_v1", timeout=2, max_retries=3)
        assert result.ok
        assert state["calls"] == 2
        result.finalize(True, "valid JSON", "output")


def test_gateway_availability_and_convenience_function(tmp_path, monkeypatch):
    monkeypatch.setattr(llm_gateway, "METRICS_PATH", tmp_path / "metrics.jsonl")

    class TagsHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            raw = json.dumps({"models": [{"name": llm_gateway.OLLAMA_MODEL}]}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, *_args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), TagsHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host = f"http://127.0.0.1:{server.server_port}"
        monkeypatch.setattr(llm_gateway, "OLLAMA_HOST", host)
        assert llm_gateway.is_ollama_available() is True
        ok, reason = llm_gateway.availability()
        assert ok is True
        assert "available" in reason
        row = json.loads((tmp_path / "metrics.jsonl").read_text(encoding="utf-8").splitlines()[-1])
        assert row["status"] == "ok"
        assert row["duration_ms"] >= 0
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)


def test_gateway_chat_json_logs_duration_ms_and_token_counts(tmp_path, monkeypatch):
    response_payload = {
        "message": {"role": "assistant", "content": '{"summary": "test passed"}'},
        "prompt_eval_count": 42,
        "eval_count": 18,
    }

    class ChatHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            raw = json.dumps(response_payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, *_args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), ChatHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host = f"http://127.0.0.1:{server.server_port}"
        monkeypatch.setattr(llm_gateway, "OLLAMA_HOST", host)
        monkeypatch.setattr(llm_gateway, "METRICS_PATH", tmp_path / "metrics.jsonl")
        res = llm_gateway.chat_json("system msg", "user msg", caller="test:chat", prompt_version="chat_v1", timeout=2)
        assert res.ok
        assert res.parsed == {"summary": "test passed"}
        res.finalize(True, "all checks passed", "test_output")
        row = json.loads((tmp_path / "metrics.jsonl").read_text(encoding="utf-8").splitlines()[-1])
        assert row["status"] == "ok"
        assert row["duration_ms"] >= 0
        assert row["ts"] > 0
        assert row["prompt_eval_count"] == 42
        assert row["eval_count"] == 18
        assert row["accepted"] is True
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)


def test_gateway_warm_ollama_nonblocking(monkeypatch):
    called = []
    monkeypatch.setattr(llm_gateway, "warmup", lambda *args, **kwargs: called.append(True) or llm_gateway.GatewayResult(
        "id", "ok", "caller", "ver", "/api/generate", "model", 0.01, None
    ))
    llm_gateway.warm_ollama(blocking=False)
    time.sleep(0.1)
    assert len(called) == 1


