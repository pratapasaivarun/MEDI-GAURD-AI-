"""Shared pytest isolation for function-based tests added to this project."""
from __future__ import annotations

import pytest


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
