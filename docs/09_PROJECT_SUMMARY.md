# MediGuard AI — completion summary

**Purpose.** MediGuard is a fictional-data college prototype that reads a hospital bill, policy and settlement letter, applies visible Python rules, compares the result, and drafts an appeal when evidence supports a possible discrepancy. It is not an insurer decision system.

```text
Bill + policy -> extraction/OCR -> reviewer-confirmed terms + clause retrieval
     -> deterministic Python rules <- settlement parser + settlement letter
     -> comparison -> LLM explanation (optional) + appeal report -> Streamlit UI
```

**Safety rule:** Python alone sets amounts, statuses and appeal eligibility. Ollama only explains an already computed comparison; a failed or ungrounded response is replaced by a checked template.

## Scorecard

All results below are for the stated fictional test set, not general accuracy.

| Check | Result | Scope |
|---|---:|---|
| Main synthetic evaluation decisions | 30/30 | 30 labeled cases |
| Adversarial bill/settlement parsing | 10/10 cases; 61/61 fields | 10 fixed cases, labels committed before scoring |
| Adversarial line-item precision / recall | 1.00 / 1.00 | Macro average across those 10 cases |
| Browser flows | 8/8 | 3 demo cases + 5 upload/review errors, isolated claim sessions |
| Explanation checklist | 30/30 points | 10 live Ollama explanations; numbers, clause/page, no overclaim |
| Ollama decision equality | 13/13 | 3 demo + 10 discrepancy cases, same decisions and amounts with explanation on and off |
| Full automated tests | 248 passed, 3 skipped | `python -m pytest -q tests`; presentation checks are opt-in and pass when enabled |

## Performance snapshot

Measured on Windows for 10 synthetic discrepancy claims. Ollama used `ibm/granite4.1:8b`; on mode used live explanations. Mean full-path time was **0.632 seconds/claim off** and **35.716 seconds/claim on**. Sampled app peak RSS was **102.6 MiB off** and **102.9 MiB on**. Ollama/llama-server process RSS peaked at **5,259.4 MiB on**. The off run still had a model resident, so its Ollama memory is not a clean off baseline. See [the evaluation results](06_EVALUATION_RESULTS.md) and [`evaluation/latest/performance.json`](../evaluation/latest/performance.json) for median, range and method.

## Browser and parser findings

Playwright passed all 8 claimant-first scenarios on an empty database, followed by reviewer confirmation and claimant refresh with amounts unchanged. A real navigation state bug had reset a newly registered claim to the blank form; it is fixed with a regression test. The missing-settlement result also now renders instead of being hidden by an early return. Adversarial parsing caught and fixed pipe-separated totals, “Claim Ref”, “Paid to hospital”, duration descriptions, explicit unheaded deductions, non-medical classifications, and missing settlement-reference review routing.

## Limits and how to run

The set is small, fictional, and hand-labeled. OCR, retrieval, policies, layouts, and model wording are not representative of real insurer documents. The LLM-on path is much slower and has a multi-gigabyte model process footprint. The 30-case evaluation and 10-case adversarial/parser checks cover different layers and must not be combined into one accuracy percentage. The historical 12/24 app result and 13/24 rules-only result were different measures on an older 24-case set; details are in the evaluation report.

Use the exact PowerShell setup and demo commands in [the root README](../README.md). Use the unique pytest temp-folder command from the README to avoid stale Windows temp permissions; run the evaluation with `python -m evaluation.run_all`. Use only fictional or de-identified documents. Deployment is out of scope.
