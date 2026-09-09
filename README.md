# Medi Gaurd AI

Local Streamlit prototype for document extraction, policy evidence retrieval, deterministic claim calculations, and an Ollama-assisted claim decision.

## Run locally on Windows

1. Create and activate a virtual environment:

   ```powershell
   py -3 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```

2. Copy `.env.example` to `.env`. Confirm that Tesseract is installed and that Ollama has the configured model:

   ```powershell
   ollama list
   ollama serve
   ```

3. Start the app:

   ```powershell
   .\.venv\Scripts\python.exe -m streamlit run app.py
   ```

   The app listens at `http://127.0.0.1:8505` by default.

## Local prerequisites

- Python 3.11 or newer (the checked environment uses Python 3.13)
- Tesseract OCR at `C:\Program Files\Tesseract-OCR\tesseract.exe`
- Ollama with `ibm/granite4.1:8b` available locally

## Verification

```powershell
.\.venv\Scripts\python.exe test_core_advancements.py
.\.venv\Scripts\python.exe test_end_to_end.py
.\.venv\Scripts\python.exe test_academic_e2e.py
```

`MEDIGUARD_CORE_DEMO=true` is for synthetic local demonstrations only. Do not use it with real patient information.
