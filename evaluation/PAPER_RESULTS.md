# Paper-ready quantitative results

These results use fictional synthetic fixtures. They do not establish real-world, clinical, or insurer performance.

## Evaluation scope and method

Two isolated evaluations were completed on Windows 11 with Python 3.13.1. Extraction run: 2026-09-26T03:56:40.679961+00:00; six synthetic bill fixtures repeated three times (18 document-processing observations). Rules run: 2026-09-26T04:08:48.102567+00:00; app document processing and deterministic rules over 24 synthetic claim scenarios. The latter used isolated temporary SQLite, storage, and Chroma locations and supplied each case's trusted reviewer context. The case labels are synthetic expected statuses, not independently reviewed insurance outcomes.

The extraction score covers four labeled fields per bill: patient name, hospital name, policy number, and total amount. It does not cover bill number, dates, procedure codes, quantities, line-item charges, or all requested structured fields. OCR field accuracy is the same field-match score restricted to the four OCR-path documents; it is not CER/WER.

## Table A — Extraction evaluation

| Metric | Result |
| --- | ---: |
| Documents tested | 6 |
| Fields evaluated | 24 |
| Correct fields | 19 |
| Incorrect or missing fields | 5 |
| Extraction accuracy | 79.17% |
| OCR field accuracy | 68.75% |
| OCR CER | Not Evaluated — Ground Truth/Data Required |
| OCR WER | Not Evaluated — Ground Truth/Data Required |

Field-level extraction currently scores patient name, hospital name, policy number, and total amount. The additional bill fields requested in the paper require more labeled fixtures. The four OCR-path fixtures contain 16 scored field values; the two selectable-text PDFs contain 8.

Per-document extraction results:

| Fixture | Input path | Correct fields / evaluated | Accuracy |
| --- | --- | ---: | ---: |
| bill_selectable_text.pdf | pymupdf | 4/4 | 100.00% |
| bill_phone_photo.png | tesseract | 4/4 | 100.00% |
| bill_low_light.jpg | No extraction output | 0/4 | 0.00% |
| bill_skewed_compressed.jpg | tesseract | 3/4 | 75.00% |
| bill_multi_page.pdf | pymupdf | 4/4 | 100.00% |
| bill_scanned_image_only.pdf | tesseract | 4/4 | 100.00% |

## Table B — Retrieval evaluation

| Metric | Result |
| --- | ---: |
| Precision@1 | Not Evaluated — Ground Truth/Data Required |
| Precision@3 | Not Evaluated — Ground Truth/Data Required |
| Precision@5 | Not Evaluated — Ground Truth/Data Required |
| Recall@3 | Not Evaluated — Ground Truth/Data Required |
| Recall@5 | Not Evaluated — Ground Truth/Data Required |

The rules-only evaluation file recorded configured embeddings `BAAI/bge-small-en-v1.5` and active backend `BAAI/bge-small-en-v1.5`. A separate controlled smoke test subsequently indexed the synthetic policy into 3 chunks and confirmed Chroma retrieval plus Policy Agent evidence handoff with zero Policy Agent LLM calls while using `BAAI/bge-small-en-v1.5`. This is a functionality check, not a quality score; retrieval metrics still need manually annotated relevant clause IDs for each query.

## Table C — Decision evaluation

| Metric | Rule engine | Decision Agent |
| --- | ---: | ---: |
| Cases scored | 21 | Not Evaluated — Ground Truth/Data Required |
| Correct outcomes | 21 | Not Evaluated — Ground Truth/Data Required |
| Accuracy | 100.00% | Not Evaluated — Ground Truth/Data Required |

Rule-engine confusion matrix (expected rows × predicted columns):

| Expected \ Predicted | Approved | Partially approved | Rejected | Manual review |
| --- | ---: | ---: | ---: | ---: |
| Approved | 5 | 0 | 0 | 0 |
| Partially Approved | 0 | 5 | 0 | 0 |
| Rejected | 0 | 0 | 2 | 0 |
| Manual Review | 0 | 0 | 0 | 9 |

