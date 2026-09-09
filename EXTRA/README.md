# Medi Gaurd AI — MVP Foundation

This milestone implements the first foundation slice of the Medi Gaurd AI architecture: local development login scaffolding, SQLite persistence, claim registration, document uploads, upload metadata, audit events, and Ollama connectivity status.

## Prerequisites

Install Python 3.11 or newer and Ollama for Windows. Confirm that the Granite model is available:

```bat
ollama list
```

The default configuration expects:

```text
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=ibm/granite4.1:8b
```

## Setup on Windows

From the project directory, create a virtual environment and install dependencies:

```bat
py -3 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Copy `.env.example` to `.env`, update the model name if necessary, and start the application:

```bat
copy .env.example .env
streamlit run app.py
```

Open the displayed local URL in a browser. Enter an email and display name for the local development login, register a claim, and upload PDF or image documents. Uploaded files are saved under `data\uploads\` and metadata is stored in `data\mediguard.db`.

## Current scope

The local login is intentionally a development scaffold. Firebase token verification must replace it before a pilot deployment. Document extraction is now included in this milestone. Select a saved claim, upload documents, and click **Extract and normalize documents**. PyMuPDF extracts text from normal PDFs. Scanned PDFs and image documents are rendered or routed to PaddleOCR. Common fields are normalized with code-first parsing, and every extracted field retains source-page provenance and confidence. Fields below the current 70% confidence threshold, missing required fields, or extraction failures are surfaced as `Needs Review`.

The deterministic rules, policy retrieval, and final decision agents are the next milestone. The current workflow records files safely and stores extracted JSON so the downstream policy and rule modules can consume it.

### Persistent policy indexing with ChromaDB

When a document marked as `policy` is extracted, the application splits its text into section-aware chunks and upserts them into a persistent ChromaDB collection at `data\\chroma`. Each chunk stores the policy identifier, document identifier, source filename, page number, and section metadata. The Policy Agent uses semantic search filtered by the policy identifier, so unrelated or obsolete policy documents are not mixed into a claim.

The configuration is available in `.env`:

```text
CHROMA_DIR=data/chroma
CHROMA_COLLECTION=mediguard_policy_clauses
CHROMA_EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
```

The default embedding configuration attempts to use BGE-small. If the optional sentence-transformers model cannot be loaded locally, ChromaDB falls back to its default embedding function. The Claim review screen reports the number of indexed policy chunks after extraction. The next agent run retrieves semantically relevant clauses and displays their source and page metadata.

### Policy version management

The **Policy management** tab is a dedicated policy-ingestion screen. Upload each policy edition with its policy number, version label, insurer, and effective date. Each edition is saved in `data\\policies`, persisted in the `policy_versions` SQLite table, indexed in ChromaDB using its own version identifier, and shown with active or archived status. Uploading a newer edition for the same policy automatically archives the previously active edition.

When at least two editions exist, select an older and newer edition and click **Compare selected editions**. The comparison reports text similarity, added clauses, removed clauses, changed terms such as annual limit/deductible/copayment/waiting period, and a unified diff. This is comparative analysis for review; it does not silently rewrite historical claim decisions.

The agent workflow now uses the matching active standalone policy edition from this table. You do not need to upload the same policy again under Claim review. If no matching active edition exists, the workflow falls back to a claim-uploaded policy document. If neither source is available, it asks you to ingest or upload policy evidence.

### Testing image-based OCR

A synthetic image bill is included at `sample_documents\\sample_medical_bill_image.png`. Upload it as a `medical_bill` from the Claim review tab and click **Extract and normalize documents**. Image files and rendered scanned-PDF pages are routed through the configured Tesseract adapter. OCR is initialized lazily and cached for the session so the engine is not loaded repeatedly.

For Windows CPU stability, the application now uses **Tesseract-OCR** for image and scanned-PDF OCR. PaddlePaddle 2.6.1 is not available for this project’s Python 3.13 environment, so the requested PaddleOCR 2.7.3 fallback cannot be installed here. The exact Tesseract settings are:

```text
OCR_BACKEND=tesseract
TESSERACT_CMD=C:\\Program Files\\Tesseract-OCR\\tesseract.exe
```

The installed fallback was validated against `sample_medical_bill_image.png` and returned OCR confidence of approximately 95%. Confidence-based `Needs Review` behavior remains unchanged. The first OCR run may take longer while Tesseract initializes.

If the Tesseract executable is not installed, install it with the Windows package manager or install it from the official Tesseract Windows distribution, then restart Streamlit.

### Testing deterministic coverage rules

After extraction succeeds, click **Run deterministic coverage rules**. The current rule version is `mvp-1.0` and calculates the policy limit, deductible, copayment, and payable amount using decimal arithmetic. A claim with missing or low-confidence fields is routed to `Manual Review`; a claim above the annual limit is `Partially Approved`; otherwise the result is `Approved`.

The default sample terms are an annual limit of INR 500000, deductible of INR 10000, and 10 percent copayment. These are demonstration values and should be replaced by policy-specific terms after policy retrieval is implemented.

### Running the Policy Agent and Decision Agent

After uploading and extracting both a policy document and a medical bill, run the deterministic rules first, then click **Run Policy Agent + Decision Agent**. The LangGraph workflow executes two main Granite calls: the Policy Agent interprets retrieved policy evidence, and the Decision Agent combines the normalized claim, policy findings, and deterministic rule results. The workflow displays policy evidence, reasons, status, confidence, and the number of LLM calls used.

The Policy Agent and Decision Agent are intentionally constrained to the supplied evidence. The Decision Agent cannot change deterministic calculated amounts, and a rule result of `manual_review` forces the final workflow status to `manual_review`. If no extracted policy document is available, the UI asks you to upload and extract one first.

The application is designed for a laptop demo: use small files, approximately 5–10 pages per document, and start Ollama before launching Streamlit so the model remains warm. Ollama calls use `OLLAMA_TIMEOUT_SECONDS=120`, `num_predict=256`, and `keep_alive=10m`; the application also performs one short warm-up call before the first real Policy Agent/Decision Agent workflow. The final determination should always be confirmed by an authorized reviewer.
