# Evaluation results

All scores below are from fictional sample data and are not estimates of real-world or insurer accuracy.

| Check | Result | What it measures |
|---|---:|---|
| Bill field extraction | 12/12 (100%) | Four labeled fields on three sample bills |
| Deterministic rules status agreement | 13/24 (54.17%) | Rule result versus fictional case labels after supplying reviewer-confirmed terms |
| End-to-end case status | 12/24 (50%) | App result compared with fictional case labels; includes reviewer gates |
| Retrieval precision@1 | 14/24 (58.33%) | Correct labeled clause at rank 1 |
| Retrieval precision@3 | 23/72 (31.94%) | Macro precision across the top three results |
| Retrieval precision@5 | 24/120 (20.00%) | Macro precision across the top five results |
| Retrieval recall@3 | 23/24 (95.83%) | Queries with a relevant clause in the top three |
| Retrieval recall@5 | 24/24 (100%) | Queries with a relevant clause in the top five |

The rules evaluation uses the separately recorded, source-page-backed reviewer-confirmed terms for all 24 fictional scenarios; 13 statuses match their case labels and 11 do not. The app-level result is lower because it includes reviewer gates and compares the complete workflow. Neither score is an independent expert assessment or a real-world accuracy measure. The retrieval set has 24 labeled questions over 24 fictional policies. Low precision means the correct clause is often ranked below unrelated evidence, especially in the top results. The score files and labels are under `evaluation/`; prior paper tables are preserved and marked outdated in `archive/`.

Run the reproducible scripts from the repository root using the commands in [README](../README.md). The latest checked outputs are in `evaluation/latest/`.
