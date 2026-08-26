# Medi Gaurd AI — Must-Check Project Audit

**Author:** Manus AI  
**Audit scope:** Current Windows local MVP after reviewer lifecycle, Phase 4–7 controls, approved deterministic business rules, TOTP MFA, and password reset  
**Audit purpose:** Determine what is functional, what is accurate, what is only partially proven, and what loose ends must be fixed before real medical-document use.

## Executive conclusion

The current Medi Gaurd AI prototype is functionally coherent for a controlled, local, synthetic-data demonstration. The core pipeline is working: PDF and image extraction, Tesseract OCR, normalization with provenance, deterministic financial calculations, policy-term extraction, ChromaDB retrieval, two-agent LangGraph execution, reviewer workflow, reports, local authentication, reviewer invitation, TOTP MFA, password reset, secure document reads, deletion, and encrypted SQLite backup/restore are all covered by automated tests.

The audit baseline is strong but must not be described as production-ready or legally authoritative. The largest remaining risks are not the normal happy path; they are the boundary between extracted input and business decision. Real patient documents have not yet been validated, several new UI flows have backend tests but no full browser validation, the rule engine receives only a limited claim context from the current UI, and the local session model has not yet been upgraded to expiring signed sessions or throttled authentication.

> **Safety position:** Any missing, low-confidence, contradictory, unavailable, or ambiguous evidence must remain `manual_review`. Deterministic calculations remain authoritative over AI suggestions, and reviewer sign-off remains separate from automated output.

## Verified baseline

### Automated test result

The full `test_*.py` matrix was executed after the MFA, password reset, Phase 6 rules, and Phase 7 security changes.

```text
COMPILE_EXIT=0
FAILED_COUNT=0
```

The completed checks include:

| Area | Verified result |
|---|---|
| Password authentication, TOTP MFA, and reset lifecycle | `AUTH_LIFECYCLE_OK` |
| PDF extraction and policy-term extraction | `DYNAMIC_POLICY_TERMS_TEST_OK` |
| Complete PDF/image/OCR/rules/ChromaDB/agents flow | `E2E_TEST_OK` |
| Normalization and policy isolation | Passed |
| OCR fallback | `OCR_FALLBACK` test passed |
| Ollama warm-up | `OLLAMA_WARMUP_TEST_OK` |
| Agent malformed-output and failure paths | `PHASE2_AGENT_FAILURES_OK` |
| Six defined failure paths | `PHASE2_FAILURE_PATHS_OK` |
| Synthetic real-document fixture matrix | `PHASE4_FIXTURE_MATRIX_OK 8 synthetic_only=True` |
| Field-level quality and provenance | `PHASE5_REAL_DOCUMENT_QUALITY_OK 6 synthetic_only=True` |
| Approved deterministic business rules | `PHASE6_BUSINESS_RULES_OK` |
| Encrypted backup, restore, secure read, deletion, and isolation | `PHASE7_DATA_SECURITY_OK` |
| Reviewer invitation and activation | `REVIEWER_INVITATION_OK` |
| Reviewer workflow and controls | `REVIEWER_WORKFLOW_TEST_OK`, `REVIEWER_CONTROLS_OK` |
| Security access and claimant isolation | `SECURITY_ACCESS_OK` |
| Reports | `REPORT_EXPORT_TEST_OK` |

### Core E2E result

The controlled happy path continues to produce:

```text
Patient:        Jane Doe
Hospital:       City Care Hospital
Bill amount:    INR 145,000
Rules status:   approved
Payable amount: INR 121,500
Agent calls:    2
Evidence:       retrieved
```

This verifies the normal synthetic workflow only. It does not prove that every policy or real document will produce the same level of extraction quality.

## Architecture audit

The implementation follows the intended architecture:

```text
Streamlit UI
  → SQLite claims, documents, policies, rules, audit events
  → PyMuPDF selectable-text extraction
  → Tesseract image and scanned-PDF OCR
  → normalized values with confidence and provenance
  → deterministic Decimal-based rules
  → persistent ChromaDB policy retrieval
  → Policy Agent
  → Decision Agent
  → four-state decision and reviewer workflow
```

