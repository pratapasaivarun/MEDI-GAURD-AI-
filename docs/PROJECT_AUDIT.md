# MediGuard AI Project Audit

**Audit date:** 2026-10-09
**Repository branch:** `mediguard-prototype-implementation`
**Audit scope:** source code, repository layout, automated tests, Python compilation, and the documented synthetic evaluation entry point. This is a source-level audit, not a clinical, insurance, privacy, or penetration certification.

## Summary

The repository contains a coherent academic prototype with typed pipeline models, deterministic rules, document extraction, policy retrieval, settlement parsing, comparison/report generation, role-based Streamlit workflows, SQLite persistence, and security-focused tests. The main automated suite passes (61 tests), and the audited application modules compile.

There are two high-impact correctness problems in the application path: room-category values produced by extraction do not match the case-sensitive category check used to derive room limits, and settlement data is not bound to the selected claim or reconciled against the uploaded bill when the settlement letter supplies its own bill total. These can lead to incomplete or misleading financial comparisons. There are also workflow and prototype-readiness gaps described below. Do not use this prototype to make real claim decisions without fixing and validating these issues.

## Findings

### P1 — Room-limit context is skipped for extracted room line items

`extraction._infer_line_category` returns category names from `config/categories.yaml`, whose group names are uppercase (`ROOM`, `SURGERY`, etc.). But `app._derived_claim_context` selects room items only when `item["category"] == "room"`. Thus normal extracted `ROOM` items are not recognized, and the app does not derive `room_charge`, `room_days`, or `room_linked_charges` for the rules engine. This prevents the room-cap/proportionate-deduction path from receiving the context it needs.

Evidence: [app.py](/C:/MediGaurd%20AI/app.py:1061), [extraction.py](/C:/MediGaurd%20AI/extraction.py:327), [categories.yaml](/C:/MediGaurd%20AI/config/categories.yaml:2).

### P1 — Settlement comparison does not verify claim identity or bill-total consistency

`parse_settlement` extracts a claim reference, but `run_settlement_comparison` never compares it with the selected claim number. A settlement letter for a different claim can therefore be compared against the selected claim. When the letter includes its own bill total, the app also does not check that amount against the uploaded bill total; that settlement total then feeds `comparison.compare` while the expected patient share comes from claim rules. These mismatches can produce a misleading discrepancy result rather than a manual-review result.

Evidence: [settlement.py](/C:/MediGaurd%20AI/settlement.py:113), [app.py](/C:/MediGaurd%20AI/app.py:1219), [comparison.py](/C:/MediGaurd%20AI/comparison.py:18).

### P2 — Uploaded policy text can auto-confirm terms based on a keyword

During policy ingestion, the app marks extracted required terms as confirmed when the policy text contains a broad keyword such as `synthetic` or `fictional` and the required term keys were extracted. That is not proof that the document is a trusted test fixture. A real policy containing one of those words could bypass reviewer confirmation of the extracted terms. Fixture detection should use trusted fixture provenance/configuration, not document text alone.

Evidence: [app.py](/C:/MediGaurd%20AI/app.py:1017).

### P2 — Settlement comparison is kept in Streamlit session state only

The claim and document records are saved, but the comparison and parsed settlement result are assigned only to `st.session_state`. The claimant result view reads those session values and does not reload/recompute the comparison from persisted data. A new browser session or lost Streamlit session can therefore make a completed comparison disappear from the result screen. Reviewer comparison state has the same session-only behavior.

Evidence: [app.py](/C:/MediGaurd%20AI/app.py:2147), [app.py](/C:/MediGaurd%20AI/app.py:1877), [app.py](/C:/MediGaurd%20AI/app.py:2337).

### P2 — Password reset and reviewer invitation delivery is incomplete by default

The app creates reset/invitation tokens and logs token-bearing URLs, but no email delivery mechanism is present. The UI only displays these links when `MEDIGUARD_DEV_SHOW_LINKS=true` (false in `.env.example`). With the default configuration, a user requesting a reset and an invited reviewer are not given a usable link. Accessing the URL through logs is not a sound delivery mechanism and risks exposing credentials if those logs are shared.

