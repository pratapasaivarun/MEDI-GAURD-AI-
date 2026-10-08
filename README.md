# MediGuard AI

> **Intelligent Medical Bill Verification and Insurance Compliance System**  
> An automated claim verification prototype for Indian health insurance — deterministic, explainable, and human-reviewer-gated.

---

## Overview

MediGuard AI is an academic prototype for comparing medical bills, policy terms, and insurer settlement letters. Its extraction and calculation paths require source confirmation and human review where evidence is incomplete. No insurer integration or production certification is provided. The current project does not claim validation against a representative set of insurers or policy editions. Its core principle is:

> **Deterministic code determines all financial outcomes. RAG retrieves policy evidence. The LLM explains the result. The LLM never decides the financial outcome.**

The automated scenario suite covers 22 synthetic cases, including room limits, duplicate billing, waiting periods, co-payment, coverage limits, and patient-name mismatch. Passing synthetic tests does not establish real-world claim accuracy.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        MEDIGUARD AI                             │
│                                                                 │
│  PDF / Image Upload                                             │
│        │                                                        │
│        ▼                                                        │
│  ┌─────────────────────────────────┐                            │
│  │  Document Extraction Layer       │  PyMuPDF + Tesseract OCR  │
│  │  extraction.py                   │  (PDF, scanned image,     │
│  └──────────────┬──────────────────┘   phone photo, multi-page)│
│                 │                                               │
│        ┌────────┴─────────┐                                     │
│        ▼                  ▼                                     │
│  Bill Data (JSON)   Policy Data (JSON)                          │
│        │                  │                                     │
│        └────────┬─────────┘                                     │
│                 ▼                                               │
│  ┌──────────────────────────────────────────────────┐           │
│  │             LangGraph Workflow (agents.py)        │           │
│  │                                                  │           │
│  │  START                                           │           │
│  │    │                                             │           │
│  │    ▼                                             │           │
│  │  Policy RAG Agent          BGE-small-v1.5        │           │
│  │  (policy_index.py)    ◄──  ChromaDB              │           │
│  │    │  Retrieves relevant policy clauses          │           │
│  │    ▼                                             │           │
│  │  Deterministic Rule Engine (rules.py)            │           │
│  │    │  Applies all financial rules deterministically│         │
│  │    ▼                                             │           │
│  │  Decision Agent            Ollama                │           │
│  │  (ibm/granite4.1:8b)  ◄──  local, 1 call only   │           │
│  │    │  Generates patient-friendly explanation     │           │
│  │    ▼                                             │           │
│  │  END → Result + Evidence + Recommendations       │           │
│  └──────────────────────────────────────────────────┘           │
│                 │                                               │
│                 ▼                                               │
│  ┌──────────────────────────────────────────────────┐           │
│  │  Report Generator (reports.py)                   │           │
│  │  PDF decision report + draft appeal letter       │           │
│  └──────────────────────────────────────────────────┘           │
│                 │                                               │
│                 ▼                                               │
│  ┌──────────────────────────────────────────────────┐           │
│  │  Streamlit UI (app.py)                           │           │
│  │  Patient portal + Admin/Reviewer dashboard       │           │
│  └──────────────────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────────────┘
```

**Components:**
| Component | File | Role |
|---|---|---|
| Document Extraction | `extraction.py` | OCR + structured field extraction from PDF/image |
| Deterministic Rule Engine | `rules.py` | All financial math — coverage, limits, exclusions, deductibles, co-pay |
| Policy RAG | `policy_index.py` | BGE-small-v1.5 embeddings + ChromaDB vector retrieval |
| Policy Term Parser | `policy_terms.py` | RegEx + LLM-fallback extraction of policy parameters |
| Agent Workflow | `agents.py` | LangGraph: Policy RAG Agent → Rule Engine → Decision Agent |
| Report Generator | `reports.py` | PDF decision report + appeal letter |
| Web Interface | `app.py` | Streamlit UI for patients and reviewers |

---

## 22 Patient-Centered Scenarios — All Implemented & Tested

| # | Scenario | Status |
|---|---|---|
| 1 | Covered medical/surgical expenses | ✅ |
| 2 | Excluded expenses (C10 non-medical) | ✅ |
| 3 | Non-medical charges | ✅ |
| 4 | Room-rent daily limit | ✅ |
| 5 | ICU daily limits | ✅ |
| 6 | Procedure sub-limits | ✅ |
| 7 | Deductibles | ✅ |
| 8 | Co-payment (% cost share) | ✅ |
| 9 | Waiting periods | ✅ |
| 10 | Policy exclusions | ✅ |
| 11 | Partial approval | ✅ |
| 12 | Rejection | ✅ |
| 13 | Manual review / uncertain cases | ✅ |
| 14 | Duplicate charge detection | ✅ |
| 15 | Bill ↔ policy patient-name mismatch | ✅ |
| 16 | Charges requiring policy-clause verification | ✅ |
| 17 | Multiple bill line items (itemized) | ✅ |
| 18 | Policy coverage limit exceeded | ✅ |
| 19 | Cumulative sum-insured exhaustion | ✅ |
| 20 | Pre / post-hospitalization expenses | ✅ |
| 21 | Daycare procedures (0-night stays) | ✅ |
| 22 | Package billing ambiguity (C11-style) | ✅ |

See the current automated test suite for implementation checks; test results are not a measure of real-world accuracy.

---

## Prerequisites

| Requirement | Version / Notes |
|---|---|
| Python | 3.11 or newer |
| [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) | Installed locally. On Windows, set `TESSERACT_CMD` if not at `C:\Program Files\Tesseract-OCR\tesseract.exe` |
| [Ollama](https://ollama.com/) | Running locally at `http://localhost:11434` |
| Ollama model | `ibm/granite4.1:8b` (pull before first run) |
| HuggingFace weights | BGE-small-v1.5 auto-downloaded on first policy index; stored at `.venv/hf-cache` by default (override with `HF_HOME`) |

