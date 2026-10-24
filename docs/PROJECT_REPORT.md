# MediGuard AI — Project Report

**Project type:** Local, fictional-data health-insurance settlement comparison prototype  
**Interface:** Streamlit web application  
**Primary implementation:** Python, LangGraph, SQLite  
**Intended use:** Academic demonstration and software evaluation only  
**Data scope:** Synthetic documents and test cases; do not upload real patient information

## 1. Executive summary

MediGuard AI helps a claimant or reviewer understand how a hospital bill, an insurance policy, and an insurer's settlement letter relate to one another. It extracts bill and policy information, calculates an estimate using explicit Python rules, parses the insurer's settlement, and compares the two results. When the evidence is incomplete or inconsistent, it reports Manual Review rather than treating unknown policy terms as zero. If the documents support a possible unexplained settlement deduction, it can produce a provisional appeal draft for human review.

The system's central safety boundary is **Python decides; AI may explain**. Deterministic Python code owns every calculated amount, comparison status, and appeal-eligibility decision. Optional local Ollama features can explain a result or answer a limited claimant question; their output cannot change the underlying calculation or decision.

This is a college prototype, not an insurer adjudication system, financial or legal advice, or a tool validated for real claims. Its evaluation uses a small, hand-labeled synthetic dataset.

## 2. Problem statement and objectives

Claimants may find it difficult to reconcile an insurer's deductions with a hospital bill and policy wording. The prototype demonstrates a transparent workflow that:

1. Accepts a bill, policy, and optional settlement letter.
2. Extracts structured facts and preserves evidence such as source document and page.
3. Applies explicit policy-based calculations to bill line items.
4. Checks whether the settlement's payment and deductions reconcile with the estimate.
5. Escalates missing, uncertain, conflicting, or unreconciled facts to human review.
6. Presents a claimant-facing explanation and, when eligible, an appeal draft.

## 3. Users and roles

- **Claimant:** Registers, creates a claim, uploads documents, views the estimate and comparison, asks supported questions, and downloads eligible draft documents.
- **Reviewer:** Checks extracted bill and policy values against cited source pages, corrects or confirms evidence, reviews claim details, and triggers recomputation.
- **Administrator:** Manages privileged access and reviewer setup, subject to role checks in the service layer.

Self-registered accounts are claimant accounts. Reviewer/admin access is privileged and provisioned through the configured local workflow. Passwords are stored as salted PBKDF2-HMAC-SHA256 hashes rather than plaintext.

## 4. Technology and repository structure

| Area | Main implementation |
|---|---|
| Application entry | [`app.py`](../app.py) delegates to the Streamlit application service. |
| Demo launcher | [`run_demo.py`](../run_demo.py) starts an isolated demo on `127.0.0.1:8506` using `data/final_demo`. |
| UI | `mediguard/ui/` contains authentication, navigation, claimant/reviewer pages, components, and styles. |
| Application services | `mediguard/services/` handles authentication, persistence, document processing, orchestration, and claim lifecycle. |
| Ingestion | `mediguard/ingestion/` extracts bill fields and line items, reads PDFs/images, runs optional OCR, and parses settlement letters. |
| Policy | `mediguard/policy/` extracts source-backed policy terms and provides optional page/section-aware Chroma retrieval. |
| Decision engine | `mediguard/engine/` contains typed financial models, deterministic rules, category normalization, and settlement comparison. |
| AI features | `mediguard/ai/` contains the shared local-model gateway, optional explanation/analysis, and claimant Q&A. |
| Reports | `mediguard/reporting/reports.py` generates decision reports and appeal/hospital-note PDF or DOCX drafts. |
| Configuration | `config/` contains category mappings, prototypes, prompts, and trusted fictional-fixture configuration. |
| Samples and tests | `samples/`, `tests/`, and `evaluation/` provide fictional fixtures, automated tests, labels, and runners. |
| Documentation | `docs/` contains the architecture, setup, math examples, safety notes, evaluation, limitations, and this report. |

The runtime dependencies are pinned in [`requirements.txt`](../requirements.txt). The documented verified Python runtime is Python 3.13. Tesseract is an optional system dependency for OCR; Ollama and its configured local model are optional.

