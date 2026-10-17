# MediGuard AI end-to-end project report

**Audit date:** 2026-10-17
**Repository:** `MediGaurd_AI`
**Branch reviewed:** `finish-mini-prototype`
**Scope:** supplied project ZIP, tracked repository contents, documented architecture, local test suite, compilation, and packaging hygiene. This is a prototype review, not a clinical, legal, privacy, or penetration assessment.

## Executive summary

MediGuard AI is a Streamlit decision-support prototype for comparing a hospital bill and insurance policy with an insurer's settlement letter. It uses document extraction and policy-clause retrieval to prepare evidence, deterministic Python rules to calculate amounts, and optional model output only for explanation or review-flagged extraction. Uncertain or unreconciled inputs are routed to a human reviewer.

The project source is organized into business-logic modules, a shared typed model layer, UI modules, tests, synthetic fixtures, evaluation tools, configuration, and documentation. At inspection time, the supplied ZIP matched the then-current `finish-mini-prototype` revision: **all 173 tracked files matched byte-for-byte**. The cleanup in this report then removed three unused, unlabelled PDFs, moved the plan into `docs/`, and added this report. The supplied ZIP is a machine snapshot, not a clean deliverable; it also contains a local `.env`, a SQLite data file, a multi-gigabyte Python environment, temporary outputs, and nested ZIP backups. Do not redistribute the supplied archive as-is.

## End-to-end workflow

1. **Account and claim setup:** the Streamlit app provides claimant, reviewer, and administrator workflows. Authentication, role checks, claim ownership, reviewer assignment, and local SQLite persistence are coordinated in `app.py`.
2. **Upload validation and storage:** bill, policy, and settlement files are checked for allowed type, size, and file signature where applicable, then stored in the app's local data area.
3. **Bill and policy processing:** `extraction.py` reads document text and OCR results into normalized fields and line items. `policy_terms.py` extracts candidate terms, while `policy_index.py` retrieves policy passages and page references. Extracted or ambiguous evidence can require reviewer confirmation.
4. **Deterministic claim calculation:** `rules.py` calculates line-level allowed and disallowed amounts, room and ICU limits, co-pay, sum-insured effects, and patient/insurer shares using Decimal values. Uncertain inputs remain subject to manual review.
5. **Settlement parsing and binding:** `settlement.py` extracts claim references, labeled payments, bill totals, co-pay, and deductions from text-layer PDFs or text files. `app.py` binds the settlement to the selected claim and checks the bill total before comparison. Missing paid amount, missing identity, or unreconciled totals block reliance.
6. **Comparison and explanation:** `comparison.py` compares insurer deductions with rule-supported amounts and policy evidence. `agents.py` may explain the result, but validated or fallback wording cannot change the calculation or status.
7. **Review and document generation:** claimant/reviewer screens show evidence and review reasons. `reports.py` creates neutral PDF/DOCX drafts; appeal drafts are gated on a supported possible discrepancy. A reviewer makes the final determination.
8. **Persistence and reload:** parsed settlement and comparison data are saved in SQLite and tied to the settlement document hash so stale comparisons are not reused after the document changes.

## Repository structure

```text
README.md                 Setup, user workflow, test commands, and limitations
app.py                    Streamlit entry point, auth, persistence, orchestration
models.py                 Typed data contracts and Decimal amounts
extraction.py             PDF/image text extraction and bill-field validation
policy_terms.py           Policy term extraction and reviewer confirmation support
policy_index.py           Policy-clause indexing and retrieval
rules.py                  Deterministic claim calculation
settlement.py             Settlement-letter parsing and validation
comparison.py             Pure settlement-versus-rules comparison
agents.py                 Bounded explanations and fallback language
reports.py                Neutral appeal and hospital-note outputs
ui/                       Authentication, claimant/reviewer pages, shared components
config/                   Category and trusted-fixture configuration
fixtures/, demo_assets/    Synthetic claim, policy, and settlement examples
tests/                    Unit, integration, security, and workflow regression tests
evaluation/               Synthetic evaluation runners and recorded outputs
docs/                     Changelog, decisions, audits, security notes, implementation plan
requirements*.txt         Runtime and development dependency pins
```

