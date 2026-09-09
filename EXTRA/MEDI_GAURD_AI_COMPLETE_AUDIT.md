# Medi Gaurd AI — Complete Project Audit

**Prepared by:** Manus AI  
**Audit scope:** Current Windows Streamlit prototype and its local SQLite/ChromaDB/Ollama workflow  
**Audit date:** 26 August 2026  
**Overall assessment:** Strong, working MVP prototype with reliable happy-path automation, but not yet production-ready for real patient documents or external users.

## Executive summary

Medi Gaurd AI is a medical-bill and insurance-claim verification prototype. Its implemented workflow is:

> Streamlit UI → SQLite claim/document storage → PyMuPDF/Tesseract extraction → normalized fields with provenance and confidence → deterministic rule engine → ChromaDB policy retrieval → Policy Agent → Decision Agent → reviewer sign-off → PDF/JSON exports.

The core MVP is substantially complete. PDF extraction works, image OCR works through Tesseract, multi-word OCR fields were corrected, policy text is isolated from bill totals, policy terms are extracted dynamically, deterministic calculations are authoritative, ChromaDB retrieval is persistent, the workflow uses two LLM calls, strict JSON parsing has safe fallback behavior, reviewer controls are present, and reports are generated.

The principal remaining risks are not the basic claim calculation. They are operational and security concerns: production authentication lifecycle, reviewer invitation and password setup, actual use of `SESSION_SECRET`, empty `.gitignore`, local secret/data files present in the project directory, unrestricted or insufficiently scoped low-level claim access paths, lack of encrypted storage, lack of retention/deletion, and incomplete test alignment after the new role guards changed expected behavior.

## Status legend

| Status | Meaning |
|---|---|
| **Complete and verified** | Implemented and passed a focused automated or end-to-end check |
| **Implemented, needs hardening** | Present in code but not sufficient for production or has an identified gap |
| **Partially complete** | Some functionality exists, but important paths or lifecycle controls are missing |
| **Pending** | Not implemented or not yet validated |
| **Regression/stale test** | The implementation changed, but an existing test or fixture still expects older behavior |

## 1. Architecture audit

### Intended architecture

The uploaded architecture diagram describes a broader production-oriented design containing Firebase authentication, a Document Agent, a Supervisor Agent, a Policy Agent, a Decision Agent, SQLite checkpoints, ChromaDB retrieval, report generation, appeal letters, and a future Q&A chatbot.

The current code implements a smaller and safer MVP architecture. Document extraction is code-first rather than a third LLM agent. The active OCR backend is Tesseract rather than PaddleOCR because PaddlePaddle 2.6.1 was unavailable for the Python 3.13 Windows environment. The current agent workflow is Policy Agent followed by Decision Agent, with exactly two real LLM calls on the successful path.

| Architecture component | Current status | Audit result |
|---|---|---|
| Streamlit frontend | Implemented | Working, but role-based UI visibility needs refinement |
| Firebase authentication | Not implemented | Replaced temporarily by local password authentication |
| SQLite persistence | Implemented | Functional local persistence; requires backup/encryption/retention hardening |
| PyMuPDF PDF extraction | Implemented | Verified |
| PaddleOCR | Not used | Correct decision for current Python 3.13 Windows environment |
| Tesseract OCR | Implemented | Image OCR verified |
| Text normalization | Implemented | Multi-word and policy/bill isolation fixes verified |
| Deterministic Python rules | Implemented | Core calculation verified; one old test expectation is stale |
| ChromaDB indexing/retrieval | Implemented | Persistent indexing and retrieval verified |
| Policy Agent | Implemented | Strict JSON, compact retrieved evidence, timing metrics, fallback |
| Decision Agent | Implemented | Strict JSON and safe fallback; deterministic result remains authoritative |
| Supervisor Agent | Not implemented | Not required for the current two-agent MVP |
| LangGraph workflow | Implemented | Two-node graph verified |
| Reviewer workflow | Implemented | Queue, assignments, edits, evidence, sign-off, reopen, audit events |
| PDF decision report | Implemented | Export test passed |
| Appeal-letter draft | Implemented | Available as text export |
| Q&A chatbot | Pending | Future feature |
| Production deployment | Pending | Not ready for real PHI/PII |

