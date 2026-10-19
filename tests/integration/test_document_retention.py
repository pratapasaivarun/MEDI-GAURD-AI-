from datetime import datetime, timedelta, timezone

import pytest

from mediguard.services import application as app


class Upload:
    def __init__(self, name, content):
        self.name = name
        self.content = content

    def getvalue(self):
        return self.content


def test_only_admin_can_purge_expired_documents_and_recent_files_remain(monkeypatch, tmp_path):
    monkeypatch.setenv("MEDIGUARD_DB_PATH", str(tmp_path / "retention.db"))
    monkeypatch.setenv("MEDIGUARD_STORAGE_DIR", str(tmp_path / "private"))
    app.init_db()
    claimant = app.register_user("claimant@example.test", "Fictional Claimant", "a-long-test-password")
    admin_registration = app.register_user("admin@example.test", "Fictional Admin", "a-long-test-password")
    with app.db() as conn:
        conn.execute("UPDATE users SET role='admin' WHERE user_id=?", (admin_registration["user_id"],))
    admin = app.get_user(admin_registration["user_id"])
    claim_id = app.create_claim(claimant["user_id"], "CLM-RETENTION", "Sample Patient", "Sample Hospital", "POL-RETENTION", "2026-08-10")

    app.save_document(claim_id, claimant, Upload("old.pdf", b"%PDF-1.4 old"), "medical_bill")
    app.save_document(claim_id, claimant, Upload("recent.pdf", b"%PDF-1.4 recent"), "medical_bill")
    with app.db() as conn:
        rows = conn.execute("SELECT document_id,stored_path FROM documents WHERE claim_id=? ORDER BY original_name", (claim_id,)).fetchall()
        conn.execute(
            "UPDATE documents SET created_at=? WHERE document_id=?",
            ((datetime.now(timezone.utc) - timedelta(days=40)).isoformat(), rows[0]["document_id"]),
        )

    with pytest.raises(PermissionError):
        app.purge_expired_documents(claimant, 30)
    assert app.purge_expired_documents(admin, 30) == 1

    with app.db() as conn:
        remaining = conn.execute("SELECT document_id FROM documents WHERE claim_id=?", (claim_id,)).fetchall()
    assert [row["document_id"] for row in remaining] == [rows[1]["document_id"]]
    assert not app.Path(rows[0]["stored_path"]).exists()
    assert app.Path(rows[1]["stored_path"]).exists()


def test_retention_period_must_be_positive_and_admin_only(monkeypatch, tmp_path):
    monkeypatch.setenv("MEDIGUARD_DB_PATH", str(tmp_path / "retention-invalid.db"))
    app.init_db()
    registration = app.register_user("admin@example.test", "Fictional Admin", "a-long-test-password")
    with app.db() as conn:
        conn.execute("UPDATE users SET role='admin' WHERE user_id=?", (registration["user_id"],))
    admin = app.get_user(registration["user_id"])
    with pytest.raises(ValueError, match="at least one day"):
        app.purge_expired_documents(admin, 0)
