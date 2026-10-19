from datetime import datetime, timezone

import pytest

import app


class Upload:
    def __init__(self, name, content):
        self.name = name
        self._content = content

    def getvalue(self):
        return self._content


def test_sixth_failed_password_attempt_is_blocked_for_fifteen_minutes(monkeypatch, tmp_path):
    monkeypatch.setenv("MEDIGUARD_DB_PATH", str(tmp_path / "auth.db"))
    app.init_db()
    app.register_user("reviewer@example.test", "Reviewer", "a-long-test-password")
    for _ in range(5):
        assert app.authenticate_password("reviewer@example.test", "wrong-password") is None
    assert app.authenticate_password("reviewer@example.test", "a-long-test-password") is None
    with app.db() as conn:
        row = conn.execute("SELECT blocked_until FROM login_attempts WHERE email=?", ("reviewer@example.test",)).fetchone()
    assert datetime.fromisoformat(row["blocked_until"]) > datetime.now(timezone.utc)


def test_successful_login_clears_failed_attempts(monkeypatch, tmp_path):
    monkeypatch.setenv("MEDIGUARD_DB_PATH", str(tmp_path / "auth-success.db"))
    app.init_db()
    app.register_user("claimant@example.test", "Claimant", "a-long-test-password")
    app.authenticate_password("claimant@example.test", "wrong-password")
    assert app.authenticate_password("claimant@example.test", "a-long-test-password") is not None
    with app.db() as conn:
        assert conn.execute("SELECT COUNT(*) FROM login_attempts").fetchone()[0] == 0


def test_settlement_upload_requires_text_or_pdf_extension_and_signature():
    assert app._validated_upload(Upload("settlement.txt", b"Amount paid: 100"), "settlement")[0]
    assert app._validated_upload(Upload("settlement.pdf", b"%PDF-1.4"), "settlement")[0]
    with pytest.raises(ValueError):
        app._validated_upload(Upload("settlement.pdf", b"not a pdf"), "settlement")
    with pytest.raises(ValueError):
        app._validated_upload(Upload("settlement.exe", b"%PDF-1.4"), "settlement")


def test_upload_filename_path_components_are_removed_before_storage():
    for hostile_name in ("../../outside.pdf", r"..\..\outside.pdf"):
        content, stored_name = app._validated_upload(Upload(hostile_name, b"%PDF-1.4"))
        assert content == b"%PDF-1.4"
        assert stored_name == "outside.pdf"


def test_user_derived_claim_name_is_html_escaped():
    markup = app.claim_context_html(
        {"claim_number": "CLM-1", "patient_name": "<script>alert(1)</script>", "policy_number": "POL-1"},
        "approved",
    )
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in markup
    assert "<script>" not in markup


def test_demo_mode_and_link_display_default_off(monkeypatch):
    monkeypatch.delenv("MEDIGUARD_CORE_DEMO", raising=False)
    monkeypatch.delenv("MEDIGUARD_DEV_SHOW_LINKS", raising=False)
    assert app.core_demo_mode() is False
    assert app.dev_show_links() is False