## 2. Functional implementation audit

### 2.1 Document upload and validation

The application accepts PDF, PNG, JPG, and JPEG files. It validates the extension, file size, empty content, and basic file signatures. The configured default limits are 10 pages and 15 MB. Uploaded files are renamed with a UUID prefix and stored under the configured storage directory.

**Assessment:** Complete for the MVP. The validation is useful but is not malware scanning or full MIME/parser validation. Page count is enforced during extraction rather than necessarily before all storage operations. A production implementation should add parser-based validation, malware scanning, upload quotas, retention, secure deletion, and document-access audit events.

### 2.2 PDF, image, and scanned-document extraction

Text-based PDFs are processed with PyMuPDF. Images are processed using Tesseract through `pytesseract`. Scanned PDFs are rendered and sent through the OCR path. The final Windows configuration intentionally does not require PaddleOCR.

The major OCR defect involving truncated multi-word values was fixed using coordinate-aware line reconstruction. The image fixture now produces the expected values:

| Field | Verified value |
|---|---|
| Patient | Jane Doe |
| Hospital | City Care Hospital |
| Policy number | POL-HEALTH-45821 |
| Diagnosis | Acute appendicitis |
| Total amount | INR 145,000 |
| OCR confidence | Approximately 95% on the clean fixture |

**Assessment:** Complete and verified for prepared fixtures. Real phone photos, skewed pages, handwriting, low light, unusual fonts, and multilingual documents remain pending robustness validation.

### 2.3 Normalization and provenance

The normalized contract contains patient name, hospital, policy number, dates, diagnosis, total amount, missing fields, review fields, evidence, source filename/page, extraction method, and confidence. Low-confidence or missing required values route the claim toward Manual Review.

Policy text is kept separate from medical-bill normalization so annual policy limits are not mistaken for the medical bill total. This was a critical correctness fix and is verified.

**Assessment:** Complete for the current data contract. The next improvement should be schema validation at module boundaries using Pydantic or an equivalent typed contract, plus explicit field-level provenance storage in SQLite rather than only JSON blobs.

### 2.4 Deterministic rule engine

The rule engine uses `Decimal` arithmetic and calculates annual limits, deductibles, copayments, covered amount, payable amount, room limits, category sub-limits, waiting periods, network restrictions, pre-authorization requirements, and exclusion warnings. It returns four states: `approved`, `partially_approved`, `rejected`, and `manual_review`.

The code correctly forces `manual_review` when required policy terms are missing, required claim fields are missing, low-confidence fields are present, policy controls require confirmation, or exclusion evidence is uncertain. The LLM is not allowed to alter the calculated monetary fields.

**Assessment:** Core rules are complete and authoritative. One existing `test_policy_and_rules.py` test currently expects `partially_approved` for a policy-limit case, while the current rule engine returns `manual_review` because a warning is present. This is either a deliberate policy change or a stale test expectation and must be resolved explicitly. The dynamic policy-term test also returned Manual Review because the extracted policy controls required confirmation; the test fixture likely reflects an older expectation.

### 2.5 Policy-term extraction and policy management

Policy versions are stored with policy number, version label, insurer, effective date, status, source path, extracted text, indexed chunk count, and extracted policy terms. Ingesting a new active edition archives the previous active edition for the same policy number. Policy comparison can display similarity and added/removed/changed clauses.

The application correctly stops with Manual Review when no active policy terms are available. This behavior is safer than using demonstration defaults.

**Assessment:** Implemented and mostly verified. Policy management still needs strict role-based UI hiding, deletion/retention controls, signed access, and protection of policy source files. The application should also distinguish “missing required terms” from “terms present but requiring human confirmation” more explicitly in the UI.

### 2.6 ChromaDB retrieval

Policy clauses are indexed into a persistent ChromaDB collection. Metadata includes policy identifiers and source information. The Policy Agent receives compact retrieved chunks rather than the entire policy document, avoiding the earlier CPU timeout caused by large prompt prefill.

**Assessment:** Implemented and verified. Remaining work includes index lifecycle management, deletion when a policy is deleted, encryption or protected volume placement, and tests for cross-policy retrieval isolation after restart.

