# HTML rendering security review

**Updated:** 2026-10-19  
**Current branch:** `fix/prototype-completion`  
**Scope:** dynamic HTML rendered by the Streamlit app and shared helpers in `mediguard/ui/components.py`.

The application-authored HTML still uses `unsafe_allow_html=True` for its visual shell. Dynamic claim, patient, policy, status, and attribute values pass through HTML escaping or a fixed allowlist before interpolation. The regression tests are `tests/integration/test_xss_rendering.py` and `tests/integration/test_app_security.py`.

The older call-by-call audit below this file was written against an earlier monolithic layout and is no longer a current line map. Treat it as historical evidence only. Current full test count and branch status are in `docs/archive/PROJECT_STATUS_2026-10-19.md` and `docs/archive/ARCHIVED_PROJECT_REPORT_2026-10-19.md`.

**Repeat the focused checks:**

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/integration/test_xss_rendering.py tests/integration/test_app_security.py
```
