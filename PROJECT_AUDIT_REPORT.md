# MediGuard AI — Project Audit and Run Report

**Audit date:** 26 September 2026
**Project path:** `C:\MediGaurd AI`
**Scope:** application, support modules, tests, configuration, synthetic fixtures, evaluation artifacts, documentation, and representative application startup/workflow checks.

## Executive summary

The application is runnable in the audited Windows environment. The configured Streamlit application returned HTTP 200 on its health endpoint, and the current pytest suite completed with **10 passed, 0 failed, 0 skipped, and 0 errors** (255.08 seconds). A complete synthetic workflow check exercised extraction, policy retrieval, deterministic rules, the 8B explanation call, report/appeal PDF creation, and a fail-closed manual-review case. Real policy and bill PDFs were also inspected locally for mini-project readiness; their contents and personal details are not reproduced here.

Two documentation descriptions were corrected: the README architecture diagram and an `agents.py` module docstring. A stale evaluation limitation about BGE availability was also corrected. No functional architecture was changed.

This audit does not establish production readiness or insurance decision quality. It uses synthetic fixtures, and independent expert review and several quality evaluations are absent.

## Implemented system

The documented processing flow is:

**Document Processing → Supervisor → Policy Agent → Rule Engine → Decision Agent → Report/appeal output**

- **Document processing:** PyMuPDF for selectable-text PDFs and Tesseract for OCR-path files; extracted fields are normalized with source evidence.
- **Supervisor:** coordinates the processing workflow and safety/precondition handling.
- **Policy Agent:** indexes/retrieves policy evidence using Chroma and the configured BGE-small embedding backend. Its role is retrieval, not coverage adjudication.
- **Rule Engine:** deterministically calculates the claim outcome and payable amount from available normalized bill/policy inputs.
- **Decision Agent:** uses the locally available Ollama model `ibm/granite4.1:8b` to explain and format the supplied rule result. It is not an independently validated decision model.
- **Application/output:** Streamlit UI, SQLite/private local storage, reviewer workflow, and PDF decision report/appeal draft.

The repository does not implement a Document Agent or an LLM extraction fallback. OpenCV preprocessing is not part of the current extraction implementation.

## Audit coverage and checks

The automated inventory covered project files outside `.git`, `.venv`, runtime `data/`, temporary `tmp/`, Python caches, and the private `.env` file. The source/fixture inventory included Python modules and tests, JSON manifests/results, PDFs, images, Markdown, configuration, and CSV artifacts. Python syntax, JSON parsing, and PDF/image readability checks completed without reported defects in the prior validation pass. `pip check` reported no broken requirements; `git diff --check` passed (Git emitted only line-ending normalization warnings).

Generated runtime databases, caches, temporary test directories, environment secrets, and installed virtual-environment package files were excluded from the source-file audit. They are not suitable for checking in or embedding in this report. The PDF/image check validates file readability, not the semantic correctness of every page or pixel.

### Application and workflow checks

- Streamlit app health endpoint: **HTTP 200** on an isolated test port.
- Full workflow smoke: completed synthetic case `02_surgery_sublimit`; status was `partially_approved`, payable amount INR 49,500, two retrieved evidence passages, one LLM call, and both report and appeal PDFs were produced.
- Fail-closed smoke: `02_missing_policy_terms` returned `manual_review` with missing required policy terms identified.
- The smoke run’s 115.8-second elapsed time was one uncontrolled test execution. It is **not** a latency benchmark and is not used as one.
- Model inventory contained `ibm/granite4.1:8b`; a 3B model was unavailable.

### Test suite

Command: `.venv\Scripts\python.exe -m pytest -q`
Result: **10 total; 10 passed; 0 failed; 0 skipped; 0 errors** (255.08 seconds).

### Real-document mini-project readiness

