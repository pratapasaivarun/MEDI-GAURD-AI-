from datetime import date
from decimal import Decimal

import pytest

from rules import PolicyTerms, evaluate_claim


def terms(**overrides):
    values = {"annual_limit": Decimal("500000"), "deductible": Decimal("0"), "copay_percent": Decimal("0"), "proportionate_deduction": False}
    values.update(overrides)
    return PolicyTerms(**values)


def claim(items, policy=None, context=None):
    total = sum((Decimal(str(row["amount"])) for row in items), Decimal("0"))
    return evaluate_claim(total, terms=policy or terms(), line_items=items, claim_context=context or {"room_days": 4, "icu_days": 2})


@pytest.mark.parametrize(("items", "policy", "context", "eligible", "payable", "status"), [
    ([{"description":"Room", "category":"other", "amount":10000}], None, {}, Decimal("10000"), Decimal("10000"), "approved"),
    ([{"description":"Room", "category":"other", "amount":10000}], terms(deductible=Decimal("2000")), {}, Decimal("10000"), Decimal("8000"), "approved"),
    ([{"description":"Room", "category":"other", "amount":10000}], terms(copay_percent=Decimal("10")), {}, Decimal("10000"), Decimal("9000"), "approved"),
    ([{"description":"Room", "category":"other", "amount":10000}], terms(deductible=Decimal("2000"), copay_percent=Decimal("10")), {}, Decimal("10000"), Decimal("7200"), "approved"),
    ([{"description":"Room rent", "category":"ROOM", "amount":20000}], terms(room_limit_per_day=Decimal("5000")), {"room_days":4}, Decimal("20000"), Decimal("20000"), "approved"),
    ([{"description":"Room rent", "category":"ROOM", "amount":24000}], terms(room_limit_per_day=Decimal("5000")), {"room_days":4}, Decimal("20000"), Decimal("20000"), "partially_approved"),
    ([{"description":"ICU stay", "category":"other", "amount":15000, "days":2}], terms(icu_limit_per_day=Decimal("6000")), {"icu_days":2}, Decimal("12000"), Decimal("12000"), "partially_approved"),
    ([{"description":"Cosmetic surgery", "category":"other", "amount":50000}], terms(source={"exclusions":{"value":["cosmetic surgery"]}}), {}, Decimal("0"), Decimal("0"), "partially_approved"),
    ([{"description":"Lab", "category":"investigation", "amount":8000}], terms(sub_limits={"investigation":Decimal("5000")}), {}, Decimal("5000"), Decimal("5000"), "partially_approved"),
    ([{"description":"A", "category":"other", "amount":8000},{"description":"B", "category":"other", "amount":7000}], terms(annual_limit=Decimal("10000")), {}, Decimal("10000"), Decimal("10000"), "partially_approved"),
    ([{"description":"Room", "category":"other", "amount":0}], None, {}, Decimal("0"), Decimal("0"), "manual_review"),
    ([{"description":"Room", "category":"other", "amount":2000}], terms(deductible=Decimal("2000")), {}, Decimal("2000"), Decimal("0"), "approved"),
    ([{"description":"Lab", "category":"investigation", "amount":5000}], terms(sub_limits={"investigation":Decimal("5000")}), {}, Decimal("5000"), Decimal("5000"), "approved"),
    ([{"description":"Pre-hospital lab", "category":"pre_hospitalization", "amount":4000, "date":"2026-08-08"}], terms(pre_hospitalization_days=2), {"admission_date":"2026-08-10","discharge_date":"2026-08-12"}, Decimal("4000"), Decimal("4000"), "approved"),
    ([{"description":"Pre-hospital lab", "category":"pre_hospitalization", "amount":4000, "date":"2026-08-07"}], terms(pre_hospitalization_days=2), {"admission_date":"2026-08-10","discharge_date":"2026-08-12"}, Decimal("0"), Decimal("0"), "partially_approved"),
    ([{"description":"Lab", "category":"investigation", "amount":4000, "date":"2026-08-10"}], None, {"admission_date":"2026-08-10","discharge_date":"2026-08-12"}, Decimal("4000"), Decimal("4000"), "approved"),
    ([{"description":"Room rent", "category":"ROOM", "amount":24000},{"description":"Pharmacy", "category":"PHARMACY", "amount":8000}], terms(room_limit_per_day=Decimal("5000"), deductible=Decimal("3000"), copay_percent=Decimal("10")), {"room_days":4}, Decimal("28000"), Decimal("22500"), "partially_approved"),
])
def test_hand_calculated_rule_golden_cases(items, policy, context, eligible, payable, status):
    result = claim(items, policy, context)
    assert Decimal(str(result["covered_amount"])) == eligible
    assert Decimal(str(result["payable_amount"])) == payable
    assert result["status"] == status


def test_date_window_exact_discharge_edge_is_covered():
    result = claim([{"description":"Post-hospital lab", "category":"post_hospitalization", "amount":4000, "date":"2026-08-14"}], terms(post_hospitalization_days=2), {"admission_date":"2026-08-10","discharge_date":"2026-08-12"})
    assert result["payable_amount"] == 4000


def test_articular_injection_does_not_match_icu():
    from rules import evaluate_line_item
    result = evaluate_line_item({"description":"Articular injection", "category":"other", "amount":2000}, terms())
    assert result["applied_rule"] != "icu_limit_not_stated"