The architecture is appropriately code-first. Document extraction does not require an LLM, only two real LLM calls are used in the normal agent path, and the Decision Agent cannot change deterministic financial amounts. The application also correctly stops the Decision Agent when the Policy Agent has invalid or unavailable output.

The main architectural limitation is that the current Streamlit application stores the authenticated user in `st.session_state`, while the configured application-level secret is not used to sign or expire an application session. This is acceptable for a local prototype but must be addressed before exposure beyond a controlled local environment.

## Functional audit by module

### Document extraction and OCR

The application uses PyMuPDF for selectable PDFs and Tesseract for images and scanned PDFs, which matches the supported Windows Python 3.13 deployment policy. PaddleOCR is not a required final backend. OCR provenance now records `tesseract` rather than incorrectly claiming PaddleOCR.

The coordinate-aware Tesseract reconstruction correctly preserves common multi-word fields such as `Jane Doe` and `City Care Hospital`. The field-level confidence contract is present, and missing or low-confidence fields populate `missing_fields` or `review_fields`.

The Phase 5 fixtures demonstrated safe failure for a low-light image and a skewed/compressed image. The low-light fixture produced missing fields and the skewed fixture produced a contaminated hospital capture that was rejected by normalization. Both cases were allowed to route to Manual Review instead of being trusted.

Remaining extraction limitations are:

| Risk | Current status |
|---|---|
| Selectable PDF confidence | Text PDFs are assigned 100% confidence rather than an independently measured extraction-quality score. |
| OCR layout | Complex tables, overlapping text, rotated pages, handwritten values, and multilingual documents remain unproven. |
| Amount parsing | The parser supports common comma/decimal formats but requires more tests for Indian grouping, currency symbols, negative corrections, and credit notes. |
| Document validation | Extension, signature, size, and page checks exist; malware scanning and deep parser validation are not implemented. |
| Human correction | Reviewer correction exists for key claim fields, but correction of line items and structured amounts is limited. |

### Normalization

Normalization isolates policy text from bill text, preventing policy annual limits from being mistaken for bill totals. Required fields are patient name, hospital, and total amount; policy number and other fields are tracked separately.

A confirmed safety improvement is the label-contamination detector. If OCR merges a label from another field into a captured value, the value is rejected and the claim becomes incomplete rather than silently accepting the wrong value.

The major remaining issue is that the normalized schema and the rule-engine context are not yet fully aligned. `NormalizedClaim` contains the core identity and bill fields, while the newly approved rules also require context such as network status, pre-authorization status, room-linked charges, duplicate suspicion, multiple-bill grouping, and exclusion-match confidence. The current UI does not collect all of those context fields, so the correct result for some policies is Manual Review rather than a complete automatic calculation. This is safe, but it is incomplete functionality that must be made explicit in the reviewer workflow.

### Deterministic rules

The rule engine uses `Decimal` money calculations and returns the required four states: `approved`, `partially_approved`, `rejected`, and `manual_review`.

The approved Phase 6 behavior is now represented in code and tests:

| Decision | Current behavior |
|---|---|
| Clear high-confidence exclusion match | `rejected` |
| Ambiguous exclusion | `manual_review` |
| Sub-limit exceeded | `partially_approved`; valid portion remains payable |
| Room limit with linked-charge basis | Proportional reduction and `partially_approved` |
| Room limit without proportional basis | `manual_review` |
| Waiting-period violation with affected/unrelated amounts | Affected portion excluded; unrelated portion remains payable |
| Waiting-period violation without enough allocation evidence | `manual_review` |
| Confirmed out-of-network provider | `rejected` when policy requires network provider |
| Unknown network status | `manual_review` |
| Missing pre-authorization confirmation | `manual_review` |
| Net amount supplied | Net amount used as the calculation basis |
| Suspected duplicate charges | `manual_review`; never auto-removed |
| Multiple bills without reviewer confirmation | `manual_review` |

