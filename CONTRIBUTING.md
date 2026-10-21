# Contributing

MediGuard AI is a fictional-data college prototype. Do not submit real patient or insurance documents, credentials, local databases, model caches, or generated test artifacts.

## Local setup

Use Python 3.13. Create and activate a virtual environment, install `requirements.txt` and `tests/requirements-dev.txt`, then copy `.env.example` to `.env`. Install Tesseract only if you need scanned-page OCR. Ollama is optional.

## Checks

From the repository root, run:

```bash
python -m pytest -q tests
python -m evaluation.run_all
```

Browser and live Ollama checks are optional; see the README and evaluation guide. Keep sample files fictional and record expected values before running evaluation.

## Changes

Keep calculation behavior covered by regression tests. Use clear names, focused commits, and update the relevant numbered docs when behavior or setup changes. The project does not currently enforce a formatter; follow existing Python style and avoid unrelated formatting churn.
