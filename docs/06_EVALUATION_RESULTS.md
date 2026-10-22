# MediGuard Evaluation Results

**30 synthetic cases; fictional data only.**

Ground truth was committed before this evaluation run. The runner never writes to expected labels.

## Scorecard

| Metric | Result | Numerator / denominator | Target | Pass |
|---|---:|---:|---:|---|
| extraction_total_match | 100.0% | 30/30 | 1.0 | PASS |
| extraction_other_fields_match | 100.0% | 60/60 | 0.95 | PASS |
| line_item_precision_recall | Precision 100.0%; recall 100.0% | 28/28 | measured | MEASURED |
| ocr_field_accuracy | 100.0% | 6/6 | 0.9 | PASS |
| policy_pdf_core_term_accuracy | 100.0% | 90/90 | 0.95 | PASS |
| policy_pdf_term_accuracy | deductible 30/30; copay_percent 30/30; room_limit_per_day 30/30; icu_limit_per_day 30/30; exclusions 30/30; date_window 30/30; annual_limit 30/30 | 210/210 | measured per term; no aggregate target | MEASURED |
| retrieval | P@1 100.0%; P@3 33.3%; P@5 20.0%; R@5 100.0%; MRR 1.000 | P@1 30/30; P@3 30/90; P@5 30/150; R@5 30/30/labeled retrieved slots | P@1 ≥.8, R@5 ≥.9 | PASS |
| rules_golden_agreement | 100.0% | 24/24 | 1.0 | PASS |
| rules_properties | 100.0% | 211/211 | 1.0 | PASS |
| settlement_paid_amount_f1 | F1 100.0% | 28/28 | measured | MEASURED |
| settlement_deductions_f1 | F1 100.0% | 37/37 | measured | MEASURED |
| comparison_decision_accuracy | 100.0% | 30/30 | 1.0 | PASS |
| comparison_false_match_rate | 0/10 false matches; rate 0.0% | 0/10 | 0.0 | PASS |
| llm_number_grounding | 100.0% | 6/6 | None | PASS |
| ollama_decision_equality | 100.0% | 3/3 | 1.0 | PASS |
| fault_injection | 100.0% | 3/3 | 1.0 | PASS |
| report_rules | 100.0% | 2/2 | 1.0 | PASS |
| browser_e2e | n/a | 0/0 | 3 demo cases and 5 upload/error cases pass | NOT RUN |
| security | 100.0% | 3/3 | 1.0 | PASS |
| seconds_per_claim | 0.022547 s/claim | 30/30 | measured | MEASURED |

## Confusion matrix

Rows are expected labels and columns are actual labels.

| Expected \ Actual | no discrepancy | possible discrepancy | manual review |
|---|---:|---:|---:|
| no_discrepancy | 14 | 0 | 0 |
| possible_discrepancy | 0 | 10 | 0 |
| manual_review | 0 | 0 | 6 |

## Case-by-case results

| Case | Expected label | Actual result | Match | Reason if no |
|---|---|---|---|---|
| match_01 | no_discrepancy | no_discrepancy | yes | — |
| match_02 | no_discrepancy | no_discrepancy | yes | — |
| match_03 | no_discrepancy | no_discrepancy | yes | — |
| match_04 | no_discrepancy | no_discrepancy | yes | — |
| match_05 | no_discrepancy | no_discrepancy | yes | — |
| match_06 | no_discrepancy | no_discrepancy | yes | — |
| match_07 | no_discrepancy | no_discrepancy | yes | — |
| match_08 | no_discrepancy | no_discrepancy | yes | — |
| match_09 | no_discrepancy | no_discrepancy | yes | — |
| match_10 | no_discrepancy | no_discrepancy | yes | — |
| discrepancy_01 | possible_discrepancy | possible_discrepancy | yes | — |
| discrepancy_02 | possible_discrepancy | possible_discrepancy | yes | — |
| discrepancy_03 | possible_discrepancy | possible_discrepancy | yes | — |
| discrepancy_04 | possible_discrepancy | possible_discrepancy | yes | — |
| discrepancy_05 | possible_discrepancy | possible_discrepancy | yes | — |
| discrepancy_06 | possible_discrepancy | possible_discrepancy | yes | — |
| discrepancy_07 | possible_discrepancy | possible_discrepancy | yes | — |
| discrepancy_08 | possible_discrepancy | possible_discrepancy | yes | — |
| discrepancy_09 | possible_discrepancy | possible_discrepancy | yes | — |
| discrepancy_10 | possible_discrepancy | possible_discrepancy | yes | — |
| manual_01 | manual_review | manual_review | yes | — |
| manual_02 | manual_review | manual_review | yes | — |
| manual_03 | manual_review | manual_review | yes | — |
| manual_04 | manual_review | manual_review | yes | — |
| manual_05 | manual_review | manual_review | yes | — |
| edge_01 | no_discrepancy | no_discrepancy | yes | — |
| edge_02 | manual_review | manual_review | yes | — |
| edge_03 | no_discrepancy | no_discrepancy | yes | — |
| edge_04 | no_discrepancy | no_discrepancy | yes | — |
| edge_05 | no_discrepancy | no_discrepancy | yes | — |