- The supplied bill and both policy copies are text-selectable PDFs, so the current document pipeline can read their page text without invoking OCR.
- The bill parser finds some candidate header fields and a total, but it does not reliably populate all claim identifiers, dates, diagnosis, or itemized charges. A reviewer must correct/enter missing fields and line items in Claim Review before any calculation.
- Automatic policy-term parsing did not produce the core calculation terms needed for this real policy. The policy library therefore requires a reviewer to confirm the applicable terms and their source pages before the Rule Engine can calculate. Unconfirmed policy terms fail closed to Manual Review.
- Use one applicable policy edition for a claim. The 10-page copy and complete copy should not be combined as if they were one edition. Link the edition that applies to the claim and confirm the terms from its source text. A retrieved clause is evidence to inspect, not a validated relevance result.
- These inputs were explored for parsing readiness only. No real claim decision was calculated or verified, and the PDFs are not evidence of insurer or real-world performance.

## Synthetic evaluation results

These values come from the generated evaluation artifacts and describe separate experiments. They must not be combined into overall system accuracy or end-to-end latency.

### Extraction

| Measure | Reproduced result | Source/meaning |
| --- | ---: | --- |
| Overall field matches | 19/24 = 79.17% | Six synthetic bills; four annotated fields each |
| OCR-path field matches | 11/16 = 68.75% | Four OCR-path fixtures; field accuracy, not CER/WER |
| Selectable-text PDF field matches | 8/8 = 100.00% | Two selectable-text PDF fixtures |
| Extraction-run mean | 0.719 s | 18 document-processing observations, 3 repeats per fixture |
| OCR-path mean | 1.055 s | 12 OCR document-processing observations |

The older figures of **0.770 s** and **1.129 s** do not match the current `evaluation/results.json` extraction run and should not be used for this run. OCR CER/WER remain unevaluated because manually verified full-text transcripts are absent.

### Rules-only scenario audit

The independently produced application outputs were read from `evaluation/system_rules_only.csv`. Expected statuses come from the synthetic case manifests. All 24 observed statuses match their expected synthetic labels, but only 21 cases executed the core `rules.evaluate_claim` calculation. The three other cases stopped at fail-closed precondition gates and therefore do **not** count in core rule-engine accuracy. The defensible core result is **21/21 = 100.00% status agreement**. Full status agreement across the 24-case application audit is 24/24, including those three gate outcomes; it is not a 24/24 core-engine run.

| Case ID | Expected | Actual | Result | Core rules executed? |
| --- | --- | --- | --- | --- |
| `01_standard_approved` | approved | approved | Match | Yes |
| `02_annual_limit_boundary` | approved | approved | Match | Yes |
| `03_below_deductible` | approved | approved | Match | Yes |
| `04_zero_copayment` | approved | approved | Match | Yes |
| `05_zero_deductible` | approved | approved | Match | Yes |
| `01_annual_limit_exceeded` | partially_approved | partially_approved | Match | Yes |
| `02_surgery_sublimit` | partially_approved | partially_approved | Match | Yes |
| `03_room_limit_proportional` | partially_approved | partially_approved | Match | Yes |
| `04_waiting_period_partial` | partially_approved | partially_approved | Match | Yes |
| `05_combined_sublimit_costshare` | partially_approved | partially_approved | Match | Yes |
| `01_confirmed_exclusion` | rejected | rejected | Match | Yes |
| `02_out_of_network` | rejected | rejected | Match | Yes |
| `01_policy_number_mismatch` | manual_review | manual_review | Match | **No — policy-match gate** |
| `02_missing_policy_terms` | manual_review | manual_review | Match | **No — required-terms gate** |
| `03_invalid_bill_total` | manual_review | manual_review | Match | Yes |
| `04_incomplete_bill_fields` | manual_review | manual_review | Match | **No — required-terms/precondition gate** |
| `05_low_quality_scan` | manual_review | manual_review | Match | Yes |
| `06_waiting_period_unconfirmed` | manual_review | manual_review | Match | Yes |
| `07_preauthorization_unconfirmed` | manual_review | manual_review | Match | Yes |
| `08_network_status_unknown` | manual_review | manual_review | Match | Yes |
| `09_possible_exclusion` | manual_review | manual_review | Match | Yes |
| `10_room_basis_missing` | manual_review | manual_review | Match | Yes |
| `11_multiple_bills_unconfirmed` | manual_review | manual_review | Match | Yes |
| `12_possible_duplicate_charge` | manual_review | manual_review | Match | Yes |