The rule engine is now safer than the original baseline. However, the code still has a product-level limitation: a clear exclusion or out-of-network rejection requires trusted structured context such as `exclusion_match` or `in_network=False`. The application should not infer these flags directly from an LLM. They need evidence-backed extraction or reviewer confirmation.

### Policy-term extraction and policy management

Policy terms are extracted deterministically from policy evidence and retain source text, page, source name, confidence, and method. Policy editions are stored with status, effective date, source path, content, indexed chunk count, and policy-term JSON. Active policy matching by policy number is implemented.

Policy-version comparison currently compares text and a subset of terms: annual limit, deductible, copayment, and waiting period. It does not yet compare every new rule control such as sub-limits, exclusions, room rules, network restrictions, or pre-authorization requirements. This is a real completeness gap for comparative policy analysis.

The ChromaDB integration is persistent and tested. The main risks are that `CHROMA_DIR` is resolved relative to the process working directory rather than necessarily the application directory, and the code silently falls back to another embedding configuration when the preferred sentence-transformer embedding cannot load. That fallback may change retrieval behavior between machines or restarts. The embedding model and resolved index path should be made explicit and validated at startup.

### Agents and Ollama

The agent workflow is correctly ordered: Policy Agent first, then Decision Agent. The Policy Agent receives compact claim fields and a maximum of two retrieved evidence chunks, not the entire policy document in its prompt. Strict JSON schemas, bounded output, low temperature, `num_ctx`, `num_thread`, and `keep_alive` are configured.

The recent metrics show approximately:

| Agent | Typical elapsed time | Prompt size estimate | Output cap |
|---|---:|---:|---:|
| Policy Agent | Approximately 50–68 seconds | Approximately 846 characters / 212 estimated tokens | 192 tokens |
| Decision Agent | Approximately 49–74 seconds | Approximately 970 characters / 242 estimated tokens | 192 tokens |

The two-call limit and failure fallback are functioning. The main efficiency limitation is that the normal path can still take roughly two minutes on CPU, and warm-up does not guarantee that every Ollama load is instantaneous. The UI must continue to show progress and elapsed time rather than appearing frozen.

One remaining code-quality issue is broad exception handling in the OCR, ChromaDB, and agent modules. Some broad catches are intentional safety fallbacks, but they should be narrowed and logged with redacted diagnostic identifiers so real configuration failures are not silently converted into low-quality retrieval.

### Reviewer workflow

The reviewer queue, assignment, field corrections, evidence confirmation, reviewer decision, reopen behavior, and audit records are implemented. Deterministic results and human final decisions are stored separately.

The reviewer invitation flow now solves the original `NULL password` lockout. A provisioned reviewer receives a one-time setup token, sets a password, and can then log in. Role revocation and account disabling are enforced by backend checks.

Remaining reviewer-workflow gaps are:

1. The administrator provisioning UI displays a local setup link rather than delivering an invitation through a real protected notification channel.
2. There is no session invalidation mechanism for a reviewer who is disabled while already signed in.
3. Field editing does not yet include every structured financial/context input required by the new business rules.
4. The full invitation, MFA enrollment, and reset flows have backend tests but have not yet had a full browser/manual validation pass.

### Authentication, MFA, and password reset

Password hashes use PBKDF2-HMAC-SHA256 with a per-password salt and 310,000 iterations. Password comparison uses `hmac.compare_digest`. Public registration creates claimant accounts only. Reviewer accounts are administrator-provisioned.

TOTP MFA is implemented using `pyotp`. The secret is encrypted with Fernet using a key derived from `MEDIGUARD_MFA_KEY`, with `MEDIGUARD_BACKUP_KEY` as a configured fallback. Login uses a pending MFA state and does not create the authenticated user session until the TOTP code succeeds.

Password reset uses a random token, stores only its SHA-256 hash, expires the token after one hour, invalidates previous unused tokens, and marks the token used after a successful password change. Unknown email requests return a non-disclosing response.

The remaining authentication risks are important:

