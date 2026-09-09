# Medi Gaurd AI — Complete Backend Report

**Project:** Medi Gaurd AI  
**Report date:** 27 August 2026  
**Environment:** Windows, Python 3.13, Streamlit, SQLite, Tesseract OCR, PyMuPDF, ChromaDB, LangGraph, Ollama

## 1. Executive summary

Medi Gaurd AI is a medical-bill and insurance-claim decision-support system. Its backend answers one core question: **how much of a medical bill is covered, how much the claimant must pay, and why**.

The core backend is operational and has been verified on the live Windows project. A full suite of **23 test scripts passed, with 0 failures and 0 timeouts**. The verified end-to-end path accepts PDF and image documents, extracts and normalizes claim information, extracts policy terms, indexes and retrieves policy evidence, evaluates deterministic rules, and runs exactly two LLM agents through Ollama.

The deterministic rule engine is authoritative. The Policy Agent and Decision Agent provide evidence-based interpretation and reasoning only. If required information is missing, confidence is low, policy evidence is unavailable, or an agent response is invalid, the system routes the claim to Manual Review rather than guessing.

## 2. Core architecture

```text
Streamlit UI
    |
    v
SQLite claims, documents, policies, evaluations, audit events
    |
    +--> PyMuPDF text extraction for text PDFs
    +--> Tesseract OCR for image bills and scanned PDFs
    |
    v
Normalized claim fields, line items, confidence, provenance, review flags
    |
    v
Active policy edition + deterministic policy-term extraction
    |
    +--> ChromaDB policy indexing and semantic retrieval
    |
    v
Deterministic Python rule engine
    |
    v
Policy Agent -- Ollama Granite 4.1 8B
    |
    v
Decision Agent -- Ollama Granite 4.1 8B
    |
    v
Approved | Partially Approved | Rejected | Manual Review
    |
    v
Reviewer confirmation, audit event, reports and exports
```

## 3. Backend modules

| Module | Responsibility | Verification status |
|---|---|---|
| `app.py` | Streamlit entry point, database lifecycle, document processing orchestration, page actions, reviewer flow, and result presentation | Compiled and exercised through E2E |
| `extraction.py` | PyMuPDF extraction, Tesseract OCR adapter, field normalization, line items, confidence, provenance, duplicate detection, and missing-field routing | PDF, image, line-item, fixture, and isolation tests passed |
| `policy_terms.py` | Deterministic extraction of deductible, copayment, annual limit, room limit, waiting period, currency, and related terms | Dynamic policy-term tests passed |
| `policy_index.py` | Policy chunking, persistent ChromaDB indexing, metadata, and policy-scoped evidence retrieval | Policy retrieval passed in E2E |
| `rules.py` | Authoritative deterministic adjudication including limits, deductible, copayment, exclusions, waiting periods, network, and preauthorization | Business-rule and negative-path tests passed |
| `agents.py` | LangGraph workflow, compact evidence prompts, strict JSON schemas, Ollama calls, warm-up, metrics, and safe fallbacks | Two-agent E2E and failure-path tests passed |
| `reports.py` | Decision-support report and export generation | Report tests passed |
| `policy_compare.py` | Historical policy-edition comparison | Policy-control tests passed |
| `claim_doc_map.py` | Claim/document mapping support | Included in project source and audit suite dependencies |

## 4. Database structure

The SQLite database contains the following functional areas:

| Table | Purpose |
|---|---|
| `users` | Local users and retained role/authentication fields |
| `claims` | Claim identity, patient/provider, policy number, status, context, and timestamps |
| `documents` | Private document metadata, stored path, hash, type, processing status, and extracted JSON |
| `policy_versions` | Historical and active policy editions, source text, indexed chunks, and extracted terms |
| `rule_evaluations` | Versioned deterministic rule results for a claim |
| `audit_events` | Claim and administrative audit trail |
| `reviewer_decisions` | Automated status, reviewer final status, comments, and timestamp |
| `reviewer_field_edits` | Reviewer corrections to extracted fields |
| `evidence_confirmations` | Reviewer-confirmed document/page evidence |
| `password_reset_tokens` | Deferred authentication lifecycle support |
| `reviewer_invitations` | Deferred reviewer invitation lifecycle support |

The backend initializes the schema and applies lightweight migrations for fields introduced during later phases.

## 5. Document and OCR pipeline

For text PDFs, PyMuPDF extracts page text and retains page-level evidence. For image bills and scanned PDFs, Tesseract OCR is used through the configured adapter. The pipeline preserves source name, page, method, extracted text, and confidence.

The normalized output includes patient name, hospital/provider, policy number, claim number, admission and discharge dates, diagnosis, total amount, line items, source documents, raw page text, duplicate candidates, missing fields, and review fields.

The current OCR backend is intentionally Tesseract on Windows because PaddleOCR/PaddlePaddle 2.6.1 was unavailable for Python 3.13 in the tested environment. The confidence threshold is retained; low-confidence fields do not silently pass.

## 6. Policy processing

A policy document is extracted separately from a medical bill. Policy text is not allowed to contaminate financial claim fields. Policy terms are extracted deterministically and stored with value, confidence, source text, source page, source name, and extraction method.

