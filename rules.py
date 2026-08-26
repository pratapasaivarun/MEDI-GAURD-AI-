"""Deterministic claim coverage rules for the Medi Gaurd MVP."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import Decimal, ROUND_HALF_UP
import re
from typing import Any

RULE_VERSION = "mvp-1.0"
MONEY = Decimal("0.01")


@dataclass
class PolicyTerms:
    # Defaults are retained only for backwards-compatible unit tests. The app
    # passes terms extracted from the active policy edition.
    annual_limit: Decimal | None = Decimal("500000")
    deductible: Decimal | None = Decimal("10000")
    copay_percent: Decimal | None = Decimal("10")
    room_limit_per_day: Decimal | None = Decimal("5000")
    waiting_period_months: int | None = None
    sub_limits: dict[str, Decimal] = field(default_factory=dict)
    source: dict[str, Any] = field(default_factory=dict)


@dataclass
class RuleResult:
    rule_id: str
    rule_version: str
    status: str
    inputs: dict[str, Any]
    calculation: str
    amount: Decimal | None = None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        if self.amount is not None:
            value["amount"] = float(self.amount)
        return value


def money(value: Any) -> Decimal:
    return Decimal(str(value or 0)).quantize(MONEY, rounding=ROUND_HALF_UP)


def evaluate_claim(total_amount: Any, terms: PolicyTerms | None = None, review_fields: list[str] | None = None, missing_fields: list[str] | None = None, policy_terms_missing: list[str] | None = None, claim_context: dict[str, Any] | None = None) -> dict[str, Any]:
    terms = terms or PolicyTerms()
    review_fields = review_fields or []
    missing_fields = missing_fields or []
    policy_terms_missing = policy_terms_missing or []
    claim_context = claim_context or {}
    if policy_terms_missing:
        warnings = ["Required policy terms missing: " + ", ".join(policy_terms_missing)]
        return {"status": "manual_review", "rule_version": RULE_VERSION, "results": [], "covered_amount": 0.0, "deductible": 0.0, "copayment": 0.0, "payable_amount": 0.0, "warnings": warnings, "policy_terms_missing": policy_terms_missing, "policy_terms": terms.source}
    if terms.annual_limit is None or terms.deductible is None or terms.copay_percent is None:
        warnings = ["Annual limit, deductible, and copayment must come from the active policy edition."]
        return {"status": "manual_review", "rule_version": RULE_VERSION, "results": [], "covered_amount": 0.0, "deductible": 0.0, "copayment": 0.0, "payable_amount": 0.0, "warnings": warnings, "policy_terms_missing": ["annual_limit", "deductible", "copay_percent"], "policy_terms": terms.source}
    warnings: list[str] = []
    results: list[RuleResult] = []
    hard_reject = False
    review_required = False
    partial_recommended = False
    raw_net = claim_context.get("net_amount")
    total = money(raw_net if raw_net is not None else total_amount)
    if raw_net is not None:
        warnings.append("net_amount_basis_used")

    if total <= 0:
        results.append(RuleResult("amount_present", RULE_VERSION, "manual_review", {"total_amount": float(total)}, "A positive total amount is required.", warnings=["total_amount_missing_or_invalid"]))
        return {"status": "manual_review", "rule_version": RULE_VERSION, "results": [r.to_dict() for r in results], "covered_amount": 0.0, "deductible": 0.0, "copayment": 0.0, "payable_amount": 0.0, "warnings": ["total_amount_missing_or_invalid"]}

    if missing_fields:
        warnings.append("Missing required fields: " + ", ".join(missing_fields))
    if review_fields:
        warnings.append("Fields require review: " + ", ".join(review_fields))

    covered_before_limit = min(total, terms.annual_limit)
    partial_recommended = total > terms.annual_limit
    results.append(RuleResult("policy_limit", RULE_VERSION, "pass" if total <= terms.annual_limit else "partial", {"billed_amount": float(total), "annual_limit": float(terms.annual_limit)}, f"min({total}, {terms.annual_limit}) = {covered_before_limit}", covered_before_limit, ["annual_limit_exceeded"] if total > terms.annual_limit else []))

    control_warnings: list[str] = []
    if terms.source.get("preauthorization_required", {}).get("value") is True and claim_context.get("preauthorization_obtained") is not True:
        review_required = True
        control_warnings.append("Policy requires pre-authorization confirmation.")
    waiting_violation = terms.waiting_period_months and claim_context.get("waiting_period_satisfied") is False
    if waiting_violation:
        affected_amount = claim_context.get("waiting_period_affected_amount")
        unrelated_amount = claim_context.get("unrelated_eligible_amount")
        if affected_amount is not None and unrelated_amount is not None:
            partial_recommended = True
            covered_before_limit = max(Decimal("0"), covered_before_limit - money(affected_amount))
            warnings.append("waiting_period_affected_condition_excluded")
            results.append(RuleResult("waiting_period", RULE_VERSION, "partial", {"affected_amount": float(money(affected_amount)), "unrelated_eligible_amount": float(money(unrelated_amount))}, "affected condition excluded; unrelated eligible items remain payable", money(affected_amount), ["waiting_period_violation"]))
        else:
            review_required = True
            control_warnings.append(f"Policy waiting period of {terms.waiting_period_months} months requires confirmation for the affected condition.")
    elif terms.waiting_period_months and claim_context.get("waiting_period_satisfied") is not True:
        review_required = True
        control_warnings.append(f"Policy waiting period of {terms.waiting_period_months} months requires confirmation.")

    exclusions = terms.source.get("exclusions", {}).get("value", [])
    diagnosis = str(claim_context.get("diagnosis", "")).lower()
    if exclusions and diagnosis:
        possible = [str(item) for item in exclusions if any(token in diagnosis for token in re.findall(r"[a-z]{4,}", str(item).lower()))]
        if possible:
            match = claim_context.get("exclusion_match") or {}
            if match.get("matched") is True and float(match.get("confidence", 0)) >= 0.90:
                hard_reject = True
                control_warnings.append("Claim diagnosis clearly matches a policy exclusion.")
            else:
                review_required = True
                control_warnings.append("Claim diagnosis may match a policy exclusion; reviewer confirmation is required.")
    if terms.source.get("network_required", {}).get("value") is True:
        in_network = claim_context.get("in_network")
        if in_network is False:
            hard_reject = True
            control_warnings.append("Policy requires a network provider and this provider is out of network.")
        elif in_network is not True:
            review_required = True
            control_warnings.append("Policy requires network-provider confirmation.")
    if claim_context.get("duplicate_suspected") is True:
        review_required = True
        control_warnings.append("Possible duplicate charges require reviewer confirmation; charges were not removed automatically.")
    if claim_context.get("multiple_bills") is True and claim_context.get("aggregation_confirmed") is not True:
        review_required = True
        control_warnings.append("Multiple bills require reviewer confirmation before aggregation.")
    category = str(claim_context.get("coverage_category", "")).strip().lower()
    if category and terms.sub_limits:
        matched_limit = next((limit for name, limit in terms.sub_limits.items() if name.lower() == category), None)
        if matched_limit is not None and covered_before_limit > matched_limit:
            partial_recommended = True
            covered_before_limit = matched_limit
            warnings.append(f"sub_limit_applied:{category}")
            results.append(RuleResult("sub_limit", RULE_VERSION, "partial", {"coverage_category": category, "sub_limit": float(matched_limit)}, f"covered amount capped at {matched_limit}", matched_limit, ["sub_limit_exceeded"]))

    room_charge = claim_context.get("room_charge")
    room_days = claim_context.get("room_days") or 0
    if room_charge is not None and terms.room_limit_per_day is not None and room_days:
        allowed_room = money(terms.room_limit_per_day) * int(room_days)
        room_charge_money = money(room_charge)
        if room_charge_money > allowed_room:
            linked_charges = claim_context.get("room_linked_charges")
            if linked_charges is None:
                review_required = True
                control_warnings.append("Room-limit proportional basis is missing; reviewer confirmation is required.")
            else:
                linked_money = money(linked_charges)
                factor = (allowed_room / room_charge_money) if room_charge_money else Decimal("0")
                linked_reduction = (linked_money * (Decimal("1") - factor)).quantize(MONEY, rounding=ROUND_HALF_UP)
                direct_reduction = room_charge_money - allowed_room
                partial_recommended = True
                covered_before_limit = max(Decimal("0"), covered_before_limit - direct_reduction - linked_reduction)
                warnings.append("room_limit_proportional_applied")
                results.append(RuleResult("room_limit", RULE_VERSION, "partial", {"room_charge": float(room_charge_money), "room_days": int(room_days), "allowed_room_charge": float(allowed_room), "linked_charges": float(linked_money), "proportional_factor": float(factor)}, f"room and linked charges reduced by factor {factor}", direct_reduction + linked_reduction, ["room_limit_exceeded", "proportional_reduction"]))

    deductible = min(terms.deductible, covered_before_limit)
    after_deductible = max(Decimal("0"), covered_before_limit - deductible)
    results.append(RuleResult("deductible", RULE_VERSION, "pass", {"eligible_before_deductible": float(covered_before_limit), "deductible": float(terms.deductible)}, f"{covered_before_limit} - {deductible} = {after_deductible}", deductible))

    copayment = (after_deductible * terms.copay_percent / Decimal("100")).quantize(MONEY, rounding=ROUND_HALF_UP)
    payable = max(Decimal("0"), after_deductible - copayment)
    results.append(RuleResult("copayment", RULE_VERSION, "pass", {"after_deductible": float(after_deductible), "copay_percent": float(terms.copay_percent)}, f"{after_deductible} × {terms.copay_percent}% = {copayment}", copayment))
    results.append(RuleResult("payable_amount", RULE_VERSION, "pass", {"eligible_after_deductible": float(after_deductible), "copayment": float(copayment)}, f"{after_deductible} - {copayment} = {payable}", payable))

    if control_warnings:
        warnings.extend(control_warnings)
    status = "partially_approved" if partial_recommended else "approved"
    if hard_reject:
        status = "rejected"
    elif review_required or missing_fields or review_fields:
        status = "manual_review"
    return {"status": status, "rule_version": RULE_VERSION, "results": [r.to_dict() for r in results], "covered_amount": float(covered_before_limit), "deductible": float(deductible), "copayment": float(copayment), "payable_amount": float(payable), "warnings": warnings, "policy_terms": terms.source}