| Risk | Impact |
|---|---|
| Streamlit session state is not application-signed or expiring | A production-grade session lifecycle is not yet present. |
| No login throttling or account lockout | Brute-force protection is incomplete. |
| No recovery codes | Losing the authenticator device can lock out a user. |
| Reset link is shown in the local UI | Acceptable for a controlled demo; not acceptable as production notification delivery. |
| MFA disable requires no recent password reauthentication | A stolen active session could disable MFA. |
| No audit event for every authentication failure | Security monitoring is incomplete. |

### Secure document and database access

Backend document reads call claim-access authorization and path containment checks. Claimants are restricted to their own claims, reviewers are restricted to eligible or assigned review claims, and administrators have broad access. Admin-only deletion removes the database row, removes the physical file, and writes an audit event.

Encrypted SQLite backup and restore are implemented with Fernet authenticated encryption, and wrong-key restore is rejected. The Windows operations runbook documents private storage and ACL setup.

Remaining data-lifecycle gaps are:

- Malware scanning is not implemented.
- Windows ACLs are documented but have not been applied and verified on the actual deployment directory.
- Retention currently covers uploaded documents through helper-level purge logic, but not yet all policies, generated reports, Chroma records, or backup copies.
- Legal hold behavior is not implemented.
- Claim-level deletion and cascade cleanup are not implemented as one atomic operation. SQLite foreign keys exist, but the schema does not consistently use `ON DELETE CASCADE` and the application does not yet provide a complete claim purge transaction.
- Backup scheduling and off-machine encrypted backup storage are not implemented.

### Reports and audit trail

Decision reports, appeal letters, JSON exports, reviewer decisions, field edits, evidence confirmations, assignments, and authentication lifecycle events are available. Report export tests pass.

Reports are not yet complete audit packages. The generated decision report summarizes calculations, reasons, policy source, and evidence count, but it does not yet include full field-level provenance, source page citations for every extracted value, reviewer correction history, evidence-confirmation records, or a complete immutable decision timeline. This is a correctness and defensibility gap rather than a normal-path execution failure.

## Confirmed loose ends and severity

| Severity | Loose end | Why it matters | Required action |
|---|---|---|---|
| P0 | Real documents have not been validated | Synthetic success does not establish field accuracy for actual bills and policies | Run a de-identified real-document matrix and measure field accuracy |
| P0 | Full UI validation of MFA/reset/invitation is incomplete | Backend success does not prove Streamlit state and query-parameter flow works in the browser | Perform one browser pass for each auth flow |
| P0 | Business-rule context fields are not fully collected by the UI | Some policy controls cannot be evaluated automatically and may over-route to Manual Review | Add structured reviewer inputs and evidence fields |
| P0 | No production session expiry/throttling/recovery | Local login is not sufficient for exposed deployment | Add session lifecycle, throttling, recovery codes, and reauthentication |
| P1 | Malware scanning and OS ACL verification missing | Uploaded medical documents are not fully protected at the runtime boundary | Add scanner hook and apply/verify ACLs |
| P1 | Retention does not cover all data stores | Copies can remain in reports, Chroma, and backups | Define and implement a complete retention/deletion graph |
| P1 | Policy comparison omits new control categories | Edition comparison can miss meaningful coverage changes | Compare exclusions, sub-limits, room, network, and authorization terms |
| P1 | Chroma embedding fallback is silent | Retrieval quality may change without an operator knowing | Pin embedding behavior and fail or warn explicitly |
| P1 | Reports omit complete provenance and reviewer timeline | Decisions are less defensible and harder to audit | Add provenance and reviewer-history sections |
| P2 | `fitz` deprecation warnings remain | Does not currently fail tests, but indicates future compatibility maintenance | Migrate imports to the recommended PyMuPDF API when stable |
| P2 | Broad exception catches | Some configuration failures may be hidden | Narrow catches and add redacted diagnostics |
| P2 | Many local helper/result files remain untracked | Repository hygiene can degrade even with `.gitignore` | Keep only maintained scripts and explicitly ignore disposable outputs |

## Accuracy assessment

The current system is **accurate on the tested synthetic happy path** and **safe on tested OCR failure paths**. It is not yet accurate enough to claim reliable generalization to arbitrary medical bills or insurance policies.

The strongest accuracy controls are:

