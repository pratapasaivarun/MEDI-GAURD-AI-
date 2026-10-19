# Changelog

## Unreleased

- P4.17: Added three hand-calculated, fully fictional demo cases with itemized/date-bearing bill tables, policy and settlement PDFs, including a mixed text/scanned bill for manual review. Added `docs/DEMO_GUIDE.md`. Full suite at this checkpoint: **153 passed**.
- P4.18: Added three app-path acceptance tests for extraction, reviewer-confirmed terms, deterministic rules, settlement comparison, clause page, status, amount, letter gating, and offline template explanation. Ollama and OCR are stubbed; policy indexing/retrieval is isolated. Full suite: **153 passed**.
- P0.3: Added GitHub Actions on pushes and pull requests using pinned Python dependencies, isolated temporary storage, and Ollama disabled. Local full suite: **153 passed**.
- P2.1 follow-up: Conflicting positive/negative or conditional proportionate-deduction wording now marks settlement comparison for manual review. Added failing-then-passing app-path regression and documented the wording limitation. Full suite: **154 passed**.
- P4.19: Corrected the demo guide's case-B arithmetic to INR 2,700 after including the INR 300 co-pay under-application. Verified against the case manifest and current browser comparison.
- P5.1 follow-up: The settlement comparison no longer tells a claimant to upload a letter when a letter exists but the outcome is manual review or no discrepancy. Added a focused renderer regression. Full suite: **155 passed**.

## MediGuard project hygiene — 2026-10-17

- T13: Audited the user-supplied ZIP against the Git branch; moved the implementation plan from `T/` into `docs/`, removed three unreferenced PDFs without a fictional-sample label, updated the project audit, and prepared a clean distributable excluding local secrets, environments, databases, caches, temporary outputs, and nested ZIPs. Full suite: **116 passed**.

## MediGuard follow-up — 2026-10-10

- T12: Updated the single root README to the verified **116-test** count and documented that the broad `except`/`inadmissible` clause filter can reject payable passages and lead to manual review. Final full suite: **116 passed**.
- T11: Removed the claimed-amount fallback for settlement payment. Missing payment stays `None`, comparison is gated to manual review, and the UI/report do not display an invented zero payment. Added parser and comparison regressions. Full suite: **116 passed**.
- T10: Settlement claim IDs now preserve slash-separated insurer formats and plain numeric IDs. Claim binding normalizes spaces, slashes, and hyphens so equivalent references match. Added three fictional ID fixtures and binding coverage. Full suite: **114 passed**.

## MediGuard prototype completion — 2026-10-10

