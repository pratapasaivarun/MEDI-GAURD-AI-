from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import sys
from types import SimpleNamespace
import pytest

from mediguard.ingestion.extraction import run_extraction
from mediguard.policy.policy_terms import extract_policy_terms
from mediguard.ui import claim_pages


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


def test_unconfirmed_policy_terms_are_provisional_and_missing_terms_keep_safe_subtotals(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MEDIGUARD_DB_PATH", str(tmp_path / "review.sqlite"))
    monkeypatch.setenv("MEDIGUARD_STORAGE_DIR", str(tmp_path / "storage"))
    monkeypatch.setenv("CHROMA_DIR", str(tmp_path / "chroma"))
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    import mediguard.services.application as app

    app.init_db()
    user = app.get_or_create_user("reviewer@example.test", "Test Reviewer")
    with app.db() as conn:
        conn.execute("UPDATE users SET role='admin' WHERE user_id=?", (user["user_id"],))
        conn.execute(
            "INSERT INTO policy_versions(version_id,policy_number,version_label,insurer_name,effective_date,status,source_name,stored_path,page_count,content_text,indexed_chunks,created_at,policy_terms_json,terms_review_status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("policy-test", "POL-TEST", "Complete copy", "Example", "2026-01-01", "active", "policy.pdf", "", 36, "synthetic policy text", 1, app.utc_now(), json.dumps({
                "annual_limit": {"term": "annual_limit", "value": 100000, "confidence": 0.95, "source_page": 1, "source_text": "Annual limit INR 100000", "method": "deterministic_regex"},
                "deductible": {"term": "deductible", "value": 5000, "confidence": 0.95, "source_page": 1, "source_text": "Deductible INR 5000", "method": "deterministic_regex"},
                "copay_percent": {"term": "copay_percent", "value": 10, "confidence": 0.95, "source_page": 1, "source_text": "Co-pay 10%", "method": "deterministic_regex"},
            }), "pending"),
        )
        conn.execute(
            "INSERT INTO claims(claim_id,user_id,claim_number,patient_name,policy_number,status,created_at,updated_at,policy_version_id) VALUES(?,?,?,?,?,?,?,?,?)",
            ("claim-test", user["user_id"], "CLM-TEST", "Synthetic Patient", "POL-TEST", "draft", app.utc_now(), app.utc_now(), "policy-test"),
        )
    user = app.get_user(user["user_id"])

    result = app.evaluate_saved_claim(
        "claim-test",
        user["user_id"],
        {"total_amount": {"value": 7500.0}, "patient_name": {"value": "Synthetic Patient"}, "hospital_name": {"value": "Example Hospital"}, "line_items": [], "missing_fields": [], "review_fields": []},
    )
    assert result["status"] == "approved", result.get("warnings")
    assert result["policy_terms_review_status"] == "provisional"
    assert result["payable_amount"] == 2250.0
    assert result["claimant_result"]["amount_claimant_pays"] == 5250.0
    assert result["policy_terms_issues"] == []

    with app.db() as conn:
        incomplete_candidates = json.loads(conn.execute("SELECT policy_terms_json FROM policy_versions WHERE version_id='policy-test'").fetchone()[0])
        incomplete_candidates.pop("copay_percent")
        conn.execute("UPDATE policy_versions SET policy_terms_json=? WHERE version_id='policy-test'", (json.dumps(incomplete_candidates),))
    incomplete = app.evaluate_saved_claim(
        "claim-test", user["user_id"],
        {"total_amount": {"value": 7500.0}, "patient_name": {"value": "Synthetic Patient"}, "hospital_name": {"value": "Example Hospital"}, "line_items": [], "missing_fields": [], "review_fields": []},
    )
    assert incomplete["status"] == "manual_review"
    assert incomplete["covered_amount"] == 7500.0
    assert incomplete["deductible"] == 5000.0
    assert incomplete["copayment"] is None
    assert incomplete["payable_amount"] is None
    assert "copay_percent" in incomplete["policy_terms_missing"]
    assert any("co-payment percentage" in issue["reason"] for issue in incomplete["policy_terms_issues"])

    with pytest.raises(ValueError, match="Add the source page for annual limit"):
        app.save_policy_terms_review(
            "policy-test",
            user["user_id"],
            {"annual_limit": "100000"},
            {"annual_limit": 0},
            {},
        )

    # Every reviewer-confirmed term, including category sub-limits, must cite
    # a page inside the uploaded policy rather than inheriting an unknown page.
    page_required_cases = (
        ({"deductible": "5000"}, {"deductible": 0}, {}),
        ({"copay_percent": "10"}, {"copay_percent": 0}, {}),
        ({"room_limit_per_day": "5000"}, {"room_limit_per_day": 0}, {}),
        ({"waiting_period_months": "12"}, {"waiting_period_months": 0}, {}),
        ({"exclusions": "cosmetic surgery"}, {"exclusions": 0}, {}),
        ({"network_required": True}, {"network_required": 0}, {}),
        ({"preauthorization_required": True}, {"preauthorization_required": 0}, {}),
        ({}, {"sub_limits": 0}, {"surgery": "10000"}),
    )
    for values, source_pages, sub_limits in page_required_cases:
        with pytest.raises(ValueError, match="source page"):
            app.save_policy_terms_review("policy-test", user["user_id"], values, source_pages, sub_limits)

    with pytest.raises(ValueError, match="beyond this policy document"):
        app.save_policy_terms_review(
            "policy-test", user["user_id"], {"annual_limit": "100000"}, {"annual_limit": 37}, {}
        )

    exclusions = extract_policy_terms([
        {"text": "Cosmetic surgery is excluded from coverage.", "page": 4}
   ])["terms_json"]["exclusions"]
    assert exclusions["value"] == ["cosmetic surgery"]
    assert exclusions["needs_review"] is True

    saved_normalized = {
        "document_type": "medical_bill",
        "total_amount": {"value": 7500.0},
        "patient_name": {"value": "Synthetic Patient"},
        "hospital_name": {"value": "Example Hospital"},
        "line_items": [],
        "missing_fields": [],
        "review_fields": [],
    }
    monkeypatch.setattr(app, "claim_documents", lambda *_: [{
        "document_type": "medical_bill", "extracted_json": json.dumps(saved_normalized),
    }])
    monkeypatch.setattr(app, "run_extraction", lambda _payloads: saved_normalized)
    status = app.save_policy_terms_review(
        "policy-test",
        user["user_id"],
        {"annual_limit": "100000", "deductible": "5000", "copay_percent": "10", "exclusions": "cosmetic surgery", "network_required": False, "preauthorization_required": False},
        {"annual_limit": 5, "deductible": 6, "copay_percent": 7, "exclusions": 4, "network_required": 3, "preauthorization_required": 8},
        {},
    )
    assert status == "confirmed"
    # Confirmation must recompute a previously evaluated claim from its saved
    # extraction without requiring the claimant to rerun the analysis.
    with app.db() as conn:
        recomputed_row = conn.execute(
            "SELECT result_json FROM rule_evaluations WHERE claim_id='claim-test' ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
        recompute_audit = conn.execute(
            "SELECT actor,event_type FROM audit_events WHERE claim_id='claim-test' AND event_type='rules_evaluated' ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
    confirmed_result = json.loads(recomputed_row["result_json"])
    assert confirmed_result["policy_terms_review_status"] == "reviewer_confirmed"
    assert confirmed_result["payable_amount"] == result["payable_amount"]
    assert recompute_audit["actor"] == user["user_id"]
    claimant_session = {}
    monkeypatch.setattr(claim_pages, "st", SimpleNamespace(session_state=claimant_session))
    claimant_session["rules_claim-test"] = result
    claimant_view = claim_pages._claimant_result_for_claim("claim-test", user)
    assert claimant_view["policy_terms_review_status"] == "reviewer_confirmed"
    assert claimant_view["amount_covered"] == result["payable_amount"]
    with app.db() as conn:
        saved = conn.execute("SELECT terms_review_status,reviewed_policy_terms_json,terms_reviewed_by FROM policy_versions WHERE version_id='policy-test'").fetchone()
    assert saved["terms_review_status"] == "confirmed"
    assert saved["terms_reviewed_by"] == user["user_id"]
    reviewed_policy = json.loads(saved["reviewed_policy_terms_json"])
    assert set(reviewed_policy) == {"annual_limit", "deductible", "copay_percent", "exclusions", "network_required", "preauthorization_required"}
    assert reviewed_policy["exclusions"]["method"] == "reviewer_confirmed"
    assert reviewed_policy["network_required"] == {"term": "network_required", "value": False, "confidence": 1.0, "source_page": 3, "source_name": "policy.pdf", "method": "reviewer_confirmed"}
    assert reviewed_policy["preauthorization_required"]["value"] is False
    calculated = app.evaluate_saved_claim(
        "claim-test",
        user["user_id"],
        {"total_amount": {"value": 50000.0}, "line_items": [{"description": "Cosmetic surgery", "category": "surgery", "amount": 50000.0}], "missing_fields": [], "review_fields": []},
    )
    assert calculated["rule_version"] != "policy-terms-review-required"
    assert calculated["line_item_results"][0]["status"] == "excluded"

    app.save_policy_terms_review(
        "policy-test", user["user_id"],
        {"annual_limit": "100000", "deductible": "5000", "copay_percent": "10", "network_required": True},
        {"annual_limit": 5, "deductible": 6, "copay_percent": 7, "network_required": 3}, {},
    )
    app.save_adjudication_context("claim-test", user, {"network_status": "out_of_network", "trusted": True})
    network_result = app.evaluate_saved_claim(
        "claim-test",
        user["user_id"],
        {"total_amount": {"value": 50000.0}, "line_items": [{"description": "Covered inpatient treatment", "category": "other", "amount": 50000.0}], "missing_fields": [], "review_fields": []},
    )
    assert network_result["status"] == "rejected"
    assert any("Policy requires a network provider" in warning for warning in network_result["warnings"])