### 2.7 Policy Agent and Decision Agent

The active workflow uses only two LLM calls. The Policy Agent retrieves evidence and returns structured findings. The Decision Agent receives compact claim fields, policy findings, and deterministic rule results, then returns a structured status and reasons. Ollama uses explicit context, thread, token, temperature, and keep-alive settings. Per-agent metrics record elapsed time, prompt size estimate, load duration, prompt evaluation count, and generated token count.

The JSON parser supports strict JSON, list-shaped output, extraction of an object from surrounding text, safe cleanup of trailing commas and balanced delimiters, and a Manual Review fallback for unrecoverable output. If the Policy Agent fails, the Decision Agent is skipped and the claim is routed to Manual Review.

**Assessment:** Complete for the two-agent MVP and verified. Remaining work includes broader model-failure testing under real UI conditions, log redaction, and deciding whether `OLLAMA_NUM_THREAD` and model settings should be validated at startup.

## 3. Reviewer workflow audit

The reviewer workflow contains a queue, assignment, editable extracted fields, evidence confirmations, reviewer decisions, reopen behavior, and audit events. Automated status and final reviewer status are stored separately.

### Current authorization matrix

| Operation | Claimant | Reviewer | Admin |
|---|---:|---:|---:|
| Self-register | Yes | No | No |
| View own claims | Yes | Limited | All |
| Upload to own claim | Yes | Assigned/eligible | All |
| View reviewer queue | No | Yes | Yes |
| Edit extracted fields | No | Yes | Yes |
| Confirm evidence | No | Yes | Yes |
| Reopen claim | No | Yes | Yes |
| Save final decision | No | Yes | Yes |
| Ingest policy edition | No | No | Yes |
| Archive policy edition | No | No | Yes |
| Provision reviewer role | No | No | Yes |

### RBAC strengths

The application uses backend guards rather than trusting UI fields. `require_role()` verifies roles, and reviewer mutation functions reload the user from SQLite. Claimants are generally restricted to their own claims. Reviewer and administrator operations are separately audited.

The focused reviewer and security tests passed:

```text
REVIEWER_CONTROLS_OK
SECURITY_ACCESS_OK
```

### RBAC gaps

1. `assign_claim()` currently allows reviewers and administrators to assign claims. Recommended policy: administrators may assign or reassign; reviewers may self-claim an unassigned eligible case but may not assign it to someone else.

2. `_claim_access()` allows a reviewer to access an unassigned claim without checking that the status is an eligible review state. Add a status condition for unassigned reviewer access.

3. `evaluate_saved_claim()` and `run_agents_for_claim()` should call `_claim_access()` directly. They currently rely heavily on the UI caller being correct.

4. `provision_user_role()` gives a reviewer role but sets `password_hash` to `NULL`, so the provisioned reviewer cannot log in. Add an invitation or one-time password setup flow.

5. The reviewer UI can still render controls to a claimant and then show a permission error after submission. Hide or disable reviewer-only controls at render time as well as enforcing backend guards.

6. `user_claims()` accepts a user ID and has optional role-aware behavior. A single authenticated-user object or authorization service would reduce the risk of callers passing mismatched IDs.

## 4. Authentication audit

### Implemented

Passwords are hashed with PBKDF2-HMAC-SHA256 using a unique 16-byte random salt and 310,000 iterations. Password comparisons use `hmac.compare_digest()`. Public registration is limited to claimant accounts, and password length is checked.

### Missing for production

The application still lacks password reset, reviewer invitation, email verification, login throttling, account lockout, session expiration, device/session revocation, MFA, and a real identity provider. `get_or_create_user()` creates a random unknown password for legacy test compatibility and must not be used as a real user-provisioning path.

Firebase authentication was shown in the architecture diagram but is not connected in the current code. That is an architecture-to-implementation gap, not a test failure.

## 5. Secrets and environment configuration audit

Environment variables are loaded with `python-dotenv`. The project has a useful `.env.example` containing settings for application mode, authentication, session secret, administrator bootstrap, storage paths, Ollama, OCR, and ChromaDB.