## Failed cases

No evaluated case failed its status, payable, and paid-amount labels.

## Limits

- Synthetic cases are not representative of insurer claim populations.
- Ollama and browser metrics are unavailable in this offline run.
- Browser end-to-end upload flow is not scored by this offline command.

The historical 13/24 score was rules-only status agreement with reviewer-confirmed terms; 12/24 was full-app status agreement including reviewer gates. They are distinct measurements on an older 24-case set, not comparable overall accuracy figures. See the preserved historical note and current case-by-case results.

## Supplemental measured results

The sections below are separately measured checks. The standard evaluation command refreshes the 30-case scorecard and keeps these results attached.

### Policy-term extraction from source PDFs

Measured by `extract_policy_terms` on each source `policy.pdf`, compared with separately committed source-PDF labels (not the reviewer-confirmed terms JSON): deductible 30/30; co-pay 30/30; room cap 30/30; ICU cap 30/30; exclusions 30/30; date window 30/30; annual limit 30/30. The ICU and exclusion denominators include PDFs where the labeled correct value is absence. See `evaluation/latest/policy_pdf_term_scores.json` for each case and extracted value.

### Claimant-first result time (pinned `.venv`)

The previous multi-minute wait was caused by eagerly indexing each newly uploaded policy: Chroma initialized the configured `BAAI/bge-small-en-v1.5` SentenceTransformer embedding function and embedded policy chunks before rendering the result. Settlement clause lookup also queried the index synchronously, including when a category had no extracted clause or a policy was absent. Claimant assessment now uses extracted page evidence for comparison; uploaded policies never fall back to semantic indexing during first-result calculation. Legacy linked policies without claimant-uploaded pages can still use the index, and claimant policy search or the optional policy-evidence AI initializes it only when explicitly requested. A fresh-database Playwright matrix from the fresh clone under the pinned `.venv` passed 8/8. First-result times were 1.386 s (`a_match`), 1.465 s (`b_wrongful_deduction`), and 2.054 s (`c_manual_review`); maximum 2.054 s. Screenshots remain outside the repository in the directory recorded in `evaluation/latest/claimant_browser_results.json`.

## Adversarial document cases (separate parser check)

The ten fictional adversarial cases were labeled and committed before they were run through the parser. The check covers bill totals, line items, claim references, paid amounts, settlement references, deduction totals where labeled, and review routing. It does **not** score policy calculations or end-to-end comparison decisions.

| Case | Challenge | Expected vs actual | Match |
|---|---|---|---|
| adv_01_split_columns | Pipe-separated table and total | All 6 labeled fields matched | yes |
| adv_02_noisy_ocr | Noisy text, claim reference and hospital payment wording | All 6 labeled fields matched | yes |
| adv_03_low_resolution_scan | Low-resolution scanned bill | All 6 labeled fields matched; OCR evidence returned | yes |
| adv_04_ambiguous_settlement_wording | Ambiguous paid wording | All 6 labeled fields matched; routed for review | yes |
| adv_05_exact_daily_cap | Amount exactly at daily cap | All 6 labeled fields matched | yes |
| adv_06_one_rupee_over_cap | Duration phrase and one-rupee excess | All 6 labeled fields matched | yes |
| adv_07_multiple_deductions | Several deduction lines | All 7 labeled fields matched, including deduction sum | yes |
| adv_08_missing_claim_reference | Missing settlement claim reference | All 6 labeled fields matched; routed for review | yes |
| adv_09_subtotal_tax_grand_total | Subtotal, tax, and grand total | All 6 labeled fields matched | yes |
| adv_10_slash_reference | Slash-style claim reference | All 6 labeled fields matched | yes |

