# HTML rendering security review

**Updated:** 2026-10-19  
**Current branch:** `fix/prototype-completion`  
**Scope:** dynamic HTML rendered by the Streamlit app and shared helpers in `ui/components.py`.

The application-authored HTML still uses `unsafe_allow_html=True` for its visual shell. Dynamic claim, patient, policy, status, and attribute values pass through HTML escaping or a fixed allowlist before interpolation. The regression tests are `tests/test_xss_rendering.py` and `tests/test_app_security.py`.

The older call-by-call audit below this file was written against an earlier monolithic layout and is no longer a current line map. Treat it as historical evidence only. Current full test count and branch status are in `PROJECT_STATUS.md` and `FINAL_REPORT.md`.

**Repeat the focused checks:**

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_xss_rendering.py tests/test_app_security.py
```
