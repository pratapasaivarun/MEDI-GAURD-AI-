import os
import sqlite3
import tempfile
from pathlib import Path
import app

app.init_db()
admin = app.get_or_create_user("phase7-admin@example.com", "Phase7 Admin")
with app.db() as conn:
    conn.execute("UPDATE users SET role='admin', is_active=1, password_hash=? WHERE user_id=?", (app._hash_password("phase7-admin-password"), admin['user_id']))
admin = app.get_user(admin['user_id'])
claim_id = app.create_claim(admin['user_id'], "CLM-PHASE7", "Synthetic Patient", "Synthetic Hospital", "POL-SYN", "2026-08-26")
claim_dir = app.UPLOAD_DIR / claim_id
claim_dir.mkdir(parents=True, exist_ok=True)
doc_id = "phase7-doc"
path = claim_dir / f"{doc_id}_synthetic.txt"
path.write_bytes(b"synthetic document only")
with app.db() as conn:
    conn.execute("INSERT OR REPLACE INTO documents(document_id,claim_id,original_name,stored_path,document_type,size_bytes,sha256,page_count,processing_status,extracted_json,extraction_error,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (doc_id, claim_id, "synthetic.txt", str(path), "medical_bill", path.stat().st_size, "synthetic", 1, "uploaded", None, None, app.utc_now()))
read_bytes, original_name, document_type = app.read_document_bytes(doc_id, admin)
assert read_bytes == b"synthetic document only" and original_name == "synthetic.txt" and document_type == "medical_bill"
claimant = app.register_user(f"phase7-claimant-{__import__('uuid').uuid4().hex[:8]}@example.com", "Phase7 Claimant", "phase7-claimant-password")
try:
    app.read_document_bytes(doc_id, claimant)
    raise AssertionError("claimant should not read another user's document")
except PermissionError:
    pass
app.delete_document(doc_id, admin)
assert not path.exists()
with app.db() as conn:
    assert conn.execute("SELECT 1 FROM documents WHERE document_id=?", (doc_id,)).fetchone() is None
    assert conn.execute("SELECT 1 FROM audit_events WHERE event_type='document_deleted' AND details LIKE ?", (f"%{doc_id}%",)).fetchone() is not None

os.environ["MEDIGUARD_BACKUP_KEY"] = "phase7-backup-secret-abcdefghijklmnopqrstuvwxyz"
with tempfile.TemporaryDirectory() as temp:
    encrypted = app.create_encrypted_backup(admin, Path(temp) / "mediguard.sqlite")
    assert encrypted.suffix == ".enc" and encrypted.exists()
    restored = app.restore_encrypted_backup(admin, encrypted, Path(temp) / "restored.sqlite")
    restored_conn = sqlite3.connect(restored)
    assert restored.exists() and restored_conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'").fetchone()
    restored_conn.close()
    os.environ["MEDIGUARD_BACKUP_KEY"] = "wrong-backup-secret-abcdefghijklmnopqrstuvwxyz"
    try:
        app.restore_encrypted_backup(admin, encrypted, Path(temp) / "wrong.sqlite")
        raise AssertionError("wrong backup key should fail")
    except ValueError:
        pass
print("PHASE7_DATA_SECURITY_OK")