A policy must be ingested as an edition before it becomes the active policy source for adjudication. Ingestion stores the edition, extracts terms, chunks the text, indexes it in ChromaDB, and allows historical editions to remain available for comparison.

This separation addresses the earlier operational confusion in which uploading a policy under Claim Review did not automatically mean that its terms were active for rules.

## 7. Deterministic adjudication

The rule engine is the source of truth for financial outcomes. Its processing includes required-field validation, policy-term availability, exclusion checks, waiting-period checks, network and preauthorization conditions, room-charge limits, sub-limits, deductible, copayment, covered amount, and payable amount.

The engine returns one of four supported states:

| State | Meaning |
|---|---|
| Approved | Evidence and policy rules support full approval under the configured semantics |
| Partially Approved | Some amount is payable while specific charges are excluded or limited |
| Rejected | The claim is not payable under the evaluated policy rules |
| Manual Review | Evidence, terms, trust status, or agent output is insufficient for safe automation |

Claimant assertions such as network status and preauthorization are not treated as trusted until an authorized reviewer confirms them in the reviewer workflow.

## 8. Two-agent workflow

The backend uses exactly two intended LLM calls per normal successful claim:

1. **Policy Agent:** receives compact normalized claim facts and retrieved policy evidence. It returns structured findings, missing evidence, and confidence.
2. **Decision Agent:** receives compact claim facts, Policy Agent findings, and deterministic rule results. It returns status, short reasons, policy citations, confidence, and reviewer note.

The agents cannot change deterministic financial amounts. If the Policy Agent returns invalid or unavailable JSON, the Decision Agent is not called and the system creates a safe Manual Review result. If the Decision Agent returns an invalid status, the system constrains it to the allowed statuses and preserves Manual Review when deterministic rules require it.

Ollama configuration includes a 120-second timeout, explicit context and thread options, short structured JSON output, a 10-minute keep-alive, and a warm-up call. The live E2E test verified **2 LLM calls**.

## 9. Security and operational state

The project retains PBKDF2 password hashing, TOTP MFA, password reset tokens, reviewer invitations, RBAC checks, private storage validation, encrypted backup support, secure document access, document deletion, and audit events. These features remain in the codebase.

For core-first development, the main UI currently uses reversible demo mode. `MEDIGUARD_CORE_DEMO=true` creates a local demo reviewer actor so the core claim workflow can be demonstrated without authentication friction. Set `MEDIGUARD_CORE_DEMO=false` to restore the login/MFA path.

This is appropriate for local prototype testing only. It is not a production security configuration.

## 10. Verification evidence

The live Windows project ran the following complete suite:

```text
SUMMARY total=23 pass=23 fail=0 timeout=0
```

The passed scripts cover authentication lifecycle, dynamic policy terms, PDF and image E2E processing, line items, policy isolation, OCR fallback, Ollama warm-up, agent failure paths, real fixtures, the fixture matrix, real-document quality, business rules, data security, policy controls, reports, reviewer controls, invitations, reviewer workflow, security access, and structured adjudication.

The core E2E evidence was:

```text
Normalized patient: Jane Doe
Normalized hospital: City Care Hospital
Normalized policy: POL-HEALTH-45821
Normalized total: INR 145000
Missing fields: none
Deterministic status: approved
Deterministic payable: INR 121500
Policy evidence retrieved: 1
LLM calls: 2
Final workflow: approved
E2E_TEST_OK
```

The application source also compiled successfully after the core-demo change, and Streamlit started on `127.0.0.1:8505`.

## 11. Issues found and corrections

The audit tooling initially expected outdated function names. The live extraction module uses `normalize_documents` and `run_extraction`, while the policy index uses `index_policy_documents`. The audit script was corrected and rerun successfully.

The earlier UI result was invalid because the policy had been uploaded but not activated as an edition and because an older duplicate bill file missed line items. The backend correctly returned Manual Review instead of approving with incomplete policy terms. The project now documents the distinction between document upload, policy ingestion, and active-policy selection.

A PyMuPDF `fitz` deprecation warning remains. It is non-blocking and should be removed by migrating to the modern `pymupdf` import API.

## 12. Current conclusion

The **core backend is operational and test-verified**. The core data path, rule engine, policy evidence path, two-agent workflow, and safe fallback behavior are connected correctly.

The project should still be described as a **local prototype decision-support system**, not a production insurance adjudication service. Final determination must remain with an authorized human reviewer.

## 13. Remaining work in priority order

1. Finish manual browser validation of the reference-style frontend at 100% zoom.
2. Add the claimant-facing summary with billed amount, covered amount, claimant responsibility, plain-language status, and simple explanation.
3. Make policy activation and claim-policy matching explicit before rules can run.
4. Add duplicate-document and incomplete-line-item warnings.
5. Replace deprecated `fitz` imports.
6. Re-enable authentication, MFA, and RBAC after core UX acceptance.
7. Finalize retention, deletion, deployment, identity-provider, and production security decisions.

## 14. Evidence files in the project

```text
C:\MediGaurd AI\backend_full_audit_test_results.txt
C:\MediGaurd AI\CORE_PROJECT_AUDIT.md
C:\MediGaurd AI\audit_backend_now.py
C:\MediGaurd AI\run_full_audit_suite.py
C:\MediGaurd AI\app.py
C:\MediGaurd AI\app_backup_before_reference_ui.py
```
