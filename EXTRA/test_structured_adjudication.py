import json
import os
import uuid
import app
from rules import PolicyTerms, evaluate_claim

app.init_db()
claimant = app.register_user(f"claimant-{uuid.uuid4().hex[:8]}@example.com", "Claimant", "claimant-password-123")
admin_email = f"admin-{uuid.uuid4().hex[:8]}@example.com"
admin_id = uuid.uuid4().hex[:24]
with app.db() as conn:
    conn.execute("INSERT INTO users(user_id,email,display_name,role,password_hash,is_active,password_set_at,created_at) VALUES(?,?,?,?,?,?,?,?)", (admin_id, admin_email, "Admin", "admin", app._hash_password("admin-password-123"), 1, app.utc_now(), app.utc_now()))
admin = app.get_user(admin_id)
invitation = app.provision_user_role(admin, f"reviewer-{uuid.uuid4().hex[:8]}@example.com", "Reviewer", "reviewer")
reviewer = app.complete_reviewer_setup(invitation["setup_token"], "reviewer-password-123")
claim_id = app.create_claim(claimant['user_id'], f"CLM-{uuid.uuid4().hex[:8]}", "Alex Morgan", "North Star General Hospital", "POL-SYN-1001", "2026-07-10")
app.save_adjudication_context(claim_id, claimant, {"network_status":"in_network", "preauthorization_status":"confirmed", "waiting_period_status":"satisfied", "trusted":True})
context = app.load_adjudication_context(claim_id, claimant)
assert context['trusted'] is False and context['source'] == 'claimant_asserted'
terms = PolicyTerms(source={"network_required":{"value":True}, "preauthorization_required":{"value":True}}, waiting_period_months=12)
manual = evaluate_claim(145000, terms=terms, claim_context={"diagnosis":"acute appendicitis", "in_network":None, "preauthorization_obtained":None, "waiting_period_satisfied":None})
assert manual['status'] == 'manual_review'
app.assign_claim(claim_id, reviewer['user_id'], admin['user_id'])
app.save_adjudication_context(claim_id, reviewer, {"network_status":"in_network", "preauthorization_status":"confirmed", "waiting_period_status":"satisfied", "preauthorization_reference":"AUTH-123", "trusted":True})
confirmed = app.load_adjudication_context(claim_id, reviewer)
assert confirmed['trusted'] is True and confirmed['source'] == 'reviewer_confirmed'
ready = evaluate_claim(145000, terms=terms, claim_context={"diagnosis":"acute appendicitis", "in_network":True, "preauthorization_obtained":True, "waiting_period_satisfied":True})
assert ready['status'] == 'approved'
print('STRUCTURED_ADJUDICATION_OK')
