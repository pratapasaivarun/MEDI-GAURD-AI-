# Implementation decisions

## 2026-10-10 mini-prototype completion

- Keep one root README as the current user guide; changelog, decisions, and the project audit are supporting records under `docs/`. Report the current verified test count rather than copying counts from older implementation phases.
- Settlement layout integration must pass through the saved-document parser and claim-bound comparison path. Test fixtures are fictional, and missing totals remain blocked until an explicit confirmation step.
- LLM-derived claim values use confidence 60.0 and always require human review; a structurally valid model response is not a verified document fact.
- Bill and rules date parsing must share `extraction.parse_bill_date`; do not maintain a second list of accepted formats or date-order rules.
- ICU charges use their own category and daily limit, separate from the room-rent cap. If the policy stores the ICU limit as a sub-limit, interpret it as a daily ICU cap in this prototype, and use the hospitalization room-day count as the available ICU-day estimate.
- An ICU line with no stated or parseable policy limit cannot be assumed fully covered; mark the line `needs_review` with reason `ICU_LIMIT_NOT_STATED`.
- Policy clauses attached to comparison rows must come from indexed evidence for the linked policy version, match the category, include coverage/payability wording, and not contain exclusion wording. Retrieval failure yields no clause rather than a guessed match.
- A settlement's explicit outside/window/pre/post reason is not accepted as proof by itself. Compare same-category bill dates against admission/discharge dates; missing/out-of-range data stays in `REVIEW`, while dates entirely within the stay leave an unexplained deduction for neutral explanation. Surface the date-check note in results and letters.
- Settlement claim identifiers must contain a digit. Hyphenated IDs and legacy spaced-numeric IDs are supported, while narrative phrases such as “Your claim has been processed” and adjacent dates are excluded.
- For settlement amount labels, explicit payment labels take precedence. `Claimed amount` and `Amount claimed` remain fallbacks for both the claim total and paid amount when no clearer paid label exists.
- A missing bill total may use the extracted uploaded-bill total only as a proposed value. The first comparison stays manual-review until a user checks the confirmation box and submits it. The settlement and comparison are then persisted; separate parser uncertainty (for example, unreadable amount or deductions) remains blocking even after total confirmation.

## 2026-10-09 completion work

- Category matching uses `category_names.normalize_category` and uppercase shared constants at module boundaries. Room days are elapsed date days (`discharge - admission`), which gives four room days for 10–14 August and avoids counting the discharge date as an additional billed day.
- Settlement references are normalized by removing spaces and hyphens and comparing case-insensitively. A missing reference is recorded as a review reason and still forces a manual-review result; absent or materially mismatched bill totals also block reliance.
- Fixture auto-confirmation is allowed only in the isolated demo launcher, behind `MEDIGUARD_TRUSTED_FIXTURES`, and only for a bundled policy whose SHA-256 is in `config/trusted_fixtures.json`. Text inside an uploaded document is never trusted as fixture provenance.
- The comparison-based appeal workflow is the only claimant appeal-download path. A decision status alone does not establish a settlement discrepancy.
- Persisted comparison results are only reused while a current settlement document with the saved SHA-256 remains attached to the same claim. Decimal values serialize as strings and are reconstructed as Decimal on load.
- No email provider is included. Password-reset links remain disabled in the UI by default; reviewer setup links are surfaced once to the administrator who creates the invitation, in that authenticated admin session only. Tokens are never written to application logs.
- `app.py` retains app-authored HTML only for the existing visual shell. Dynamic claim strings are escaped, status values are allowlisted and escaped, and `docs/XSS_AUDIT.md` records the per-call review and tests.
- The demo policy uses deterministic admission non-payable extraction so the application calculation, not test-only hand-built rule terms, produces the fixture's INR 111,600 insurer estimate. The demo PDFs are searchable text PDFs and all contain a `FICTIONAL SAMPLE` label.
- Co-pay is represented as its own comparison category. A difference in co-pay is already a patient-share difference, so it must not be multiplied by the co-pay percentage a second time.
- The seven comparison scenarios are synthetic functional checks authored for this prototype; their agreement is not an accuracy metric or insurer validation.
- Shared HTML widgets and styles live in `ui/`; authentication and claim/result pages are imported lazily by `app.main()` to avoid changing the established app module API during the split.
- Retention purge remains a manual administrator operation. It is not run automatically at startup, which avoids deleting active prototype records without an explicit administrator action.
- Appeal-letter insurer reasons are terminated as sentences before the separate review point to avoid run-on text while preserving the source reason.
- Repository text uses LF through `.gitattributes`; binary document fixtures remain detected as binary by Git's automatic text detection.

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
