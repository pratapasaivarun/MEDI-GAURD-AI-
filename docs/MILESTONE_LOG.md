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

**What changed:** Restored `evaluation/ground_truth.json` from three labeled fictional bill fixtures and verified the field values against extraction output. Added a source-backed, synthetic policy retrieval query label. Updated the system evaluator to print end-to-end app-status agreement with a denominator and explicit scope; it keeps standalone core rule accuracy marked not evaluated when reviewer-confirmation gates prevent `rules.evaluate_claim` from running.

**Verify commands:**
- `$env:OLLAMA_HOST='http://127.0.0.1:1'; .\.venv\Scripts\python.exe evaluation/scripts/run_evaluation.py --repeats 1 --output evaluation/.phase4-extraction.json`
- `$env:OLLAMA_HOST='http://127.0.0.1:1'; .\.venv\Scripts\python.exe evaluation/scripts/run_system_evaluation.py --rules-only --output evaluation/.phase4-system-final.json`
- `$env:OLLAMA_HOST='http://127.0.0.1:1'; .\.venv\Scripts\python.exe -m pytest -q tests --basetemp 'C:\Users\prata\mediguard_phase4_pytest'`

**Expected output:** Extraction runner exits 0 with a real field numerator/denominator; system runner exits 0 with a 24-case status comparison plus labeled retrieval metrics; full test suite passes.

**Observed output:** Extraction `12/12` fields correct (100.00%) over 3 fictional bills. System app-status agreement `12/24` (50.00%); all 24 app evaluations stopped at the policy reviewer-confirmation gate, so standalone rule-engine accuracy remains honestly `Not Evaluated`. Retrieval query metrics: `1` annotated query, precision@1 `1.00`, precision@3 `0.33`, precision@5 `0.20`, recall@3/5 `1.00`; this is a tiny synthetic set. Full suite: `194 passed in 34.84s`.

The prior paper numbers (79.17% extraction, 68.75% OCR fields and 21/21 core rules) describe an older dataset/run and are not comparable to these rebuilt three-document results. They will be marked outdated in the documentation cleanup phase.

## Phase 5 — Playwright browser verification (partial)

**What changed:** No application code changed for this browser check. Playwright opened the real Streamlit app, created a fictional claimant account, registered a fictional claim, uploaded the three fictional PDFs, submitted them, and captured the result page. After the refactor, the page showed Manual Review while the policy terms awaited reviewer confirmation. The settlement fixture also had a different claim ID from the test registration, so the app correctly added a claim-ID-mismatch review reason. Screenshots were saved outside the repository under `C:\Users\prata\mediguard-final-*.png`.

**Verify command:** Start the app with `.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1 --server.port 8519 --server.headless true --server.fileWatcherType none`; use Playwright to register a fictional claim, attach `samples/demo_cases/a_match/{bill,policy,settlement}.pdf`, submit, and inspect Claim result.

**Observed output:** Account creation, registration, upload, document extraction and Claim result screen worked. The result was Manual Review; the app did not show raw exception text or make up a payout. This was a single browser scenario. The three complete browser demo cases, live Ollama ON/OFF browser comparison, and five invalid-upload scenarios were **not** completed. Python workflow and upload validation tests cover related paths, but they do not replace this browser matrix. Phase 5 is therefore partial, not passed.

## Phase 6 — Structure and cleanup

**What changed:** Added `services/auth.py`, `services/storage.py`, and `services/orchestration.py`, plus `mediguard/ui/routing.py`; `app.py` now delegates password/role primitives, local DB/path/upload validation, assessment sequencing, and page routing through these modules. Claim and reviewer UI errors now log details and show friendly messages instead of raw exception text. `APP_BASE_URL` now defaults to Streamlit's documented port 8501 in code and `.env.example`; README and historical audit notes were updated. Added clean-worktree ignores for phase evidence and pytest scratch output. Added service-boundary regression tests.

**Verify command:** `$env:OLLAMA_HOST='http://127.0.0.1:1'; .\.venv\Scripts\python.exe -m pytest -q tests --basetemp 'C:\Users\prata\mediguard_phase6_full'`.

**Expected output:** all tests pass with Ollama disabled; no internal exception details are sent to claim/reviewer error banners.

**Observed output:** `198 passed in 29.81s`.

## Phase 7 — Final report and closeout

**What changed:** Added `docs/archive/ARCHIVED_PROJECT_REPORT_2026-10-19.md` and `docs/architecture.svg`. The report records the actual math, test, evaluation and browser evidence and names unverified areas rather than presenting them as complete.

**Verify command:** `$env:OLLAMA_HOST='http://127.0.0.1:1'; .\.venv\Scripts\python.exe -m pytest -q tests --basetemp 'C:\Users\prata\mediguard_phase7_pytest'`.

