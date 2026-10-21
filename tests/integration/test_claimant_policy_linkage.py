"""Claimant upload must link the policy even when clause indexing is unavailable."""
from __future__ import annotations

import json
import uuid
from pathlib import Path

from mediguard.services import application as app


class Upload:
    def __init__(self, name: str, content: bytes):
        self.name = name
        self._content = content

    def getvalue(self) -> bytes:
        return self._content


def test_claimant_upload_links_policy_without_blocking_on_semantic_index(monkeypatch, tmp_path):
    monkeypatch.setenv("MEDIGUARD_DB_PATH", str(tmp_path / "claims.db"))
    monkeypatch.setenv("MEDIGUARD_STORAGE_DIR", str(tmp_path / "storage"))
    monkeypatch.setenv("MEDIGUARD_TRUSTED_FIXTURES", "false")
    index_calls = []
    monkeypatch.setattr(
        app, "index_policy_documents",
        lambda *_args, **_kwargs: index_calls.append(_args),
    )
    app.init_db()

    user_id = str(uuid.uuid4())
    with app.db() as conn:
        conn.execute(
            "INSERT INTO users(user_id,email,display_name,role,created_at) VALUES(?,?,?,?,?)",
            (user_id, f"{user_id}@fictional.test", "Fictional Claimant", "claimant", app.utc_now()),
        )
    user = app.get_user(user_id)
    case_dir = Path(__file__).parents[2] / "samples" / "demo_cases" / "a_match"
    manifest = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
    claim_id = app.create_claim(
        user_id, manifest["claim_number"], manifest["patient_name"],
        manifest["hospital_name"], manifest["policy_number"], "2026-08-10",
    )
    for filename, kind in (
        ("bill.pdf", "medical_bill"), ("policy.pdf", "policy"),
        ("settlement.pdf", "settlement"),
    ):
        app.save_document(claim_id, user, Upload(filename, (case_dir / filename).read_bytes()), kind)

    normalized = app.process_claim_documents(claim_id, user_id)

    assert normalized.get("active_policy_version_id"), {
        "policy_number": normalized.get("policy_number"),
        "policy_index_error": normalized.get("policy_index_error"),
    }
    with app.db() as conn:
        linked_id = conn.execute(
            "SELECT policy_version_id FROM claims WHERE claim_id=?", (claim_id,)
        ).fetchone()["policy_version_id"]
    assert linked_id == normalized["active_policy_version_id"]
    rules = app.evaluate_saved_claim(claim_id, user_id, normalized)
    assert not any("No matching policy edition is linked" in warning for warning in rules["warnings"])
    assert rules["policy_terms_review_status"] == "provisional"
    assert index_calls == []
    assert normalized["policy_index"]["status"] == "deferred_until_policy_search"
