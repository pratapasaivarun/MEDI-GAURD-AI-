# Medi Gaurd AI — Core-First Project Audit

**Audit date:** 27 August 2026  
**Scope:** Core claim-verification workflow, frontend integration, backend connections, OCR, policy terms, deterministic rules, ChromaDB retrieval, and the two-agent workflow.

## Product purpose

Medi Gaurd AI exists to answer one question safely and clearly: **how much of a medical bill is covered, how much the claimant must pay, and why**. OCR, policy extraction, deterministic calculations, retrieval, agents, and reviewer controls are supporting machinery for that answer. The system must never silently guess; incomplete or uncertain evidence must result in Manual Review.

## Current core architecture

```text
Streamlit core-demo UI
  -> SQLite claims/documents/policy/audit state
  -> PyMuPDF text extraction or Tesseract image OCR
  -> normalized claim fields, line items, confidence and review flags
  -> active policy edition and deterministic policy-term extraction
  -> ChromaDB policy evidence retrieval
  -> Policy Agent (Ollama Granite 4.1 8B)
  -> Decision Agent (Ollama Granite 4.1 8B)
  -> Approved / Partially Approved / Rejected / Manual Review
  -> reviewer sign-off and audit trail
```

## Frontend status

The live `app.py` now uses a reference-inspired interface with a navy sidebar, Medi Gaurd AI branding, white bordered cards, compact two-column forms, dashboard metrics, role-aware navigation, four Claim Review steps, extraction metrics, deterministic result cards, agent progress feedback, policy management, and an admin panel.

The main pages are:

| Page | Core behavior |
|---|---|
| Dashboard | Loads claims and statuses from SQLite and opens a selected claim directly |
| Register claim | Creates a claim in SQLite and automatically moves to Claim Review |
| Claim Review | Selects a claim, uploads documents, extracts fields, displays line items, runs rules, runs two agents, and supports sign-off |
| Policy Management | Ingests a policy edition, extracts terms, indexes evidence, activates the edition, and retains history |
| Admin Panel | Creates reviewer invitations and displays users when the full role workflow is later enabled |

## Authentication change for core-first development

Authentication and MFA were **not deleted**. A reversible `MEDIGUARD_CORE_DEMO` mode was added. It defaults to `true` for the current core demo and creates a local `Demo Reviewer` actor so the adjudication workflow can be tested without login friction. Set:

```text
MEDIGUARD_CORE_DEMO=false
```

when authentication, MFA, and role-gated deployment are ready to be re-enabled. The underlying password hashing, TOTP, password reset, invitation, RBAC, and authorization functions remain in the codebase.

## Backend verification results

The following checks passed on the live Windows project:

| Check | Result |
|---|---|
| Updated `app.py` compilation | Passed: `CORE_PYCOMPILE_OK` |
| Dynamic policy-term extraction | Passed: `DYNAMIC_POLICY_TERMS_TEST_OK` |
| Policy negative/rule test | Passed: `POLICY_RULE_NEGATIVE_TEST_OK` |
| Line-item extraction | Passed: `LINE_ITEMS_OK` |
| Tesseract image OCR | Passed: `TESSERACT_IMAGE_OCR_TEST_OK` |
| Synthetic fixture matrix | Passed: `PHASE4_FIXTURE_MATRIX_OK`, 8 fixtures |
| Full PDF + image E2E workflow | Passed: `E2E_TEST_OK` |
| Deterministic business rules | Passed: `PHASE6_BUSINESS_RULES_OK` |
| Data security controls | Passed: `PHASE7_DATA_SECURITY_OK` |
| Structured adjudication | Passed: `STRUCTURED_ADJUDICATION_OK` |

The full E2E test extracted Jane Doe, City Care Hospital, policy `POL-HEALTH-45821`, total `INR 145,000`, produced an approved deterministic result with payable `INR 121,500`, indexed and retrieved policy evidence, completed Ollama warm-up in approximately 41 seconds, and completed the workflow with exactly **2 LLM calls**.

## Important warnings and limitations

The PDF extraction layer still emits the existing PyMuPDF `fitz` deprecation warning. This is non-blocking, but it should be cleaned up later by migrating imports to the modern `pymupdf` API.

The browser screenshot that appeared extremely small was caused by browser zoom/display scaling; the Streamlit server itself started correctly on IPv4 port 8505. Use `Ctrl+0` in the browser before judging visual sizing.

The current report is a core-first prototype audit. Authentication and reviewer lifecycle tests remain available but are intentionally outside the main demo path until the adjudication UX is accepted. The complete project test suite was rerun during this audit using `run_full_audit_suite.py`: **23 tests passed, 0 failed, and 0 timed out**. The detailed evidence is saved in `backend_full_audit_test_results.txt`.

## Safe run instructions

From Command Prompt:

```bat
cd /d "C:\MediGaurd AI"
.venv\Scripts\activate
streamlit run app.py --server.address=127.0.0.1 --server.port=8505
```

Open:

```text
http://127.0.0.1:8505
```

Use the core demo without login. Register a claim, upload a medical bill and matching policy, extract and normalize, confirm the fields and line items, run deterministic rules, and only then run the Policy Agent plus Decision Agent. If policy terms, required fields, line items, or trusted reviewer facts are uncertain, the correct outcome is Manual Review.

## Strict verification evidence

The full audit suite passed all 23 test scripts: authentication lifecycle, dynamic policy terms, PDF and image end-to-end processing, line items, policy isolation, OCR fallback, Ollama warm-up, agent failure paths, real fixtures, fixture matrix, document quality, business rules, data security, policy controls, reports, reviewer controls, invitations, reviewer workflow, security access, and structured adjudication. The live core-demo mode was also compiled successfully and the updated Streamlit server started on IPv4 port 8505.

## Priority next work

1. Validate the refreshed UI manually at normal browser zoom across Dashboard, Register Claim, Claim Review, and Policy Management.
2. Add a claimant-facing summary that shows only billed amount, covered amount, claimant responsibility, plain-language status, and a short explanation.
3. Improve policy activation guidance and show the claim-policy number match before rules can run.
4. Add explicit duplicate/older-document warnings and incomplete-line-item warnings.
5. Clean the PyMuPDF deprecation warning.
6. After core UX and business rules are signed off, re-enable authentication, MFA, RBAC, reviewer invitations, and deployment hardening.
7. Add retention/deletion policy confirmation and complete the remaining operational regression matrix.

## Backups

Before the UI update, the previous live frontend was saved as:

```text
C:\MediGaurd AI\app_backup_before_reference_ui.py
```

The current source is:

```text
C:\MediGaurd AI\app.py
```

Both the frontend and backend should be treated as prototype decision-support software. Final insurance determination must remain with an authorized human reviewer.
