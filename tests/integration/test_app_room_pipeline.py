import secrets
from decimal import Decimal

from mediguard.services import application as app
from mediguard.ingestion.extraction import Evidence, _extract_line_items
from mediguard.engine.rules import PolicyTerms, evaluate_claim


def test_extracted_room_category_reaches_app_context_and_room_cap(monkeypatch, tmp_path):
    monkeypatch.setenv("MEDIGUARD_DB_PATH", str(tmp_path / "room.db"))
    monkeypatch.setenv("MEDIGUARD_STORAGE_DIR", str(tmp_path / "storage"))
    app.init_db()
    user = app.register_user("room@example.test", "Room Test", secrets.token_urlsafe(24))
    claim_id = app.create_claim(user["user_id"], "CLM-ROOM-1", "Ravi Reddy", "Hospital", "POL-1", "2026-08-10")
    bill_text = "Room rent Rs 24,000, 4 days\nDoctor and nursing Rs 12,000"
    evidence = [Evidence("bill-1", "bill.txt", 1, "text", bill_text, 100.0)]
    line_items = _extract_line_items(bill_text, evidence)
    assert line_items[0]["category"] == "ROOM"

    normalized = {
        "line_items": line_items,
        "admission_date": {"value": "2026-08-10"},
        "discharge_date": {"value": "2026-08-14"},
        "total_amount": {"value": Decimal("36000")},
    }
    context = app._derived_claim_context(claim_id, user["user_id"], normalized)
    result = evaluate_claim(
        Decimal("36000"),
        terms=PolicyTerms(
            annual_limit=Decimal("500000"),
            deductible=Decimal("0"),
            copay_percent=Decimal("0"),
            room_limit_per_day=Decimal("5000"),
        ),
        claim_context=context,
        line_items=line_items,
    )

    assert context["room_charge"] == Decimal("24000")
    assert context["room_days"] == 4
    assert result["line_item_results"][0]["covered_amount"] == 20000
    assert result["line_item_results"][1]["covered_amount"] == 10000
    assert result["line_item_results"][1]["applied_rule"] == "proportionate_deduction"
