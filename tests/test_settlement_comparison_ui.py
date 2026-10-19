from contextlib import nullcontext
from types import SimpleNamespace

import mediguard.ui.claim_pages as claim_pages


class FakeStreamlit:
    def __init__(self):
        self.messages = []

    def columns(self, *_args, **_kwargs):
        return [self, self, self]

    def metric(self, *_args, **_kwargs):
        pass

    def container(self, *_args, **_kwargs):
        return nullcontext()

    def __getattr__(self, name):
        if name in {"markdown", "caption", "warning", "success", "info", "write"}:
            return lambda message, *_args, **_kwargs: self.messages.append(str(message))
        raise AttributeError(name)


def test_manual_review_does_not_say_settlement_is_missing(monkeypatch):
    fake = FakeStreamlit()
    monkeypatch.setattr(claim_pages, "st", fake)
    comparison = SimpleNamespace(
        status="manual_review",
        actual_insurer_payment=None,
        expected_insurer_payment=None,
        possible_difference=None,
        review_reasons=["SETTLEMENT_TOTAL_MISSING"],
        categories=[],
    )
    settlement = SimpleNamespace(bill_total=None, review_reasons=[])

    claim_pages._render_settlement_comparison({}, comparison, settlement)

    messages = " ".join(fake.messages)
    assert "Upload the insurer's settlement letter" not in messages
    assert "authorized reviewer" in messages
