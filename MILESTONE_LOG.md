# Milestone log

## Phase 0 — Architecture note check

**What changed:** Added this architecture check. No application behavior changed.

### Diagram notes against the code

| Diagram note | Status | What the code shows |
|---|---|---|
| `extraction.py`: “Flag LLM fields, more dates” | **Done** | `extraction.py:92-113` parses numeric and month-name date formats. `extraction.py:23` sets LLM extraction confidence to 60; `extraction.py:711-743` marks LLM-filled fields and line items for review. |
| `rules.py`: “Merge two calculation paths” | **Done** | `rules.py:313-324` has one `evaluate_claim` entry point. Typed bills and aggregate totals are both handled there; aggregate-only claims become a synthetic item at `rules.py:414`. `rules.py:532-533` keeps that case on the same item calculation path. The old `_evaluate_claim_total_only` helper is absent. |
| `app.py`: “Escape HTML” | **Done for dynamic display values** | Escaping helpers in `ui/components.py:57-99` HTML-escape titles, claim values and attributes, and constrain status values. The rendering regressions are in `tests/test_xss_rendering.py`. The app still uses trusted static HTML for its visual shell. |
| `app.py`: “Fix auth” | **Done for the prototype safeguards** | `app.py:133-151` hashes and verifies passwords; `app.py:154-158` checks roles; `app.py:175-204` applies login throttling. MFA and email delivery are outside the current prototype. |
| `app.py`: “Split file” | **Partial** | Authentication and claim screens are in `ui/auth_pages.py` and `ui/claim_pages.py`, imported by `app.py:1839-1840`. However, `app.py` is still about 1,857 lines and retains database/storage, authentication services, orchestration and routing. |

### Pipeline order

The diagram order is broadly correct, with one detail: `app.py` coordinates the whole flow; it is not only a final screen. `process_claim_documents` begins at `app.py:1027`, extracts documents, then indexes policy text and extracts terms (`app.py:1065-1072`). Rules run at `app.py:1245`. Settlement parsing and comparison happen in `app.py:1327` and `app.py:1437`. The claimant/reviewer UI then requests explanations and report drafts (`ui/claim_pages.py:311-321`).

In plain language: bill and policy files are extracted; policy terms and searchable clauses are prepared; rules calculate the claim; the settlement parser reads the insurer letter; comparison checks it against the rules; explanations and draft reports follow; the Streamlit app coordinates and displays these steps.

**Verify command:**

```powershell
$env:OLLAMA_HOST='http://127.0.0.1:1'
.\.venv\Scripts\python.exe -m pytest -q --basetemp 'C:\Users\prata\mediguard_phase0_pytest'
```

**Expected output:** 166 tests pass; no failed tests. Ollama is disabled for the run.

**Observed output:** `166 passed in 46.72s`.

**Observed output:** `166 passed in 59.10s`.

## Phase 1 — Baseline

**Branch:** `fix/prototype-completion`  
**Commit at baseline:** `a3f5bca` — `docs: record phase 0 architecture check`  
**What changed:** Recorded the current branch and baseline. No application behavior changed.

**Verify command:**

```powershell
$env:OLLAMA_HOST='http://127.0.0.1:1'
.\.venv\Scripts\python.exe -m pytest -q --basetemp 'C:\Users\prata\mediguard_phase1_pytest'
```

**Expected output:** 166 tests pass; no failed tests. Ollama is disabled for the run.

