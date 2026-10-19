# Evaluation results

All scores below are from fictional sample data and are not estimates of real-world or insurer accuracy.

| Check | Result | What it measures |
|---|---:|---|
| Bill field extraction | 12/12 (100%) | Four labeled fields on three sample bills |
| End-to-end case status | 12/24 (50%) | App result compared with fictional case labels; includes reviewer gates |
| Retrieval precision@1 | 14/24 (58.33%) | Correct labeled clause at rank 1 |
| Retrieval precision@3 | 23/72 (31.94%) | Macro precision across the top three results |
| Retrieval precision@5 | 24/120 (20.00%) | Macro precision across the top five results |
| Retrieval recall@3 | 23/24 (95.83%) | Queries with a relevant clause in the top three |
| Retrieval recall@5 | 24/24 (100%) | Queries with a relevant clause in the top five |

The retrieval set has 24 labeled questions over 24 fictional policies. Low precision means the correct clause is often ranked below unrelated evidence, especially in the top results. End-to-end status agreement is not a standalone calculation score: reviewer gates prevent some cases from reaching the rules. A separate rules score is therefore not claimed here. The score files and labels are under `evaluation/`; prior paper tables are preserved and marked outdated in `archive/`.

Run the reproducible scripts from the repository root using the commands in [README](../README.md). The latest checked outputs are in `evaluation/latest/`.
