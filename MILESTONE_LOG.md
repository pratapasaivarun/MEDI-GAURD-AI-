# Milestone log

## Phase 0 — Architecture note check

**What changed:** Added this architecture check. No application behavior changed.

### Diagram notes against the code

| Diagram note | Status | What the code shows |
|---|---|---|
| `extraction.py`: “Flag LLM fields, more dates” | **Done** | `extraction.py:92-113` parses numeric and month-name date formats. `extraction.py:23` sets LLM extraction confidence to 60; `extraction.py:711-743` marks LLM-filled fields and line items for review. |
| `rules.py`: “Merge two calculation paths” | **Done** | `rules.py:313-324` has one `evaluate_claim` entry point. Typed bills and aggregate totals are both handled there; aggregate-only claims become a synthetic item at `rules.py:414`. `rules.py:532-533` keeps that case on the same item calculation path. The old `_evaluate_claim_total_only` helper is absent. |
| `app.py`: “Escape HTML” | **Done for dynamic display values** | Escaping helpers in `ui/components.py:57-99` HTML-escape titles, claim values and attributes, and constrain status values. The rendering regressions are in `tests/test_xss_rendering.py`. The app still uses trusted static HTML for its visual shell. |
| `app.py`: “Fix auth” | **Done for the prototype safeguards** | `app.py:133-151` hashes and verifies passwords; `app.py:154-158` checks roles; `app.py:175-204` applies login throttling. MFA and email delivery are outside the current prototype. |
| `app.py`: “Split file” | **Partial** | Authentication and claim screens are in `ui/auth_pages.py` and `ui/claim_pages.py`, imported by `app.py:1839-1840`. However, `app.py` is still about 1,857 lines and retains database/storage, authentication services, orchestration and routing. |

### Pipeline order

The diagram order is broadly correct, with one detail: `app.py` coordinates the whole flow; it is not only a final screen. `process_claim_documents` begins at `app.py:1027`, extracts documents, then indexes policy text and extracts terms (`app.py:1065-1072`). Rules run at `app.py:1245`. Settlement parsing and comparison happen in `app.py:1327` and `app.py:1437`. The claimant/reviewer UI then requests explanations and report drafts (`ui/claim_pages.py:311-321`).

In plain language: bill and policy files are extracted; policy terms and searchable clauses are prepared; rules calculate the claim; the settlement parser reads the insurer letter; comparison checks it against the rules; explanations and draft reports follow; the Streamlit app coordinates and displays these steps.

**Verify command:**

```powershell
$env:OLLAMA_HOST='http://127.0.0.1:1'
.\.venv\Scripts\python.exe -m pytest -q --basetemp 'C:\Users\prata\mediguard_phase0_pytest'
```

**Expected output:** 166 tests pass; no failed tests. Ollama is disabled for the run.

**Observed output:** `166 passed in 59.10s`.

## Phase 1 — Baseline

**Branch:** `fix/prototype-completion`  
**Commit at baseline:** `a3f5bca` — `docs: record phase 0 architecture check`  
**What changed:** Recorded the current branch and baseline. No application behavior changed.

**Verify command:**

```powershell
$env:OLLAMA_HOST='http://127.0.0.1:1'
.\.venv\Scripts\python.exe -m pytest -q --basetemp 'C:\Users\prata\mediguard_phase1_pytest'
```

**Expected output:** 166 tests pass; no failed tests. Ollama is disabled for the run.

**Observed output:** `166 passed in 46.72s`.

## Phase 2 — Hand-calculated math cases (specification first)

**What changed:** Added a 17-case arithmetic specification before executing code against these cases. Amounts are INR. Unless stated otherwise, policy terms are explicitly confirmed, proportionate deduction is off, there are no other caps, and arithmetic uses the documented sequence: item coverage limits, sum insured, deductible, then co-pay.

