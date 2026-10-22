from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
import threading
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from mediguard.ai import llm_gateway


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