**Result: 10/10 cases and 61/61 labeled field checks; macro line-item precision 1.00 and recall 1.00 (10 synthetic cases).** The machine-readable run is `evaluation/latest/adversarial_results.json`; reproduce it with `python -m evaluation.scripts.score_adversarial_cases`. The low-resolution case used Tesseract OCR. This score is a small targeted regression set, not a general accuracy estimate.

The run initially found six parser defects: pipe-separated total labels were missed; `Claim Ref` and `Paid to hospital` were not recognized; “for 4 days” was discarded from a charge description; explicit above-limit deductions outside a Deductions heading were dropped; non-medical charges were classified as ordinary items; and a missing settlement reference did not request review. Regression tests were added for each behavior. The hand-labeled values were not changed to make the parser pass.

## Claimant-first browser matrix (fresh database)

**8/8 passed**, including registration, uploading each demo's bill, policy, and settlement without a reviewer step, and reaching a visible result. Five independent fresh claims also safely handled an empty file, wrong type, oversized file, corrupted PDF, and missing settlement. In a second session, a reviewer confirmed policy terms; the claimant signed in again and refreshed. The badge changed from “Provisional: terms not yet confirmed” to “Reviewer-confirmed policy terms,” while all 11 displayed INR values stayed identical.

The original 0/8 was initially caused by an app bug: policy indexing ran before the claim was linked to the policy edition, and an indexing error prevented linking. That order is fixed and covered by `tests/integration/test_claimant_policy_linkage.py`. A later rerun exposed a separate Playwright test issue: its selector matched the same reviewer badge twice. The locator now selects the first badge; it was a test-script defect. A BGE-enabled Playwright run under the pinned virtual environment did not reach the first result within its five-minute timeout; the successful 8/8 run used the system-Python runtime used by the open local app, which selects Chroma's fallback embedding. This is a real runtime/performance difference and remains a limitation of the BGE browser run.

Screenshots are saved outside the repo at `<USER_HOME>\AppData\Local\Temp\mediguard-claimant-screenshots-jkh4w_sm`. The compact result is `evaluation/latest/claimant_browser_results.json`.

## Explanation quality (live Ollama)

Ten fictional deductible-discrepancy comparisons were sent through `explain_comparison` with Ollama enabled. Each earns one point for grounded numbers, one for identifying the matching deductible term and page (currency punctuation is normalized), and one for avoiding unsupported certainty or reversed payout direction. `template_fallback_used` is shown so a fallback is not misreported as model quality.

| Case | Numbers | Clause and page | No overclaim | Template fallback | Score / 3 |
|---|---|---|---|---:|---:|
| discrepancy_01 | yes | yes (p. 1) | yes | no | 3/3 |
| discrepancy_02 | yes | yes (p. 1) | yes | no | 3/3 |
| discrepancy_03 | yes | yes (p. 1) | yes | no | 3/3 |
| discrepancy_04 | yes | yes (p. 1) | yes | no | 3/3 |
| discrepancy_05 | yes | yes (p. 1) | yes | no | 3/3 |
| discrepancy_06 | yes | yes (p. 1) | yes | no | 3/3 |
| discrepancy_07 | yes | yes (p. 1) | yes | no | 3/3 |
| discrepancy_08 | yes | yes (p. 1) | yes | no | 3/3 |
| discrepancy_09 | yes | yes (p. 1) | yes | no | 3/3 |
| discrepancy_10 | yes | yes (p. 1) | yes | no | 3/3 |

**Score: 30/30 checks (100.0%).** Validated on ten synthetic explanations only. Full text and per-check results: `evaluation/latest/explanation_quality.json`.

## Performance (ten synthetic discrepancy claims)

Measured on Windows with `ibm/granite4.1:8b`; the Ollama-on model was warm at the start. Each timing includes claim construction, settlement parsing, comparison, and explanation. This is a small local run, not a production capacity estimate.