## 5. End-to-end working flow

### 5.1 Start and authenticate

1. Run the Streamlit app or the isolated demo launcher.
2. The application initializes its SQLite schema, resumes any pending opt-in analysis jobs, validates local security configuration, and renders the welcome/login flow.
3. A claimant signs in or creates an account. Role checks protect reviewer and administrative actions.

### 5.2 Register a claim and upload documents

1. The claimant creates a claim with basic claim, patient, hospital, policy, and incident information.
2. The claimant uploads the medical bill and policy. The settlement letter is uploaded when a settlement comparison is required.
3. Upload validation checks the expected file type, size, non-empty content, and supported file signatures; settlement text must be UTF-8.
4. Documents are stored in the configured local storage area. SQLite records document metadata, type, hash, processing state, and claim relationship.

### 5.3 Extract evidence

1. The document stage reads PDF text or image content. When text is not available on scanned pages, local Tesseract OCR can supply text if installed and configured.
2. Deterministic extraction identifies bill fields, dates, totals, and candidate line items. Extracted values retain confidence and source evidence where available.
3. Policy terms such as annual limit, deductible, co-pay, room/ICU limits, date windows, and sub-limits are extracted from policy evidence with source page information.
4. The settlement parser reads PDF text or UTF-8 text and identifies claim reference, billed total, amount paid, co-pay, and deduction rows.
5. Missing or ambiguous values are not silently invented. Failed extraction, missing required fields, inconsistent totals, unidentified claim references, or uncertain terms are surfaced for review.

### 5.4 Resolve policy terms and reviewer gates

1. Policy terms begin as candidates. A term is used only when its value, evidence, confidence, and source page pass the provisional checks; missing values are not assumed to be zero.
2. A claimant can see a provisional estimate with its unresolved policy issues. Reviewers can inspect the source document and page, edit bill extraction, and confirm policy terms.
3. Reviewer-confirmed values are persisted with reviewer and evidence information. The service recomputes affected linked claims after a policy review.
4. A recognized trusted fixture can be pre-confirmed only in the explicitly enabled fictional demo configuration; this is recorded in the audit trail.

### 5.5 Run the deterministic claim calculation

The LangGraph `Supervisor` coordinates four deterministic worker stages in order: document processing, policy/rule evaluation, settlement decision when a settlement exists, and output assembly. This is the five-part structure named in the project description (Supervisor plus Document, Policy, Decision, and Output); the Supervisor is the orchestrator, not a fifth calculation stage. The optional `enqueue_analysis` node is separate and disabled by default. The graph passes claim identifiers and compact results rather than document bytes as graph state.

The rule engine uses decimal monetary arithmetic and applies supported rules to each line item. Its core calculation sequence is:

1. Check missing or uncertain fields, term availability, patient identity, date information, duplicates, and bill-total reconciliation.
2. Apply confirmed non-payable categories, room/ICU caps, relevant exclusions, and other item-level coverage rules.
3. Apply room-linked proportionate reductions when policy wording supports them.
4. Apply remaining annual/sum-insured limits to eligible line items.
5. Subtract the deductible, then calculate co-pay on the remainder.
6. Calculate insurer payable and claimant responsibility only when the required terms are available; otherwise preserve an unavailable value or a range and route uncertainty to review.

The implementation intentionally does not remove duplicate-looking charges automatically. It retains them and raises a reviewer warning. Confidently extracted but uncategorized lines may be included in an upper estimate; where possible policy caps or exclusions could affect them, the result includes a range and a reason.

### 5.6 Compare settlement and estimate

If exactly one settlement letter is present, its claim reference and bill total are checked against the selected claim and uploaded bill. Missing, conflicting, or mismatched values trigger Manual Review.

The comparison engine groups insurer deductions and Python rule disallowances by category, compares their amounts and reasons, and checks whether the patient-share difference reconciles with category-level payout effects. Outcomes are:

- **`no_discrepancy`:** The available evidence does not show a supported unexplained difference.
- **`possible_discrepancy`:** Evidence supports an unexplained or excess deduction and the overall difference reconciles.
- **`manual_review`:** Required evidence is missing, uncertain, inconsistent, or does not reconcile.

