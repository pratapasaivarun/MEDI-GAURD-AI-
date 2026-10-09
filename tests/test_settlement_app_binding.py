from decimal import Decimal

import app
import uuid
from ui.claim_pages import needs_bill_total_confirmation


class Upload:
    def __init__(self, name, content):
        self.name = name
        self._content = content

    def getvalue(self):
        return self._content


def _run_comparison(monkeypatch, tmp_path, settlement_text, bill_total=Decimal("1000"), with_context=False):
    monkeypatch.setenv("MEDIGUARD_DB_PATH", str(tmp_path / "settlement.db"))
    monkeypatch.setenv("MEDIGUARD_STORAGE_DIR", str(tmp_path / "storage"))
    app.init_db()
    user_id = str(uuid.uuid4())
    with app.db() as conn:
        conn.execute(
            "INSERT INTO users(user_id,email,display_name,role,password_hash,created_at) VALUES(?,?,?,?,?,?)",
            (user_id, "settlement@example.test", "Settlement Test", "claimant", "test-hash", app.utc_now()),
        )
    user = app.get_user(user_id)
    claim_id = app.create_claim(user_id, "CLM-2026-0417", "Ravi Reddy", "Hospital", "POL-558201", "2026-08-10")
    app.save_document(claim_id, user, Upload("settlement.txt", settlement_text.encode("utf-8")), "settlement")
    normalized = {
        "total_amount": {"value": bill_total},
        "patient_name": {"value": "Ravi Reddy"},
        "line_items": [{"description": "Admission fee", "category": "ADMISSION", "amount": bill_total}],
    }
    rules = {
        "status": "approved",
        "covered_amount": Decimal("0"),
        "payable_amount": Decimal("0"),
        "copayment": Decimal("0"),
        "line_item_results": [{"covered_amount": Decimal("0"), "applied_rule": "non_payable"}],
    }
    result = app.run_settlement_comparison(claim_id, user_id, normalized, rules)
    return (*result, (claim_id, user_id, normalized, rules)) if with_context else result


def test_wrong_claim_id_blocks_comparison(monkeypatch, tmp_path):
    result, settlement = _run_comparison(
        monkeypatch, tmp_path,
        "Claim No: CLM-OTHER-1\nBill Total: INR 1,000\nDeductions\nAdmission | INR 1,000\nAmount Paid: INR 0",
    )
    assert result.status == "manual_review"
    assert "CLAIM_ID_MISMATCH" in " ".join(result.review_reasons)


def test_wrong_bill_total_blocks_comparison(monkeypatch, tmp_path):
    result, _ = _run_comparison(
        monkeypatch, tmp_path,
        "Claim No: CLM-2026-0417\nBill Total: INR 1,200\nDeductions\nAdmission | INR 1,200\nAmount Paid: INR 0",
    )
    assert result.status == "manual_review"
    assert "BILL_TOTAL_MISMATCH" in " ".join(result.review_reasons)


def test_missing_settlement_bill_total_blocks_comparison(monkeypatch, tmp_path):
    result, settlement = _run_comparison(
        monkeypatch, tmp_path,
        "Claim No: CLM-2026-0417\nDeductions\nAdmission | INR 1,000\nAmount Paid: INR 0",
    )
    assert settlement.bill_total == Decimal("1000")
    assert result.status == "manual_review"
    assert "SETTLEMENT_TOTAL_FROM_BILL" in " ".join(result.review_reasons)
    assert needs_bill_total_confirmation(settlement)


def test_bill_total_fallback_requires_confirmation_then_comparison_runs(monkeypatch, tmp_path):
    result, settlement, context = _run_comparison(
        monkeypatch, tmp_path,
        "Claim No: CLM-2026-0417\nDeductions\nAdmission | INR 1,000\nAmount Paid: INR 0",
        with_context=True,
    )
    assert settlement.bill_total == Decimal("1000")
    assert "SETTLEMENT_TOTAL_FROM_BILL" in " ".join(settlement.review_reasons)
    assert result.status == "manual_review"

    claim_id, user_id, normalized, rules = context
    confirmed_result, confirmed_settlement = app.run_settlement_comparison(
        claim_id, user_id, normalized, rules, confirm_inferred_bill_total=True,
    )
    assert confirmed_settlement.bill_total == Decimal("1000")
    assert "confirmed by user" in " ".join(confirmed_settlement.review_reasons)
    assert needs_bill_total_confirmation(confirmed_settlement) is False
    assert confirmed_result.status == "no_discrepancy"


def test_missing_claim_id_adds_review_reason(monkeypatch, tmp_path):
    result, settlement = _run_comparison(
        monkeypatch, tmp_path,
        "Bill Total: INR 1,000\nDeductions\nAdmission | INR 1,000\nAmount Paid: INR 0",
    )
    assert settlement.claim_id is None
    assert "CLAIM_ID_MISSING" in " ".join(result.review_reasons)


def test_matching_claim_and_bill_total_comparison_succeeds(monkeypatch, tmp_path):
    result, settlement = _run_comparison(
        monkeypatch, tmp_path,
        "Claim No: clm 2026 0417\nBill Total: INR 1,000\nDeductions\nAdmission | INR 1,000\nAmount Paid: INR 0",
    )
    assert settlement.needs_review is False
    assert result.status == "no_discrepancy"
