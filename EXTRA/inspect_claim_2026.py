import json
import sqlite3
with sqlite3.connect('data/mediguard.db') as conn:
    conn.row_factory = sqlite3.Row
    claims = conn.execute("SELECT claim_id,user_id,claim_number,patient_name,policy_number,status,created_at FROM claims WHERE claim_number='CLM-2026-0001' ORDER BY created_at DESC").fetchall()
    print('CLAIMS=', json.dumps([dict(r) for r in claims], indent=2, default=str))
    for claim in claims:
        docs = conn.execute("SELECT document_id,original_name,document_type,processing_status,created_at,extracted_json FROM documents WHERE claim_id=? ORDER BY created_at", (claim['claim_id'],)).fetchall()
        print('DOCS_FOR=', claim['claim_id'])
        for d in docs:
            payload = json.loads(d['extracted_json']) if d['extracted_json'] else {}
            text = payload.get('text','')
            print(json.dumps({'id':d['document_id'],'name':d['original_name'],'type':d['document_type'],'status':d['processing_status'],'has_145000':'145000' in text,'has_85000':'85000' in text,'tail':text[-100:]}, default=str))
