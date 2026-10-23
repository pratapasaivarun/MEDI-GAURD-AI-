"""Single, bounded and auditable gateway for optional local Ollama requests.

The gateway does not interpret claim decisions. Callers validate returned data
for their own domain and finalize the request with the acceptance reason.
"""
from __future__ import annotations

import contextvars
import hashlib
import json
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests


OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "ibm/granite4.1:8b")
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "15"))
OLLAMA_EXPLAIN_TIMEOUT = float(os.getenv("OLLAMA_EXPLAIN_TIMEOUT_SECONDS", "120"))
OLLAMA_NUM_CTX = max(256, min(int(os.getenv("OLLAMA_NUM_CTX", "2048")), 8192))
OLLAMA_NUM_THREAD = max(1, int(os.getenv("OLLAMA_NUM_THREAD", str(os.cpu_count() or 4))))
OLLAMA_NUM_PREDICT = max(1, min(int(os.getenv("OLLAMA_NUM_PREDICT", "320")), 2048))
OLLAMA_KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "30m")
METRICS_PATH = Path(os.getenv("LLM_METRICS_PATH", os.getenv("AGENT_METRICS_PATH", "data/llm_metrics.jsonl")))

_claim_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("mediguard_llm_claim_id", default=None)
_request_lock = threading.BoundedSemaphore(1)
_cache_lock = threading.RLock()
_response_cache: dict[tuple[str, str, str, str], tuple[str, str | None, Any, dict[str, Any], str | None]] = {}
_metrics_lock = threading.Lock()


def extraction_fallback_enabled() -> bool:
    """Return whether unstructured document fields may use an LLM fallback.

    Deterministic extraction remains the default. This flag applies only to
    bill, policy-term, and settlement parsing fallbacks; explanation calls are
    controlled separately by their own user/app settings.
    """
    return os.getenv("MEDIGUARD_LLM_EXTRACTION_FALLBACK", "false").strip().lower() == "true"


def set_metrics_path(path: str | Path) -> None:
    """Set metrics output for the current process (primarily isolated evaluations)."""
    global METRICS_PATH
    METRICS_PATH = Path(path)


class claim_context:
    """Attach a claim id to all gateway calls made in this synchronous flow."""

    def __init__(self, claim_id: str):
        self.claim_id = str(claim_id)
        self._token: contextvars.Token[str | None] | None = None

    def __enter__(self) -> "claim_context":
        self._token = _claim_id.set(self.claim_id)
        return self

    def __exit__(self, *_exc: Any) -> None:
        if self._token is not None:
            _claim_id.reset(self._token)


def current_claim_id() -> str | None:
    return _claim_id.get()


def _write_event(event: dict[str, Any]) -> None:
    now = time.time()
    row = {"ts": now, "timestamp": now, **event}
    try:
        METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _metrics_lock, METRICS_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    except OSError:
        # Metrics must never break claim processing.
        pass


def _schema_error(value: Any, schema: Any, path: str = "$", root: dict[str, Any] | None = None) -> str | None:
    """Validate the JSON-schema subset used by the project without new deps."""
    if not isinstance(schema, dict):
        return None
    if root is None:
        root = schema
    ref = schema.get("$ref")
    if isinstance(ref, str) and ref.startswith("#/"):
        target: Any = root
        for part in ref[2:].split("/"):
            target = target.get(part) if isinstance(target, dict) else None
        return _schema_error(value, target, path, root)
    expected = schema.get("type")
    checks = {
        "object": lambda v: isinstance(v, dict),
        "array": lambda v: isinstance(v, list),
        "string": lambda v: isinstance(v, str),
        "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
        "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
        "boolean": lambda v: isinstance(v, bool),
        "null": lambda v: v is None,
    }
    if isinstance(expected, str) and expected in checks and not checks[expected](value):
        return f"{path} must be {expected}"
    if "enum" in schema and value not in schema["enum"]:
        return f"{path} is outside the allowed values"
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                return f"{path}.{key} is required"
        for key, child_schema in schema.get("properties", {}).items():
            if key in value:
                error = _schema_error(value[key], child_schema, f"{path}.{key}", root)
                if error:
                    return error
    if isinstance(value, list) and isinstance(schema.get("items"), dict):
        for index, item in enumerate(value):
            error = _schema_error(item, schema["items"], f"{path}[{index}]", root)
            if error:
                return error
    return None


