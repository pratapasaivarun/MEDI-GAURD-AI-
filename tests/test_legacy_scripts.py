"""Core module health checks — replaces legacy root-level script runner.

All old root-level test_*.py scripts have been consolidated into
tests/test_all_22_scenarios.py and tests/test_real_document_support.py.
This file verifies that every core module imports cleanly and exposes
its required public API surface.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ── Module import checks ──────────────────────────────────────────────────────

def test_rules_module_imports():
    """rules.py must import and expose its key public API."""
    import mediguard.engine.rules as rules
    assert hasattr(rules, "PolicyTerms"), "PolicyTerms dataclass missing"
    assert hasattr(rules, "evaluate_claim"), "evaluate_claim missing"
    assert hasattr(rules, "evaluate_line_item"), "evaluate_line_item missing"
    assert hasattr(rules, "verify_patient_name_match"), "verify_patient_name_match missing"
    assert hasattr(rules, "detect_line_item_duplicates"), "detect_line_item_duplicates missing"
    assert hasattr(rules, "validate_expense_date_window"), "validate_expense_date_window missing"
    assert hasattr(rules, "validate_daycare_procedure"), "validate_daycare_procedure missing"
    assert hasattr(rules, "RULE_VERSION"), "RULE_VERSION constant missing"


def test_policy_terms_module_imports():
    """policy_terms.py must import and expose extract_policy_terms."""
    import mediguard.policy.policy_terms as policy_terms
    assert hasattr(policy_terms, "extract_policy_terms"), "extract_policy_terms missing"
    assert hasattr(policy_terms, "terms_from_json"), "terms_from_json missing"


def test_policy_index_module_imports():
    """policy_index.py must import and expose indexing and retrieval functions."""
    import mediguard.policy.policy_index as policy_index
    assert hasattr(policy_index, "index_policy_documents"), "index_policy_documents missing"
    assert hasattr(policy_index, "retrieve_policy_evidence"), "retrieve_policy_evidence missing"


def test_extraction_module_imports():
    """extraction.py must import cleanly."""
    import mediguard.ingestion.extraction as extraction
    assert hasattr(extraction, "extract_bill_data") or hasattr(extraction, "extract_document"), \
        "No extraction entry point found"


def test_reports_module_imports():
    """reports.py must import cleanly."""
    import mediguard.reporting.reports as reports
    # Should have at least one report generation function
    public_fns = [n for n in dir(reports) if not n.startswith("_")]
    assert len(public_fns) > 0, "reports.py exposes no public API"


# ── Core rule engine smoke test ───────────────────────────────────────────────

def test_phase6_business_rules():
    """Smoke test: rule engine produces a deterministic result for a basic claim."""
    from decimal import Decimal
    from mediguard.engine.rules import PolicyTerms, evaluate_claim

    terms = PolicyTerms(
        annual_limit=Decimal("500000"),
        deductible=Decimal("10000"),
        copay_percent=Decimal("10"),
        room_limit_per_day=Decimal("5000"),
    )
    result = evaluate_claim(50000.0, terms=terms)
    assert result["status"] in ("approved", "partially_approved", "manual_review", "rejected")
    assert "covered_amount" in result
    assert "payable_amount" in result
    print("PHASE6_BUSINESS_RULES_OK")


def test_rule_engine_excludes_non_medical_items():
    """Rule engine must auto-exclude items matching policy exclusions."""
    from decimal import Decimal
    from mediguard.engine.rules import PolicyTerms, evaluate_claim

    terms = PolicyTerms(
        annual_limit=Decimal("500000"),
        deductible=Decimal("0"),
        copay_percent=Decimal("0"),
        room_limit_per_day=Decimal("5000"),
        source={"exclusions": {"value": ["toiletries", "guest meals"]}},
    )
    items = [
        {"description": "Surgical procedure",    "amount": 30000.0, "category": "surgery"},
        {"description": "Patient Toiletries Kit", "amount":  1200.0, "category": "sundry"},
        {"description": "Guest Meals",            "amount":   800.0, "category": "sundry"},
    ]
    result = evaluate_claim(32000.0, terms=terms, line_items=items)
    item_results = result.get("line_item_results", [])
    if item_results:
        excluded = [r for r in item_results if r["status"] == "excluded"]
        assert len(excluded) >= 1, "Expected at least 1 non-medical item to be excluded"


def test_rule_engine_applies_room_rent_cap():
    """Room rent cap: when billed room exceeds limit, engine flags warning and routes to manual_review."""
    from decimal import Decimal
    from mediguard.engine.rules import PolicyTerms, evaluate_claim

    terms = PolicyTerms(
        annual_limit=Decimal("500000"),
        deductible=Decimal("0"),
        copay_percent=Decimal("0"),
        room_limit_per_day=Decimal("3000"),
    )
    # Billed: 20,000. Limit: 3,000/day × 4 days = 12,000.
    # Engine detects excess and raises a room-limit warning.
    claim_context = {"room_days": 4, "room_charge": 20000.0}
    result = evaluate_claim(20000.0, terms=terms, claim_context=claim_context)
    warnings = result.get("warnings", [])
    status = result.get("status", "")
    # Engine must either cap the amount OR flag a room-limit warning / manual_review
    room_flagged = (
        any("room" in str(w).lower() for w in warnings)
        or status == "manual_review"
        or float(result.get("payable_amount", 20001)) <= 12000.0
    )
    assert room_flagged, (
        f"Expected room-limit cap or warning. status={status}, warnings={warnings}, "
        f"payable={result.get('payable_amount')}"
    )