- T5 follow-up: Added the canonical `ICU_CATEGORY` constant and used it in rule matching so extraction, app, and calculations share the same category name. Full suite: **110 passed**.
- T3 follow-up: The Suresh-style inside-window case now asserts the specified ₹20,400 patient share, ₹9,000 possible difference, page-9 clause, and flagged pharmacy deduction. Full suite: **110 passed**.
- T4 follow-up: Coverage retrieval now accepts “included” and rejects passages containing “except” or “inadmissible,” in addition to exclusion/not-covered language. Added mocked tests for the extra cases and empty retrieval. Full suite: **110 passed**.
- T5 follow-up: ICU line items now require `ICU_LIMIT_NOT_STATED` manual review when the linked policy provides no daily ICU limit. Added an explicit regression. Full suite: **108 passed**.
- T9: Updated the single root README with current date-window, fallback-confirmation, ICU, LLM-confidence, and six-layout behavior. Refreshed the project audit from the old 61-test snapshot; confirmed no `_evaluate_claim_total_only` helper exists. Final full suite: **110 passed**.
- T8: Added a real app-path integration using the demo bill and policy across all six fictional settlement layouts through parsing, claim binding, comparison, and neutral letter generation. An in-stay pharmacy date exercises the Suresh-style check; the layout missing a bill total stays in manual review until explicit confirmation. External model and index calls are mocked. Full suite: **110 passed**.
- T7: LLM-derived claim fields and line items now carry confidence **60.0** and remain flagged for review. Full suite: **106 passed**.
- T6: `rules.parse_date_flexible` now delegates to `extraction.parse_bill_date`, so rule checks and extracted dates share accepted formats and day/month interpretation. Full suite: **106 passed**.
- T5: ICU is now classified separately from room rent. Policy extraction and reviewed JSON carry a daily ICU cap into the shared typed rules path, with ICU stay days used for the cap and the result labeled `ICU_CAP`. Full suite: **105 passed**.
- T4: Comparison clause evidence is now retrieved from the active policy index with category and coverage terms. Results need positive coverage language and are discarded when exclusion language appears. Missing evidence uses a plain policy-check message. Retrieval tests mock the index. Full suite: **102 passed**.
- T3: Settlement reasons that mention a hospitalization window now trigger a date check for matching bill categories. Missing/out-of-stay dates require manual review; fully dated entries inside admission/discharge are labeled `UNEXPLAINED_DEDUCTION`. Notes appear in comparison results and letters. Full suite: **101 passed**.
- Fixed the extracted uppercase room category being skipped by the app's room-limit context, introduced shared case-insensitive category normalization, and use Decimal amounts for room-linked context. Hospital stay days use the date difference, matching the four-day room example for 10–14 August.
- Added an app-context regression test. It failed before the fix because `room_charge` was absent, then passed; full suite after the task: **62 passed**.
- Bound settlement comparisons to the selected claim and uploaded bill total (tolerance INR 1), made missing totals a manual-review condition, and surfaced missing claim IDs as review reasons. Added five app-path settlement tests, including a spaced/case-variant matching reference.
- Removed document-keyword shortcuts for policy confirmation and bill-line review. Trusted fixture auto-confirmation now requires `MEDIGUARD_TRUSTED_FIXTURES=true`, a required-term set, and an allowlisted SHA-256 hash; only `run_demo.py` opts in. Added two upload-pipeline tests; the pre-fix keyword-based test failed, and both pass after the change.
- Removed the legacy status-based appeal PDF from claimant results. Appeal drafts now have a single comparison-gated path and are available only for `possible_discrepancy`; otherwise the UI asks the claimant to upload the insurer settlement letter. Added status-gate tests; full suite: **71 passed**.
- Persisted settlement and comparison dataclasses as JSON with Decimal values encoded as strings, tied each result to its settlement document SHA-256, and added an idempotent SQLite table creation migration. Claimant/reviewer views hydrate empty session state from the saved result. A reload-state test passes.
- Removed token-bearing reset/invitation URLs from logs. Issuance logs contain only the user ID; reset URLs stay hidden by default, and the created reviewer invite URL is displayed only in the admin panel/session. Added link visibility/log tests and documented email delivery as out of scope.
- Audited all 21 `unsafe_allow_html` calls in `app.py`, extracted interpolated markup into testable helpers, and escaped dynamic claim/status values. Added seven payload-based rendering-helper tests and documented every call in `docs/XSS_AUDIT.md`.
- Added the three requested, searchable fictional demo PDFs and a no-network end-to-end test through extraction, saved policy terms, app context, deterministic rules, settlement comparison, and appeal-letter generation. The first run exposed that admission non-payable wording was not entering the rule engine; policy-term extraction now records that supported deterministic category. The exact estimate, pharmacy discrepancy, page-9 clause, letter figures, forbidden wording check, and wrong/mismatched/unreadable settlement cases now pass.

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
# Unreleased

- T2: When a readable settlement letter omits its bill total, comparison now uses the uploaded bill total but remains `manual_review` until the user explicitly confirms it in the claimant or reviewer UI. Confirmed values are persisted with the comparison; other parser review conditions still block it. Regression before fix: `bill_total` was `None`; targeted checks: **7 passed**; full suite: **98 passed**.
- T1: Added six fictional settlement layouts and prioritized explicit paid-amount labels over the `claimed amount` fallback. Claim IDs now capture only a digit-bearing token (including legacy spaced-numeric IDs), and settlement totals/payments are not parsed as deduction rows. Baseline layout tests: **6 failed, 1 passed**; focused parser/binding/end-to-end tests: **22 passed**; full suite: **96 passed**.

- Added a seven-case synthetic comparison evaluation and runner; its generated outcomes match the declared expectations.
- Comparison now reconciles co-pay deductions explicitly and calculates their patient-share effect without applying the co-pay percentage twice.
- Moved the application stylesheet and reusable escaped presentation helpers into the `ui` package while retaining `app.py`'s current rendering API for compatibility.
- Moved welcome/login screens into `ui/auth_pages.py` and claim/result/reviewer screens into `ui/claim_pages.py`; `app.main()` now routes to those pages. Kept `appeal_draft_available` in `app.py` as a compatibility helper used by tests and callers.
- Added `.gitattributes` with LF text normalization and committed the renormalization separately. Appeal-letter insurer reasons now end as a sentence before the review point. README documents the prototype pipeline, manual retention purge, and known limitations: no MFA/email, synthetic data only, multiple fictional settlement layout examples, and estimates only.
- Final verification added a stylesheet structure check and changed the end-to-end category assertion to use the shared category constant.