@dataclass
class GatewayResult:
    request_id: str
    status: str
    caller: str
    prompt_version: str
    endpoint: str
    model: str
    elapsed_seconds: float
    claim_id: str | None
    text: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    parsed: Any = None
    error: str | None = None
    cache_hit: bool = False
    _finalized: bool = False
    _cached_value: tuple[str, str | None, Any, dict[str, Any], str | None] | None = None

    @property
    def ok(self) -> bool:
        return self.status in {"ok", "cache_hit"}

    def finalize(self, accepted: bool, reason: str, accepted_into: str) -> None:
        """Persist the domain-level decision about using this response."""
        if self._finalized:
            return
        self._finalized = True
        _write_event({
            "request_id": self.request_id,
            "claim_id": self.claim_id,
            "caller": self.caller,
            "endpoint": self.endpoint,
            "model": self.model,
            "prompt_version": self.prompt_version,
            "status": self.status,
            "duration_seconds": round(self.elapsed_seconds, 6),
            "duration_ms": round(self.elapsed_seconds * 1000.0, 2),
            "prompt_eval_count": self.payload.get("prompt_eval_count") if isinstance(self.payload, dict) else None,
            "eval_count": self.payload.get("eval_count") if isinstance(self.payload, dict) else None,
            "cache_hit": self.cache_hit,
            "accepted": bool(accepted),
            "accepted_into": accepted_into,
            "acceptance_reason": str(reason),
            "reject_reason": str(reason) if not accepted else None,
            "error": self.error,
        })
    def _mark_cached(self, key: tuple[str, str, str, str], value: tuple[str, str | None, Any, dict[str, Any], str | None]) -> None:
        self._cache_key = key  # type: ignore[attr-defined]
        self._cached_value = value


def clear_cache() -> None:
    with _cache_lock:
        _response_cache.clear()