| # | Case and hand calculation | Expected result |
|---:|---|---|
| 1 | Basic cover: eligible bill 10,000; no deductible; 0% co-pay. | Insurer 10,000; patient 0. |
| 2 | Deductible: 10,000 eligible − 2,000 deductible. | Insurer 8,000; patient 2,000. |
| 3 | Co-pay: 10,000 eligible × 10% = 1,000 patient co-pay. | Insurer 9,000; patient 1,000. |
| 4 | Combined: (10,000 − 2,000 deductible) × 10% = 800 co-pay; 8,000 − 800. | Insurer 7,200; patient 2,800. |
| 5 | Room exactly at cap: 4 days × 5,000/day = 20,000 cap; room bill 20,000. | Eligible 20,000; no room reduction. |
| 6 | Room above cap: 4 × 5,000 = 20,000; room bill 24,000. | Eligible 20,000; room reduction 4,000. |
| 7 | ICU daily cap: 2 days × 6,000 = 12,000; ICU bill 15,000. | Eligible 12,000; ICU reduction 3,000. |
| 8 | Confirmed exclusion: cosmetic surgery 50,000; policy explicitly excludes it. | Eligible 0; full 50,000 excluded. |
| 9 | Category sub-limit: investigation bill 8,000; confirmed limit 5,000. | Eligible 5,000; reduction 3,000. |
| 10 | Sum insured: eligible lines 8,000 + 7,000; annual limit 10,000. | Eligible 10,000; insurer 10,000 before cost sharing. |
| 11 | Zero bill: total 0, regardless of policy limits. | Manual review; payout 0. |
| 12 | Bill equals deductible: eligible 2,000 − deductible 2,000. | Insurer 0; patient 2,000. |
| 13 | Bill exactly equals sub-limit: investigation 5,000; sub-limit 5,000. | Eligible 5,000; reduction 0. |
| 14 | Pre-hospital edge included: admission 10 Aug; 2-day window begins 8 Aug; expense 8 Aug. | Covered 4,000. |
| 15 | Pre-hospital one day outside: admission 10 Aug; 2-day window; expense 7 Aug. | Excluded 4,000; eligible 0. |
| 16 | Stay boundaries: expense on admission (10 Aug) or discharge (12 Aug). | Both are within the inpatient dates. |
| 17 | Combination: room bill 24,000 capped to 20,000 plus pharmacy 8,000; eligible 28,000; deductible 3,000; 10% co-pay on 25,000 = 2,500. | Insurer 22,500; patient 9,500 (bill 32,000 − 22,500). |

These are the expected values, not results from the software. Date cases assume policy language explicitly covers the stated pre-hospital window and inpatient dates. The cases avoid a proportional deduction because wording/application scope can vary and the prototype requires reviewer confirmation for uncertain terms.

**Verify command after implementation:** `python -m pytest -q tests/test_golden_cases.py tests/test_comparison_golden_cases.py`.

**Expected output:** all golden rule and comparison assertions pass; the test output reports the exact count when run.


**Phase 2 verification:** Added 19 direct golden rule tests plus 2 direct comparison tests. The rule and comparison checks passed (`21 passed in 1.64s`). The full suite passed: `187 passed in 62.96s` with Ollama disabled.

**Full-suite verify command:** `$env:OLLAMA_HOST='http://127.0.0.1:1'; .\.venv\Scripts\python.exe -m pytest -q --basetemp 'C:\Users\prata\mediguard_phase2_pytest'`.

**Expected output:** 187 tests pass; no failures.

**Result:** No mismatch with the arithmetic specification was found. The cases verify line caps and limits, then deductible and co-pay applied to the remaining covered amount.

## Phase 3 — LLM safety

**What changed:** The explanation validator now checks every number in model-written text against deterministic comparison amounts and the cited clause page/section. Added fallback regressions for Ollama down, timeout, malformed output, fabricated numbers, and proof that valid explanatory text cannot mutate the comparison object. The 8.8B Granite model is installed and the local Ollama tag endpoint responded, but these automated tests deliberately use disabled/mocked model responses. Live three-case on/off UI equivalence remains for the browser phase; no claim is made yet that a full live-model demo was run.

**Verify command:** `$env:OLLAMA_HOST='http://127.0.0.1:1'; .\.venv\Scripts\python.exe -m pytest -q --basetemp 'C:\Users\prata\mediguard_phase3_pytest'`.

**Expected output:** all tests pass with Ollama disabled; model failures select template explanation and rule results remain unchanged.

**Observed output:** `192 passed in 32.04s`.