The expected labels are synthetic fixtures, not independent expert judgments. This is status agreement, not proof of complete financial-rule correctness.

### Other reproducible stage timings

| Stage | Current rules-only artifact mean | Interpretation |
| --- | ---: | --- |
| App document processing | 29.830 s | 24 runs; one 707.896 s outlier dominates the mean (median 0.279 s). Treat this mean as anomalous and investigate before publication. |
| Rule engine | 0.027 s | 24 measured stage runs |
| Report/appeal PDF generation | 0.023 s | 24 measured stage runs |
| Full app end-to-end | Not measured | No valid end-to-end timing claim |

The older values 1.32 s, 0.03 s, and 0.03 s do not match the current artifacts. Extraction and rules-only timings come from separate runs. The rules-only run omits retrieval and Decision Agent inference; stages must not be summed to imply end-to-end latency.

The current rules-only evaluation records configured and active embedding backend `BAAI/bge-small-en-v1.5`. The full-workflow smoke also confirmed retrieval and evidence handoff. Neither is a retrieval quality evaluation; there are no manually relevant clause IDs.

## Remaining evaluation limits

The project and paper must continue to mark these as unevaluated:

- OCR character/word error rates (CER/WER).
- Policy retrieval precision/recall or relevance accuracy.
- Decision Agent accuracy and evidence-support correctness.
- Human-scored appeal-letter quality and independent expert validation.
- Full end-to-end latency.
- Matched 8B-versus-3B accuracy, quality, or latency.
- Real-world, clinical, insurer, or production performance.

Do not describe 79.17% extraction field accuracy or 100% synthetic rule-status agreement as overall system accuracy. Do not claim 8B superiority or expert validation.

## Corrections made during this audit

1. Updated the README flow diagram to show the implemented Supervisor, Policy Agent, Rule Engine, and Decision Agent responsibilities.
2. Corrected the `agents.py` module docstring: the Decision Agent explains/formats the rule result; deterministic rules calculate the outcome.
3. Corrected the generated paper-results limitations so it reports the active BGE backend while retaining the retrieval-quality limitation.
4. Preserved extraction and rules-only evaluation outputs separately so a rules-only run does not overwrite extraction/full-model result files.
5. Fixed Q&A routing so “inpatient” is not mistaken for a question about the “patient” name.

## Submission/readiness issues

1. **Do not publish the current app-document-processing mean (29.830 s) without addressing the 707.896 s outlier.** The current value is reproducible but not representative without explaining or rerunning a controlled benchmark.
2. The prior extraction timing figures need to be replaced with values from the selected run (0.719 s and 1.055 s here), or the corresponding evaluation must be rerun and frozen consistently.
3. Keep every unevaluated metric explicitly labeled as such. A successful retrieval smoke test does not establish retrieval quality.
4. The present system is an academic synthetic-data prototype, not a validated insurance decision service.

## Key result files

- `evaluation/PAPER_RESULTS.md` — generated results narrative and tables.
- `evaluation/results.json` — extraction run and unsupported-metric declarations.
- `evaluation/system_rules_only.json` and `evaluation/system_rules_only.csv` — 24-case application/rule audit and timing details.
- `evaluation/annotation_scores.json` — annotation-dependent measures marked unevaluated where labels are absent.
- `evaluation/final_workflow_verification.json` — synthetic full-workflow smoke result.
