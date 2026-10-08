from types import SimpleNamespace

import app


def test_manual_review_and_no_discrepancy_have_no_appeal_download():
    assert app.appeal_draft_available(SimpleNamespace(status="manual_review")) is False
    assert app.appeal_draft_available(SimpleNamespace(status="no_discrepancy")) is False


def test_possible_discrepancy_enables_the_single_appeal_path():
    assert app.appeal_draft_available(SimpleNamespace(status="possible_discrepancy")) is True