Core rule-engine status agreement is 21/21 on cases that reached the core rules.evaluate_claim calculation. 3 scenarios returned a fail-closed status from policy/bill precondition checks before that calculation; their actual outcomes remain in the case audit but are excluded from core-engine accuracy. The score uses synthetic fixture labels and does not establish expert validation, full financial-rule correctness, Decision Agent accuracy, or real-world accuracy.

## Table D — Model comparison

| Metric | 8B model | 3B model |
| --- | ---: | ---: |
| Decision accuracy | Not Evaluated — Ground Truth/Data Required | Not Evaluated — Ground Truth/Data Required |
| Evidence support (human review) | Not Evaluated — Ground Truth/Data Required | Not Evaluated — Ground Truth/Data Required |
| Appeal quality (mean 0–2) | Not Evaluated — Ground Truth/Data Required | Not Evaluated — Ground Truth/Data Required |
| Mean end-to-end latency | Not Evaluated — Ground Truth/Data Required | Not Evaluated — Ground Truth/Data Required |

The local Ollama inventory contained: ibm/granite4.1:8b. The full 8B model batch did not complete, and no 3B model was installed; thus no model accuracy/quality comparison is reported.

## Evidence and latency

| Stage | Runs | Mean (s) | Median (s) | Min (s) | Max (s) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Bill document processing (extraction run) | 18 | 0.719 s | 0.905 s | 0.004 s | 2.343 s |
| OCR-path document processing | 12 | 1.055 s | 1.055 s | 0.469 s | 2.343 s |
| App document processing (rules-only run) | 24 | 29.830 s | 0.279 s | 0.142 s | 707.896 s |
| Rule engine | 24 | 0.027 s | 0.027 s | 0.015 s | 0.044 s |
| Report/appeal PDF generation (rules-only run) | 24 | 0.023 s | 0.023 s | 0.014 s | 0.039 s |
| Full app end-to-end | 0 | Not Evaluated — Ground Truth/Data Required | Not Evaluated — Ground Truth/Data Required | Not Evaluated — Ground Truth/Data Required | Not Evaluated — Ground Truth/Data Required |

Evidence-support percentage: Not Evaluated — Ground Truth/Data Required

The rules-only measurements omit policy retrieval and Decision Agent inference. The extraction-run and app-run stages are separate experiments and must not be added to estimate total latency. Full end-to-end latency is not available. The full workflow clock, when captured by the model runner, starts after file bytes are staged and ends after decision plus appeal/report PDF generation; warm-up is recorded separately.

## Expert validation

Not Evaluated — Ground Truth/Data Required

## Limitations

Synthetic cases only and limited sample sizes; expected statuses are fixture labels rather than independent domain judgments; OCR quality varies with image quality; insurer and policy wording vary; CPU-only local execution; no expert or human evidence/appeal reviews; OCR CER/WER and retrieval relevance labels are absent; the configured BGE backend was active for the rules-only run, but retrieval relevance was not evaluated; the full 8B workflow did not complete; 3B is unavailable; and no real-world or production evaluation was conducted. No performance or quality claim should be generalized beyond these fixtures.

## Recommended Results wording for the paper

An exploratory evaluation of a synthetic prototype measured 6 bill documents and 24 annotated field values across patient name, hospital name, policy number, and total amount. The extractor matched 19/24 fields (79.17%). On four OCR-path fixtures, field accuracy was 11/16 (68.75%); this is field accuracy, not character or word error rate. In a separate rules-only run across 24 scenarios, 3 fail-closed precondition cases were excluded because the core rules.evaluate_claim calculation did not run; on the remaining cases, deterministic rule statuses agreed with the expected synthetic labels in 21/21 cases (100.00%). These measurements are limited to synthetic fixtures and do not establish real-world performance. OCR CER/WER, policy retrieval relevance, final Decision Agent accuracy, human evidence/appeal ratings, end-to-end latency, matched 8B/3B performance, and expert validation were not evaluated.
