"""Streamlit page routing, separated from application setup and services."""
from __future__ import annotations

from typing import Any

import streamlit as st


def render_current_page(app_services: Any) -> None:
    from mediguard.ui.auth_pages import _render_welcome, _render_login
    from mediguard.ui.claim_pages import (
        _render_claimant_result, _render_claim_review, _render_claim_submission,
        _render_dashboard, _render_register,
    )

    if not st.session_state.get("welcome_seen") and not (st.query_params.get("reset_token") or st.query_params.get("setup_token")):
        _render_welcome()
        return
    if "user" not in st.session_state:
        _render_login()
        return
    user = st.session_state.user
    page = app_services._render_sidebar(user)
    routes = {
        "Dashboard": _render_dashboard,
        "Register claim": _render_register,
        "Submit documents": _render_claim_submission,
        "Claim review": _render_claim_review,
        "Claim result": _render_claimant_result,
        "Policy management": app_services._render_policy_management,
        "Admin panel": app_services._render_admin_panel,
    }
    render = routes.get(page)
    if render:
        render(user)