- Policy text is isolated from bill totals.
- OCR fields carry confidence and provenance.
- Missing fields force Manual Review.
- OCR label contamination is rejected.
- Deterministic Decimal arithmetic controls amounts.
- AI cannot directly change calculated amounts.
- Invalid Policy Agent output blocks the Decision Agent.
- Ambiguous policy controls route to Manual Review.
- Duplicate and multi-bill uncertainty is not auto-resolved.

The remaining accuracy risks are:

- Some business-rule inputs are not present in normalized claim data.
- Selectable-PDF confidence is optimistic.
- Policy retrieval depends on runtime embedding availability.
- Reports do not yet expose every source citation needed for human verification.
- Real-world layouts and policy language remain under-tested.

## Efficiency assessment

The architecture already removes unnecessary LLM work from document extraction and enforces two calls per normal claim. Prompt trimming is working; recent prompts are only approximately 212 and 242 estimated tokens. The main remaining performance cost is CPU inference, approximately 50–74 seconds per agent in recent metrics.

Recommended efficiency actions, in order:

1. Keep the current two-call limit and compact prompts.
2. Keep Tesseract code-first extraction and do not reintroduce PaddleOCR for Python 3.13 Windows.
3. Cache policy retrieval and avoid rebuilding Chroma embedding configuration unnecessarily.
4. Avoid repeated Streamlit reruns around long operations.
5. Preserve staged progress messages and per-agent timing.
6. Add an explicit demo-mode timeout/fallback configuration without changing the tested 8B default.
7. Only consider a smaller model after measuring the current 8B path under the exact demo environment.

## Required next sequence

### Step 1 — Browser validation of new authentication

Validate reviewer invitation setup, MFA enrollment, MFA-gated login, MFA disable, password-reset request, reset completion, reset-token reuse, and logout. Record screenshots or timestamps only where they do not contain secrets or medical data. Do not paste real setup tokens, TOTP secrets, passwords, or reset links into reports.

### Step 2 — Real-document quality matrix

Use de-identified or synthetic-but-realistic documents that resemble real inputs. Test selectable PDFs, image-only PDFs, phone photos, low-light images, skewed images, multi-page claims, table-heavy bills, and variant policy wording. Record expected fields, actual fields, confidence, provenance, and final Manual Review routing.

### Step 3 — Align structured business inputs

Add explicit fields or reviewer controls for network status, pre-authorization, waiting-period allocation, exclusion evidence, room-linked charges, duplicate suspicion, and multiple-bill aggregation. Every field must retain source/evidence and confidence. A missing value must remain Manual Review.

### Step 4 — Complete retention and document security

Implement malware scanning, claim-level atomic purge, policy/Chroma/report retention, legal holds, encrypted scheduled backups, and verified Windows ACLs. Test both unauthorized access and recovery from backup.

### Step 5 — Improve audit reports

Add field-level provenance, policy clause citations, reviewer corrections, evidence confirmations, automated versus final decision history, and a complete audit timeline to PDF and JSON exports.

### Step 6 — Decide deployment architecture

After the above work, choose whether local authentication is sufficient for a controlled deployment or whether Firebase/Entra should own identity. If an external provider is selected, retain the backend role checks and claim isolation in Medi Gaurd rather than trusting client-side roles.

## Final readiness rating

| Readiness category | Rating | Interpretation |
|---|---|---|
| Controlled synthetic demo | **Ready** | Core flow, failure routing, reviewer workflow, and two-agent behavior are tested. |
| De-identified pilot | **Conditional** | Requires browser auth validation, real-document matrix, and operational storage/ACL checks. |
| Real patient-document production | **Not ready** | Requires retention, malware scanning, session security, operational backups, full provenance, compliance review, and deployment controls. |

## Final conclusion

No current automated test failure was found. The project is not broken on its tested paths. The most important finding is different: **passing tests do not yet prove broad claim accuracy**. The next work should focus on browser validation of the new authentication flows, real-document quality measurement, and structured business-rule inputs. Only after those gates pass should the project proceed to deployment and retention decisions or an external identity provider.
