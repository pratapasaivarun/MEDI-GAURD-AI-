# Changelog

## v1.0-prototype

- Organized the Streamlit prototype into ingestion, policy, rules, comparison, explanation, reporting, services, and UI modules.
- Added fictional end-to-end demo cases, reviewer confirmation, source-backed policy terms, settlement comparison, appeal drafts, and offline evaluation.
- Documented that Python determines amounts and status while the optional local language model only explains results.
- Added CI checks and a reproducible synthetic-data evaluation suite.
- Added a deterministic LangGraph Supervisor, four deterministic workflow workers, and the checked background Analysis Agent.
- Kept category suggestions disabled because available labels do not meet the 90% evidence gate; added read-only, grounded claimant Q&A fallback.
