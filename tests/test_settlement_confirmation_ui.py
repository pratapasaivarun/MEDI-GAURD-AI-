from decimal import Decimal
from types import SimpleNamespace

import mediguard.ui.claim_pages as claim_pages
from mediguard.engine.models import SettlementData


class RerunRequested(BaseException):
    pass


class FakeStreamlit:
    def __init__(self):
        self.session_state = {}
        self.labels = []

    def columns(self, count, **_kwargs):
        return [SimpleNamespace(metric=lambda *_args, **_kwargs: None) for _ in range(count)]

    def markdown(self, *_args, **_kwargs):
        pass

    def caption(self, *_args, **_kwargs):
        pass

    def warning(self, *_args, **_kwargs):
        pass

    def write(self, *_args, **_kwargs):
        pass

    def info(self, *_args, **_kwargs):
        pass

    def error(self, *_args, **_kwargs):
        pass

    def checkbox(self, label, **_kwargs):
        self.labels.append(label)
        return True

    def button(self, label, **kwargs):
        self.labels.append(label)
        assert kwargs["disabled"] is False
        return True

    def rerun(self):
        raise RerunRequested


def test_ui_requires_explicit_checkbox_then_calls_confirmed_comparison(monkeypatch):
    fake_st = FakeStreamlit()
    monkeypatch.setattr(claim_pages, "st", fake_st)
    calls = []
    confirmed = SimpleNamespace(status="no_discrepancy")
    settlement = SettlementData(
        "CLM-2026-0417", Decimal("0"), bill_total=Decimal("1000"),
        needs_review=True,
        review_reasons=["SETTLEMENT_TOTAL_FROM_BILL: uploaded bill total proposed; user confirmation required."],
    )

    def run_comparison(*args, **kwargs):
        calls.append((args, kwargs))
        return confirmed, settlement

    monkeypatch.setattr(claim_pages, "run_settlement_comparison", run_comparison)
    current = SimpleNamespace(
        status="manual_review", actual_insurer_payment=Decimal("0"),
        expected_insurer_payment=Decimal("0"), possible_difference=Decimal("0"),
        review_reasons=["SETTLEMENT_TOTAL_FROM_BILL: user confirmation required."], categories=[],
    )

    try:
        claim_pages._render_settlement_comparison(
            {"claim_id": "claim-1"}, current, settlement,
            {"user_id": "user-1"}, {"total_amount": {"value": 1000}}, {"status": "approved"},
        )
    except RerunRequested:
        pass

    assert "I confirm the uploaded hospital bill total should be used for this comparison." in fake_st.labels
    assert "Confirm bill total and compare" in fake_st.labels
    assert calls[0][1]["confirm_inferred_bill_total"] is True
    assert fake_st.session_state["comparison_claim-1"] is confirmed
    assert fake_st.session_state["settlement_claim-1"] is settlement
