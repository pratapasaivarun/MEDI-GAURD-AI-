from pathlib import Path
from types import SimpleNamespace
import uuid

import app

app.init_db()
email_a = f"claimant-{uuid.uuid4().hex[:8]}@example.com"
email_b = f"claimant-{uuid.uuid4().hex[:8]}@example.com"
user_a = app.register_user(email_a, "Claimant A", "correct-horse-battery")
assert app.authenticate_user(email_a, "correct-horse-battery") is not None
assert app.authenticate_user(email_a, "wrong-password") is None
try:
    app.register_user(email_a, "Claimant A", "another-password")
    raise AssertionError("duplicate registration should fail")
except ValueError:
    pass
user_b = app.register_user(email_b, "Claimant B", "correct-horse-staple")
claim_id = app.create_claim(user_a['user_id'], 'CLM-SECURITY-1', 'Patient A', 'Hospital A', 'POL-SECURITY', '2026-08-25')
with app.db() as conn:
    conn.execute("UPDATE claims SET status='manual_review' WHERE claim_id=?", (claim_id,))
try:
    app._claim_access(claim_id, user_b)
    raise AssertionError("cross-user claim access should fail")
except PermissionError:
    pass
with app.db() as conn:
    conn.execute("UPDATE users SET role='reviewer' WHERE user_id=?", (user_b['user_id'],))
user_b = app.get_user(user_b['user_id'])
try:
    app.save_reviewer_decision(claim_id, user_a['user_id'], 'manual_review', 'approved', 'not allowed')
    raise AssertionError("claimant reviewer sign-off should fail")
except PermissionError:
    pass
app._claim_access(claim_id, user_b)
app.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
private_file = app.STORAGE_DIR / f"security-{uuid.uuid4().hex}.txt"
private_file.write_text("private", encoding="utf-8")
doc = {"claim_id": claim_id, "stored_path": str(private_file)}
assert app.secure_document_path(doc, user_b) == private_file.resolve()
try:
    app.secure_document_path({"claim_id": claim_id, "stored_path": str(Path(app.APP_DIR) / "app.py")}, user_b)
    raise AssertionError("outside-storage path should fail")
except PermissionError:
    pass
private_file.unlink(missing_ok=True)
print("SECURITY_ACCESS_OK")
