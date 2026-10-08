# Implementation decisions

## 2026-10-09 completion work

- Category matching uses `category_names.normalize_category` and uppercase shared constants at module boundaries. Room days are elapsed date days (`discharge - admission`), which gives four room days for 10–14 August and avoids counting the discharge date as an additional billed day.
- Settlement references are normalized by removing spaces and hyphens and comparing case-insensitively. A missing reference is recorded as a review reason and still forces a manual-review result; absent or materially mismatched bill totals also block reliance.
- Fixture auto-confirmation is allowed only in the isolated demo launcher, behind `MEDIGUARD_TRUSTED_FIXTURES`, and only for a bundled policy whose SHA-256 is in `config/trusted_fixtures.json`. Text inside an uploaded document is never trusted as fixture provenance.
- The comparison-based appeal workflow is the only claimant appeal-download path. A decision status alone does not establish a settlement discrepancy.
- Persisted comparison results are only reused while a current settlement document with the saved SHA-256 remains attached to the same claim. Decimal values serialize as strings and are reconstructed as Decimal on load.
- No email provider is included. Password-reset links remain disabled in the UI by default; reviewer setup links are surfaced once to the administrator who creates the invitation, in that authenticated admin session only. Tokens are never written to application logs.

## Phase 0

- Demo mode defaults to off. `run_demo.py` opts in explicitly. The synthetic demo account is provisioned only by that launcher, and only when `MEDIGUARD_ADMIN_PASSWORD` is set.
- Existing rule and persistence APIs remain unchanged during Phase 0; the typed dataclasses are introduced as the target contracts and will be adopted during the later pipeline phases.
- Dependency pins match the versions present in the repository's current `.venv` so this baseline remains reproducible.

## Phase 1

- The existing Streamlit and persistence layers depend on a JSON-compatible rule result. The rule engine accepts the typed contracts directly for new callers and adapts its typed `ClaimResult` at that boundary, while existing app callers retain their dictionary response.
- Diagnosis-level exclusion matches require human confirmation and do not automatically deny a claim. Exact duplicate line items remain in the calculation and block final reliance pending review.

## Phase 2

- Numeric dates use day/month when both values are at most 12. If only the second value can be a day, the input is interpreted month/day because that is the only valid ordering; those dates are not inherently ambiguous.
- LLM output failing any schema check is discarded completely. Existing code-first fields remain usable, while unresolved required fields continue to route the claim to manual review.
- The category configuration uses a small, dependency-free YAML subset (uppercase keys with inline keyword lists) to keep startup deterministic without adding a YAML dependency.

## Phase 3

- Settlement parsing accepts text-layer PDFs and UTF-8 text. Image-only settlement letters are left for manual review rather than silently OCR'd.
- A settlement file may include its own bill total; comparison is blocked when that value is absent because patient-share reconciliation cannot be computed safely.

## Phase 4

- An amount above the rule-supported deduction is labeled `UNEXPLAINED_DEDUCTION` when rules support no deduction in that category, and `EXCESS_DEDUCTION` when rules support a smaller amount.
- Matching categories do not need a clause to remain a match. A disputed category without a supporting clause is `REVIEW` and cannot produce an appeal claim.

## Phase 5

- The appeal draft is available only for a reconciled `possible_discrepancy`; `manual_review` and no-discrepancy outcomes cannot produce an allegation letter.
- Generated letters use fixed templates and comparison facts. Model text is optional and rejected if amounts, quotes, clause references, or length fail validation.
- Hospital notes ask the provider to keep the possible amount under insurer review; they do not direct the patient to withhold payment.

## Phase 6

- Uploaded settlement documents are parsed as untrusted source material. The comparison only runs from extracted bill/rule outputs and stored settlement documents; missing or mismatched inputs block reliance.
- Patient and reviewer views use one comparison renderer to keep amounts, statuses, and downloadable documents consistent.
- Login lockout is 5 failed attempts in a 15-minute window. Reset messaging is generic; development links are hidden unless explicitly enabled.

## Phase 7

- README accuracy takes precedence over earlier unsupported marketing/performance assertions; no insurer-specific validation or field accuracy is claimed without reproducible evidence.
- MFA is explicitly documented as not implemented, rather than implying security coverage that the app does not provide.
