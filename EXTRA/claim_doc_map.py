import sqlite3
with sqlite3.connect('data/mediguard.db') as conn:
    conn.row_factory = sqlite3.Row
    claims = conn.execute("SELECT claim_id,user_id,claim_number,status,created_at FROM claims WHERE claim_number='CLM-2026-0001' ORDER BY created_at DESC").fetchall()
    for claim in claims:
        docs = conn.execute("SELECT original_name,document_type,processing_status FROM documents WHERE claim_id=? ORDER BY created_at", (claim['claim_id'],)).fetchall()
        print(claim['claim_id'], claim['status'], claim['created_at'], [(d['original_name'], d['document_type'], d['processing_status']) for d in docs])