Evidence: [app.py](/C:/MediGaurd%20AI/app.py:1599), [app.py](/C:/MediGaurd%20AI/app.py:1605), [app.py](/C:/MediGaurd%20AI/app.py:2472), [.env.example](/C:/MediGaurd%20AI/.env.example:6).

### P2 — Legacy appeal draft can be offered without settlement-comparison evidence

The README says appeal drafts are enabled only when the comparison finds a possible discrepancy. The claimant result page separately enables a legacy appeal-letter PDF for `partially_approved` or `rejected` statuses, using rules/workflow alone. That is inconsistent with the documented comparison-gated behavior and can present a general appeal draft without evidence that the insurer settlement was compared. Either gate it consistently or clearly distinguish and label the general appeal document.

Evidence: [README.md](/C:/MediGaurd%20AI/README.md:68), [app.py](/C:/MediGaurd%20AI/app.py:1846), [reports.py](/C:/MediGaurd%20AI/reports.py:454).

## Working and verified

- The repository has one root README, plus focused implementation history/decision notes under `docs/`.
- The main pipeline is separated into modules for models, extraction, policy terms/indexing, deterministic rules, settlement parsing, comparison, explanations, reports, and the Streamlit app.
- Claimant, reviewer, and administrator flows exist; the app uses role checks and claim ownership checks, and reviewer decisions are audited.
- Uploaded-document path checks, file limits/signature validation, password hashing, login throttling, reset token hashing, and role-gated actions have corresponding implementation and/or tests.
- HTML output that interpolates claim names and other user values escapes those values in the inspected helper paths. The `unsafe_allow_html` calls are mainly app-authored markup; this audit did not confirm an XSS issue.
- Deterministic rule logic and parser/report behavior have dedicated test modules.

## Verification results

- `\.venv\Scripts\python.exe -m pytest -q --basetemp=tmp/pytest_audit` — **61 passed**.
- `\.venv\Scripts\python.exe -m compileall -q app.py agents.py comparison.py extraction.py models.py policy_index.py policy_terms.py reports.py rules.py settlement.py` — **passed** (no diagnostics).
- Source search for `_evaluate_claim_total_only` — **no match**.
- Source search for the literal `Mediguard@2026` — **no match**.
- `.env.example` sets `MEDIGUARD_CORE_DEMO=false`.
- `app.py` contains 21 `unsafe_allow_html` uses; count alone is not a vulnerability finding. The inspected dynamic claim-card/auth markup escapes interpolated values.
- `evaluation/run_system_evaluation.py --rules-only` — **not completed** during this audit; it loaded model weights and produced no completion output after several minutes, so it was stopped. The unit suite is the completed verification result.
- No interactive browser/UI end-to-end test was run. The test suite does not establish real-world OCR, insurer-document accuracy, or correctness across actual policies and claims.

## Readiness limits and follow-up

- The README states that MFA is not implemented and the prototype is not suitable for production claims handling. Uploaded files and SQLite data are stored locally; encryption at rest and a production-grade operational deployment were not established by this audit.
- `purge_expired_documents` exists as a helper, but the audit found no scheduled/application call path that applies `MEDIGUARD_RETENTION_DAYS`; retention is therefore not automatic.
- README documents missing legacy `fixtures/phase4/` inputs for the older extraction evaluation runner and `run_full_evaluation.py`.
- Fix and add regression tests for the P1 findings before using results beyond synthetic demonstrations. Add durable persistence for comparison results and a real secure reset/invitation delivery path before broader pilot use.

## Repository hygiene observed

The tracked project has a single top-level `README.md` and a focused `docs/` directory. At audit time the Git worktree also had two untracked items, `MediGuard_AI_implementation.zip` and `T/`; they were not part of the tracked source audit and were left unchanged. Review those separately before sharing a repository archive.
