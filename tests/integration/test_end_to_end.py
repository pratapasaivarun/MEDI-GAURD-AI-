from decimal import Decimal
from datetime import date
import re
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests

from mediguard.services import application as app
import mediguard.policy.policy_index as policy_index
from mediguard.reporting.reports import FORBIDDEN_APPEAL_WORDS, build_comparison_appeal_letter_text
from mediguard.engine.category_names import ROOM_CATEGORY, normalize_category


FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "demo_case"


class Upload:
    def __init__(self, name, content):
        self.name = name
        self._content = content

    def getvalue(self):
        return self._content


class InMemoryPolicyCollection:
    def get(self, **_kwargs):
        return {"ids": []}

    def upsert(self, **_kwargs):
        return None


def _run_demo_pipeline(monkeypatch, tmp_path, settlement_bytes, *, include_pharmacy_date=False):
    tmp_path.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("MEDIGUARD_DB_PATH", str(tmp_path / "demo.db"))
    monkeypatch.setenv("MEDIGUARD_STORAGE_DIR", str(tmp_path / "storage"))
    monkeypatch.setenv("MEDIGUARD_TRUSTED_FIXTURES", "true")
    monkeypatch.setenv("MEDIGUARD_DEV_SHOW_LINKS", "false")
    monkeypatch.setattr(requests, "post", lambda *_args, **_kwargs: SimpleNamespace(status_code=503))
    monkeypatch.setattr(policy_index, "_client_and_collection", lambda: InMemoryPolicyCollection())
    monkeypatch.setattr(app, "retrieve_indexed_policy_evidence", lambda query, policy_id, limit=8: [
        {"text": "Clause 3.4: prescribed medicines are covered during hospitalization.", "page": 9, "section": "coverage"}
    ] if "medicine" in query.lower() or "pharmacy" in query.lower() else [])
    app.init_db()
    user_id = str(uuid.uuid4())
    with app.db() as conn:
        conn.execute(
            "INSERT INTO users(user_id,email,display_name,role,created_at) VALUES(?,?,?,?,?)",
            (user_id, "demo@example.test", "Demo Patient", "claimant", app.utc_now()),
        )
    user = app.get_user(user_id)
    claim_id = app.create_claim(user_id, "CLM-2026-0417", "Ravi Reddy", "Fictional Hospital", "POL-558201", "2026-08-10")
    for name, document_type in (("bill.pdf", "medical_bill"), ("policy.pdf", "policy")):
        app.save_document(claim_id, user, Upload(name, (FIXTURE_DIR / name).read_bytes()), document_type)
    settlement_name = "settlement.pdf" if settlement_bytes.startswith(b"%PDF") else "settlement.txt"
    app.save_document(claim_id, user, Upload(settlement_name, settlement_bytes), "settlement")

    normalized = app.process_claim_documents(claim_id, user_id)
    if include_pharmacy_date:
        pharmacy = next(item for item in normalized["line_items"] if item.get("category") == "PHARMACY")
        pharmacy["date"] = "12 Aug 2026"
    rules = app.evaluate_saved_claim(claim_id, user_id, normalized)
    comparison, settlement = app.run_settlement_comparison(claim_id, user_id, normalized, rules)
    claim = {
        "claim_id": claim_id, "user_id": user_id, "claim_number": "CLM-2026-0417", "patient_name": "Ravi Reddy",
        "hospital_name": "Fictional Hospital", "policy_number": "POL-558201", "stay_dates": "10-14 Aug 2026",
    }
    return normalized, rules, comparison, settlement, claim


