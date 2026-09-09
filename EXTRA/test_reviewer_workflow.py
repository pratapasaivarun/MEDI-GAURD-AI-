import app

app.init_db()
user = app.get_or_create_user('reviewer-test@example.com', 'Reviewer Test')
with app.db() as conn:
    conn.execute("UPDATE users SET role='reviewer' WHERE user_id=?", (user['user_id'],))
user = app.get_user(user['user_id'])
claim_id = app.create_claim(user['user_id'], 'CLM-TEST-REVIEW', 'Test Patient', 'Test Hospital', 'POL-TEST', '2026-08-25')
app.save_reviewer_decision(claim_id, user['user_id'], 'approved', 'manual_review', 'Policy evidence requires confirmation.')
review = app.latest_reviewer_decision(claim_id)
assert review is not None
assert review['automated_status'] == 'approved'
assert review['final_status'] == 'manual_review'
assert review['comments'] == 'Policy evidence requires confirmation.'
with app.db() as conn:
    claim = conn.execute('SELECT status FROM claims WHERE claim_id=?', (claim_id,)).fetchone()
assert claim['status'] == 'manual_review'
print('REVIEWER_WORKFLOW_TEST_OK')
