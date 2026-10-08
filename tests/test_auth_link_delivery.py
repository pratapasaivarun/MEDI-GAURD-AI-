import uuid

import pytest
from streamlit.testing.v1 import AppTest

import app


def test_reset_and_invitation_tokens_are_never_logged_and_default_reset_link_is_hidden(monkeypatch, tmp_path, caplog):
    monkeypatch.setenv("MEDIGUARD_DB_PATH", str(tmp_path / "links.db"))
    monkeypatch.setenv("MEDIGUARD_DEV_SHOW_LINKS", "false")
    app.init_db()
    admin_id = str(uuid.uuid4())
    reviewer_id = str(uuid.uuid4())
    with app.db() as conn:
        conn.execute(
            "INSERT INTO users(user_id,email,display_name,role,password_hash,is_active,created_at) VALUES(?,?,?,?,?,?,?)",
            (admin_id, "admin@example.test", "Admin", "admin", "test-hash", 1, app.utc_now()),
        )
        conn.execute(
            "INSERT INTO users(user_id,email,display_name,role,password_hash,is_active,created_at) VALUES(?,?,?,?,?,?,?)",
            (reviewer_id, "reviewer@example.test", "Reviewer", "claimant", "test-hash", 1, app.utc_now()),
        )
    admin = app.get_user(admin_id)
    with caplog.at_level("INFO"):
        reset = app.create_password_reset_request("reviewer@example.test")
        invitation = app.create_reviewer_invitation(admin, "new-reviewer@example.test", "New Reviewer")

    assert reset["reset_token"] not in caplog.text
    assert invitation["setup_token"] not in caplog.text
    assert "token issued" in caplog.text.lower()
    assert reviewer_id in caplog.text
    assert invitation["user_id"] in caplog.text
    assert app.password_reset_link_for_display(reset) is None
    app_output = AppTest.from_function(lambda: app._render_password_reset_link(reset)).run()
    assert reset["reset_token"] not in str(app_output)


def test_only_admin_can_obtain_reviewer_invite_link(monkeypatch):
    monkeypatch.setenv("APP_BASE_URL", "http://localhost:8505")
    invitation = {"setup_token": "example-one-time-token", "user_id": "reviewer-id"}
    assert "example-one-time-token" in app.reviewer_invitation_link({"role": "admin"}, invitation)
    with pytest.raises(PermissionError):
        app.reviewer_invitation_link({"role": "claimant"}, invitation)
