from pathlib import Path
import sqlite3

from app import ingest_policy_version

DB = Path('data/mediguard.db')

with sqlite3.connect(DB) as conn:
    conn.execute("UPDATE policy_versions SET status='archived' WHERE policy_number IN ('POL-HEALTH-4565099', 'POL-HEALTH-45821')")
    conn.commit()

class Upload:
    name = 'sample_policy.pdf'
    def getvalue(self):
        return Path('sample_policy.pdf').read_bytes()

result = ingest_policy_version(Upload(), 'POL-HEALTH-45821', '2026 Edition', 'Example Health Insurance Ltd.', '2026-08-25')
print('INGESTED_VERSION_ID=', result['version_id'])
print('TERMS=', sorted(result['policy_terms'].get('terms_json', {}).keys()))
print('MISSING=', result['policy_terms'].get('missing_terms'))
print('VALIDATION=', result['policy_terms'].get('validation_errors'))
print('CHUNKS=', result['chunks_indexed'])

with sqlite3.connect(DB) as conn:
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT policy_number, version_label, status, indexed_chunks, policy_terms_json FROM policy_versions ORDER BY policy_number, effective_date").fetchall()
    for row in rows:
        print(dict(row))
