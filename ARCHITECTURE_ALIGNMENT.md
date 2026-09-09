# Academic prototype architecture

The active claim path follows the hardware-optimized architecture reference:

1. Streamlit claim registration and results UI.
2. PyMuPDF extraction with Tesseract for scanned/image documents.
3. ChromaDB policy indexing and metadata-filtered clause retrieval.
4. LangGraph routes a deterministic retrieval-only Policy Agent to one LLM-backed Decision Agent.
5. `rules.py` remains the sole authority for coverage arithmetic.
6. SQLite stores claim state; ChromaDB stores policy chunks; local storage retains uploaded documents.
7. ReportLab produces the decision report and a deterministic appeal-letter draft.

Ollama uses `OLLAMA_KEEP_ALIVE` (default `30m`) to retain the CPU model between demonstrations. MFA, encryption, production operations, PaddleOCR, and policy comparison remain in `deferred/` because they are not part of the academic demo path.
