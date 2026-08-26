import os
import uuid
from datetime import datetime, timedelta, timezone
import pyotp
import app

os.environ["MEDIGUARD_MFA_KEY"] = "mfa-test-key-abcdefghijklmnopqrstuvwxyz"
app.init_db()
email = f"auth-{uuid.uuid4().hex[:8]}@example.com"
user = app.register_user(email, "Auth Test User", "initial-password-123")
assert app.authenticate_user(email, "initial-password-123") is not None
enrollment = app.begin_totp_enrollment(user)
with app.db() as conn:
    stored = conn.execute("SELECT mfa_secret_encrypted FROM users WHERE user_id=?", (user['user_id'],)).fetchone()['mfa_secret_encrypted']
assert stored and enrollment['secret'] not in stored
code = pyotp.TOTP(enrollment['secret']).now()
user = app.complete_totp_enrollment(user, code)
assert user['mfa_enabled'] == 1
assert app.authenticate_password(email, "initial-password-123") is not None
assert app.authenticate_user(email, "initial-password-123") is None
assert app.authenticate_user(email, "initial-password-123", pyotp.TOTP(enrollment['secret']).now()) is not None
reset = app.create_password_reset_request(email)
assert reset['reset_token'] and reset['reset_token'] not in [row[0] for row in app.db().execute("SELECT token_hash FROM password_reset_tokens").fetchall()]
updated = app.complete_password_reset(reset['reset_token'], "new-password-456")
assert updated['password_set_at']
assert app.authenticate_user(email, "new-password-456", pyotp.TOTP(enrollment['secret']).now()) is not None
try:
    app.complete_password_reset(reset['reset_token'], "third-password-789")
    raise AssertionError("reset token reuse should fail")
except ValueError:
    pass
expired = app.create_password_reset_request(email)
with app.db() as conn:
    conn.execute("UPDATE password_reset_tokens SET expires_at=? WHERE token_hash=?", ((datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(), app._token_hash(expired['reset_token'])))
try:
    app.complete_password_reset(expired['reset_token'], "expired-password-123")
    raise AssertionError("expired reset token should fail")
except ValueError:
    pass
unknown = app.create_password_reset_request("unknown-auth@example.com")
assert unknown['reset_token'] is None
print("AUTH_LIFECYCLE_OK")