An appeal draft is available only for a comparison whose status is `possible_discrepancy`. Drafts are clearly marked provisional until relevant policy terms are confirmed.

### 5.7 Present, explain, and export

1. The claimant screen shows the current estimate, claimant responsibility, policy-term status, settlement comparison, and review reasons.
2. Deterministic Q&A answers supported questions from saved decision facts without model calls. Off-topic questions are declined; only an unmatched claim question may use the optional, evidence-checked local-model fallback.
3. The user may request an optional AI explanation of an already computed result. The response is checked for unsupported numbers and citations; a deterministic template is used when the model is unavailable or the output fails validation.
4. Eligible appeal letters and related documents can be generated as PDF or DOCX drafts. The drafts are for human review and are not automatically submitted.

## 6. Calculation and AI boundaries

### 6.1 Deterministic rule ownership

The calculation and comparison path does not require an LLM. The rule engine determines amounts and claim status; the comparison engine determines discrepancy status; and the appeal gate checks that computed comparison status. Model-generated text is not fed back into those decisions.

### 6.2 Optional local AI

All active Ollama traffic is routed through `mediguard/ai/llm_gateway.py`. By default:

- Automatic background analysis is off.
- Startup Ollama warm-up is off.
- LLM extraction fallbacks are off.
- Supported Q&A intents are answered from saved data without an LLM.
- User-triggered explanation is optional.

If enabled, optional model output is validated and does not change the rule result. Local policy retrieval uses Chroma and the configured BGE-small embedding model when that feature is explicitly invoked; claimant first-result calculation does not synchronously index uploaded policies.

## 7. Data and persistence

The default architecture is local-first:

- **SQLite** stores user accounts, claims, document metadata, policy versions, rule evaluations, settlement comparisons, reviewer decisions, evidence confirmations, audit events, and optional analysis jobs.
- **Private local files** store uploaded documents under the configured storage root.
- **Chroma** persists policy-clause vectors when semantic indexing is requested.
- **JSONL metrics files** may record agent/LLM metrics, depending on configuration.

The database and storage paths can be redirected with environment variables, which is how `run_demo.py` separates its synthetic demo state from normal app storage. This local storage design is not a production privacy, backup, retention, or deployment solution.

## 8. Security and safety controls

The project includes role checks, password hashing, login-attempt tracking, expiring and hashed reset/setup tokens, upload validation, claim-access checks, path validation for stored documents, reviewer audit records, and explicit review gates for uncertain evidence. The tests include access-control, upload, rendering, and zero-automatic-LLM-call checks.

These controls are prototype safeguards, not a claim of production security certification. The repository documentation explicitly says that no production security/privacy/retention assessment or hosting/deployment validation has been completed. Do not use real patient data.

## 9. Demonstration scenarios

The bundled demo cases are fictional:

- **`a_match`:** The bill and settlement reconcile under the sample policy; expected result is `no_discrepancy`, with no appeal draft.
- **`b_wrongful_deduction`:** An INR 3,000 investigation deduction conflicts with in-hospital policy evidence, with a net possible difference of INR 2,700 after the sample co-pay adjustment; expected result is `possible_discrepancy`, with PDF/DOCX appeal drafts available for review.
- **`c_manual_review`:** A scanned bill page and INR 1,000 settlement/bill-total mismatch require human review; expected result is `manual_review`, with no appeal draft.

The sample walkthrough and exact scenario details are in [`03_RUNNING_THE_DEMO.md`](03_RUNNING_THE_DEMO.md).

## 10. Evaluation and test coverage

The repository reports evaluations on synthetic, hand-labeled data. These are measurements on the stated fixtures, not estimates of real-world claim accuracy. Labels were prepared by the project author before scoring; no independent clinical, insurance, or legal adjudication is claimed.

The current evaluation guide reports:

- **30/30** deterministic decision agreement with reviewer-confirmed terms on the labeled evaluation cases.
- **6/30** status agreement before reviewer confirmation; the other 24 cases were safely routed to Manual Review.
- **30/30** cases showed an amount, range, or specific review reason before confirmation.
- **210/210** source-PDF policy-term extraction checks matched the fixture labels.
- **13/13** decision-and-amount equality for the documented Ollama on/off comparison set.
- **0/27** valid category-label items for the BGE category prototype evidence gate; category suggestions remain disabled.

