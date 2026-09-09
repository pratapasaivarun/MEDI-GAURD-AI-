import json
import sqlite3
with sqlite3.connect('data/mediguard.db') as conn:
    conn.row_factory = sqlite3.Row
    claim = conn.execute("SELECT claim_id FROM claims WHERE claim_number='CLM-UI-45821' ORDER BY created_at DESC LIMIT 1").fetchone()
    rows = conn.execute("SELECT document_id,original_name,document_type,processing_status,extracted_json FROM documents WHERE claim_id=? ORDER BY created_at", (claim['claim_id'],)).fetchall()
print('DOC_COUNT=', len(rows))
for row in rows:
    payload = json.loads(row['extracted_json']) if row['extracted_json'] else {}
    text = payload.get('text', '')
    print(json.dumps({'document_id': row['document_id'], 'name': row['original_name'], 'type': row['document_type'], 'status': row['processing_status'], 'has_145000': '145000' in text, 'has_85000': '85000' in text, 'text_tail': text[-350:]}, default=str))