| Mode | Claims | Mean seconds/claim | Median | Range | App peak RSS | Ollama/llama-server peak RSS |
|---|---:|---:|---:|---:|---:|---:|
| Ollama off | 10 | 0.632 | 0.249 | 0.008–4.335 s | 102.6 MiB | 1,532.1 MiB |
| Ollama on | 10 | 35.716 | 31.423 | 28.813–58.004 s | 102.9 MiB | 5,259.4 MiB |

The off run did not unload the already resident Ollama model, so its Ollama RSS is not an Ollama-free baseline. The on run samples all processes with `ollama` or `llama` in their name every 0.2 seconds; peak values are process working-set samples and can miss shorter spikes. The result file is `evaluation/latest/performance.json`; rerun with `python -m evaluation.scripts.benchmark_claims`.

## Provisional claimant app-path verification (2026-10-21)

All 30 labeled cases were uploaded through the claimant app path without reviewer confirmation before the first result. “Result shown” means the claimant path returned an amount or range, or Manual Review with a specific reason; it does not mean the hand-labeled status matched.

| Case | Expected | Actual | Result shown | Displayed estimate (INR) | Cause when different |
|---|---|---|---:|---:|---|
| match_01 | no_discrepancy | manual_review | yes | 0–8,100 (range) | Generic “Eligible treatment” line has no defensible category; app shows a range and asks for category review. |
| match_02 | no_discrepancy | manual_review | yes | 0–18,000 (range) | Generic “Eligible treatment” line has no defensible category; app shows a range and asks for category review. |
| match_03 | no_discrepancy | manual_review | yes | 0–14,000 (range) | Generic “Eligible treatment” line has no defensible category; app shows a range and asks for category review. |
| match_04 | no_discrepancy | manual_review | yes | 0–10,000 (range) | Generic “Eligible treatment” line has no defensible category; app shows a range and asks for category review. |
| match_05 | no_discrepancy | manual_review | yes | 0–22,500 (range) | Generic “Eligible treatment” line has no defensible category; app shows a range and asks for category review. |
| match_06 | no_discrepancy | manual_review | yes | 0–8,000 (range) | Generic “Eligible treatment” line has no defensible category; app shows a range and asks for category review. |
| match_07 | no_discrepancy | manual_review | yes | 0–16,000 (range) | Generic “Eligible treatment” line has no defensible category; app shows a range and asks for category review. |
| match_08 | no_discrepancy | manual_review | yes | 0–27,000 (range) | Generic “Eligible treatment” line has no defensible category; app shows a range and asks for category review. |
| match_09 | no_discrepancy | manual_review | yes | 0–13,500 (range) | Generic “Eligible treatment” line has no defensible category; app shows a range and asks for category review. |
| match_10 | no_discrepancy | manual_review | yes | 0–40,500 (range) | Generic “Eligible treatment” line has no defensible category; app shows a range and asks for category review. |
| discrepancy_01 | possible_discrepancy | manual_review | yes | 0–8,100 (range) | Generic “Eligible treatment” line has no defensible category; app shows a range and asks for category review. |
| discrepancy_02 | possible_discrepancy | manual_review | yes | 0–18,000 (range) | Generic “Eligible treatment” line has no defensible category; app shows a range and asks for category review. |
| discrepancy_03 | possible_discrepancy | manual_review | yes | 0–14,000 (range) | Generic “Eligible treatment” line has no defensible category; app shows a range and asks for category review. |
| discrepancy_04 | possible_discrepancy | manual_review | yes | 0–10,000 (range) | Generic “Eligible treatment” line has no defensible category; app shows a range and asks for category review. |
| discrepancy_05 | possible_discrepancy | manual_review | yes | 0–22,500 (range) | Generic “Eligible treatment” line has no defensible category; app shows a range and asks for category review. |
| discrepancy_06 | possible_discrepancy | manual_review | yes | 0–8,000 (range) | Generic “Eligible treatment” line has no defensible category; app shows a range and asks for category review. |
| discrepancy_07 | possible_discrepancy | manual_review | yes | 0–16,000 (range) | Generic “Eligible treatment” line has no defensible category; app shows a range and asks for category review. |
| discrepancy_08 | possible_discrepancy | manual_review | yes | 0–27,000 (range) | Generic “Eligible treatment” line has no defensible category; app shows a range and asks for category review. |
| discrepancy_09 | possible_discrepancy | manual_review | yes | 0–13,500 (range) | Generic “Eligible treatment” line has no defensible category; app shows a range and asks for category review. |
| discrepancy_10 | possible_discrepancy | manual_review | yes | 0–40,500 (range) | Generic “Eligible treatment” line has no defensible category; app shows a range and asks for category review. |
| manual_01 | manual_review | manual_review | yes | 0–8,100 (range) | — |
| manual_02 | manual_review | manual_review | yes | 0–18,000 (range) | — |
| manual_03 | manual_review | manual_review | yes | 0–14,000 (range) | — |
| manual_04 | manual_review | manual_review | yes | 0–10,000 (range) | — |
| manual_05 | manual_review | manual_review | yes | 0–22,500 (range) | — |
| edge_01 | no_discrepancy | manual_review | yes | 0–0 (range) | Generic “Eligible treatment” line has no defensible category; app shows a range and asks for category review. |
| edge_02 | manual_review | manual_review | yes | 0 | Bill total is missing or invalid; app shows INR 0 and names the missing total. |
| edge_03 | no_discrepancy | manual_review | yes | 0–10,000 (range) | Generic “Eligible treatment” line has no defensible category; app shows a range and asks for category review. |
| edge_04 | no_discrepancy | manual_review | yes | 3,600–12,600 (range) | Generic “Eligible treatment” line has no defensible category; app shows a range and asks for category review. |
| edge_05 | no_discrepancy | manual_review | yes | 0 | Generic “Exclusion” settlement row cannot be tied to the date-window category; comparison asks for review. The estimate is INR 0. |