There is one root `README.md`. The source is partitioned sensibly around the calculation pipeline and UI. `app.py` remains a large orchestration module that also owns authentication and persistence; splitting those responsibilities into dedicated services is a reasonable future refactor, but doing so now would create broad behavioral risk without improving this audit deliverable.

## What is implemented and verified

- A shared typed data model and deterministic rules path; the legacy `_evaluate_claim_total_only` helper is absent.
- Bill extraction, India-oriented date parsing, category mapping, review flags, and policy-term handling.
- Policy clause retrieval with page references and conservative filtering.
- Settlement parsing for six fictional layouts, including slash-separated and numeric claim IDs. A claimed amount is no longer used as a substitute for a missing paid amount.
- Claim and bill-total binding, explicit confirmation when the settlement omits a bill total, category-level comparison, reconciliation, and date-window review.
- Optional constrained explanations, fixed-template report fallbacks, comparison persistence, and discrepancy-gated appeal drafts.
- Login throttling, role-based access, upload checks, reset/invitation-link safeguards, and escaping coverage for dynamic HTML.
- A synthetic end-to-end workflow and focused regressions; external model/index calls are mocked by tests.
- The three unreferenced PDFs formerly under `tests/fixtures/real_documents/` were removed. Their path/name implied real documents and the files lacked the required fictional-sample label; no source or test referenced them.

### Verification run on 2026-10-17

- `.venv\\Scripts\\python.exe -m pytest -q --basetemp=.pytest-audit-final` — **116 passed** in 104.16 seconds after removing the unused fixtures.
- Python `compileall` for the app, business modules, UI, and tests — passed.
- `git diff --check` — passed after report formatting was corrected.
- The supplied ZIP was compared with the current Git checkout; all **173 tracked files matched**.

These are synthetic software checks only. They do not demonstrate performance, accuracy, or suitability on real claims or insurer documents.

## Limitations and follow-up

- Use synthetic data only. The prototype is not a real claim adjudicator and must not process real patient documents.
- MFA and outbound email delivery are not implemented. Password reset and reviewer setup are constrained in-app flows.
- OCR depends on a local Tesseract installation. Ollama and the configured model are optional; first-time embedding/model setup may require network access.
- Settlement layouts, policy wording, retrieval relevance, OCR quality, and model explanations have not been validated with representative real-world data.
- Clause retrieval conservatively discards passages containing terms such as “except” or “inadmissible”; a payable clause with a legitimate exception may therefore be omitted and sent to review.
- Retention cleanup is an explicit administrator action; automatic purging is not configured. Production encryption-at-rest and deployment controls have not been established.
- The older extraction/full evaluation commands reference legacy `fixtures/phase4/` inputs that are not present. The current automated suite is independent of those legacy inputs.

## ZIP audit and cleanup plan

The supplied `MediGaurd AI.zip` is about **1.86 GB compressed** and expands to about **3.47 GB** with roughly **75,500 entries**. It contains the project plus:

- `.venv/` at about **2.34 GB**, including large binary packages and a model cache.
- A `.env` file. Its contents were not inspected or copied. If it contains real credentials and this ZIP has been shared beyond a trusted recipient, rotate those credentials.
- `data/` with a local SQLite database; its records were not inspected and must stay out of a distributable project archive.
- `tmp/` with about **1,025 generated files** and more than **22 MB** of test/runtime artifacts, along with pytest caches and bytecode caches.
- Nested ZIP backups, including a roughly **320 MB** implementation archive.

The original ZIP was left untouched. The implementation-plan PDF was moved from the stray `T/` folder into `docs/IMPLEMENTATION_PLAN.pdf` so its role is clear and it remains available with the project. The clean project ZIP contains the repository source, synthetic fixtures, tests, docs, and shallow Git metadata while excluding `.env`, `.venv`, databases, user uploads, caches, temporary outputs, and nested archives. The unused PDFs described above are not included.

The local Git database is also unusually large because the repository history contains old archive content and loose objects. Do not rewrite published history to shrink it; the clean deliverable can use a shallow branch clone with Git metadata while preserving the complete current source tree.
