import app

app.init_db()
user = app.get_or_create_user('controls-reviewer@example.com', 'Controls Reviewer')
with app.db() as conn:
    conn.execute("UPDATE users SET role='reviewer' WHERE user_id=?", (user['user_id'],))
user = app.get_user(user['user_id'])
claim_id = app.create_claim(user['user_id'], 'CLM-CONTROLS-1', 'Old Name', 'Old Hospital', 'POL-CONTROLS', '2026-08-25')
with app.db() as conn:
    conn.execute("UPDATE claims SET status='manual_review' WHERE claim_id=?", (claim_id,))
app.assign_claim(claim_id, user['user_id'], user['user_id'])
queue = app.reviewer_queue()
assert any(item['claim_id'] == claim_id for item in queue), queue
app.save_claim_field_edits(claim_id, user['user_id'], {'patient_name': 'New Name', 'hospital_name': 'New Hospital'})
app.confirm_evidence(claim_id, user['user_id'], [{'field_name': 'patient_name', 'document_id': 'doc-1', 'page_number': 1}])
with app.db() as conn:
    row = conn.execute('SELECT patient_name,hospital_name,assigned_reviewer_id FROM claims WHERE claim_id=?', (claim_id,)).fetchone()
    assert row['patient_name'] == 'New Name', row
    assert row['hospital_name'] == 'New Hospital', row
    assert row['assigned_reviewer_id'] == user['user_id'], row
    assert conn.execute('SELECT COUNT(*) FROM reviewer_field_edits WHERE claim_id=?', (claim_id,)).fetchone()[0] == 2
    assert conn.execute('SELECT COUNT(*) FROM evidence_confirmations WHERE claim_id=?', (claim_id,)).fetchone()[0] == 1
app.reopen_claim(claim_id, user['user_id'], 'New supporting document received.')
with app.db() as conn:
    assert conn.execute('SELECT status FROM claims WHERE claim_id=?', (claim_id,)).fetchone()['status'] == 'manual_review'
    events = [row['event_type'] for row in conn.execute('SELECT event_type FROM audit_events WHERE claim_id=?', (claim_id,)).fetchall()]
    assert 'reviewer_assigned' in events and 'claim_fields_edited' in events and 'evidence_confirmed' in events and 'claim_reopened' in events
print('REVIEWER_CONTROLS_OK')
