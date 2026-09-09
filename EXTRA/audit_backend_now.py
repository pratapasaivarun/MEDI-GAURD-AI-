from __future__ import annotations
import importlib
import inspect
import os
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)

modules = ["extraction", "policy_terms", "policy_index", "rules", "agents", "reports", "app"]
required = {
    "extraction": ["extract_document", "normalize_documents", "run_extraction"],
    "policy_terms": ["extract_policy_terms"],
    "policy_index": ["index_policy_documents", "retrieve_policy_evidence"],
    "rules": ["evaluate_claim"],
    "agents": ["run_claim_workflow"],
    "reports": [],
    "app": ["init_db", "process_claim_documents", "evaluate_saved_claim"],
}

print("=== MODULE IMPORTS ===")
loaded = {}
for name in modules:
    mod = importlib.import_module(name)
    loaded[name] = mod
    print(f"{name}: OK")
    missing = [fn for fn in required[name] if not hasattr(mod, fn)]
    if missing:
        raise AssertionError(f"{name} missing required functions: {missing}")

print("=== FUNCTION SIGNATURES ===")
for mod_name, functions in required.items():
    for fn in functions:
        if hasattr(loaded[mod_name], fn):
            print(f"{mod_name}.{fn}{inspect.signature(getattr(loaded[mod_name], fn))}")

app = loaded["app"]
app.init_db()
print("=== DATABASE ===")
with app.db() as conn:
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
required_tables = {"users", "claims", "documents", "policy_versions", "rule_evaluations", "audit_events", "reviewer_decisions"}
missing_tables = required_tables - tables
if missing_tables:
    raise AssertionError(f"Missing database tables: {sorted(missing_tables)}")
print("tables: OK", len(tables), "tables present")

print("=== CORE FLAGS ===")
print("CORE_DEMO_MODE=", getattr(app, "CORE_DEMO_MODE", None))
print("AUTH_REQUIRED=", getattr(app, "AUTH_REQUIRED", None))
print("OLLAMA_MODEL=", getattr(app, "OLLAMA_MODEL", None))
print("OLLAMA_TIMEOUT=", getattr(app, "OLLAMA_TIMEOUT", None))

print("=== AGENT SAFETY CHECKS ===")
agent_source = Path("agents.py").read_text(encoding="utf-8")
if "Policy Agent" not in agent_source or "Decision Agent" not in agent_source:
    raise AssertionError("Two-agent labels not found")
if "llm_calls" not in agent_source:
    raise AssertionError("Agent call accounting not found")
print("two-agent workflow markers: OK")

print("=== BACKEND_AUDIT_OK ===")