---

## Quick Start

```powershell
# 1. Clone
git clone https://github.com/pratapasaivarun/MEDI-GAURD-AI-.git
cd "MEDI-GAURD-AI-"

# 2. Create virtual environment
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt

# 3. Configure environment
Copy-Item .env.example .env
# Edit .env — set TESSERACT_CMD if needed

# 4. Start Ollama and pull model
ollama serve
ollama pull ibm/granite4.1:8b

# 5. Launch the app
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Open `http://127.0.0.1:8501` in your browser.

---

## Environment Variables

Copy `.env.example` to `.env` and configure:

| Variable | Default | Description |
|---|---|---|
| `TESSERACT_CMD` | `C:\Program Files\Tesseract-OCR\tesseract.exe` | Path to Tesseract binary |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `ibm/granite4.1:8b` | LLM model for explanations |
| `OLLAMA_TIMEOUT_SECONDS` | `120` | Request timeout in seconds |
| `HF_HOME` | `.venv/hf-cache` | HuggingFace model cache directory |
| `MEDIGUARD_CORE_DEMO` | `false` | Enable synthetic demo mode only through `run_demo.py` |
| `MEDIGUARD_ADMIN_PASSWORD` | unset | Required by `run_demo.py` to provision its isolated demo administrator |

> **Security:** Never commit `.env`. Real patient documents must never be committed to the repository.

---

## User Roles

### Patient / Claimant
- Register an account → upload medical bill + insurance policy PDF
- View itemized adjudication result with clause-level evidence
- Download decision report and draft appeal letter

### Admin / Reviewer
- Sign in at the admin portal
- Review flagged claims requiring human judgement
- Correct extracted fields, override decisions, add notes
- Sign off for final settlement

The demo administrator is created only when `run_demo.py` is launched with
`MEDIGUARD_ADMIN_PASSWORD` set. No demo password is published or supplied by default.

---

## Demo Mode

Run an isolated synthetic demo (port 8506, separate data directory):

```powershell
.\.venv\Scripts\python.exe run_demo.py
```

Three pre-loaded walkthroughs using files in `demo_assets/`:

| Case | Bill | Policy | Expected Result |
|---|---|---|---|
| Approved | `approved_bill.pdf` | `approved_policy.pdf` | Approved — payable INR 67,500 |
| Partial | `partial_bill.pdf` | `partial_policy.pdf` | Partially approved — payable INR 81,000 |
| Manual review | `approved_bill.pdf` | Policy number mismatch | Manual review — calculation blocked |

---

## Running Tests

```powershell
# Full automated test suite
.\.venv\Scripts\python.exe -m pytest tests/ -v --basetemp=tmp/pytest_tmp
```
---

## Project Structure