The docs also record distinct parser, browser, golden-rule, and LLM-grounding checks. These denominators measure different parts of the system and must not be combined into one accuracy score. The full pytest run on 2026-10-24 reported **305 passed, 3 skipped, 0 failed** (`.\.venv\Scripts\python.exe -m pytest -q tests --basetemp "$env:TEMP\mediguard-final-full-20261024"`). For methods, the dated live explanation-quality reruns, confidence intervals, and exported result tables, see [`06_EVALUATION_RESULTS.md`](06_EVALUATION_RESULTS.md), [`10_RESEARCH_PAPER_RESULTS.md`](10_RESEARCH_PAPER_RESULTS.md), and [`09_PROJECT_SUMMARY.md`](09_PROJECT_SUMMARY.md).

The test suite is organized into unit, integration, golden, and browser tests under `tests/`. The full run recorded above used:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests --basetemp "$env:TEMP\mediguard-final-full-20261024"
```

The browser checks are opt-in and may require a local browser environment; the browser group tests are skipped by the full pytest invocation. See [`09_PROJECT_SUMMARY.md`](09_PROJECT_SUMMARY.md) for the latest run date and group counts.

## 11. Running the project on Windows

From PowerShell, after installing Python 3.13:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r tests/requirements-dev.txt
Copy-Item .env.example .env
```

Start the isolated fictional demo:

```powershell
.\.venv\Scripts\python.exe run_demo.py
```

The demo is documented at `http://127.0.0.1:8506`. For the normal app, run:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py --server.port 8501
```

The ordinary app is documented at `http://127.0.0.1:8501`. Install and configure Tesseract only if scanned-image/PDF OCR is required. Ollama is optional. See [`README.md`](../README.md) for the complete setup and evaluation commands.

## 12. Known limitations and future work

Known limitations include:

- Small, synthetic, hand-labeled evaluation sets that are not representative of real claims.
- OCR sensitivity to scan quality and local Tesseract availability.
- Policy wording can be conditional or ambiguous; source pages still need reviewer inspection.
- Semantic retrieval can include relevant clauses but has low precision at larger result counts.
- An exclusion passage can cause the current clause filter to reject a broader passage containing a valid coverage sentence.
- Optional local LLM and embedding features require local installation and compute resources; LLM-on processing is slower.
- The category suggestion prototype is disabled because its available labeled evidence did not meet the configured evidence gate.
- Production deployment, security/privacy assessment, formal retention controls, and real-claim validation are out of scope.

Reasonable future project work would be to expand independently reviewed synthetic and de-identified test coverage, improve document-layout/OCR robustness, evaluate clause retrieval on better-labeled evidence, conduct a formal security/privacy review before any broader deployment, and preserve reviewer approval as a hard gate for uncertain policy interpretations.

## 13. Conclusion

MediGuard AI demonstrates an end-to-end local workflow for document extraction, evidence review, deterministic claim estimation, settlement comparison, and provisional claimant support. Its most important design choice is to separate calculation from generated language: the rule engine owns financial outcomes, and uncertain evidence is exposed for human review. The project is suitable for academic demonstration with fictional data; it is not ready or validated for real insurance decisions.

## 14. Further reading

- [Project overview](01_OVERVIEW.md)
- [Architecture](02_ARCHITECTURE.md)
- [Running the demo](03_RUNNING_THE_DEMO.md)
- [Hand-calculated rule examples](04_MATH_GOLDEN_CASES.md)
- [LLM safety and usage](05_LLM_SAFETY.md)
- [Evaluation results](06_EVALUATION_RESULTS.md)
- [Limitations](07_LIMITATIONS.md)
- [Screenshot capture guide](08_SCREENSHOT_CAPTURE.md)
- [Project completion summary](09_PROJECT_SUMMARY.md)
- [Milestone log](10_MILESTONE_LOG.md)
- [Research paper results](10_RESEARCH_PAPER_RESULTS.md)
- [Documentation index](README.md)
- [Project report](PROJECT_REPORT.md)