**Expected output:** all tests pass with Ollama disabled; the report's test count matches the final output.

**Observed output:** `198 passed in 29.89s`. The report is 645 words, and `docs/architecture.svg` parses as valid XML. No `st.error(str(exc))` or `{exc}` raw-exception banners remain in `mediguard/ui/claim_pages.py`.

## Follow-up A1 — Reviewer-confirmed fixture terms and honest rules score

**What changed:** Added `evaluation/reviewer_confirmed_policy_terms.json` with source text and page-backed confirmed term values for each of the 24 fictional scenario policies. The direct rules evaluator now uses that file as its input, includes the scenario's explicitly labeled reviewer context, scores all 24 cases, and stores every mismatch. `docs/archive/ARCHIVED_PROJECT_REPORT_2026-10-19.md` replaces the misleading old `12/24` app-gate figure with the actual direct rules status-agreement result. Missing required terms in the deliberately incomplete fixture remain missing and produce Manual Review.

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

**Verify command:** Start a clean local app with isolated paths, then use Playwright file inputs to run the three `samples/demo_cases/{a_match,b_wrongful_deduction,c_manual_review}` folders and the five error uploads. The saved screenshots listed above are the evidence from this run.

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

## Part B — Fictional sample and evaluation data move

**What changed:** Moved demo assets, demo cases, claim scenarios, settlement layouts, and shared test documents into `samples/`; moved the current extraction ground-truth file into `evaluation/ground_truth.json`. Updated test, evaluation, demo, and project paths while retaining the fictional fixture hashes and contents. Added a one-paragraph samples index. Fixed the synthetic case generator so newly generated cases also land in `samples/claim_scenarios/`.

**Verify command:** `$env:OLLAMA_HOST='http://127.0.0.1:1'; .\.venv\Scripts\python.exe -m compileall -q app.py mediguard evaluation tests; .\.venv\Scripts\python.exe -m pytest -q tests --tb=short --basetemp 'C:\Users\prata\mediguard_move_samples_pytest'`

**Expected output:** compilation succeeds and the full suite passes with Ollama disabled.

**Observed output:** compilation succeeded; `199 passed in 48.85s`.

**Evaluation path checks:** `.\.venv\Scripts\python.exe evaluation/scripts/run_evaluation.py --repeats 1 --output 'C:\Users\prata\mediguard-sample-eval.json'` exited 0: 12/12 extracted fields correct across 3 bills. `.\.venv\Scripts\python.exe evaluation/scripts/run_system_evaluation.py --rules-only --output 'C:\Users\prata\mediguard-sample-system.json'` exited 0: 12/24 end-to-end synthetic statuses agreed (50.0%); standalone rule and decision scores remain explicitly not evaluated. Ollama was unavailable by deliberate host setting at `127.0.0.1:1`; the app, pytest, and evaluation operated without it.

## Part B — Evaluation scripts and latest results

**What changed:** Grouped evaluation Python tools under `evaluation/scripts/` and recorded outputs under `evaluation/latest/`. Updated project-root discovery, runner-to-runner paths, default output paths, tests, and the evaluation folder guide. Retained source labels and annotations at the evaluation root. Added the latest results index.

**Verify command:** `$env:OLLAMA_HOST='http://127.0.0.1:1'; .\.venv\Scripts\python.exe -m compileall -q evaluation tests; .\.venv\Scripts\python.exe -m pytest -q tests --tb=short --basetemp 'C:\Users\prata\mediguard_move_eval_pytest'`

**Expected output:** compilation succeeds and all tests pass.

**Observed output:** compilation succeeded; `199 passed in 32.33s`.

**Script path checks:** extraction evaluator exited 0 with 12/12 fields correct across 3 bills; system rules-only evaluator exited 0 with end-to-end status agreement `12/24 (50.0%)`; annotation scorer exited 0 with 24 retrieval queries scored. The configured BGE embedding backend loaded. Ollama was intentionally unavailable at `127.0.0.1:1`. Refreshed extraction, rules-only, and annotation JSON/CSV artifacts are in `evaluation/latest/`.

## Part B — Numbered guides and archive

**What changed:** Added the seven current guides in reading order: overview, architecture, demo instructions, golden math cases, LLM safety, evaluation results, and limitations. Moved historical audits, plans, decisions, changelog, old paper results, and superseded reports to `docs/archive/`. Moved the architecture SVG beside its guide and added short folder indexes for docs, configuration, archive, and GitHub workflow files. Updated the decision-history test path.

**Verify command:** `$env:OLLAMA_HOST='http://127.0.0.1:1'; .\.venv\Scripts\python.exe -m pytest -q tests --tb=short --basetemp 'C:\Users\prata\mediguard_docs_pytest'`

