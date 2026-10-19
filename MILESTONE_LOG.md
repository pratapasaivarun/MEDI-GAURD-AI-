# Milestone log

## Phase 0 — Architecture note check

**What changed:** Added this architecture check. No application behavior changed.

### Diagram notes against the code

| Diagram note | Status | What the code shows |
|---|---|---|
| `extraction.py`: “Flag LLM fields, more dates” | **Done** | `extraction.py:92-113` parses numeric and month-name date formats. `extraction.py:23` sets LLM extraction confidence to 60; `extraction.py:711-743` marks LLM-filled fields and line items for review. |
| `rules.py`: “Merge two calculation paths” | **Done** | `rules.py:313-324` has one `evaluate_claim` entry point. Typed bills and aggregate totals are both handled there; aggregate-only claims become a synthetic item at `rules.py:414`. `rules.py:532-533` keeps that case on the same item calculation path. The old `_evaluate_claim_total_only` helper is absent. |
| `app.py`: “Escape HTML” | **Done for dynamic display values** | Escaping helpers in `mediguard/ui/components.py:57-99` HTML-escape titles, claim values and attributes, and constrain status values. The rendering regressions are in `tests/integration/test_xss_rendering.py`. The app still uses trusted static HTML for its visual shell. |
| `app.py`: “Fix auth” | **Done for the prototype safeguards** | `app.py:133-151` hashes and verifies passwords; `app.py:154-158` checks roles; `app.py:175-204` applies login throttling. MFA and email delivery are outside the current prototype. |
| `app.py`: “Split file” | **Partial** | Authentication and claim screens are in `mediguard/ui/auth_pages.py` and `mediguard/ui/claim_pages.py`, imported by `app.py:1839-1840`. However, `app.py` is still about 1,857 lines and retains database/storage, authentication services, orchestration and routing. |

### Pipeline order

The diagram order is broadly correct, with one detail: `app.py` coordinates the whole flow; it is not only a final screen. `process_claim_documents` begins at `app.py:1027`, extracts documents, then indexes policy text and extracts terms (`app.py:1065-1072`). Rules run at `app.py:1245`. Settlement parsing and comparison happen in `app.py:1327` and `app.py:1437`. The claimant/reviewer UI then requests explanations and report drafts (`mediguard/ui/claim_pages.py:311-321`).

In plain language: bill and policy files are extracted; policy terms and searchable clauses are prepared; rules calculate the claim; the settlement parser reads the insurer letter; comparison checks it against the rules; explanations and draft reports follow; the Streamlit app coordinates and displays these steps.

**Verify command:**

