from decimal import Decimal
import json
from pathlib import Path
import uuid

import app
from reports import build_comparison_appeal_letter_text


FIXTURE_DIR = Path(__file__).parents[1] / "fixtures" / "settlements"
LAYOUTS = (
    ("pipe_table.txt", Decimal("132000")),
    ("tab_table.txt", Decimal("132000")),
    ("colon_list.txt", Decimal("132000")),
    ("claimed_amount_labels.txt", Decimal("132000")),
    ("no_bill_total.txt", None),
    ("indian_grouping.txt", Decimal("132000")),
)


class Upload:
    def __init__(self, name, content):
        self.name = name
        self._content = content

    def getvalue(self):
        return self._content


def _end_to_end_layout(monkeypatch, tmp_path, filename):
    monkeypatch.setenv("MEDIGUARD_DB_PATH", str(tmp_path / "layout.db"))
    monkeypatch.setenv("MEDIGUARD_STORAGE_DIR", str(tmp_path / "storage"))
    monkeypatch.setattr("settlement._llm_deductions", lambda _text: [])
    monkeypatch.setattr(app, "retrieve_indexed_policy_evidence", lambda query, policy_id, limit=8: [
        {"text": "Clause 3.4: prescribed medicines are covered during hospitalization.", "page": 9, "section": "coverage"}
    ] if "medicine" in query.lower() or "pharmacy" in query.lower() else [])
    reviewed_terms = {
        "annual_limit": {"value": "500000", "confidence": 1},
        "deductible": {"value": "0", "confidence": 1},
        "copay_percent": {"value": "10", "confidence": 1},
        "room_limit_per_day": {"value": "5000", "confidence": 1},
        "non_payable_categories": {"value": ["ADMISSION"], "confidence": 1},
    }
    monkeypatch.setattr(app, "active_policy_for_claim", lambda *_args: {
        "version_id": "fictional-policy-v1", "reviewed_policy_terms_json": json.dumps(reviewed_terms),
        "policy_number": "POL-TEST", "version_label": "Fictional test edition",
    })
    app.init_db()
    user_id = str(uuid.uuid4())
    with app.db() as conn:
        conn.execute(
            "INSERT INTO users(user_id,email,display_name,role,password_hash,created_at) VALUES(?,?,?,?,?,?)",
            (user_id, "layout@example.test", "Fictional Claimant", "claimant", "test-hash", app.utc_now()),
        )
    user = app.get_user(user_id)
    claim_id = app.create_claim(user_id, "CLM-2026-0417", "Fictional Patient", "Fictional Hospital", "POL-TEST", "2026-08-10")
    app.save_document(claim_id, user, Upload(filename, (FIXTURE_DIR / filename).read_bytes()), "settlement")
    normalized = {
        "total_amount": {"value": Decimal("132000")},
        "patient_name": {"value": "Fictional Patient"},
        "admission_date": {"value": "2026-08-10"},
        "discharge_date": {"value": "2026-08-14"},
        "line_items": [
            {"description": "Admission registration", "category": "ADMISSION", "amount": Decimal("2000")},
            {"description": "Room rent", "category": "ROOM", "amount": Decimal("24000")},
            {"description": "Doctor nursing fees", "category": "DOCTOR_NURSING", "amount": Decimal("12000")},
            {"description": "Medicines", "category": "PHARMACY", "amount": Decimal("94000"), "date": "2026-08-12"},
        ],
    }
    rules = {
        "status": "partially_approved", "covered_amount": Decimal("124000"),
        "payable_amount": Decimal("111600"), "copayment": Decimal("12400"),
        "line_item_results": [
            {"covered_amount": Decimal("0"), "applied_rule": "non_payable"},
            {"covered_amount": Decimal("20000"), "applied_rule": "room_limit"},
            {"covered_amount": Decimal("10000"), "applied_rule": "proportionate_deduction"},
            {"covered_amount": Decimal("94000"), "applied_rule": "standard"},
        ],
    }
    claim = {
        "claim_number": "CLM-2026-0417", "patient_name": "Fictional Patient",
        "hospital_name": "Fictional Hospital", "policy_number": "POL-TEST", "stay_dates": "10-14 Aug 2026",
    }
    return app.run_settlement_comparison, claim_id, user_id, normalized, rules, claim


def test_all_six_settlement_layouts_bind_compare_and_gate_letters(monkeypatch, tmp_path):
    for filename, expected_total in LAYOUTS:
        runner, claim_id, user_id, normalized, rules, claim = _end_to_end_layout(monkeypatch, tmp_path / Path(filename).stem, filename)
        if expected_total is None:
            first, proposed = runner(claim_id, user_id, normalized, rules)
            assert proposed.bill_total == Decimal("132000")
            assert "proposed; user confirmation required" in " ".join(proposed.review_reasons)
            assert first.status == "manual_review"
            comparison, settlement = runner(claim_id, user_id, normalized, rules, confirm_inferred_bill_total=True)
        else:
            comparison, settlement = runner(claim_id, user_id, normalized, rules)

        assert settlement.claim_id == "CLM-2026-0417"
        assert settlement.bill_total == Decimal("132000")
        assert comparison.status == "possible_discrepancy", (filename, comparison.review_reasons, comparison.possible_difference, comparison.expected_patient_share, comparison.actual_patient_share, [(row.category, row.status, row.difference, row.payout_effect) for row in comparison.categories])
        assert comparison.possible_difference == Decimal("9000")
        letter = build_comparison_appeal_letter_text(claim, comparison, settlement)
        assert "possible difference is ₹9,000" in letter
        assert "written review" in letter
        if filename in {"pipe_table.txt", "tab_table.txt", "claimed_amount_labels.txt"}:
            assert "all dated entries fall inside the stay" in letter