**Visible amount or range: 30/30; expected decision label matched: 6/30; provisional values and decisions equal the reviewer-confirmed run: 30/30.** The 24 ordinary match/discrepancy cases remain Manual Review because their only bill item is named “Eligible treatment”; the estimate is shown as a range and the line is listed with its INR amount. Those status mismatches are caused by missing category detail, not by changing the hand-calculated payable labels.

`edge_05` now estimates INR 0. The original source PDF lacked the labeled date-window rule and dated line, so the fictional policy and scanned bill were corrected while the expected label remained unchanged. The reviewer-confirmed terms manifest was also corrected to include the extracted 30-day pre- and 60-day post-hospitalization windows; the reviewer form now supports confirming those terms with source pages. Its status remains Manual Review because the settlement says only “Exclusion,” which cannot be reliably tied to the date-window category. The displayed estimate is 0 and the unresolved comparison reason is shown; this is a remaining fixture limitation, not a mismatch in the payable calculation.

The 10 adversarial extraction-only cases also showed a reasoned result **10/10**. These fixtures deliberately contain no policy PDF or final decision label; Manual Review is the safe outcome. Exact per-case strings are in `evaluation/latest/provisional_app_path.json`. Reproduce with `python -m evaluation.scripts.run_provisional_app_path`.

