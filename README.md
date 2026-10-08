# MediGuard AI

MediGuard AI is an academic prototype for reviewing medical bills against policy terms and insurer settlement letters. It combines deterministic calculations with document extraction and policy evidence retrieval. It is decision support only: an authorized reviewer must confirm the final claim determination.

## What the prototype does

- Extracts claim fields and itemized charges from PDF and image bills and policy documents.
- Applies deterministic coverage rules, including limits, co-payment, deductible, exclusions, and review flags.
- Parses settlement letters in PDF or UTF-8 text and compares insurer deductions with the policy calculation.
- Shows category-level evidence and can generate conditional appeal-letter and hospital-note drafts in PDF and Word formats.
- Provides claimant, reviewer, and administrator workflows in a Streamlit app.

Model-assisted extraction and explanations are optional and subject to validation. Financial calculations are made by code. Missing, uncertain, or unreconciled information should go to manual review.

**Use synthetic data only. Do not upload real patient documents.** This prototype produces estimates for review and must not be used to make a real claim decision.

## Architecture

```text
Bill + policy --> extraction.py --> policy_terms.py / policy_index.py --> rules.py --+
                                                                                     +--> comparison.py
Settlement letter -------------------------------> settlement.py --------------------+
                                                                                          |--> agents.py (bounded explanation)
                                                                                          |--> reports.py (PDF/DOCX drafts)
                                                                                          +--> app.py (claimant/reviewer UI)
```

| Area | Main files | Responsibility |
|---|---|---|
| Streamlit application and persistence | `app.py` | Authentication, claim/document workflows, reviewer gate, upload checks, and SQLite access |
| Typed pipeline contracts | `models.py` | Shared data classes for bills, policy terms, calculations, settlement data, and comparisons |
| Extraction and policy evidence | `extraction.py`, `policy_terms.py`, `policy_index.py`, `config/categories.yaml` | OCR/text extraction, field review flags, candidate terms, and clause retrieval |
| Deterministic calculation | `rules.py` | Coverage and patient/insurer share calculations |
| Settlement and comparison | `settlement.py`, `comparison.py` | Settlement parsing, reconciliation, and category-level comparison |
| Explanation and reports | `agents.py`, `reports.py` | Evidence-bounded explanations and review document generation |
| Synthetic evaluations | `evaluation/`, `fixtures/claim_scenarios/` | Reproducible evaluation scripts, annotations, and fictional claim cases |

## Requirements

- Python 3.11 or newer
- Tesseract OCR installed locally for scanned documents
- Ollama and the configured model (`ibm/granite4.1:8b`) for optional local model-assisted features
- Commands below use Windows PowerShell; adapt virtual-environment paths for other operating systems

## Install and run

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` as needed. Set `TESSERACT_CMD` if Tesseract is installed outside the example path. Start Ollama and install the configured model only if using model-assisted features:

```powershell
ollama serve
ollama pull ibm/granite4.1:8b
```

Start the application:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Open `http://127.0.0.1:8501`. Claimant accounts can be created from the sign-in screen. Reviewer access is invitation-based. For a local synthetic demonstration, run `run_demo.py`; it uses isolated demo storage and creates its demo administrator only when `MEDIGUARD_ADMIN_PASSWORD` is explicitly set.

## Typical claim workflow

1. Register a claim and upload the applicable policy and hospital bill.
2. Optionally add the insurer settlement letter (`.pdf` or `.txt`) for comparison.
3. Review extracted fields and correct source-backed details where needed.
4. Link and confirm the applicable policy edition, then run the deterministic rules. The rules determine amounts and statuses; the policy provides evidence, and model output is explanatory only and must be reviewed.
5. Review the settlement comparison. Draft letters are enabled only when a possible discrepancy is supported by the comparison; review and personalize any draft before use.
6. An authorized reviewer confirms the final determination.

## Tests

Install development dependencies and run the suite:

```powershell
pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest tests/ -v --basetemp=tmp/pytest_tmp
```

