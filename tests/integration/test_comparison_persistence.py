from decimal import Decimal
import uuid

from mediguard.services import application as app


class Upload:
    def __init__(self, name, content):
        self.name = name
        self._content = content

    def getvalue(self):
        return self._content


def test_comparison_reloads_from_database_after_session_state_is_empty(monkeypatch, tmp_path):
    monkeypatch.setenv("MEDIGUARD_DB_PATH", str(tmp_path / "persist.db"))
    monkeypatch.setenv("MEDIGUARD_STORAGE_DIR", str(tmp_path / "storage"))
    app.init_db()
    user_id = str(uuid.uuid4())
    with app.db() as conn:
        conn.execute(
            "INSERT INTO users(user_id,email,display_name,role,created_at) VALUES(?,?,?,?,?)",
            (user_id, "persist@example.test", "Persist Test", "claimant", app.utc_now()),
        )
    user = app.get_user(user_id)
    claim_id = app.create_claim(user_id, "CLM-PERSIST", "Ravi Reddy", "Hospital", "POL-1", "2026-08-10")
    app.save_document(
        claim_id, user,
        Upload("settlement.txt", b"Claim No: CLM-PERSIST\nBill Total: INR 1,000\nDeductions\nAdmission | INR 1,000\nAmount Paid: INR 0"),
        "settlement",
    )
    normalized = {
        "total_amount": {"value": Decimal("1000")},
        "patient_name": {"value": "Ravi Reddy"},
        "line_items": [{"description": "Admission fee", "category": "ADMISSION", "amount": Decimal("1000")}],
    }
    rules = {
        "status": "approved", "covered_amount": Decimal("0"), "payable_amount": Decimal("0"),
        "copayment": Decimal("0"), "line_item_results": [{"covered_amount": Decimal("0"), "applied_rule": "non_payable"}],
    }
    result, settlement = app.run_settlement_comparison(claim_id, user_id, normalized, rules)
    assert result.actual_patient_share == Decimal("1000.00")
    with app.db() as conn:
        saved_row = conn.execute(
            "SELECT settlement_document_sha256,comparison_json,settlement_json FROM settlement_comparisons WHERE claim_id=?",
            (claim_id,),
        ).fetchone()
    assert saved_row is not None
    assert '"actual_patient_share": "1000.00"' in saved_row["comparison_json"]

    session_state = {}
    loaded_result, loaded_settlement = app.get_comparison_for_view(claim_id, user, session_state)

    assert session_state[f"comparison_{claim_id}"].possible_difference == Decimal("0.00")
    assert loaded_result.expected_patient_share == result.expected_patient_share
    assert loaded_result.actual_patient_share == result.actual_patient_share
    assert loaded_result.possible_difference == result.possible_difference
    assert loaded_result.status == result.status
    assert loaded_settlement.amount_paid == settlement.amount_paid
    assert loaded_settlement.bill_total == settlement.bill_total
