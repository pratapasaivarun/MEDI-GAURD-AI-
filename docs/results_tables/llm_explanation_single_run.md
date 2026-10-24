**Run classification: live LLM, single run, variable. No aggregate is claimed.**

## Explanation quality (live Ollama)

Ten fictional deductible-discrepancy comparisons were sent through `explain_comparison` with Ollama enabled. Each earns one point for grounded numbers, one for quoting the correct deductible term and page, and one for avoiding unsupported certainty. `template_fallback_used` is shown so a fallback is not misreported as model quality.

| Case | Numbers | Clause and page | No overclaim | Template fallback | Score / 3 |
|---|---|---|---|---:|---:|
| discrepancy_01 | yes | yes (p. 1) | yes | yes | 3/3 |
| discrepancy_02 | yes | no (p. 1) | yes | yes | 2/3 |
| discrepancy_03 | yes | yes (p. 1) | yes | no | 3/3 |
| discrepancy_04 | yes | no (p. 1) | yes | no | 2/3 |
| discrepancy_05 | yes | no (p. 1) | yes | yes | 2/3 |
| discrepancy_06 | yes | no (p. 1) | yes | yes | 2/3 |
| discrepancy_07 | yes | no (p. 1) | yes | yes | 2/3 |
| discrepancy_08 | yes | yes (p. 1) | yes | no | 3/3 |
| discrepancy_09 | yes | no (p. 1) | yes | yes | 2/3 |
| discrepancy_10 | yes | no (p. 1) | yes | yes | 2/3 |

**Score: 23/30 checks (76.7%).** Validated on ten synthetic explanations only. Full text and per-check results: `docs/results_tables/llm_explanation_single_run.json`.