def test_demo_pdfs_run_through_full_pipeline_and_support_the_letter(monkeypatch, tmp_path):
    normalized, rules, comparison, settlement, claim = _run_demo_pipeline(
        monkeypatch, tmp_path, (FIXTURE_DIR / "settlement.pdf").read_bytes(),
    )
    assert rules["status"] == "partially_approved", {
        "total": normalized.get("total_amount"), "lines": normalized.get("line_items"),
        "review": normalized.get("review_fields"), "missing": normalized.get("missing_fields"),
        "warnings": rules.get("warnings"), "line_sum": sum(Decimal(str(x.get("amount", 0))) for x in normalized.get("line_items", [])),
        "rule_line_warnings": rules.get("line_item_reconciliation_failed"),
    }
    assert Decimal(str(rules["payable_amount"])) == Decimal("111600")
    assert Decimal(str(rules["covered_amount"])) == Decimal("124000")
    room = next(row for row in rules["line_item_results"] if normalize_category(row["category"]) == ROOM_CATEGORY)
    doctor = next(row for row in rules["line_item_results"] if normalize_category(row["category"]) == "DOCTOR_NURSING")
    assert Decimal(str(room["covered_amount"])) == Decimal("20000")
    assert Decimal(str(doctor["covered_amount"])) == Decimal("10000")
    assert comparison.expected_patient_share == Decimal("20400")
    assert comparison.actual_patient_share == Decimal("29400.00")
    assert comparison.expected_insurer_payment == Decimal("111600")
    assert comparison.possible_difference == Decimal("9000")
    # The settlement says the pharmacy deduction is outside the hospitalization
    # window, but the demo bill has no pharmacy dates to verify that assertion.
    # The date-window check therefore requires review and blocks an appeal draft.
    assert comparison.status == "manual_review"
    pharmacy = next(row for row in comparison.categories if row.category == "PHARMACY")
    assert pharmacy.insurer_deducted == Decimal("10000.00")
    assert pharmacy.status == "REVIEW"
    assert pharmacy.review_note == "one or more bill entries are undated or outside the stay"
    assert pharmacy.clause.section == "3.4"
    assert pharmacy.clause.page == 9
    assert normalized["patient_name"]["value"] == "Ravi Reddy"
    assert settlement.amount_paid == Decimal("102600.00")

    assert app.appeal_draft_available(comparison) is False


@pytest.mark.parametrize(
    ("settlement_text", "expected_reason"),
    [
        ("Claim ID: CLM-WRONG-1\nBill Total: INR 132000\nDeductions\nAdmission and registration | INR 2000\nAmount paid: INR 0", "CLAIM_ID_MISMATCH"),
        ("Claim ID: CLM-2026-0417\nBill Total: INR 131000\nDeductions\nAdmission and registration | INR 2000\nAmount paid: INR 0", "BILL_TOTAL_MISMATCH"),
        ("Unreadable fictional settlement document", "SETTLEMENT_TOTAL_MISSING"),
    ],
)
def test_unbound_or_unreadable_settlement_never_enables_a_letter(monkeypatch, tmp_path, settlement_text, expected_reason):
    _normalized, _rules, comparison, settlement, claim = _run_demo_pipeline(
        monkeypatch, tmp_path, settlement_text.encode("utf-8"),
    )
    assert comparison.status == "manual_review"
    assert expected_reason in " ".join(comparison.review_reasons)
    assert app.appeal_draft_available(comparison) is False
    with pytest.raises(ValueError, match="only for a possible discrepancy"):
        build_comparison_appeal_letter_text(claim, comparison, settlement)


def test_app_date_window_lab_deduction_needs_dates_and_a_coverage_clause(monkeypatch, tmp_path):
    settlement_text = """Claim ID: CLM-2026-0417
Bill Total: INR 132000
Deductions:
Admission and registration | 2000 | Non-payable
Room rent | 4000 | Room cap
Doctor and nursing fees | 2000 | Proportionate deduction
Lab tests | 3000 | Outside pre-hospitalization window
Co-pay | 12100
Amount Paid: INR 108900
"""
    normalized, rules, _initial, _settlement, claim = _run_demo_pipeline(
        monkeypatch, tmp_path, settlement_text.encode("utf-8"),
    )

    def retrieve(query, _policy_id, limit=8):
        if "diagnostic" in query.lower() or "lab" in query.lower():
            return [{"text": "Clause 5.2: Lab tests and diagnostic investigations during hospitalization are payable.", "page": 11, "section": "5.2"}]
        if "medicine" in query.lower() or "pharmacy" in query.lower():
            return [{"text": "Clause 3.4: Pharmacy medicines during hospitalization are payable.", "page": 9, "section": "3.4"}]
        return []

    monkeypatch.setattr(app, "retrieve_indexed_policy_evidence", retrieve)
    lab_item = next(item for item in normalized["line_items"] if item.get("category") == "INVESTIGATION")
    lab_item["date"] = "2026-08-12"
    comparison, _ = app.run_settlement_comparison(claim["claim_id"], claim["user_id"], normalized, rules)
    lab = next(row for row in comparison.categories if row.category == "INVESTIGATION")
    assert comparison.status == "possible_discrepancy", (comparison.review_reasons, lab)
    assert lab.review_note == "all dated entries fall inside the stay"
    assert lab.clause is not None and lab.clause.page == 11

    lab_item["date"] = None
    undated, _ = app.run_settlement_comparison(claim["claim_id"], claim["user_id"], normalized, rules)
    undated_lab = next(row for row in undated.categories if row.category == "INVESTIGATION")
    assert undated.status == "manual_review"
    assert undated_lab.status == "REVIEW"