The most important issue is that `SESSION_SECRET` is only validated in `pilot` or `production` mode. It is not currently used to sign sessions, invitation tokens, password-reset tokens, or any other security artifact. `AUTH_REQUIRED` is read but does not materially change application behavior.

The project directory contains a `.env` file and generated local data artifacts. The root `.gitignore` is empty. This is a high-priority repository hygiene problem because the project handles claim documents, policy documents, OCR text, SQLite data, Chroma indexes, and local metrics.

### Required `.gitignore`

```gitignore
# Secrets and local configuration
.env
.env.*
!.env.example
*.pem
*.key
*.crt

# Patient, policy, database, and generated data
data/
*.db
*.sqlite
*.sqlite3
uploads/
policies/
chroma_index/

# Python environments and caches
.venv/
venv/
__pycache__/
*.py[cod]
.pytest_cache/
.mypy_cache/

# Streamlit secrets and logs
.streamlit/secrets.toml
*.log
*.err
*.out

# Generated reports and test artifacts
reports/
artifacts/
coverage.xml
htmlcov/
```

If sensitive files were ever committed, `.gitignore` is not enough. They must be removed from the Git index and all exposed credentials must be rotated.

## 6. Upload, SQLite, and Chroma security audit

### Uploads

The private storage-root and path-containment checks are a good start. The application should also validate files with parser libraries, enforce a pre-extraction page limit, scan uploads for malware, protect files with Windows ACLs, add secure deletion, and audit preview/download events.

No direct raw-document download endpoint is currently present. This reduces exposure, but future previews or downloads must always call `secure_document_path()` with the authenticated user and must never expose arbitrary `stored_path` values.

### SQLite

SQLite stores users, claims, documents, policy versions, rule evaluations, reviewer decisions, field edits, evidence confirmations, and audit events. It is appropriate for the local MVP, but production operation requires encrypted storage, encrypted backups, restore testing, restricted OS permissions, foreign-key enforcement, transaction-safe backup procedures, and formal migrations.

The custom database path should create its parent directory and reject paths located inside public/static directories. Database backups must be treated as sensitive medical data.

### ChromaDB

ChromaDB stores policy-derived embeddings and metadata. It must be placed under the same protected storage policy as SQLite, with index deletion tied to policy deletion and cross-policy retrieval isolation tested after restart.

## 7. UI and operational audit

The Streamlit UI contains Dashboard, Register Claim, Claim Review, and Policy Management areas. It provides staged status feedback for extraction and agent execution, reports elapsed workflow time, displays the policy source and evidence, and visibly states that the final determination must be confirmed by an authorized reviewer.

The primary operational limitation is that Streamlit session state is not equivalent to a complete production authentication/session-management system. The application also needs error boundaries around every privileged action, a visible user role indicator, role-specific navigation, session timeout, and an administrator-only account-management screen.

The current model is CPU-bound. The happy-path agent workflow is functional but can take approximately one minute per agent on the tested Windows laptop. Warm-up, compact retrieval, bounded tokens, and two-agent enforcement are the right optimizations. The application should continue to show progress and should not add more LLM calls.

## 8. Verified test matrix

| Test | Result | Interpretation |
|---|---|---|
| `test_phase2_failure_paths.py` | Passed | Invalid files, missing fields, and failure routing behave safely |
| `test_normalization_policy_isolation.py` | Passed | Policy limits do not contaminate bill totals |
| `test_ocr_fallback.py` | Passed | Tesseract image OCR works on the prepared image fixture |
| `test_phase1_decisions.py` | Passed | Five decision scenarios passed |
| `test_phase2_agent_failures.py` | Passed | Agent failure and fallback paths passed |
| `test_policy_controls_batch.py` | Passed | Policy control behavior passed |
| `test_reports.py` | Passed | Report exports passed |
| `test_reviewer_controls.py` | Passed | Queue, edits, evidence, reopen, and audit controls passed |
| `test_security_access.py` | Passed | Password, cross-claim isolation, role rejection, and path containment passed |
| `test_end_to_end.py` | Passed | PDF, image, normalization, rules, ChromaDB, warm-up, and two-agent workflow passed |
| `test_policy_and_rules.py` | Failed | Existing expectation conflicts with current Manual Review behavior |
| `test_dynamic_policy_terms.py` | Failed | Existing expectation conflicts with current policy-control Manual Review behavior |
| `test_reviewer_workflow.py` | Failed after RBAC tightening | Fixture still uses a claimant where a reviewer is now required |
| Full wildcard compile command | Command issue | PowerShell passed `*.py` incorrectly to Python; compile individual files or use PowerShell expansion explicitly |