**Expected output:** all tests pass with Ollama disabled.

**Observed output:** `199 passed in 29.08s`.

## Part B — Root guide and repository hygiene

**What changed:** Replaced the old root guide with the requested ordered README sections, using current fictional-data scores and Windows PowerShell commands. Corrected Streamlit's configured port from 8505 to 8501. Expanded `.gitignore` for additional model, browser, and test artifacts. Updated stale guide links and the evaluation script paths. Added a test that verifies the README points to real evaluation commands and that the Streamlit configured port matches the documented port. Kept `.streamlit/`, `.dockerignore`, and `.gitattributes` because the first contains the app theme/default, the second prevents local secrets/data from entering Docker build contexts, and the third preserves predictable text diffs.

**Verify command:** `$env:OLLAMA_HOST='http://127.0.0.1:1'; .\.venv\Scripts\python.exe -m compileall -q app.py mediguard evaluation tests; .\.venv\Scripts\python.exe -m pytest -q tests --tb=short --basetemp 'C:\Users\prata\mediguard_cleanup_pytest'`

**Expected output:** compilation succeeds and all 200 tests pass.

**Observed output:** the first full run found the old repository-guide test expected a sentence removed by the new README; the README was updated to document the three labeled bills. The next run passed: `200 passed in 29.42s`.

## Part B — Remove obsolete paper-table generator

**What changed:** Removed the obsolete evaluation-to-paper table generator, which emitted stale claims about missing retrieval labels and would have rewritten an archived paper-results file. The combined evaluation runner now passes the current rules-only or model-run results explicitly to the annotation scorer. Updated the root README note about text line endings.

**Verify command:** `$env:OLLAMA_HOST='http://127.0.0.1:1'; .\.venv\Scripts\python.exe -m pytest -q tests --tb=short --basetemp 'C:\Users\prata\mediguard_eval_cleanup_pytest'`

**Expected output:** all tests pass with Ollama disabled.

**Observed output:** `200 passed in 33.33s`.

## Part C — Main branch, default, and stale branch cleanup

**What changed:** Merged `fix/prototype-completion` into a new `main` branch with merge commit `ba36909`. Before merging, inspected local `master`'s two commits ahead of `origin/master`: `fac501f Implement MediGuard settlement comparison plan` and `c687015 Consolidate project documentation into root README`; both are ancestors of the feature branch and remain in `main`. Pushed the feature branch and `main` without force. Set the GitHub default branch to `main` and verified the remote symbolic HEAD points to it. Confirmed ancestry into `main` before deleting `finish-mini-prototype`, `mediguard-prototype-implementation`, and the superseded `master` branch locally and on origin. The active `fix/prototype-completion` branch remains available.

**Verify command:** `$env:OLLAMA_HOST='http://127.0.0.1:1'; .\.venv\Scripts\python.exe -m compileall -q app.py mediguard evaluation tests; .\.venv\Scripts\python.exe -m pytest -q tests --tb=short --basetemp 'C:\Users\prata\mediguard_main_merge_pytest'`

**Expected output:** compilation succeeds and all tests pass with Ollama disabled.

**Observed output:** compilation succeeded; `200 passed in 30.82s` on merged `main` commit `ba36909`.

## Part C — Fresh clone verification

**What changed:** No application code changed. Cloned the pushed remote `main` branch to `C:\Users\prata\mediguard-ai-fresh-clone-20261020`, created a new Python 3.13.1 virtual environment, installed both requirement files, and copied `.env.example` to the clone-local ignored `.env`.

**Verify commands:** Run from the fresh clone:

- `py -3.13 -m venv .venv`
- ` .\.venv\Scripts\python.exe -m pip install --upgrade pip` then ` .\.venv\Scripts\python.exe -m pip install -r requirements.txt -r tests/requirements-dev.txt`
- `Copy-Item .env.example .env`
- `$env:OLLAMA_HOST='http://127.0.0.1:1'; .\.venv\Scripts\python.exe -m pytest -q tests`
- ` .\.venv\Scripts\python.exe -m streamlit run app.py --server.port 8501` — health endpoint `/_stcore/health`
- `$env:MEDIGUARD_ADMIN_PASSWORD=Read-Host "Choose a local demo password"; .\.venv\Scripts\python.exe run_demo.py` — health endpoint `/_stcore/health`
- The three evaluation commands in the root README.

**Observed output:** Dependency installation completed. The clean-clone suite passed: `200 passed in 85.43s (0:01:25)`. Regular app on port 8501 and demo on port 8506 each returned HTTP `200`, body `ok`. Extraction evaluation exited 0 with 12/12 fields correct; rules-only evaluation exited 0 with 12/24 (50.0%) end-to-end status agreement and BGE active; annotation scoring exited 0 with 24 labeled retrieval queries. Ollama was deliberately unavailable at `127.0.0.1:1`. Tesseract was available on this machine; no real patient records were used.

