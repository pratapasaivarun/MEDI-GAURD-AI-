"""Exercise page routing and password links against an isolated database."""
import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent
RUN = Path(tempfile.mkdtemp(prefix="ui_audit_", dir=ROOT / "data"))
os.environ["MEDIGUARD_DB_PATH"] = str(RUN / "test.db")
os.environ["MEDIGUARD_STORAGE_DIR"] = str(RUN)
os.environ["MEDIGUARD_CORE_DEMO"] = "false"
os.environ["ADMIN_EMAIL"] = ""
import app
from streamlit.testing.v1 import AppTest

app.init_db()
claimant = dict(app.register_user("ui@local.test", "UI Test", "test-password-123"))
claim_id = app.create_claim(claimant['user_id'], 'UI-1', 'Test', 'Hospital', 'POL-1', '2026-09-16')
admin = app._core_demo_user()
demo_admin = app.authenticate_password('demo@mediguard.local', 'Mediguard@2026')
assert demo_admin and demo_admin['role'] == 'admin'
welcome = AppTest.from_file(str(ROOT / 'app.py'))
welcome.run(timeout=40)
assert not welcome.exception
assert len(welcome.radio) == 1
next(b for b in welcome.button if b.label == 'Continue as user').click().run()
assert not welcome.exception
print('WELCOME_SCREEN_OK')
for user, pages in [(claimant, ['Dashboard', 'Register claim', 'Submit documents', 'Claim result']),
                    (admin, ['Dashboard', 'Register claim', 'Claim review', 'Claim result', 'Policy management', 'Admin panel'])]:
    for page in pages:
        ui = AppTest.from_file(str(ROOT / 'app.py'))
        ui.session_state['welcome_seen'] = True
        ui.session_state['user'] = user
        ui.session_state['page'] = page
        ui.run(timeout=40)
        assert not ui.exception, (page, ui.exception)
        assert ui.radio[0].value == page
        if page == 'Claim result':
            next(b for b in ui.button if b.label == 'Continue claim review').click().run()
            assert not ui.exception and ui.radio[0].value == ('Submit documents' if user['role'] == 'claimant' else 'Claim review')
        print('PAGE_OK', user['role'], page)

token = app.create_password_reset_request(claimant['email'])['reset_token']
ui = AppTest.from_file(str(ROOT / 'app.py'))
ui.query_params['reset_token'] = token
ui.run(timeout=40)
ui.text_input[0].set_value('replacement-password-123')
ui.text_input[1].set_value('replacement-password-123')
next(b for b in ui.button if b.label == 'Save password').click().run()
assert not ui.exception
assert app.authenticate_password(claimant['email'], 'replacement-password-123')
assert not ui.query_params
print('RESET_LINK_OK')

invitation = app.create_reviewer_invitation(admin, 'reviewer@local.test', 'Reviewer')
ui = AppTest.from_file(str(ROOT / 'app.py'))
ui.query_params['setup_token'] = invitation['setup_token']
ui.run(timeout=40)
ui.text_input[0].set_value('reviewer-password-123')
ui.text_input[1].set_value('reviewer-password-123')
next(b for b in ui.button if b.label == 'Save password').click().run()
assert not ui.exception
assert app.authenticate_password('reviewer@local.test', 'reviewer-password-123')['role'] == 'reviewer'
print('REVIEWER_SETUP_LINK_OK')
