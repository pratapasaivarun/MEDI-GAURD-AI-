from decimal import Decimal
import re
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests

import app
import policy_index
from reports import FORBIDDEN_APPEAL_WORDS, build_comparison_appeal_letter_text


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "demo_case"


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


def _run_demo_pipeline(monkeypatch, tmp_path, settlement_bytes):
    monkeypatch.setenv("MEDIGUARD_DB_PATH", str(tmp_path / "demo.db"))
    monkeypatch.setenv("MEDIGUARD_STORAGE_DIR", str(tmp_path / "storage"))
    monkeypatch.setenv("MEDIGUARD_TRUSTED_FIXTURES", "true")
    monkeypatch.setenv("MEDIGUARD_DEV_SHOW_LINKS", "false")
    monkeypatch.setattr(requests, "post", lambda *_args, **_kwargs: SimpleNamespace(status_code=503))
    monkeypatch.setattr(policy_index, "_client_and_collection", lambda: InMemoryPolicyCollection())
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
    rules = app.evaluate_saved_claim(claim_id, user_id, normalized)
    comparison, settlement = app.run_settlement_comparison(claim_id, user_id, normalized, rules)
    claim = {
        "claim_id": claim_id, "claim_number": "CLM-2026-0417", "patient_name": "Ravi Reddy",
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
    room = next(row for row in rules["line_item_results"] if row["category"] == "room")
    doctor = next(row for row in rules["line_item_results"] if row["category"] == "doctor_nursing")
    assert Decimal(str(room["covered_amount"])) == Decimal("20000")
    assert Decimal(str(doctor["covered_amount"])) == Decimal("10000")
    assert comparison.expected_patient_share == Decimal("20400")
    assert comparison.actual_patient_share == Decimal("29400.00")
    assert comparison.expected_insurer_payment == Decimal("111600")
    assert comparison.possible_difference == Decimal("9000")
    assert comparison.status == "possible_discrepancy"
    unexplained = [row for row in comparison.categories if row.status == "UNEXPLAINED_DEDUCTION"]
    assert len(unexplained) == 1
    assert unexplained[0].category == "PHARMACY"
    pharmacy = next(row for row in comparison.categories if row.category == "PHARMACY")
    assert pharmacy.insurer_deducted == Decimal("10000.00")
    assert pharmacy.payout_effect == Decimal("9000.00")
    assert pharmacy.clause.section == "3.4"
    assert pharmacy.clause.page == 9
    assert normalized["patient_name"]["value"] == "Ravi Reddy"
    assert settlement.amount_paid == Decimal("102600.00")

    letter = build_comparison_appeal_letter_text(claim, comparison, settlement)
    for required in ("₹1,32,000", "₹1,02,600", "₹1,11,600", "₹9,000", "₹10,000"):
        assert required in letter
    assert not any(word in letter.lower() for word in FORBIDDEN_APPEAL_WORDS)
    comparison_figures = {
        comparison.billed_total, comparison.actual_insurer_payment, comparison.expected_insurer_payment,
        comparison.possible_difference, comparison.expected_patient_share,
        *(row.insurer_deducted for row in comparison.categories),
        *(row.engine_disallowed for row in comparison.categories),
        *(row.payout_effect for row in comparison.categories),
    }
    letter_figures = {Decimal(value.replace(",", "")) for value in re.findall(r"(?:INR\s+|₹)\s*([0-9,]+(?:\.[0-9]{2})?)", letter)}
    assert letter_figures <= comparison_figures


@pytest.mark.parametrize(
    ("settlement_text", "expected_reason"),
    [
        ("Claim ID: CLM-WRONG\nBill Total: INR 132000\nDeductions\nAdmission and registration | INR 2000\nAmount paid: INR 0", "CLAIM_ID_MISMATCH"),
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
