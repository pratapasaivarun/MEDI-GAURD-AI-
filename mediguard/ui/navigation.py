"""Small helpers for keeping programmatic page changes in sync with the sidebar."""
from __future__ import annotations

from typing import MutableMapping, Sequence


def queue_page(session: MutableMapping[str, object], page: str) -> None:
    """Apply a page change on the next rerun, before its radio widget is built."""
    session["page"] = page
    session["pending_navigation"] = page


def prepare_navigation(session: MutableMapping[str, object], pages: Sequence[str]) -> None:
    """Transfer a queued page change to the sidebar widget before rendering it."""
    pending = session.pop("pending_navigation", None)
    if pending in pages:
        session["workspace_navigation"] = pending