```
MediGaurd AI/
│
├── app.py                          # Streamlit UI — patient & admin portals
├── agents.py                       # LangGraph workflow (Policy RAG → Rules → LLM)
├── extraction.py                   # OCR + document field extraction (PyMuPDF + Tesseract)
├── rules.py                        # Deterministic rule engine — all financial logic
├── policy_index.py                 # BGE-small-v1.5 embeddings + ChromaDB indexing
├── policy_terms.py                 # Policy parameter extraction (regex + LLM fallback)
├── reports.py                      # PDF report and appeal letter generation
├── benchmark_performance.py        # Pipeline stage timing benchmarks
├── generate_synthetic_case_library.py  # Synthetic test case generation utility
├── run_demo.py                     # Launch isolated synthetic demo on port 8506
│
├── requirements.txt                # Python dependencies
├── pytest.ini                      # Pytest configuration
├── conftest.py                     # Shared pytest fixtures
├── .env.example                    # Environment variable template
├── .gitignore                      # Excludes runtime data, secrets, binaries
│
├── tests/                          # Automated test suite
│   ├── test_all_22_scenarios.py    # 22/22 patient scenario coverage
│   ├── test_real_document_support.py  # Optional local document checks
│   ├── test_legacy_scripts.py      # Regression guard for legacy scripts
│   └── fixtures/
│       └── real_documents/         # Optional local documents (gitignored)
│
├── demo_assets/                    # Synthetic PDF walkthroughs (safe to commit)
│   ├── approved_bill.pdf
│   ├── approved_policy.pdf
│   ├── partial_bill.pdf
│   ├── partial_policy.pdf
│   └── partial_policy_preview.png
│
├── fixtures/                       # Tracked test fixtures and scenario libraries
│   └── claim_scenarios/            # Structured claim scenario PDFs
│       ├── approved/
│       └── rejected/
│
└── evaluation/                     # Research evaluation pipeline
    ├── run_evaluation.py           # Main evaluation runner
    ├── run_full_evaluation.py      # Full end-to-end evaluation
    ├── metric_calculators.py       # Precision / recall / F1 computation
    ├── generate_paper_tables.py    # LaTeX table generation for research paper
    ├── score_annotations.py        # Annotation scoring
    ├── annotations.json            # Human annotation ground truth
    ├── final_workflow_verification.json  # Verified workflow results
    ├── PAPER_RESULTS.md            # Evaluation results for the research paper
    └── README.md                   # Evaluation pipeline guide
```

> **Not tracked in git:** `data/` (runtime session data), `.venv/`, `chroma_db/`, `*.db`, `*.sqlite`, `tmp/`, `.env`, all real patient documents.

---

## Performance

No representative performance or field-accuracy benchmark is currently published. Runtime depends on document length, OCR, local hardware, and whether optional local model assistance is used.

---

## Research Context

MediGuard AI is an academic prototype developed as part of a research project on deterministic AI-assisted insurance claim verification. Key design decisions:

1. **LLM role is explanatory or extraction assistance only** — financial decisions (coverage amounts, deductibles, co-pay, exclusions) are computed deterministically in `rules.py`; model-derived extraction values require review.
2. **RAG provides evidence, not decisions** — ChromaDB + BGE-small-v1.5 retrieves the most relevant policy clauses; the rule engine then applies them.
3. **Ambiguous cases go to human review** — patient name mismatches, unknown policy terms, package billing ambiguity, and uncertain ICU limits are explicitly routed to a human reviewer rather than auto-rejected.
4. **Human reviewer gate** — automated output is a recommendation. An authorized reviewer confirms the claim determination.

---

## Limitations

- **Academic prototype only** — not certified for production insurance use.
- **No multi-factor authentication (MFA)** — MFA is not implemented; account access uses password authentication and login throttling.
- **No insurer API integration** — operates on uploaded documents only.
- **OCR quality dependent** — heavily skewed or very low-resolution images may reduce extraction accuracy.
- **Local LLM latency** — `ibm/granite4.1:8b` on CPU is slow (~2 minutes per claim). Use a GPU or a faster model for production.
- **Limited validation** — synthetic fixtures and automated tests do not establish accuracy for real claims or any particular insurer.

---

## License

This project is for academic and research purposes. See `LICENSE` if present, or contact the authors for usage terms.

---

*MediGuard AI — Intelligent Medical Bill Verification and Insurance Compliance System*