The tests cover deterministic rules, extraction validation, settlement parsing, comparison, generated reports, and app security behavior. Passing synthetic tests is not evidence of accuracy on real claims or any insurer's documents.

## Known limitations

- No MFA is implemented.
- Email delivery is out of scope; password-reset and reviewer setup links are not sent by email.
- Use synthetic data only. Do not use real patient data or upload real patient documents.
- Settlement parsing supports one settlement-letter layout, provided as a text-layer PDF or UTF-8 text, with an optional LLM fallback. Image-only settlement documents require manual review.
- Results are estimates for human review, not insurer decisions or verified entitlements.
- OCR, retrieval relevance, model quality, and expert validation have not been established beyond the synthetic checks described in `evaluation/PAPER_RESULTS.md`.

## Evaluation tools

The scenario library in `fixtures/claim_scenarios/` contains fictional bill/policy PDFs, a `case.json` manifest per scenario, and a `case_index.json` index. Some cases require trusted reviewer context, such as confirmed network or preauthorization status.

Run the isolated app workflow against those scenarios without calling an LLM:

```powershell
.\.venv\Scripts\python.exe evaluation\run_system_evaluation.py --rules-only
```

For a local model run, configure Ollama first and optionally provide model tags and a case limit:

```powershell
.\.venv\Scripts\python.exe evaluation\run_system_evaluation.py --models ibm/granite4.1:8b --limit 2
```

Then score available human annotations and regenerate paper tables:

```powershell
.\.venv\Scripts\python.exe evaluation\score_annotations.py
.\.venv\Scripts\python.exe evaluation\generate_paper_tables.py
```

`evaluation/annotations.json` is the annotation source. Retrieval quality, OCR text error, model quality, and expert validation remain unmeasured where verified ground truth is absent. See `evaluation/PAPER_RESULTS.md` for recorded synthetic results and their limits. The extraction evaluation runner currently expects legacy fixtures under `fixtures/phase4/`; those fixtures are not part of this repository, so that runner and `run_full_evaluation.py` need those inputs before use.

Only add manually verified annotations. `evaluation/annotation_template.json` describes the annotation fields. Retrieval annotations need a query, its case ID, and manually confirmed relevant clause IDs. OCR annotations need a checked transcript and reviewer/date metadata. Evidence and appeal-quality scores require human review; blank or unverified labels should remain unevaluated. The retention purge function is available for an authorized administrator to run manually; automatic retention purging is not configured.

## Configuration and security notes

- Copy `.env.example` to `.env`; never commit secrets or local environment files.
- `MEDIGUARD_CORE_DEMO` defaults to `false`; `run_demo.py` is the supported isolated synthetic demo launcher.
- The demo administrator requires an explicitly supplied `MEDIGUARD_ADMIN_PASSWORD`; no default credential is provided.
- Login throttling is enabled. Password reset responses do not disclose whether an account exists. Reset links remain hidden unless `MEDIGUARD_DEV_SHOW_LINKS=true`; email delivery is out of scope. A reviewer invitation link is shown only to the signed-in administrator who created it.
- This prototype is not certified or suitable for production claims handling. Keep local data and secrets out of commits.

## Repository layout

```text
app.py                         Streamlit application
agents.py                      Model-assisted workflow and explanations
comparison.py                  Settlement-to-policy comparison
config/categories.yaml         Extraction category keywords
docs/                          Implementation changelog and decisions
evaluation/                    Evaluation code, annotations, and results
fixtures/claim_scenarios/      Fictional end-to-end claim fixtures
models.py                      Typed pipeline data structures
policy_index.py                Policy clause indexing and retrieval
policy_terms.py                Policy-term extraction and normalization
reports.py                     Decision, appeal, and hospital documents
rules.py                       Deterministic claim calculation
settlement.py                  Settlement letter parser
tests/                         Automated tests and test fixtures
```

For implementation history and recorded design choices, see `docs/CHANGELOG.md` and `docs/DECISIONS.md`.
