import json
import threading
from types import SimpleNamespace

from mediguard.services import application as app


def _create_claimant(email):
    user = app.get_or_create_user(email, "Synthetic Analysis Claimant")
    claim_id = app.create_claim(user["user_id"], "CLM-ANALYSIS-001", "Fictional Patient", "Fictional Hospital", "POL-SYNTHETIC", "2026-08-10")
    return user, claim_id


def _resolved_result(status="no_discrepancy"):
    comparison = SimpleNamespace(
        status=status, categories=[], expected_insurer_payment=100,
        actual_insurer_payment=100, possible_difference=0,
        expected_patient_share=0, actual_patient_share=0, billed_total=100,
        review_reasons=[],
    )
    return {"rules": {"status": status, "warnings": []}, "comparison": comparison}


def test_analysis_job_deduplicates_unchanged_facts_and_requeues_changed_facts(monkeypatch, tmp_path):
    monkeypatch.setenv("MEDIGUARD_ANALYSIS_ENABLED", "true")
    monkeypatch.setenv("MEDIGUARD_DB_PATH", str(tmp_path / "analysis-jobs.db"))
    monkeypatch.setenv("MEDIGUARD_STORAGE_DIR", str(tmp_path / "storage"))
    app.init_db()
    user, claim_id = _create_claimant("analysis-dedupe@fictional.test")
    queued = []
    monkeypatch.setattr(app, "_ensure_analysis_worker", lambda: queued.append(True))
    first_result = _resolved_result()

    first = app.enqueue_analysis_job(claim_id, user["user_id"], first_result)
    repeated = app.enqueue_analysis_job(claim_id, user["user_id"], first_result)
    changed_result = _resolved_result()
    changed_result["comparison"].possible_difference = 25
    changed = app.enqueue_analysis_job(claim_id, user["user_id"], changed_result)

    assert first == repeated
    assert changed != first
    assert len(queued) == 2
    with app.db() as conn:
        rows = conn.execute("SELECT job_id,status FROM analysis_jobs WHERE claim_id=?", (claim_id,)).fetchall()
    assert len(rows) == 2
    assert {row["status"] for row in rows} == {"queued"}


def test_analysis_worker_stores_only_safe_result_fields(monkeypatch, tmp_path):
    monkeypatch.setenv("MEDIGUARD_ANALYSIS_ENABLED", "true")
    monkeypatch.setenv("MEDIGUARD_DB_PATH", str(tmp_path / "analysis-worker.db"))
    monkeypatch.setenv("MEDIGUARD_STORAGE_DIR", str(tmp_path / "storage"))
    app.init_db()
    user, claim_id = _create_claimant("analysis-worker@fictional.test")
    monkeypatch.setattr(app, "_ensure_analysis_worker", lambda: None)
    monkeypatch.setattr(app.claim_analysis, "analyze_payload", lambda _payload, _claim_id, _fallback: {
        "accepted": True, "reason": "grounded", "explanation": "Rules-based explanation.",
        "deductions": [], "status": "rejected", "amount": "1.00",
        "reviewer_candidate": {"explanation": "Conflicting but grounded text.", "deductions": []},
    })
    app.enqueue_analysis_job(claim_id, user["user_id"], _resolved_result())

    app._analysis_worker()
    job = app.claim_analysis_job(claim_id, user["user_id"])

    assert job["status"] == "complete"
    assert job["explanation"] == "Rules-based explanation."
    assert job["deductions"] == []
    assert "amount" not in job
    with app.db() as conn:
        stored = json.loads(conn.execute("SELECT result_json FROM analysis_jobs WHERE claim_id=?", (claim_id,)).fetchone()["result_json"])
    assert "status" not in stored and "amount" not in stored
    claimant_view = app.claim_analysis_job(claim_id, user["user_id"])
    assert "reviewer_candidate" not in claimant_view
    with app.db() as conn:
        conn.execute("UPDATE users SET role='admin' WHERE user_id=?", (user["user_id"],))
    admin_view = app.claim_analysis_job(claim_id, user["user_id"])
    assert admin_view["reviewer_candidate"]["explanation"] == "Conflicting but grounded text."


def test_background_worker_does_not_call_streamlit(monkeypatch, tmp_path):
    monkeypatch.setenv("MEDIGUARD_ANALYSIS_ENABLED", "true")
    monkeypatch.setenv("MEDIGUARD_DB_PATH", str(tmp_path / "analysis-no-streamlit.db"))
    monkeypatch.setenv("MEDIGUARD_STORAGE_DIR", str(tmp_path / "storage"))
    app.init_db()
    user, claim_id = _create_claimant("analysis-thread@fictional.test")
    monkeypatch.setattr(app, "_ensure_analysis_worker", lambda: None)
    thread_ids = []

    def fake_analysis(_payload, _claim_id, fallback):
        thread_ids.append(threading.current_thread().name)
        return {"accepted": False, "reason": "offline", "explanation": fallback, "deductions": []}

    monkeypatch.setattr(app.claim_analysis, "analyze_payload", fake_analysis)
    app.enqueue_analysis_job(claim_id, user["user_id"], _resolved_result())
    app._analysis_worker()
    assert thread_ids == [threading.current_thread().name]
    assert app.claim_analysis_job(claim_id, user["user_id"])["status"] == "fallback"


def test_manual_review_uses_template_without_queuing_model_call(monkeypatch, tmp_path):
    monkeypatch.setenv("MEDIGUARD_DB_PATH", str(tmp_path / "analysis-manual.db"))
    monkeypatch.setenv("MEDIGUARD_STORAGE_DIR", str(tmp_path / "storage"))
    monkeypatch.setenv("MEDIGUARD_ANALYSIS_ENABLED", "true")
    app.init_db()
    user, claim_id = _create_claimant("analysis-manual@fictional.test")
    queued = []
    monkeypatch.setattr(app, "_ensure_analysis_worker", lambda: queued.append(True))

    app.enqueue_analysis_job(claim_id, user["user_id"], _resolved_result("manual_review"))
    job = app.claim_analysis_job(claim_id, user["user_id"])

    assert queued == []
    assert job["status"] == "fallback"
    assert "authorized reviewer" in job["explanation"]
