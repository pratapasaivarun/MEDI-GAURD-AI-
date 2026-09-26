from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import sys

from extraction import run_extraction


def test_bill_layout_labels_and_net_total_are_extracted() -> None:
    text = """FINAL IN-PATIENT BILL
Patient
Synthetic Patient
Hospital / Provider
Example Hospital
Policy No. of Patient
POL-TEST-2026
Claim No.
CLM-TEST-001
Bill Date
12.01.2026
Admission Date
10.01.2026
Discharge Date
12.01.2026
Diagnosis
Synthetic diagnosis
Room charges: INR 5000
Doctor consultation: INR 2500
NET BILL AMOUNT
INR 7,500.00
"""
    result = run_extraction([{"document_id": "synthetic-layout", "source_name": "synthetic_bill.pdf", "document_type": "medical_bill", "text": text, "evidence": [], "raw_by_page": {"1": text}}])
    assert result["patient_name"]["value"] == "Synthetic Patient"
    assert result["hospital_name"]["value"] == "Example Hospital"
    assert result["policy_number"]["value"] == "POL-TEST-2026"
    assert result["claim_number"]["value"] == "CLM-TEST-001"
    assert result["total_amount"]["value"] == 7500.0
    assert len(result["line_items"]) == 2


def test_real_policy_terms_are_not_used_until_reviewer_confirmed(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MEDIGUARD_DB_PATH", str(tmp_path / "review.sqlite"))
    monkeypatch.setenv("MEDIGUARD_STORAGE_DIR", str(tmp_path / "storage"))
    monkeypatch.setenv("CHROMA_DIR", str(tmp_path / "chroma"))
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import app

    app.init_db()
    user = app.get_or_create_user("reviewer@example.test", "Test Reviewer")
    with app.db() as conn:
        conn.execute("UPDATE users SET role='admin' WHERE user_id=?", (user["user_id"],))
        conn.execute(
            "INSERT INTO policy_versions(version_id,policy_number,version_label,insurer_name,effective_date,status,source_name,stored_path,page_count,content_text,indexed_chunks,created_at,policy_terms_json,terms_review_status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("policy-test", "POL-TEST", "Complete copy", "Example", "2026-01-01", "active", "policy.pdf", "", 36, "synthetic policy text", 1, app.utc_now(), json.dumps({}), "pending"),
        )
        conn.execute(
            "INSERT INTO claims(claim_id,user_id,claim_number,patient_name,policy_number,status,created_at,updated_at,policy_version_id) VALUES(?,?,?,?,?,?,?,?,?)",
            ("claim-test", user["user_id"], "CLM-TEST", "Synthetic Patient", "POL-TEST", "draft", app.utc_now(), app.utc_now(), "policy-test"),
        )

    result = app.evaluate_saved_claim(
        "claim-test",
        user["user_id"],
        {"total_amount": {"value": 7500.0}, "line_items": [], "missing_fields": [], "review_fields": []},
    )
    assert result["status"] == "manual_review"
    assert "policy-terms-review-required" == result["rule_version"]
    assert "reviewed_policy_terms" in result["policy_terms_missing"]

    status = app.save_policy_terms_review(
        "policy-test",
        user["user_id"],
        {"annual_limit": "100000", "deductible": "5000", "copay_percent": "10"},
        {"annual_limit": 5, "deductible": 6, "copay_percent": 7},
        {},
    )
    assert status == "confirmed"
    with app.db() as conn:
        saved = conn.execute("SELECT terms_review_status,reviewed_policy_terms_json,terms_reviewed_by FROM policy_versions WHERE version_id='policy-test'").fetchone()
    assert saved["terms_review_status"] == "confirmed"
    assert saved["terms_reviewed_by"] == user["user_id"]
    assert set(json.loads(saved["reviewed_policy_terms_json"])) == {"annual_limit", "deductible", "copay_percent"}
    calculated = app.evaluate_saved_claim(
        "claim-test",
        user["user_id"],
        {"total_amount": {"value": 7500.0}, "line_items": [], "missing_fields": [], "review_fields": []},
    )
    assert calculated["rule_version"] != "policy-terms-review-required"
