"""Shared pytest isolation for function-based tests added to this project."""
from __future__ import annotations

import pathlib
import pytest

# Ensure the pytest basetemp directory exists before any test session starts.
# This prevents FileNotFoundError when tmp/ has been cleared between runs.
pathlib.Path("tmp/pytest_tmp").mkdir(parents=True, exist_ok=True)


@pytest.fixture(autouse=True)
def reset_streamlit_session_state():
    """Avoid carrying Streamlit session values between future pytest tests."""
    try:
        import streamlit as st
        for key in list(st.session_state):
            del st.session_state[key]
    except Exception:
        pass
    yield
    try:
        import streamlit as st
        for key in list(st.session_state):
            del st.session_state[key]
    except Exception:
        pass


@pytest.fixture(autouse=True)
def keep_background_llm_jobs_off_in_tests(monkeypatch):
    """All tests use deterministic outputs; queue behavior has direct mocks."""
    try:
        from mediguard.services import application
        monkeypatch.setattr(application, "_ensure_analysis_worker", lambda: None)
    except Exception:
        pass