| Adversarial cases | Expected | Actual | Result shown | Reason |
|---|---|---|---:|---|
| adv_01_split_columns | Manual Review (no policy/decision labels supplied) | manual_review | yes | No matching policy edition is linked to this claim. Link an edition in Claim review first.; Policy edition: no matching policy page is linked to this claim. Ingest and link the applicable policy edition before calculation. |
| adv_02_noisy_ocr | Manual Review (no policy/decision labels supplied) | manual_review | yes | No matching policy edition is linked to this claim. Link an edition in Claim review first.; Policy edition: no matching policy page is linked to this claim. Ingest and link the applicable policy edition before calculation. |
| adv_03_low_resolution_scan | Manual Review (no policy/decision labels supplied) | manual_review | yes | No matching policy edition is linked to this claim. Link an edition in Claim review first.; Policy edition: no matching policy page is linked to this claim. Ingest and link the applicable policy edition before calculation. |
| adv_04_ambiguous_settlement_wording | Manual Review (no policy/decision labels supplied) | manual_review | yes | No matching policy edition is linked to this claim. Link an edition in Claim review first.; Policy edition: no matching policy page is linked to this claim. Ingest and link the applicable policy edition before calculation.; Settlement amount paid was not identified.; Settlement deductions could not be read from the letter. |
| adv_05_exact_daily_cap | Manual Review (no policy/decision labels supplied) | manual_review | yes | No matching policy edition is linked to this claim. Link an edition in Claim review first.; Policy edition: no matching policy page is linked to this claim. Ingest and link the applicable policy edition before calculation. |
| adv_06_one_rupee_over_cap | Manual Review (no policy/decision labels supplied) | manual_review | yes | No matching policy edition is linked to this claim. Link an edition in Claim review first.; Policy edition: no matching policy page is linked to this claim. Ingest and link the applicable policy edition before calculation. |
| adv_07_multiple_deductions | Manual Review (no policy/decision labels supplied) | manual_review | yes | No matching policy edition is linked to this claim. Link an edition in Claim review first.; Policy edition: no matching policy page is linked to this claim. Ingest and link the applicable policy edition before calculation. |
| adv_08_missing_claim_reference | Manual Review (no policy/decision labels supplied) | manual_review | yes | No matching policy edition is linked to this claim. Link an edition in Claim review first.; Policy edition: no matching policy page is linked to this claim. Ingest and link the applicable policy edition before calculation.; Settlement claim reference was not identified.; CLAIM_ID_MISSING: settlement claim reference was not identified. |
| adv_09_subtotal_tax_grand_total | Manual Review (no policy/decision labels supplied) | manual_review | yes | No matching policy edition is linked to this claim. Link an edition in Claim review first.; Policy edition: no matching policy page is linked to this claim. Ingest and link the applicable policy edition before calculation. |
| adv_10_slash_reference | Manual Review (no policy/decision labels supplied) | manual_review | yes | No matching policy edition is linked to this claim. Link an edition in Claim review first.; Policy edition: no matching policy page is linked to this claim. Ingest and link the applicable policy edition before calculation. |

### Ollama on/off with provisional app results

The same 3 demo cases and 10 discrepancy cases were uploaded through the claimant orchestration path with no reviewer confirmation. Explanations were requested once with Ollama disabled and once enabled; the comparison snapshot was checked before and after.

| Set | Decision, amounts, and number grounding | Model behavior |
|---|---:|---|
| Three demos | 3/3 equal and grounded | Ollama called for the two resolved comparisons; manual-review case used the safe template. |
| Ten discrepancy cases | 10/10 equal and grounded | All ten stayed Manual Review due generic line descriptions, so the safety gate correctly used the template and made zero model calls. |
| Total | **13/13** | Ollama available; two actual model calls; no decision or amount changes. |

Full records are in `evaluation/latest/provisional_ollama_equivalence.json`. “Ollama on” cannot be interpreted as 13 generated answers: the LLM is deliberately not called for unresolved Manual Review results.

### Embedding backend and “Pending review” check

The earlier Chroma fallback came from running evaluation with system Python (`C:\Program Files\Python313\python.exe`), which has Chroma but no `sentence-transformers`. In the fresh-clone `.venv`, `run_all` loaded `BAAI/bge-small-en-v1.5`; retrieval on 30 synthetic queries scored P@1 **30/30**, P@3 **30/90**, P@5 **30/150**, recall@5 **30/30**, and MRR **1.000**. Claimant assessment does not load or wait for BGE: the latest claimant-first browser matrix took **1.948 s**, **1.626 s**, and **2.627 s** for the three demo cases; the slowest first result was **2.627 s**. Semantic policy search still requires the configured embedding package and its first model download.

No claimant UI source contains the literal status “Pending review.” Unavailable amounts are labeled “Not calculable” with the unresolved term/document reason displayed nearby; the comparison uses “Manual review is needed because…” and lists the specific issue. A clean-database Playwright check confirmed those screens. This is a source and browser check, not proof about every possible future screen or state.

### Current background explanation queue (2026-10-22)

The asynchronous `analysis.py` path was run against the three fictional demos with Ollama on and compared with deterministic template output with Ollama off. The Python comparison stayed identical in **3/3** cases and explanation number grounding passed **6/6** checks. Manual Review skipped the model call and used its reviewer-required template. For the other two cases, the model response was rejected and the deterministic template shown: the match response called the claim approved, and the discrepancy response's deduction assessment conflicted with Python. The two rejected calls are recorded in `data/llm_metrics.jsonl`; no model-written explanation was accepted in this run.