**Tag note:** `v1.0-prototype` points to the verified implementation merge `0b39a43`. This log-only commit records the separate clean-clone verification performed from that exact source commit; no code changed after tagging.

## CI follow-up — Workflow validation and rules-score correction

**What changed:** GitHub rejected `.github/workflows/tests.yml` because its job-wide environment referenced the `runner` context, which is unavailable there. Moved the temporary database, storage, and Chroma paths to the test step environment, where that context is supported. Also corrected the evaluation summary to show the measured direct rules agreement separately from the end-to-end app score: 13/24 (54.17%) and 12/24 (50.00%), respectively.

**Verify command:** `$env:OLLAMA_HOST='http://127.0.0.1:1'; $env:MEDIGUARD_DB_PATH=(Join-Path (Get-Location) '.pytest-temp\mediguard-test.db'); $env:MEDIGUARD_STORAGE_DIR=(Join-Path (Get-Location) '.pytest-temp\storage'); $env:CHROMA_DIR=(Join-Path (Get-Location) '.pytest-temp\chroma'); New-Item -ItemType Directory -Force -Path .pytest-temp\pytest | Out-Null; py -3.13 -m pytest -q tests --basetemp (Join-Path (Get-Location) '.pytest-temp\pytest') --tb=short`

**Expected output:** all tests pass with Ollama disabled.

**Observed output:** `200 passed in 32.61s`. An initial run using the machine-wide pytest temporary directory failed during fixture setup because Windows denied access to that shared temp folder; the isolated repository-local temporary directory resolved it. The workflow YAML is now accepted by GitHub, dependencies install, and the hosted pytest step runs, but that step exits 1. The public job-log endpoint returned HTTP 403 (`Must have admin rights to Repository`), so the hosted test failure cannot be identified from this session. Local Windows tests pass; hosted Linux CI remains unresolved pending the pytest output from the linked Actions run.

## Provisional results and review exports

**What changed:** Provisional claim reports, appeal drafts, and hospital billing notes now state that they are provisional; PDF drafts carry a visible watermark and Word/text versions include the warning. Added coverage for each export type.

**Verify command:** `python -m pytest -q tests --basetemp .pytest-temp`

**Expected output:** all tests pass.

**Observed output:** `228 passed in 98.29s` after the export change.

## Provisional calculations and reviewer term panel

**What changed:** A low-confidence exclusion term no longer blocks every claim amount when none of the bill lines matches it; a matching bill line still routes to specific manual review. The reviewer panel now lists every supported term, including terms not extracted, and shows that a source page is required. Manual-review assistant answers repeat the specific reason and next step. The three fictional demo cases now compare provisional and confirmed app-service results. Updated the demo flow and recorded the current, limited results.

**Verify commands:**

- `python -m pytest -q tests --basetemp .pytest-temp`
- `$env:MEDIGUARD_EVAL_LIVE='false'; $env:MEDIGUARD_EVAL_BROWSER='false'; python -m evaluation.run_all`
- `$env:MEDIGUARD_BROWSER_ONLY='a_match'; python -m evaluation.run_browser`

**Expected output:** pytest passes; the offline evaluation reports 30 synthetic cases with no case failures; the provisional app-path check reports 3/3 demo cases; browser checks pass.

**Observed output:** `230 passed in 104.86s`; the 30-case offline evaluation exited successfully with no labeled failures (totals 30/30, other fields 60/60, line items 28/28, OCR 6/6, policy terms 90/90, rules 24/24, comparison decisions 30/30). Retrieval ran on Chroma's default fallback backend (P@1 30/30, P@3 30/90, P@5 30/150, recall@5 30/30, MRR 1.000). The provisional-vs-confirmed app path passed for 3/3 demos. The Playwright reviewer-workspace run returned 0/8 and stayed on its initial tab after the rules action; the claimant-first browser matrix and upload-error screens remain unverified, and the cause is not yet isolated.

## Keep reviewer actions on their active step

**What changed:** The reviewer workspace now reopens the step where the last calculation or comparison action completed. When a claim has no linked policy edition, the selector prefers an already confirmed edition with the same policy number. Added regression checks for both behaviors.

**Verify command:** `python -m pytest -q tests --basetemp .pytest-temp`

**Expected output:** all tests pass.

**Observed output:** `232 passed in 110.07s`. The selected `a_match` reviewer-workspace browser run passed `1/1`. The latest full reviewer-workspace Playwright run returned `0/8` because it reached Manual Review with “No matching policy edition is linked to this claim.” The cause is not isolated between the browser flow and app state. The claimant-first flow and upload errors are still unverified.
