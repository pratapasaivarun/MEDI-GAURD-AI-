# Changelog

## v1.0-prototype

- Organized the Streamlit prototype into ingestion, policy, rules, comparison, explanation, reporting, services, and UI modules.
- Added fictional end-to-end demo cases, reviewer confirmation, source-backed policy terms, settlement comparison, appeal drafts, and offline evaluation.
- Documented that Python determines amounts and status while the optional local language model only explains results.
- Added CI checks and a reproducible synthetic-data evaluation suite.
- Upgraded to a LangGraph workflow of five deterministic agents (Supervisor, Document, Policy, Decision, Output) with zero automatic LLM calls by default; optional on-demand LLM explanation and Q&A; Python decides every amount.
- Enforced strictly zero automatic LLM calls by default: disabled background analysis (`MEDIGUARD_ANALYSIS_ENABLED=false` by default, bypassed via conditional edge in `pipeline.py`) and disabled startup warm-up (`MEDIGUARD_OLLAMA_WARMUP=false` by default). Corrected earlier report: "Automatic LLM calls on upload/review path: 0" was incorrect prior to this fix because background analysis and startup warm-up previously executed by default; with this fix, automatic requests are verified to be 0 across startup, upload, review, and rendering.
- Removed unreachable dead function `_render_background_analysis` from `claim_pages.py` and handled empty analysis results cleanly in reviewer expander.
- Added audited single LLM gateway (`llm_gateway.py`) with configurable timeouts, request locking, factual deduplication, and JSONL metrics logging.
- Gated extraction fallbacks behind `MEDIGUARD_LLM_EXTRACTION_FALLBACK=false` by default, achieving identical results with Ollama on or off.
- Kept category suggestions disabled because available labels do not meet the 90% evidence gate; added read-only, grounded claimant Q&A fallback.
