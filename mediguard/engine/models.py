"""Typed data contracts for the mini prototype pipeline.

Financial fields use :class:`Decimal` throughout. Formatting and serialization
to display strings belong at the application boundary.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Literal


@dataclass
class LineItem:
    description: str
    category: str
    amount: Decimal
    date: date | None = None
    source: Literal["rule", "llm", "user"] = "rule"
    needs_review: bool = False


@dataclass
class BillData:
    patient_name: str
    policy_number: str | None
    admission_date: date | None
    discharge_date: date | None
    room_days: int | None
    total_amount: Decimal
    line_items: list[LineItem] = field(default_factory=list)
    field_flags: dict[str, bool] = field(default_factory=dict)


@dataclass
class Clause:
    text: str
    page: int
    section: str | None = None


@dataclass
class PolicyTerms:
    sum_insured: Decimal
    room_rent_cap_per_day: Decimal | None = None
    copay_percent: Decimal = Decimal("0")
    non_payable_categories: list[str] = field(default_factory=list)
    exclusions: list[str] = field(default_factory=list)
    clauses: dict[str, Clause] = field(default_factory=dict)
    proportionate_deduction: bool = True
    icu_limit_per_day: Decimal | None = None
    deductible: Decimal = Decimal("0")


@dataclass
class LineResult:
    item: LineItem
    allowed: Decimal
    disallowed: Decimal
    reason_code: str
    clause: Clause | None = None


@dataclass
class ClaimResult:
    lines: list[LineResult]
    eligible_total: Decimal
    copay: Decimal
    patient_share: Decimal
    insurer_share: Decimal
    status: Literal["computed", "manual_review"]
    deductible: Decimal = Decimal("0")
    review_reasons: list[str] = field(default_factory=list)
    admission_date: date | None = None
    discharge_date: date | None = None


@dataclass
class SettlementDeduction:
    category: str
    amount: Decimal
    reason_text: str
    needs_review: bool = False


@dataclass
class SettlementData:
    claim_id: str | None
    amount_paid: Decimal | None
    deductions: list[SettlementDeduction] = field(default_factory=list)
    copay_applied: Decimal | None = None
    needs_review: bool = False
    review_reasons: list[str] = field(default_factory=list)
    bill_total: Decimal | None = None


@dataclass
class CategoryComparison:
    category: str
    insurer_deducted: Decimal
    engine_disallowed: Decimal
    difference: Decimal
    status: Literal[
        "MATCH", "UNEXPLAINED_DEDUCTION", "EXCESS_DEDUCTION",
        "UNDER_DEDUCTION", "REVIEW",
    ]
    insurer_reason: str
    engine_reason: str
    clause: Clause | None
    payout_effect: Decimal
    review_note: str | None = None


@dataclass
class ComparisonResult:
    expected_patient_share: Decimal
    actual_patient_share: Decimal
    possible_difference: Decimal
    categories: list[CategoryComparison] = field(default_factory=list)
    status: Literal["no_discrepancy", "possible_discrepancy", "manual_review"] = "manual_review"
    review_reasons: list[str] = field(default_factory=list)
    billed_total: Decimal = Decimal("0")
    actual_insurer_payment: Decimal | None = Decimal("0")
    expected_insurer_payment: Decimal = Decimal("0")
