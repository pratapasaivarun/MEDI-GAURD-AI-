from datetime import datetime, timedelta, timezone
import uuid
import app

app.init_db()
admin = app.get_or_create_user(f"admin-{uuid.uuid4().hex[:8]}@example.com", "Admin")
with app.db() as conn:
    conn.execute("UPDATE users SET role='admin', is_active=1, password_hash=? WHERE user_id=?", (app._hash_password("admin-password-123"), admin['user_id']))
admin = app.get_user(admin['user_id'])
invitation = app.create_reviewer_invitation(admin, f"reviewer-{uuid.uuid4().hex[:8]}@example.com", "Invited Reviewer")
assert invitation['setup_token']
with app.db() as conn:
    row = conn.execute("SELECT token_hash,used_at,is_active,password_hash FROM reviewer_invitations JOIN users ON users.user_id=reviewer_invitations.user_id WHERE invitation_id=?", (invitation['invitation_id'],)).fetchone()
    assert row['token_hash'] != invitation['setup_token']
    assert row['used_at'] is None and row['is_active'] == 0 and row['password_hash'] is None
try:
    app.authenticate_user(invitation['email'], 'reviewer-password-123')
    raise AssertionError('inactive reviewer should not authenticate')
except AssertionError:
    pass
activated = app.complete_reviewer_setup(invitation['setup_token'], 'reviewer-password-123')
assert activated['role'] == 'reviewer' and activated['is_active'] == 1 and activated['password_set_at']
assert app.authenticate_user(invitation['email'], 'reviewer-password-123') is not None
set_user = app.set_user_role(admin, activated['user_id'], 'claimant')
assert set_user['role'] == 'claimant'
with app.db() as conn:
    conn.execute("UPDATE users SET role='reviewer' WHERE user_id=?", (activated['user_id'],))
reactivated_role = app.get_user(activated['user_id'])
app.disable_user(admin, activated['user_id'])
assert app.authenticate_user(invitation['email'], 'reviewer-password-123') is None
try:
    app.complete_reviewer_setup(invitation['setup_token'], 'another-password-123')
    raise AssertionError('used token should fail')
except ValueError:
    pass
expired = app.create_reviewer_invitation(admin, f"expired-{uuid.uuid4().hex[:8]}@example.com", "Expired Reviewer")
with app.db() as conn:
    conn.execute("UPDATE reviewer_invitations SET expires_at=? WHERE invitation_id=?", ((datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(), expired['invitation_id']))
try:
    app.complete_reviewer_setup(expired['setup_token'], 'expired-password-123')
    raise AssertionError('expired token should fail')
except ValueError:
    pass
print('REVIEWER_INVITATION_OK')
