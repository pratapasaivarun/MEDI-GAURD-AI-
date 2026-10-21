"""Reusable, escaped Streamlit presentation helpers."""

import html
from typing import Any
import streamlit as st

def _status_badge(status: str) -> str:
    return status.replace('_', ' ').title()


def deterministic_result_header_html(status: Any) -> str:
    safe_status = html.escape(_safe_status(status), quote=True)
    return f"<div class='mg-section-title'>Deterministic result <span class='mg-pill mg-pill-{safe_status}'>{html.escape(_status_badge(safe_status))}</span></div>"


def evidence_recommendation_header_html(status: Any) -> str:
    safe_status = html.escape(_safe_status(status), quote=True)
    return f"<div class='mg-section-title'>Evidence-based recommendation <span class='mg-pill mg-pill-{safe_status}'>{html.escape(_status_badge(safe_status))}</span></div>"


def _line_item_status_label(status: Any) -> str:
    """Return a compact, readable status cue for claimant-facing item rows."""
    return {
        "covered": "Covered",
        "partial": "Partially covered",
        "excluded": "Excluded",
        "needs_review": "Needs review",
    }.get(str(status), str(status or "Needs review").replace("_", " ").title())


def _status_color(status: str) -> str:
    return {
        'approved': '#168a57', 'partially_approved': '#b77908',
        'manual_review': '#b77908', 'rejected': '#c23b3b',
        'ready_for_review': '#b77908', 'extracted': '#2f6fb0',
        'draft': '#667085',
    }.get(status, '#667085')


def _brand_header() -> None:
    st.markdown('''
    <div class="mg-brand-head">
      <div class="mg-logo-mark" aria-label="MediGuard AI logo">
        <svg viewBox="0 0 64 64" role="img" aria-hidden="true"><path d="M32 5 54 13v16c0 14.5-9.4 25.2-22 30C19.4 54.2 10 43.5 10 29V13L32 5Z" fill="currentColor"/><path d="M32 16v30M20 31h24" stroke="#073b3a" stroke-width="5" stroke-linecap="round"/><path d="M22 42c3.1 4.2 8.4 6.9 10 7.5 1.6-.6 6.9-3.3 10-7.5" fill="none" stroke="#073b3a" stroke-width="3" stroke-linecap="round"/></svg>
      </div>
      <div><div class="mg-brand-name">MediGuard AI</div>
      <div class="mg-brand-sub">Evidence-led claim decisions</div></div>
    </div>''', unsafe_allow_html=True)


def _page_header(eyebrow: str, title: str, subtitle: str, icon: str) -> None:
    """Use one consistent, lightweight page hierarchy across the prototype UI."""
    st.markdown(page_header_html(eyebrow, title, subtitle, icon), unsafe_allow_html=True)


def page_header_html(eyebrow: str, title: str, subtitle: str, icon: str) -> str:
    return f'''<div class="mg-page-header">
        <div class="mg-header-icon">{html.escape(str(icon))}</div>
        <div><div class="mg-eyebrow">{html.escape(str(eyebrow))}</div><h1>{html.escape(str(title))}</h1>
        <p class="mg-subtitle">{html.escape(str(subtitle))}</p></div></div>'''


def auth_portal_html(label: str, title: str, copy: str) -> str:
    return f'<div class="mg-auth-kicker">{html.escape(str(label))}</div><div class="mg-auth-title">{html.escape(str(title))}</div><div class="mg-auth-copy">{html.escape(str(copy))}</div>'


def _claimant_progress(step: int, detail: str) -> None:
    """Show a simple, consistent progress cue through the claimant journey."""
    st.progress(step / 3, text=f"Step {step} of 3 · {detail}")


def _safe_status(status: Any) -> str:
    allowed = {"approved", "partially_approved", "manual_review", "rejected", "ready_for_review", "extracted", "draft"}
    value = str(status or "manual_review")
    return value if value in allowed else "manual_review"


def claim_context_html(claim: Any, status: Any) -> str:
    """Render user-derived claim labels as escaped text inside trusted markup."""
    safe_status = html.escape(_safe_status(status), quote=True)
    claim_number = html.escape(str(claim["claim_number"] or ""), quote=True)
    patient = html.escape(str(claim["patient_name"] or ""), quote=True)
    policy = html.escape(str(claim["policy_number"] or "Policy number pending"), quote=True)
    return (
        f"<div class='mg-context'><div><b>{claim_number}</b>"
        f"<div class='mg-card-copy'>{patient} · {policy}</div></div>"
        f"<span class='mg-pill mg-pill-{safe_status}'>{html.escape(_status_badge(safe_status))}</span></div>"
    )


def claim_row_html(claim: Any) -> str:
    safe_status = html.escape(_safe_status(claim["status"]), quote=True)
    claim_number = html.escape(str(claim["claim_number"] or ""), quote=True)
    patient = html.escape(str(claim["patient_name"] or ""), quote=True)
    hospital = html.escape(str(claim["hospital_name"] or "Provider pending"), quote=True)
    return (
        f"<div class='mg-claim-row'><div><b>{claim_number}</b>"
        f"<div class='mg-card-copy'>{patient} · {hospital}</div></div>"
        f"<span class='mg-pill mg-pill-{safe_status}'>{html.escape(_status_badge(safe_status))}</span></div>"
    )