def _request(
    *, endpoint: str, body: dict[str, Any], caller: str, prompt_version: str,
    facts: Any, timeout: float | tuple[float, float] | None = None,
    schema: dict[str, Any] | None = None, max_retries: int = 0,
    explicit_claim_id: str | None = None,
) -> GatewayResult:
    model = str(body.get("model") or OLLAMA_MODEL)
    scoped_claim_id = explicit_claim_id or current_claim_id()
    claim_id = scoped_claim_id or "unscoped"
    canonical_facts = json.dumps(facts, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(canonical_facts.encode("utf-8")).hexdigest()
    cache_key = (claim_id or "", model, prompt_version, f"{endpoint}:{digest}")
    request_id = str(uuid.uuid4())
    if scoped_claim_id:
        with _cache_lock:
            cached = _response_cache.get(cache_key)
        if cached is not None:
            cached_status, text, parsed, payload, cached_error = cached
            result = GatewayResult(request_id, cached_status, caller, prompt_version, endpoint, model, 0.0, claim_id, text, dict(payload), parsed, cached_error, cache_hit=True)
            result._mark_cached(cache_key, cached)
            if not result.ok:
                result.finalize(False, cached_error or cached_status, "none")
            return result

    started = time.perf_counter()
    err: str | None = None
    status = "unavailable"
    response_payload: dict[str, Any] = {}
    result_text: str | None = None
    parsed: Any = None
    max_retries = max(0, min(int(max_retries), 1))
    with _request_lock:
        if scoped_claim_id:
            with _cache_lock:
                cached = _response_cache.get(cache_key)
            if cached is not None:
                cached_status, text, cached_parsed, cached_payload, cached_error = cached
                result = GatewayResult(request_id, cached_status, caller, prompt_version, endpoint, model, 0.0,
                                       claim_id, text, dict(cached_payload), cached_parsed, cached_error, cache_hit=True)
                result._mark_cached(cache_key, cached)
                if not result.ok:
                    result.finalize(False, cached_error or cached_status, "none")
                return result
        for attempt in range(max_retries + 1):
            try:
                response = requests.post(f"{OLLAMA_HOST}{endpoint}", json=body,
                                         timeout=timeout if timeout is not None else OLLAMA_TIMEOUT)
                if response.status_code != 200:
                    status = "http_error"
                    err = f"HTTP {response.status_code}"
                    if response.status_code >= 500 and attempt < max_retries:
                        continue
                    break
                response_payload = response.json()
                if endpoint == "/api/chat":
                    message = response_payload.get("message") or {}
                    result_text = message.get("content") if isinstance(message, dict) else None
                else:
                    raw = response_payload.get("response")
                    result_text = raw if isinstance(raw, str) else None
                    if isinstance(raw, (dict, list)):
                        parsed = raw
                if result_text is not None:
                    try:
                        parsed = json.loads(result_text)
                    except (TypeError, json.JSONDecodeError):
                        if schema is not None or body.get("format") == "json":
                            status = "invalid_json"
                            err = "Response was not valid JSON"
                            break
                if schema is not None:
                    schema_error = _schema_error(parsed, schema)
                    if schema_error:
                        status = "schema_rejected"
                        err = schema_error
                        break
                status = "ok"
                err = None
                break
            except requests.Timeout as exc:
                status, err = "timeout", type(exc).__name__
                if attempt < max_retries:
                    continue
                break
            except requests.RequestException as exc:
                status, err = "unavailable", f"{type(exc).__name__}: {exc}"
                if attempt < max_retries:
                    continue
                break
            except (ValueError, TypeError) as exc:
                status, err = "invalid_json", f"{type(exc).__name__}: {exc}"
                break
        if scoped_claim_id:
            with _cache_lock:
                _response_cache[cache_key] = (status, result_text, parsed, response_payload, err)
    elapsed = time.perf_counter() - started
    result = GatewayResult(request_id, status, caller, prompt_version, endpoint, model,
                           elapsed, claim_id, result_text, response_payload, parsed, err)
    cache_value = (status, result_text, parsed, response_payload, err)
    result._mark_cached(cache_key, cache_value)
    if not result.ok:
        result.finalize(False, err or status, "none")
    return result


def chat_json(
    system: str, prompt: str, *, caller: str, prompt_version: str,
    schema: dict[str, Any] | None = None, model: str | None = None,
    timeout: float | tuple[float, float] | None = None, num_predict: int | None = None,
    num_ctx: int | None = None, num_thread: int | None = None, keep_alive: str | None = None,
    temperature: float = 0.0, max_retries: int = 0, claim_id: str | None = None,
) -> GatewayResult:
    body = {
        "model": model or OLLAMA_MODEL, "stream": False,
        "format": schema or "json", "keep_alive": keep_alive or OLLAMA_KEEP_ALIVE,
        "options": {
            "temperature": temperature,
            "num_predict": max(1, min(int(num_predict or OLLAMA_NUM_PREDICT), 2048)),
            "num_ctx": max(256, min(int(num_ctx or OLLAMA_NUM_CTX), 8192)),
            "num_thread": max(1, int(num_thread or OLLAMA_NUM_THREAD)),
        },
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
    }
    facts = {"system": system, "prompt": prompt, "options": body["options"], "schema": schema}
    return _request(endpoint="/api/chat", body=body, caller=caller, prompt_version=prompt_version,
                    facts=facts, timeout=timeout, schema=schema, max_retries=max_retries,
                    explicit_claim_id=claim_id)


def generate_text(
    prompt: str, *, caller: str, prompt_version: str, model: str | None = None,
    timeout: float | tuple[float, float] | None = None, schema: dict[str, Any] | None = None,
    num_predict: int = 320, num_ctx: int | None = None, num_thread: int | None = None,
    keep_alive: str | None = None, temperature: float = 0.0, json_mode: bool = True,
    max_retries: int = 0, claim_id: str | None = None,
) -> GatewayResult:
    body = {
        "model": model or OLLAMA_MODEL, "prompt": prompt, "stream": False,
        "keep_alive": keep_alive or OLLAMA_KEEP_ALIVE,
        "options": {"num_predict": max(1, min(int(num_predict), 2048)),
                    "num_ctx": max(256, min(int(num_ctx or OLLAMA_NUM_CTX), 8192)),
                    "num_thread": max(1, int(num_thread or OLLAMA_NUM_THREAD)),
                    "temperature": temperature},
    }
    if json_mode:
        body["format"] = "json"
    facts = {"prompt": prompt, "options": body["options"], "schema": schema}
    return _request(endpoint="/api/generate", body=body, caller=caller, prompt_version=prompt_version,
                    facts=facts, timeout=timeout, schema=schema, max_retries=max_retries,
                    explicit_claim_id=claim_id)


def availability(timeout: float = 3.0, caller: str = "llm_gateway:availability") -> tuple[bool, str]:
    """Check Ollama and the configured model; this never blocks claim logic."""
    started = time.perf_counter()
    status = "unavailable"
    reason = "Ollama is unavailable"
    try:
        response = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=timeout)
        if response.ok:
            names = [str(item.get("name")) for item in response.json().get("models", [])]
            if OLLAMA_MODEL in names:
                status, reason = "ok", f"Connected — {OLLAMA_MODEL} available"
            else:
                status, reason = "model_missing", f"Connected — configured model not found locally ({OLLAMA_MODEL})"
        else:
            status, reason = "http_error", f"Ollama returned HTTP {response.status_code}"
    except requests.RequestException as exc:
        reason = f"Ollama unavailable: {type(exc).__name__}: {exc}"
    elapsed = time.perf_counter() - started
    _write_event({"request_id": str(uuid.uuid4()), "claim_id": current_claim_id() or "application",
                  "caller": caller, "endpoint": "/api/tags",
                  "model": OLLAMA_MODEL, "prompt_version": "availability_v1",
                  "status": status, "duration_seconds": round(elapsed, 6),
                  "duration_ms": round(elapsed * 1000.0, 2),
                  "accepted": status == "ok", "accepted_into": "availability check",
                  "acceptance_reason": reason,
                  "reject_reason": reason if status != "ok" else None,
                  "cache_hit": False})
    return status == "ok", reason


def is_ollama_available(timeout: float = 3.0) -> bool:
    """Convenience predicate: check if Ollama is running and has the model."""
    ok, _ = availability(timeout=timeout, caller="llm_gateway:is_ollama_available")
    return ok


def warmup(timeout: float | None = None) -> GatewayResult:
    return generate_text("Return only OK.", caller="application.py:background_ollama_warmup",
                         prompt_version="warmup_v1", timeout=timeout or OLLAMA_TIMEOUT,
                         num_predict=4, temperature=0.0, json_mode=False,
                         claim_id="application-startup")


def warm_ollama(blocking: bool = False, timeout: float | None = None) -> None:
    """Non-blocking warm-up in a daemon thread (or blocking if requested)."""
    if blocking:
        warmup(timeout=timeout)
    else:
        thread = threading.Thread(
            target=warmup,
            args=(timeout,),
            name="mediguard-gateway-warmup",
            daemon=True,
        )
        thread.start()
