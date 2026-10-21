# Capture the app screenshots

The screenshots in `docs/images/` are real browser captures of the Streamlit app using only the fictional documents in `samples/demo_cases/`. The capture script makes a temporary copy of the repository, starts that copy with `run_demo.py`, and discards its local database and uploaded files when it exits.

From the repository root, install the development requirements and Playwright's Chromium browser once, then run:

```powershell
python -m pip install -r requirements.txt -r tests/requirements-dev.txt
python -m playwright install chromium
python scripts/capture_screenshots.py
```

The script captures at a 1440 × 900 browser viewport, hides browser chrome by using headless Chromium, uses fictional case data, and optimizes each PNG. It fails if any image exceeds 400 KB. It writes these files:

- `01-login.png`
- `02-upload.png`
- `03-result-wrongful-deduction.png`
- `04-appeal-download.png`
- `05-result-match.png`
- `06-manual-review.png`
- `07-reviewer-confirmation.png`

Do not use real records or commit screenshots from a personal browser session.
