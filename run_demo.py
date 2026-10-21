"""Launch the local synthetic-data mini-project demo in isolated storage."""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
demo_port = int(os.getenv('MEDIGUARD_DEMO_PORT', '8506'))
storage = ROOT / 'data' / 'final_demo'
os.environ.update({
    'MEDIGUARD_DB_PATH': str(storage / 'mediguard.db'),
    'MEDIGUARD_STORAGE_DIR': str(storage),
    'CHROMA_DIR': str(storage / 'chroma'),
    'MEDIGUARD_CORE_DEMO': 'true',
    'MEDIGUARD_TRUSTED_FIXTURES': 'true',
    'APP_ENV': 'development',
    'MEDIGUARD_ADMIN_EMAIL': '',
})
if os.getenv('MEDIGUARD_ADMIN_PASSWORD'):
    # The launcher is the sole place that provisions the synthetic demo admin.
    from mediguard.services.application import _core_demo_user, init_db
    init_db()
    _core_demo_user()
else:
    print('MEDIGUARD_ADMIN_PASSWORD is unset; no demo administrator was created.', flush=True)
print(f'Synthetic local demonstration: http://127.0.0.1:{demo_port}', flush=True)
print('Demo claims persist under data/final_demo. Press Ctrl+C to stop.', flush=True)
raise SystemExit(subprocess.call([sys.executable, '-m', 'streamlit', 'run', str(ROOT / 'app.py'), '--server.port', str(demo_port), '--server.address', '127.0.0.1'], cwd=ROOT))
