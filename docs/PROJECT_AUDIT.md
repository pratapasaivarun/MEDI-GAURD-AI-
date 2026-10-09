# MediGuard AI Project Audit

**Audit date:** 2026-10-10
**Repository branch:** `finish-mini-prototype`
**Audit scope:** application source, repository layout, automated tests, Python compilation, and documentation accuracy. This is a source-level review, not clinical, insurance, privacy, or penetration certification.

## Summary

The repository contains a synthetic-data Streamlit prototype with typed pipeline models, deterministic claim rules, extraction, policy-index retrieval, settlement parsing, settlement comparison, report generation, SQLite persistence, and claimant/reviewer/admin workflows. The T1–T8 implementation is committed on this branch. The current full test suite passes **110 tests**.

The previous audit's P1 findings are addressed: room categories are normalized for rules context, and settlement references and totals are checked before comparison. The previous workflow findings are also addressed in code and tests: comparisons persist against the settlement document hash, appeal drafts require a reconciled possible discrepancy, fixture trust uses explicit provenance, and token-bearing URLs are not logged. Remaining limitations are listed below.

## Prior findings and current status

- **Room-limit context:** fixed by shared category normalization and regression coverage. ICU now has a separate category and daily cap.
- **Settlement identity and bill total:** fixed. The claim reference is bound to the selected claim and a material bill-total mismatch blocks comparison. If a readable settlement omits its total, the uploaded bill total remains a proposal until the user confirms it.
- **Fixture auto-confirmation:** document text keywords no longer establish trust. Demo auto-confirmation is limited to the explicit demo path and trusted fixture hashes.
- **Comparison persistence:** comparison and parsed settlement data are saved and reloaded only while the saved settlement hash matches the currently attached document.
- **Reset/invitation tokens:** token URLs are not written to logs. Email delivery is still not implemented; reset/invitation links have constrained in-app visibility.
- **Appeal workflow:** generated comparison letters are gated on a reconciled `possible_discrepancy`; manual-review and no-discrepancy results cannot generate them.

## Working and verified

- Settlement parser fixtures cover six fictional text layouts, numeric claim references, amount-label variants, and the missing-total case.
- Date-window deductions are checked against same-category bill dates. Missing/out-of-stay dates require review; fully dated entries inside the stay are surfaced as an unexplained deduction with a note.
- Policy comparison clauses are retrieved from the linked policy index, filtered for category and positive coverage wording, and discarded when exclusion wording appears.
- ICU category and daily cap behavior use the deterministic rules path; an unstated cap requires review. Rules date parsing delegates to the bill extraction date parser.
- LLM-derived claim fields use confidence 60.0 and remain flagged for human review. LLMs do not set financial outcomes.
- All settlement fixtures are synthetic. End-to-end layout tests mock external model and vector-index services.
- Source search finds no `_evaluate_claim_total_only` helper. The repository has one root `README.md`, plus scoped documentation under `docs/`.

## Verification

- `.venv\Scripts\python.exe -m pytest -q --basetemp=.pytest-tmp` — **110 passed**.
- `.venv\Scripts\python.exe -m compileall -q app.py agents.py category_names.py comparison.py extraction.py models.py policy_index.py policy_terms.py reports.py rules.py settlement.py ui tests` — passed.
- `git diff --check` — passed after the documentation update.
- No interactive browser acceptance test or real-document evaluation was performed in this audit.

## Limits and follow-up

- Use fictional data only. The prototype is not suitable for production claim decisions.
- MFA and email delivery are not implemented. Uploaded files and SQLite records are local; encryption at rest and production operational controls were not established by this audit.
- OCR, policy-retrieval relevance, model quality, and insurer-specific layout accuracy have not been established beyond synthetic tests.
- Retention purging remains a manual administrator operation.
- Some older evaluation commands require legacy fixtures under `fixtures/phase4/`; those inputs are not present. `evaluation/` and `evaluation/PAPER_RESULTS.md` were not modified as part of this implementation.

## Repository hygiene

The root contains a single `README.md`; changelog, decisions, and this audit report live under `docs/`. T1–T8 are separate commits on `finish-mini-prototype`. Generated data, environments, databases, uploads, and personal documents are excluded from the implementation commit set.
