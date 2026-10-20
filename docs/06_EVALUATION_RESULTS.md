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
| llm_number_grounding | 100.0% | 6/6 | None | PASS |
| ollama_decision_equality | 100.0% | 3/3 | 1.0 | PASS |
| fault_injection | 100.0% | 3/3 | 1.0 | PASS |
| report_rules | 100.0% | 2/2 | 1.0 | PASS |
| browser_e2e | n/a | 0/0 | all three demo cases pass | NOT RUN |
| security | 100.0% | 3/3 | 1.0 | PASS |
| seconds_per_claim | 0.588169 s/claim | 30/30 | measured | MEASURED |

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
- The 3-case Playwright run is incomplete: `a_match` passed (1/3); repeat runs stop while registering the next claim or saving its uploads. This is a browser harness / Streamlit navigation issue that still needs fixing; do not count the browser metric as passed.
- Ollama on/off checks were run separately with `ibm/granite4.1:8b`; they passed 3/3 comparison-equality checks and grounded 6/6 explanation outputs. The model wording can still be imprecise even when its amounts and comparison object remain unchanged.
- The regular CI command disables live Ollama and browser runs. Those are separately recorded local checks.

Historical `12/24` and `13/24` figures came from different runs with an unconfirmed policy-term gate. They are superseded by this case-by-case result; they must not be presented as verified rules accuracy.
