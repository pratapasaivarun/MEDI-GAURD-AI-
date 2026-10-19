from contextlib import contextmanager
from types import SimpleNamespace

from mediguard.services import application as app
import pymupdf
from mediguard.policy.policy_index import chunk_policy_text


def test_claim_clause_map_uses_indexed_coverage_evidence_and_filters_exclusions(monkeypatch):
    @contextmanager
    def empty_db():
        yield SimpleNamespace(execute=lambda *_args: SimpleNamespace(fetchall=lambda: []))

    calls = []

    def retrieve(query, policy_id, limit):
        calls.append((query, policy_id, limit))
        return [
            {"text": "Clause 3.4: prescribed medicines are included during hospitalization.", "page": 9, "section": "coverage"},
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


def test_indexed_clause_with_exception_or_inadmissible_word_is_rejected(monkeypatch):
    monkeypatch.setattr(app, "active_policy_for_claim", lambda *_args: {"version_id": "policy-v1"})
    monkeypatch.setattr(app, "retrieve_indexed_policy_evidence", lambda *_args, **_kwargs: [
        {"text": "Clause 3.4: medicines are covered except when not prescribed.", "page": 9},
        {"text": "Clause 3.5: pharmacy costs are reimbursable but inadmissible under this plan.", "page": 10},
    ])

    assert "PHARMACY" not in app._claim_policy_clause_map("claim-1")


def test_empty_qualified_retrieval_returns_no_clause(monkeypatch):
    monkeypatch.setattr(app, "active_policy_for_claim", lambda *_args: {"version_id": "policy-v1"})
    monkeypatch.setattr(app, "retrieve_indexed_policy_evidence", lambda *_args, **_kwargs: [])

    assert app._claim_policy_clause_map("claim-1") == {}


def test_coverage_sentence_survives_exclusion_in_later_sentence(monkeypatch):
    monkeypatch.setattr(app, "active_policy_for_claim", lambda *_args: {"version_id": "policy-v1"})
    monkeypatch.setattr(app, "retrieve_indexed_policy_evidence", lambda *_args, **_kwargs: [
        {"text": "Clause 3.4: Pharmacy expenses are payable. Charges above the annual limit are excluded.", "page": 9, "section": "coverage"},
    ])

    clauses = app._claim_policy_clause_map("claim-1")
    assert clauses["PHARMACY"].text == "Clause 3.4: Pharmacy expenses are payable."


def test_demo_policy_pharmacy_query_returns_a_usable_coverage_clause(monkeypatch):
    policy_path = app.Path(__file__).resolve().parents[1] / "demo_assets" / "partial_policy.pdf"
    with pymupdf.open(policy_path) as document:
        chunks = [chunk for page_number, page in enumerate(document, start=1) for chunk in chunk_policy_text(page.get_text(), page=page_number)]
    monkeypatch.setattr(app, "active_policy_for_claim", lambda *_args: {"version_id": "demo-partial"})
    monkeypatch.setattr(app, "retrieve_indexed_policy_evidence", lambda query, _policy_id, limit: [
        {**chunk, "source_name": "partial_policy.pdf"} for chunk in chunks
        if "pharmacy" in query.lower() and "pharmacy" in chunk["text"].lower()
    ][:limit])

    clauses = app._claim_policy_clause_map("claim-demo")
    assert clauses["PHARMACY"].text == "Prescribed pharmacy medicines during hospitalization are payable within the annual limit."
