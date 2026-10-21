"""End-to-end acceptance tests for the three fictional Phase 4 cases.

The tests follow the app's document ingestion, reviewer confirmation, rules,
and settlement-comparison path. Ollama and persistent vector storage are kept
offline/isolated; retrieval returns the policy fixture's cited sentence.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests

from mediguard.services import application as app
import mediguard.ingestion.extraction as extraction
from mediguard.ai.agents import explain_comparison
from mediguard.reporting.reports import build_comparison_appeal_letter_docx, build_comparison_appeal_letter_pdf


CASES = Path(__file__).parents[2] / "samples" / "demo_cases"


class Upload:
    def __init__(self, name: str, content: bytes):
        self.name = name
        self._content = content

    def getvalue(self) -> bytes:
        return self._content


class DemoOCR:
    """Deterministic OCR stub for the scanned page in the fictional case."""

    def predict(self, _image_path: str):
        return [{
            "rec_texts": [
                "FICTIONAL SAMPLE - CLAIM INVOICE PAGE",
                "Diagnostic lab tests | Qty 1 | Rate 3000 | Amount 3000 | Date 13-Aug-2026",
                "Grand Total: INR 47000",
            ],
            "rec_scores": [0.99, 0.99, 0.99],
        }]


@pytest.fixture
def run_case(monkeypatch, tmp_path):
    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:1")
    monkeypatch.setenv("MEDIGUARD_DB_PATH", str(tmp_path / "demo.db"))
    monkeypatch.setenv("MEDIGUARD_STORAGE_DIR", str(tmp_path / "private"))
    monkeypatch.setenv("MEDIGUARD_TRUSTED_FIXTURES", "false")
    monkeypatch.setenv("MEDIGUARD_DEV_SHOW_LINKS", "false")
    def ollama_off(*_args, **_kwargs):
        raise requests.ConnectionError("Ollama deliberately disabled for Phase 4 tests")
    monkeypatch.setattr(requests, "post", ollama_off)
    monkeypatch.setattr(extraction, "_get_ocr", lambda: DemoOCR())
    ocr_evidence = []
    extract_document = extraction.extract_document
    def tracked_extract_document(*args, **kwargs):
        result = extract_document(*args, **kwargs)
        ocr_evidence.extend(item for item in result[0] if item.method == "tesseract")
        return result
    monkeypatch.setattr(extraction, "extract_document", tracked_extract_document)
    monkeypatch.setattr(app, "index_policy_documents", lambda *_args, **_kwargs: {"chunks_indexed": 1})

    def retrieve(query, _policy_id, limit=8):
        del limit
        q = query.casefold()
        if any(word in q for word in ("lab", "diagnostic", "investigation", "test")):
            return [{"text": "Diagnostic investigations are payable during hospitalization.", "page": 1, "section": "coverage"}]
        if any(word in q for word in ("pharmacy", "medicine", "drug")):
            return [{"text": "Pharmacy and medicines are payable during hospitalization.", "page": 1, "section": "coverage"}]
        if "room" in q:
            return [{"text": "Room charges are limited to INR 5000 per day.", "page": 1, "section": "room_limit"}]
        return []
    monkeypatch.setattr(app, "retrieve_indexed_policy_evidence", retrieve)

    app.init_db()

    def execute(case_name: str):
        case_dir = CASES / case_name
        manifest = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
        user_id = str(uuid.uuid4())
        with app.db() as conn:
            conn.execute(
                "INSERT INTO users(user_id,email,display_name,role,created_at) VALUES(?,?,?,?,?)",
                (user_id, f"{user_id}@fictional.test", "Ananya Sample", "claimant", app.utc_now()),
            )
            reviewer_id = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO users(user_id,email,display_name,role,created_at) VALUES(?,?,?,?,?)",
                (reviewer_id, f"{reviewer_id}@fictional.test", "Fictional Reviewer", "reviewer", app.utc_now()),
            )
        user = app.get_user(user_id)
        claim_id = app.create_claim(user_id, manifest["claim_number"], manifest["patient_name"], manifest["hospital_name"], manifest["policy_number"], "2026-08-10")
        for filename, doc_type in (("bill.pdf", "medical_bill"), ("policy.pdf", "policy"), ("settlement.pdf", "settlement")):
            app.save_document(claim_id, user, Upload(filename, (case_dir / filename).read_bytes()), doc_type)
        normalized = app.process_claim_documents(claim_id, user_id)
        version_id = normalized["active_policy_version_id"]
        provisional_rules = app.evaluate_saved_claim(claim_id, user_id, normalized)
        provisional_comparison, _ = app.run_settlement_comparison(
            claim_id, user_id, normalized, provisional_rules
        )
        app.save_policy_terms_review(
            version_id, reviewer_id,
            {"annual_limit": 500000, "deductible": 10000, "copay_percent": 10, "room_limit_per_day": 5000},
            {"annual_limit": 1, "deductible": 1, "copay_percent": 1, "room_limit_per_day": 1}, {},
        )
        rules = app.evaluate_saved_claim(claim_id, user_id, normalized)
        comparison, settlement = app.run_settlement_comparison(claim_id, user_id, normalized, rules)
        with app.db() as conn:
            claim_row = conn.execute("SELECT * FROM claims WHERE claim_id=?", (claim_id,)).fetchone()
        explanation = explain_comparison(comparison, use_llm=False)
        return (manifest, normalized, rules, comparison, settlement, dict(claim_row),
                explanation, list(ocr_evidence), provisional_rules, provisional_comparison)

    return execute


@pytest.mark.parametrize("case_name", ["a_match", "b_wrongful_deduction", "c_manual_review"])
def test_fictional_demo_case_runs_through_app_pipeline_with_ollama_off(run_case, case_name):
    (manifest, normalized, rules, comparison, settlement, claim, explanation,
     ocr_evidence, provisional_rules, provisional_comparison) = run_case(case_name)
    expected = manifest["expected"]
    assert comparison.status == expected["expected_status"], (rules.get("warnings"), settlement, comparison.review_reasons, comparison.categories)
    assert float(comparison.possible_difference) == pytest.approx(expected["possible_difference"])
    assert app.appeal_draft_available(comparison) is expected["appeal_available"]
    assert provisional_rules["policy_terms_review_status"] == "provisional"
    assert provisional_comparison.status == expected["expected_status"]
    assert provisional_comparison.expected_insurer_payment == comparison.expected_insurer_payment
    assert provisional_comparison.possible_difference == comparison.possible_difference
    assert explanation and "Ollama" not in explanation
    assert normalized["total_amount"]["value"] == expected["bill_total"]
    assert normalized["patient_name"]["value"] == manifest["patient_name"]
    assert normalized["hospital_name"]["value"] == manifest["hospital_name"]
    assert normalized["policy_number"]["value"] == manifest["policy_number"]
    if case_name == "c_manual_review":
        assert any(
            evidence.page == 2 for evidence in ocr_evidence
        )
    assert "FICTIONAL SAMPLE" in (CASES / case_name / "case.json").read_text(encoding="utf-8")
    if expected["supporting_clause_page"]:
        lab = next(row for row in comparison.categories if row.category == "INVESTIGATION")
        assert lab.clause is not None and lab.clause.page == expected["supporting_clause_page"]
    if expected["appeal_available"]:
        pdf = build_comparison_appeal_letter_pdf(claim, comparison, settlement, explanation)
        docx = build_comparison_appeal_letter_docx(claim, comparison, settlement, explanation)
        assert pdf.startswith(b"%PDF")
        assert docx.startswith(b"PK")
    else:
        assert not app.appeal_draft_available(comparison)

