# Changelog

## MediGuard prototype completion — 2026-10-09

- Fixed the extracted uppercase room category being skipped by the app's room-limit context, introduced shared case-insensitive category normalization, and use Decimal amounts for room-linked context. Hospital stay days use the date difference, matching the four-day room example for 10–14 August.
- Added an app-context regression test. It failed before the fix because `room_charge` was absent, then passed; full suite after the task: **62 passed**.
- Bound settlement comparisons to the selected claim and uploaded bill total (tolerance INR 1), made missing totals a manual-review condition, and surfaced missing claim IDs as review reasons. Added five app-path settlement tests, including a spaced/case-variant matching reference.
- Removed document-keyword shortcuts for policy confirmation and bill-line review. Trusted fixture auto-confirmation now requires `MEDIGUARD_TRUSTED_FIXTURES=true`, a required-term set, and an allowlisted SHA-256 hash; only `run_demo.py` opts in. Added two upload-pipeline tests; the pre-fix keyword-based test failed, and both pass after the change.

## Phase 0 - Baseline and safe defaults

- Added the typed pipeline contracts in `models.py`; kept them independent of the existing runtime during this baseline phase.
- Disabled core demo mode by default, removed published demo credentials, and made demo administrator creation require `MEDIGUARD_ADMIN_PASSWORD` through `run_demo.py` only.
- Added the prototype/sample-data warning, corrected the MediGuard spelling in user-facing copy, pinned application dependencies, moved pytest to `requirements-dev.txt`, and replaced PyMuPDF's legacy `fitz` import.
- Removed duplicate `.gitignore` entries.
- Tests: baseline `pytest tests/ -q --basetemp=tmp/pytest_baseline`: **32 passed in 69.72s**. No new tests in this phase.

## Phase 1 - One deterministic rule path

- Replaced the separate aggregate calculator with a shared item pipeline; aggregate-only claims are represented as a synthetic `OTHER` item.
- Added typed `BillData`/`PolicyTerms` input and `ClaimResult` output support while preserving the current JSON-facing app interface.
- Added room cap and proportionate room-linked reductions, exact surname matching with initials, diagnosis-exclusion review, duplicate retention with review flags, and 1% item-total reconciliation.
- Updated tests that expected duplicate removal or automatic exclusion denial; added the room, reconciliation, identity, duplicate, diagnosis, and typed-contract cases.
- Tests: `pytest tests/ -q --basetemp=tmp/pytest_phase1_full`: **38 passed in 12.98s**.

## Phase 2 - Extraction hardening

- Added India-oriented date parsing for numeric and month-name formats; ambiguous dates are flagged only when the stay order changes under the alternate reading.
- Marked every LLM-derived field and line item as `source="llm"` and `needs_review=True`, wrapped document text in untrusted `<bill>` tags, and added structural/type/amount/date validation.
- Added `config/categories.yaml` keyword categories; unknown descriptions map to `OTHER` and require review.
- Tests: `pytest tests/ -q --basetemp=tmp/pytest_phase2`: **43 passed in 22.93s**.

## Phase 3 - Settlement letter parser

- Added `settlement.py` for text/PDF magic-byte and size validation, regex-first extraction, category mapping, optional review-flagged LLM fallback, and INR 1 reconciliation.
- Added fictional settlement letter fixtures in text and searchable PDF formats plus parser and upload-validation tests.
- Tests: settlement-specific suite passed **5 tests**.

## Phase 4 - Comparison engine

- Added the pure `comparison.py` engine for category-level deduction comparison, clause requirements on disputed deductions, copay-adjusted payout effects, and reconciliation.
- Added the exact fictional demo arithmetic: expected insurer share INR 1,11,600, patient share INR 20,400, and possible difference INR 9,000.
- Tests: focused settlement and comparison suites passed **9 tests**.

## Phase 5 - Explanation and review documents

- Added constrained comparison explanations with fixed-template fallback; model amounts and clause citations are validated against comparison data.
- Added neutral appeal-letter and hospital billing-note drafts in PDF and DOCX, with an explicit estimate disclaimer and INR lakh/crore grouping.
- Tests: focused comparison/report suite passed **8 tests**.

## Phase 6 - App integration and security

- Added settlement uploads to claimant and reviewer flows, secure settlement comparison, category-level results, and conditional letter downloads.
- Escaped user/document-derived HTML, added login throttling and generic password-reset responses, and disabled demo/link exposure by default.
- Added a shared comparison view and source-based appeal/hospital previews for both patient and reviewer workflows.
- Full suite: `python -m pytest tests/ -q --basetemp=tmp/pytest_phase6_ui`: **61 passed in 23.14s**.

## Phase 7 - Documentation and claim accuracy

- Removed unverified insurer-validation and performance claims; documented prototype limits and that MFA is not implemented.
- Corrected remaining MediGuard branding and aligned the documented timeout variable with `.env.example`.
- Final verification after implementation and documentation changes: `python -m pytest tests/ -q --basetemp=tmp/pytest_final`: **61 passed in 15.54s**; Python compilation succeeded; `git diff --check` is clean.
