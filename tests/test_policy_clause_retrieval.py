from contextlib import contextmanager
from types import SimpleNamespace

import app


def test_claim_clause_map_uses_indexed_coverage_evidence_and_filters_exclusions(monkeypatch):
    @contextmanager
    def empty_db():
        yield SimpleNamespace(execute=lambda *_args: SimpleNamespace(fetchall=lambda: []))

    calls = []

    def retrieve(query, policy_id, limit):
        calls.append((query, policy_id, limit))
        return [
            {"text": "Clause 3.4: prescribed medicines are reimbursed during hospitalization.", "page": 9, "section": "coverage"},
            {"text": "Clause 8.2: pharmacy expenses are excluded and not payable.", "page": 20, "section": "exclusions"},
            {"text": "Clause 5.1: ICU treatment is covered subject to the daily limit.", "page": 12, "section": "coverage"},
        ]

    monkeypatch.setattr(app, "db", empty_db)
    monkeypatch.setattr(app, "active_policy_for_claim", lambda *_args: {"version_id": "policy-v1"})
    monkeypatch.setattr(app, "retrieve_indexed_policy_evidence", retrieve)

    clauses = app._claim_policy_clause_map("claim-1")

    assert clauses["PHARMACY"].page == 9
    assert clauses["ICU"].page == 12
    assert set(clauses) == {"PHARMACY", "ICU"}
    assert calls
    assert all(policy_id == "policy-v1" and limit == 8 for _, policy_id, limit in calls)
    assert all(any(word in query.lower() for word in ("covered", "payable", "reimbursed")) for query, _, _ in calls)