```powershell
$env:OLLAMA_HOST='http://127.0.0.1:1'
.\.venv\Scripts\python.exe -m pytest -q tests --basetemp 'C:\Users\prata\mediguard_phase0_pytest'
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
.\.venv\Scripts\python.exe -m pytest -q tests --basetemp 'C:\Users\prata\mediguard_phase1_pytest'
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

**Verify command after implementation:** `python -m pytest -q tests/golden/test_golden_cases.py tests/golden/test_comparison_golden_cases.py`.

**Expected output:** all golden rule and comparison assertions pass; the test output reports the exact count when run.


**Phase 2 verification:** Added 19 direct golden rule tests plus 2 direct comparison tests. The rule and comparison checks passed (`21 passed in 1.64s`). The full suite passed: `187 passed in 62.96s` with Ollama disabled.

**Full-suite verify command:** `$env:OLLAMA_HOST='http://127.0.0.1:1'; .\.venv\Scripts\python.exe -m pytest -q tests --basetemp 'C:\Users\prata\mediguard_phase2_pytest'`.

**Expected output:** 187 tests pass; no failures.

**Result:** No mismatch with the arithmetic specification was found. The cases verify line caps and limits, then deductible and co-pay applied to the remaining covered amount.

## Phase 3 — LLM safety

**What changed:** The explanation validator now checks every number in model-written text against deterministic comparison amounts and the cited clause page/section. Added fallback regressions for Ollama down, timeout, malformed output, fabricated numbers, and proof that valid explanatory text cannot mutate the comparison object. The 8.8B Granite model is installed and the local Ollama tag endpoint responded, but these automated tests deliberately use disabled/mocked model responses. Live three-case on/off UI equivalence remains for the browser phase; no claim is made yet that a full live-model demo was run.

**Verify command:** `$env:OLLAMA_HOST='http://127.0.0.1:1'; .\.venv\Scripts\python.exe -m pytest -q tests --basetemp 'C:\Users\prata\mediguard_phase3_pytest'`.

**Expected output:** all tests pass with Ollama disabled; model failures select template explanation and rule results remain unchanged.

**Observed output:** `192 passed in 32.04s`.

## Phase 4 — Synthetic evaluation data and scores

**What changed:** Restored `fixtures/phase4/ground_truth.json` from three labeled fictional bill fixtures and verified the field values against extraction output. Added a source-backed, synthetic policy retrieval query label. Updated the system evaluator to print end-to-end app-status agreement with a denominator and explicit scope; it keeps standalone core rule accuracy marked not evaluated when reviewer-confirmation gates prevent `rules.evaluate_claim` from running.

**Verify commands:**
- `$env:OLLAMA_HOST='http://127.0.0.1:1'; .\.venv\Scripts\python.exe evaluation/run_evaluation.py --repeats 1 --output evaluation/.phase4-extraction.json`
- `$env:OLLAMA_HOST='http://127.0.0.1:1'; .\.venv\Scripts\python.exe evaluation/run_system_evaluation.py --rules-only --output evaluation/.phase4-system-final.json`
- `$env:OLLAMA_HOST='http://127.0.0.1:1'; .\.venv\Scripts\python.exe -m pytest -q tests --basetemp 'C:\Users\prata\mediguard_phase4_pytest'`

**Expected output:** Extraction runner exits 0 with a real field numerator/denominator; system runner exits 0 with a 24-case status comparison plus labeled retrieval metrics; full test suite passes.

**Observed output:** Extraction `12/12` fields correct (100.00%) over 3 fictional bills. System app-status agreement `12/24` (50.00%); all 24 app evaluations stopped at the policy reviewer-confirmation gate, so standalone rule-engine accuracy remains honestly `Not Evaluated`. Retrieval query metrics: `1` annotated query, precision@1 `1.00`, precision@3 `0.33`, precision@5 `0.20`, recall@3/5 `1.00`; this is a tiny synthetic set. Full suite: `194 passed in 34.84s`.

The prior paper numbers (79.17% extraction, 68.75% OCR fields and 21/21 core rules) describe an older dataset/run and are not comparable to these rebuilt three-document results. They will be marked outdated in the documentation cleanup phase.

## Phase 5 — Playwright browser verification (partial)

**What changed:** No application code changed for this browser check. Playwright opened the real Streamlit app, created a fictional claimant account, registered a fictional claim, uploaded the three fictional PDFs, submitted them, and captured the result page. After the refactor, the page showed Manual Review while the policy terms awaited reviewer confirmation. The settlement fixture also had a different claim ID from the test registration, so the app correctly added a claim-ID-mismatch review reason. Screenshots were saved outside the repository under `C:\Users\prata\mediguard-final-*.png`.

**Verify command:** Start the app with `.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1 --server.port 8519 --server.headless true --server.fileWatcherType none`; use Playwright to register a fictional claim, attach `fixtures/demo_cases/a_match/{bill,policy,settlement}.pdf`, submit, and inspect Claim result.

**Observed output:** Account creation, registration, upload, document extraction and Claim result screen worked. The result was Manual Review; the app did not show raw exception text or make up a payout. This was a single browser scenario. The three complete browser demo cases, live Ollama ON/OFF browser comparison, and five invalid-upload scenarios were **not** completed. Python workflow and upload validation tests cover related paths, but they do not replace this browser matrix. Phase 5 is therefore partial, not passed.

## Phase 6 — Structure and cleanup

**What changed:** Added `services/auth.py`, `services/storage.py`, and `services/orchestration.py`, plus `mediguard/ui/routing.py`; `app.py` now delegates password/role primitives, local DB/path/upload validation, assessment sequencing, and page routing through these modules. Claim and reviewer UI errors now log details and show friendly messages instead of raw exception text. `APP_BASE_URL` now defaults to Streamlit's documented port 8501 in code and `.env.example`; README and historical audit notes were updated. Added clean-worktree ignores for phase evidence and pytest scratch output. Added service-boundary regression tests.

**Verify command:** `$env:OLLAMA_HOST='http://127.0.0.1:1'; .\.venv\Scripts\python.exe -m pytest -q tests --basetemp 'C:\Users\prata\mediguard_phase6_full'`.

**Expected output:** all tests pass with Ollama disabled; no internal exception details are sent to claim/reviewer error banners.

**Observed output:** `198 passed in 29.81s`.

## Phase 7 — Final report and closeout

**What changed:** Added `FINAL_REPORT.md` and `docs/architecture.svg`. The report records the actual math, test, evaluation and browser evidence and names unverified areas rather than presenting them as complete.

**Verify command:** `$env:OLLAMA_HOST='http://127.0.0.1:1'; .\.venv\Scripts\python.exe -m pytest -q tests --basetemp 'C:\Users\prata\mediguard_phase7_pytest'`.

**Expected output:** all tests pass with Ollama disabled; the report's test count matches the final output.

**Observed output:** `198 passed in 29.89s`. The report is 645 words, and `docs/architecture.svg` parses as valid XML. No `st.error(str(exc))` or `{exc}` raw-exception banners remain in `mediguard/ui/claim_pages.py`.

## Follow-up A1 — Reviewer-confirmed fixture terms and honest rules score

**What changed:** Added `evaluation/reviewer_confirmed_policy_terms.json` with source text and page-backed confirmed term values for each of the 24 fictional scenario policies. The direct rules evaluator now uses that file as its input, includes the scenario's explicitly labeled reviewer context, scores all 24 cases, and stores every mismatch. `FINAL_REPORT.md` replaces the misleading old `12/24` app-gate figure with the actual direct rules status-agreement result. Missing required terms in the deliberately incomplete fixture remain missing and produce Manual Review.

**Verify command:** `$env:OLLAMA_HOST='http://127.0.0.1:1'; .\.venv\Scripts\python.exe evaluation\run_evaluation.py --repeats 1 --output C:\Users\prata\mediguard-a1-evaluation.json`

**Expected output:** Extraction `12/12`; rules status agreement `13/24` (`54.17%`), with 11 mismatches retained in the JSON output. This is a small fictional benchmark, not real-world accuracy.

**Observed output:** Extraction `12/12` (`100.00%`), 3 fictional bills; 24 rule cases scored, 13 correct (`54.17%`). Mismatches: surgery sub-limit, waiting-period partial, combined sub-limit/cost-share, confirmed exclusion, out-of-network, policy-number mismatch, low-quality scan, preauthorization unconfirmed, unknown network status, possible exclusion, and missing room basis. Ollama was intentionally unavailable at `127.0.0.1:1` for this deterministic scoring run. First pytest attempt had 167 passes and 32 Windows temp-folder setup errors; rerunning with a dedicated temp directory passed: `199 passed in 29.79s`.

## Follow-up A2 — Labeled fictional policy retrieval set

**What changed:** Added 24 query labels spanning 24 separate fictional policy PDFs. Labels cover annual limits, deductibles, co-payment percentages, and room limits; every record carries the exact indexed source chunk, its page number, and the chunk ID used by retrieval. Added checks for count, policy coverage, topic variety, and label structure.

**Verify command:** `$env:OLLAMA_HOST='http://127.0.0.1:1'; .\.venv\Scripts\python.exe evaluation\run_system_evaluation.py --rules-only --output C:\Users\prata\mediguard-a2-system.json`

**Expected output:** 24 case-scoped queries scored against BGE retrieval, with precision@1/3/5 and recall@3/5 printed in `retrieval_annotation_scores`.

**Observed output:** 24/24 queries ran. Precision@1 `14/24` (`58.33%`); macro precision@3 `23/72` (`31.94%`); precision@5 `24/120` (`20.00%`); recall@3 `23/24` (`95.83%`); recall@5 `24/24` (`100%`). BGE (`BAAI/bge-small-en-v1.5`) loaded. The lower precision numbers show that relevant chunks often rank below unrelated chunks; this is not presented as strong retrieval quality. Full suite result is recorded with this step's commit.

## Follow-up A3 — Live Ollama explanation parity

**What changed:** Ran each of the three fictional demo cases through the app's upload, extraction, reviewer-confirmation, rules, settlement-comparison, and appeal-availability functions twice: with Ollama explanation disabled and with the installed Ollama `ibm/granite4.1:8b` enabled. The actual app rule/comparison outputs are recorded; only explanation generation calls the model.

**Verify command:** Compare the isolated results recorded below; automated safety tests can be rerun with `$env:OLLAMA_HOST='http://127.0.0.1:1'; .\.venv\Scripts\python.exe -m pytest -q`.

**Expected output:** Statuses and monetary outputs remain identical between modes; Ollama cannot change them. If its explanation is invalid, the template is used.

**Observed output (ON | OFF):**

| Case | Rule status / payable | Comparison status | Expected patient share | Actual patient share | Difference | Appeal | Explanation behavior |
| --- | --- | --- | ---: | ---: | ---: | --- | --- |
| a_match | partially_approved / 22500.00 | no_discrepancy | 24500.00 | 24500.00 | 0.00 | No | ON used validated model explanation; OFF used template |
| b_wrongful_deduction | partially_approved / 22500.00 | possible_discrepancy | 24500.00 | 27200.00 | 2700.00 | Yes | ON response was rejected by grounding validation and fell back to template; OFF used template |
| c_manual_review | partially_approved / 22500.00 | manual_review | 24500.00 | 23500.00 | -1000.00 | No | No model call in either mode because manual review uses the template |

All eight parity fields compared equal in all 3 cases. Ollama was reachable and the model responded. The lower precision explanation of the mismatch case was discarded safely rather than affecting the financial result. Full suite with Ollama disabled: `199 passed in 42.61s`.

## Follow-up A4 — Playwright demo and upload error matrix

**What changed:** No application code changed. Used Playwright against the real Streamlit app with Ollama disabled and an isolated SQLite, upload and Chroma store outside the repository. Registered fictional claims with the same IDs used by their settlement fixtures, uploaded each case's bill, policy and settlement through the browser file inputs, confirmed the policy terms and source page in the reviewer UI, and ran extraction, deterministic rules and comparison. Screenshots were saved outside the repository in `C:\Users\prata\` as `mediguard-browser-a-match-comparison.png`, `mediguard-browser-b-comparison-final2.png`, `mediguard-browser-c-comparison-final.png`, plus upload/extraction/rules screenshots. The final browser outcomes matched the hand-calculated cases: A Match — no discrepancy, ₹22,500 settlement and estimated payment, ₹0 difference, no appeal; B Wrongful Deduction — possible discrepancy, ₹19,800 paid vs ₹22,500 estimated, ₹2,700 difference, appeal available; C Manual Review — bill/settlement total mismatch with a scanned bill page, comparison withheld and no appeal. The reviewer-confirmed policy was linked before rules ran. A stale local Chroma directory initially returned no supporting clause and correctly gated B to manual review; re-running with a clean isolated Chroma store indexed the policy under its version ID and produced the expected supported discrepancy. This shows stale runtime indexes should be cleared/rebuilt after policy re-indexing.

The upload matrix rejected an empty PDF, a `.txt` uploaded as a bill, and a 15 MB + 1 byte PDF through the friendly generic UI error without showing stack traces or paths. A malformed PDF with a `%PDF` signature passed upload validation, then extraction flagged it for review without exposing raw parser errors. With no settlement document, the comparison tab displayed the instruction to upload one. Screenshots for those screens are outside the repository at `C:\Users\prata\mediguard-browser-error-*.png`.

**Verify command:** Start a clean local app with isolated paths, then use Playwright file inputs to run the three `fixtures/demo_cases/{a_match,b_wrongful_deduction,c_manual_review}` folders and the five error uploads. The saved screenshots listed above are the evidence from this run.

**Expected output:** `no_discrepancy / ₹0 / no appeal`, `possible_discrepancy / ₹2,700 / appeal available`, `manual_review / no appeal`; invalid uploads are safely rejected or flagged and the missing-settlement screen asks for the document.

**Observed output:** All three demo outcomes and all five error paths behaved as expected after using a clean, isolated Chroma index. No browser-visible stack trace or local filesystem path was shown. The malformed PDF is flagged during extraction rather than rejected at upload because upload validation checks its PDF signature, not full file integrity.

**Full-suite command:** `$env:OLLAMA_HOST='http://127.0.0.1:1'; .\.venv\Scripts\python.exe -m pytest -q tests --basetemp 'C:\Users\prata\mediguard_a4_pytest'`.

**Full-suite expected output:** all tests pass with Ollama disabled.

**Full-suite observed output:** `199 passed in 34.81s`.

## Part B — Application package move

**What changed:** Moved application modules into the requested `mediguard/` package groups. `app.py` is now a thin Streamlit entry point; services and page modules are under `mediguard/services/` and `mediguard/ui/`. Updated package imports, the app's repository-root path calculation, category configuration lookup, model-cache path, README architecture/folder map, Docker `PYTHONPATH`, and CI `PYTHONPATH`. Existing fixtures and evaluation paths are unchanged in this group.

**Verify command:** `$env:OLLAMA_HOST='http://127.0.0.1:1'; .\.venv\Scripts\python.exe -m pytest -q tests --tb=short --basetemp 'C:\Users\prata\mediguard_move_app_pytest3'`.

**Expected output:** all tests pass with Ollama disabled.

**Observed output:** `199 passed in 45.05s`. The initial run found outdated dynamic imports and monkeypatch paths; those were updated to package paths before this passing run.

## Part B — Test suite layout

**What changed:** Grouped tests under `tests/unit/`, `tests/integration/`, and `tests/golden/`; moved shared pytest setup into `tests/conftest.py`; moved the development requirements file into `tests/requirements-dev.txt`; and added a short `tests/README.md`. Updated the CI dependency path, CI test command, fixture roots, focused test commands, and documentation links. Removed the root `pytest.ini` to keep the root layout limited to the requested files. Because ignored local `data/` directories are permission-protected and pytest would otherwise scan them by default, use `python -m pytest -q tests` for the complete suite.

**Verify command:** `$env:OLLAMA_HOST='http://127.0.0.1:1'; .\.venv\Scripts\python.exe -m pytest -q tests --tb=short --basetemp 'C:\Users\prata\mediguard_move_tests_pytest2'`.

**Expected output:** all unit, integration, and golden tests pass with Ollama disabled.

**Observed output:** `199 passed in 55.79s`.
