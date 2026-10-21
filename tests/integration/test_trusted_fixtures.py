import json
import uuid
from pathlib import Path
from types import SimpleNamespace

from mediguard.services import application as app
from mediguard.ingestion.extraction import Evidence
from mediguard.ui import claim_pages


class Upload:
    def __init__(self, name, content):
        self.name = name
        self._content = content

    def getvalue(self):
        return self._content


def _process_policy(monkeypatch, tmp_path, content, text, trusted):
    monkeypatch.setenv("MEDIGUARD_DB_PATH", str(tmp_path / "fixture.db"))
    monkeypatch.setenv("MEDIGUARD_STORAGE_DIR", str(tmp_path / "storage"))
    monkeypatch.setenv("MEDIGUARD_TRUSTED_FIXTURES", "true" if trusted else "false")
    app.init_db()
    user_id = str(uuid.uuid4())
    with app.db() as conn:
        conn.execute(
            "INSERT INTO users(user_id,email,display_name,role,created_at) VALUES(?,?,?,?,?)",
            (user_id, "fixture@example.test", "Fixture Test", "claimant", app.utc_now()),
        )
    user = app.get_user(user_id)
    claim_id = app.create_claim(user_id, "CLM-FIXTURE", "Ravi Reddy", "Hospital", "POL-FIXTURE", "2026-08-10")
    app.save_document(claim_id, user, Upload("policy.pdf", content), "policy")
    evidence = [Evidence("policy-fixture", "policy.pdf", 1, "text", text, 100.0)]
    monkeypatch.setattr(app, "_extract_one", lambda _doc: (evidence, {}, 1))
    monkeypatch.setattr(app, "index_policy_documents", lambda *_args, **_kwargs: {"chunks_indexed": 1})
    terms_json = {
        name: {"term": name, "value": value, "confidence": 1.0, "method": "deterministic_regex"}
        for name, value in (("annual_limit", "500000"), ("deductible", "0"), ("copay_percent", "0"))
    }
    monkeypatch.setattr(app, "extract_policy_terms", lambda *_args, **_kwargs: {"terms_json": terms_json, "missing_terms": []})
    monkeypatch.setattr(app, "run_extraction", lambda *_args, **_kwargs: {
        "policy_number": {"value": "POL-FIXTURE"}, "total_amount": None,
        "line_items": [], "missing_fields": [], "review_fields": [],
    })
    normalized = app.process_claim_documents(claim_id, user_id)
    with app.db() as conn:
        policy = conn.execute("SELECT terms_review_status,terms_reviewed_by FROM policy_versions WHERE policy_number='POL-FIXTURE'").fetchone()
        fixture_audit = conn.execute(
            "SELECT actor,event_type,details FROM audit_events WHERE claim_id=? AND event_type='fictional_fixture_policy_attached' ORDER BY rowid DESC LIMIT 1",
            (claim_id,),
        ).fetchone()
    result = app.evaluate_saved_claim(claim_id, user_id, normalized)
    return policy, fixture_audit, result


def test_fictional_word_does_not_confirm_uploaded_policy_when_setting_off(monkeypatch, tmp_path):
    policy, _audit, _result = _process_policy(
        monkeypatch, tmp_path, b"%PDF-1.4 untrusted upload",
        "This fictional policy has an annual limit, deductible and copay.", False,
    )
    assert policy["terms_review_status"] == "pending"
    assert policy["terms_reviewed_by"] is None


def test_allowlisted_bundled_fixture_confirms_only_when_setting_on(monkeypatch, tmp_path):
    fixture = Path(__file__).parents[2] / "samples" / "claim_scenarios" / "approved" / "01_standard_approved" / "policy.pdf"
    policy, audit, result = _process_policy(
        monkeypatch, tmp_path, fixture.read_bytes(),
        "FICTIONAL SAMPLE policy with annual limit, deductible and copay.", True,
    )
    assert policy["terms_review_status"] == "confirmed"
    assert policy["terms_reviewed_by"] == "trusted_fixture"
    assert result["policy_terms_review_status"] == "preconfirmed_fictional_sample"
    assert audit["event_type"] == "fictional_fixture_policy_attached"
    assert json.loads(audit["details"])["source_name"] == "policy.pdf"


def test_preconfirmed_fixture_badge_is_explicit(monkeypatch):
    messages = []
    fake_streamlit = SimpleNamespace(info=messages.append)
    monkeypatch.setattr(claim_pages, "st", fake_streamlit)

    claim_pages._render_policy_terms_badge("preconfirmed_fictional_sample")

    assert messages == ["Pre-confirmed fictional sample. The fixture source is recorded in the audit trail."]
