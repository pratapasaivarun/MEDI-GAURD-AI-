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
| policy_term_accuracy | 100.0% | 90/90 | 0.95 | PASS |
| retrieval | P@1 100.0%; P@3 33.3%; P@5 20.0%; R@5 100.0%; MRR 1.000 | P@1 30/30; P@3 30/90; P@5 30/150; R@5 30/30/labeled retrieved slots | P@1 ≥.8, R@5 ≥.9 | PASS |
| rules_golden_agreement | 100.0% | 24/24 | 1.0 | PASS |
| rules_properties | 100.0% | 211/211 | 1.0 | PASS |
| settlement_paid_amount_f1 | F1 100.0% | 28/28 | measured | MEASURED |
| settlement_deductions_f1 | F1 100.0% | 37/37 | measured | MEASURED |
| comparison_decision_accuracy | 100.0% | 30/30 | 1.0 | PASS |
| comparison_false_match_rate | 0/10 false matches; rate 0.0% | 0/10 | 0.0 | PASS |
| llm_number_grounding | 100.0% | 4/4 | 1.0 | PASS |
| ollama_decision_equality | n/a | 0/0 | 1.0 | NOT RUN |
| fault_injection | 100.0% | 3/3 | 1.0 | PASS |
| report_rules | 100.0% | 2/2 | 1.0 | PASS |
| browser_e2e | n/a | 0/0 | 3 demo cases and 5 upload/error cases pass | NOT RUN |
| security | 100.0% | 3/3 | 1.0 | PASS |
| seconds_per_claim | 0.602346 s/claim | 30/30 | measured | MEASURED |

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

## Browser matrix (live Playwright run)

**8/8 passed.** The three demo cases reached their expected outcomes; `b_wrongful_deduction` showed the appeal PDF download, while the match and manual-review cases did not. Empty file, wrong type, oversized file, corrupted PDF, and missing settlement all displayed safe outcomes. Each scenario used a fresh browser page and claim. Current screenshots are in the temporary directory `C:\Users\prata\AppData\Local\Temp\mediguard-eval-screenshots-u96waj78` and are not committed.

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

## Supplemental provisional app-path verification

The integration suite now runs each fictional demo case through the application's document processing, unconfirmed policy-term evaluation, and settlement-comparison services, then confirms the terms and repeats the calculation. It checks that the provisional result is visible, the status and comparison values match after confirmation, and a reviewer does not change the amounts when extracted terms were correct.

| Case | Provisional status | Provisional insurer estimate | Settlement payment | Difference | Confirmed run equal? |
|---|---|---:|---:|---:|---|
| `a_match` | no discrepancy | INR 22,500 | INR 22,500 | INR 0 | yes |
| `b_wrongful_deduction` | possible discrepancy | INR 22,500 | INR 19,800 | INR 2,700 | yes |
| `c_manual_review` | manual review (bill/settlement totals do not reconcile; scanned evidence is reviewed) | INR 22,500 | INR 22,500 | not relied on | yes |

**Result shown without reviewer confirmation: 3/3 demo cases.** Status and insurer estimate matched the subsequent reviewer-confirmed run in all three cases; the comparison difference also matched in the two cases where it is relied on. The app-level comparison is covered by `tests/integration/test_phase4_demo_cases.py`. This is not a result for all 30 evaluation plus 10 adversarial cases.

The Playwright acceptance run remains unresolved. The available browser script currently exercises the reviewer workspace and returned to its initial review-path tab after the rules step (0/8 on the latest attempt). It is not yet isolated whether this is an app tab-state issue or an outdated automation flow. The claimant-first browser matrix, reviewer confirmation in a second browser session, and five upload-error screens have not yet been verified. Do not treat the earlier recorded browser score as current verification of the provisional claimant flow.
