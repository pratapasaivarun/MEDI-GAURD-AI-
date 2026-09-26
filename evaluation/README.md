# MediGuard AI quantitative evaluation

This evaluation uses only the repository's fictional synthetic fixtures. It is
not evidence of clinical, insurer, expert, or real-world performance.

## Reproduce extraction results

From the repository root:

```powershell
.\.venv\Scripts\python.exe evaluation\run_evaluation.py --repeats 3
```

The command runs the live PDF/text and Tesseract extraction pipeline on the
medical-bill fixtures with field-level ground truth in
`fixtures/phase4/ground_truth.json`. It writes a timestamped, structured report
to `evaluation/results.json`. `TESSERACT_CMD` is set automatically when the
standard Windows installation path exists; set it explicitly elsewhere.

The 24 claim scenario manifests in `fixtures/claim_scenarios/` are used as the
synthetic expected-decision inventory. They provide expected outcome labels,
but not complete expected rule traces or policy clause relevance labels.

## Run the complete synthetic workflow

```powershell
.\.venv\Scripts\python.exe evaluation\run_full_evaluation.py
```

This drives all 24 case manifests through the app's isolated SQLite document
processing and rule workflow, then through each locally installed 8B/3B Ollama
model, followed by report and appeal generation. It writes
`system_results.json` and `system_results.csv`; temporary storage is isolated
from `data/`. Full model runs can take many minutes on a CPU. To omit LLM calls:

```powershell
.\.venv\Scripts\python.exe evaluation\run_full_evaluation.py --rules-only
```

The rules-only run writes `system_rules_only.json` and
`system_rules_only.csv`. Keeping it separate preserves full-model results and
lets `generate_paper_tables.py` use the current rules-only run for stage latency
and core rule-engine agreement.

The structured results separate rule-engine status agreement from final
Decision Agent accuracy, include confusion matrices, and record document,
retrieval, rule, decision, report, and end-to-end wall times per case. The
end-to-end clock starts at document processing after file bytes are staged;
Ollama's one-time warm-up is recorded separately and included in the first
claim's end-to-end time. Results identify the active embedding backend.

## Complete ground-truth annotations

Edit `evaluation/annotations.json` only with verified transcripts, manual
relevance labels, and human reviews. `annotation_template.json` documents each
field and rubric. For retrieval, add a query with `query_id`, `case_id`, and
`query`; run the complete workflow once to obtain clause IDs under
`retrieval_runs_by_query_id`, then manually enter `relevant_clause_ids` and
rerun. IDs are stable for each synthetic case and policy clause.

For OCR, enter manually checked `reference_text` and reviewer/date metadata.
`run_evaluation.py` calculates CER/WER only for annotated documents. For
evidence and appeal quality, complete review rows per case/model; the appeal
rubric uses 0–2 ratings for factual consistency, policy consistency,
disputed-item relevance, completeness, absence of fabrication, clarity, and
usefulness.

Then generate annotation scores and paper tables:

```powershell
.\.venv\Scripts\python.exe evaluation\score_annotations.py
.\.venv\Scripts\python.exe evaluation\generate_paper_tables.py
```

## Metric availability

| Metric | Current status | Additional ground truth needed |
| --- | --- | --- |
| Bill field extraction | Measured for the 4 annotated fields per fixture | More documents and annotations for bill ID, service/code, quantity, and individual amounts |
| OCR CER/WER | Not Evaluated — Ground Truth/Data Required | Manually verified full-text transcripts for every scanned image |
| Retrieval P@1/P@3/P@5, R@3/R@5 | Not Evaluated — Ground Truth/Data Required | Expected relevant policy chunk IDs per query |
| Core rule-engine status agreement | Measured only for cases that reach `rules.evaluate_claim`; fail-closed policy/bill precondition cases are listed but excluded | Expected calculation values are not separately annotated |
| Final Decision Agent accuracy | Not evaluated in the completed results | A completed full model run against synthetic expected-status labels |
| Evidence support | Not Evaluated — Ground Truth/Data Required | Human-labeled claim/evidence consistency judgments |
| Appeal quality | Not Evaluated — Ground Truth/Data Required | Human rubric scoring against factual and policy answer keys |
| Full component/end-to-end latency | Not evaluated; completed results contain rules-only stage timings | A completed full app/Decision Agent run |
| 8B vs 3B | Not Evaluated — Ground Truth/Data Required | Installable 3B model plus matched runs and quality annotations |
| Expert validation | Not Evaluated — Ground Truth/Data Required | Independent qualified reviewers |

The project environment was provisioned with the already-declared
`sentence-transformers` dependency and configured BGE weights. A controlled
smoke test indexed the existing synthetic policy, retrieved policy clauses
from ChromaDB with `BAAI/bge-small-en-v1.5`, and confirmed that the Policy
Agent returned evidence without an LLM call. This is a functionality smoke
test, not a retrieval-quality evaluation; P@K and R@K still require human
relevance labels.

The extractor uses PyMuPDF and Tesseract. OpenCV is not imported by the
current extraction implementation, so OpenCV preprocessing is not claimed.

Do not describe these synthetic results as real-world system performance. The
repository currently contains no research paper document to update; use the
generated results and statuses when updating the paper source.