The failures above should not be ignored. Two are likely stale expectations after the safety behavior was strengthened, and one is a stale reviewer fixture after backend authorization was correctly added. They must be updated or the implementation behavior must be deliberately changed and documented.

## 9. Priority implementation roadmap

### P0 — Protect the repository and close authorization gaps

1. Add and commit the `.gitignore` above.
2. Check Git history for `.env`, databases, uploads, policies, Chroma indexes, and logs. Remove tracked sensitive files and rotate exposed secrets.
3. Restrict reviewer assignment to administrators, with a self-claim operation for reviewers.
4. Require eligible claim status in `_claim_access()` for unassigned reviewer access.
5. Add authorization checks directly inside `evaluate_saved_claim()` and `run_agents_for_claim()`.
6. Hide reviewer-only controls from claimant UI.
7. Fix `test_reviewer_workflow.py` to use a reviewer fixture.
8. Resolve the two stale deterministic-policy tests by deciding whether warnings should produce Manual Review or partial approval.

**P0 completion gate:** all focused tests pass, unauthorized direct helper calls fail safely, no secrets or patient data are tracked, and role-specific UI actions are unavailable to claimants.

### P1 — Complete account lifecycle and secure configuration

1. Add reviewer invitation and one-time password setup.
2. Add password reset with expiring, signed tokens.
3. Use `SESSION_SECRET` for tokens or remove it until a real signed-token mechanism exists.
4. Add login throttling, account lockout, logout invalidation, and session expiration.
5. Add administrator-only user and role management UI.
6. Wire `AUTH_REQUIRED` into explicit startup behavior or remove the unused flag.
7. Add startup rejection of placeholder secrets in pilot/production mode.

**P1 completion gate:** a provisioned reviewer can safely activate an account, sign in, expire a session, reset a password, and lose access after role revocation.

### P1 — Secure documents and data lifecycle

1. Add parser/content validation and malware scanning.
2. Add document preview/download endpoints with ownership/assignment checks.
3. Add secure deletion of both files and database rows.
4. Add retention configuration and deletion audit events.
5. Apply Windows ACLs to storage, database, backups, and Chroma directories.
6. Create encrypted backup and restore procedures.
7. Reject public/static storage paths and create parent directories for custom database paths.

**P1 completion gate:** unauthorized OS users and application users cannot read another user’s documents, deletion is complete and audited, and a backup can be restored.

### P2 — Reliability and production operations

1. Add typed schemas at extraction, rules, and agent boundaries.
2. Add cross-policy Chroma isolation tests after restart.
3. Test phone photos, skewed images, multi-page PDFs, scanned PDFs, corrupted documents, and large files.
4. Add structured redacted logging, metrics dashboards, and alerting.
5. Add concurrency and transaction tests for SQLite.
6. Add CI with individual test discovery, compile checks, and a no-secrets scan.
7. Add a deployment runbook and rollback procedure.

### P3 — Future product features

1. Firebase or another managed identity provider.
2. Multi-tenant organization model.
3. Supervisor/checkpointing layer if workflow complexity justifies it.
4. Claimant-facing Q&A chatbot restricted to verified evidence.
5. Appeals workflow and external integrations.
6. Production deployment with encrypted managed storage and formal privacy/compliance review.

## Final conclusion

The project has achieved a credible MVP foundation and the core verification path works. The strongest technical decisions are code-first extraction, Tesseract for the current Windows environment, deterministic financial authority, compact evidence retrieval, exactly two LLM calls, safe Manual Review fallback, and separate reviewer sign-off storage.

The project should not yet be described as production-ready or as a legally binding claim adjudication platform. The next work should not add new AI features. The correct sequence is: **repository/data protection → RBAC tightening → reviewer account lifecycle → secure document lifecycle → test cleanup → deployment hardening → only then Firebase or additional product features.**
