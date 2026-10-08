"""Pure comparison between deterministic claim rules and a settlement letter."""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from models import CategoryComparison, ClaimResult, ComparisonResult, PolicyTerms, SettlementData
from category_names import OTHER_CATEGORY, normalize_category

CENT = Decimal("0.01")


def compare(claim: ClaimResult, settlement: SettlementData, terms: PolicyTerms) -> ComparisonResult:
    """Compare insurer deductions with rule-engine disallowances.

    This function performs no I/O and never calls a model. Missing proof or
    unreconciled data yields ``manual_review`` and prevents a discrepancy claim.
    """
    actual_patient = max(Decimal("0"), (settlement.bill_total or Decimal("0")) - settlement.amount_paid)
    expected_patient = claim.patient_share
    possible_difference = actual_patient - expected_patient
    billed_total = settlement.bill_total or Decimal("0")
    expected_insurer = max(Decimal("0"), billed_total - expected_patient)
    if claim.status == "manual_review" or settlement.needs_review or settlement.bill_total is None:
        reasons = list(claim.review_reasons) + list(settlement.review_reasons)
        if settlement.bill_total is None:
            reasons.append("Bill total is required to compare the insurer payment.")
        if claim.status == "manual_review" and not reasons:
            reasons.append("Claim calculation requires confirmation.")
        return ComparisonResult(expected_patient, actual_patient, possible_difference, status="manual_review", review_reasons=reasons, billed_total=billed_total, actual_insurer_payment=settlement.amount_paid, expected_insurer_payment=expected_insurer)

    engine_totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    engine_reasons: dict[str, list[str]] = defaultdict(list)
    clauses = {}
    for row in claim.lines:
        category = normalize_category(row.item.category)
        engine_totals[category] += row.disallowed
        if row.reason_code != "OK":
            engine_reasons[category].append(row.reason_code)
        if row.clause:
            clauses[category] = row.clause
    if claim.copay:
        engine_totals["COPAY"] += claim.copay
    insurer_totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    insurer_reasons: dict[str, list[str]] = defaultdict(list)
    category_review: set[str] = set()
    for row in settlement.deductions:
        category = normalize_category(row.category)
        insurer_totals[category] += row.amount
        if row.reason_text:
            insurer_reasons[category].append(row.reason_text)
        if row.needs_review:
            category_review.add(category)
    if settlement.copay_applied:
        insurer_totals["COPAY"] += settlement.copay_applied

    comparisons: list[CategoryComparison] = []
    discrepancy_total = Decimal("0")
    for category in sorted(set(engine_totals) | set(insurer_totals)):
        engine_amount = engine_totals[category]
        insurer_amount = insurer_totals[category]
        difference = insurer_amount - engine_amount
        clause = clauses.get(category) or terms.clauses.get(category)
        review = category == OTHER_CATEGORY or category in category_review or (difference > 0 and clause is None)
        if review:
            status = "REVIEW"
            payout_effect = Decimal("0")
        elif difference == 0:
            status = "MATCH"
            payout_effect = Decimal("0")
        elif difference < 0:
            status = "UNDER_DEDUCTION"
            payout_effect = Decimal("0")
        else:
            status = "UNEXPLAINED_DEDUCTION" if engine_amount == 0 else "EXCESS_DEDUCTION"
            # A co-pay difference is already a patient-share amount. Applying
            # the co-pay percentage to it again would understate its effect.
            payout_effect = difference.quantize(CENT, rounding=ROUND_HALF_UP) if category == "COPAY" else (difference * (Decimal("1") - terms.copay_percent / Decimal("100"))).quantize(CENT, rounding=ROUND_HALF_UP)
            discrepancy_total += payout_effect
        comparisons.append(CategoryComparison(
            category=category,
            insurer_deducted=insurer_amount,
            engine_disallowed=engine_amount,
            difference=difference,
            status=status,
            insurer_reason="; ".join(insurer_reasons[category]),
            engine_reason="; ".join(engine_reasons[category]) or ("No rule supports a deduction in this category." if engine_amount == 0 else "The policy rule engine supports this disallowance."),
            clause=clause,
            payout_effect=payout_effect,
        ))

    if possible_difference > Decimal("0") and abs(possible_difference - discrepancy_total) > Decimal("1"):
        return ComparisonResult(
            expected_patient, actual_patient, possible_difference, comparisons,
            "manual_review", ["UNRECONCILED_DIFFERENCE: category-level payout effects do not reconcile with the patient-share difference."],
            billed_total, settlement.amount_paid, expected_insurer,
        )
    if any(row.status == "REVIEW" for row in comparisons):
        return ComparisonResult(expected_patient, actual_patient, possible_difference, comparisons, "manual_review", ["One or more comparison categories lack sufficient evidence."], billed_total, settlement.amount_paid, expected_insurer)
    status = "possible_discrepancy" if possible_difference > 0 and any(row.status in {"UNEXPLAINED_DEDUCTION", "EXCESS_DEDUCTION"} for row in comparisons) else "no_discrepancy"
    return ComparisonResult(expected_patient, actual_patient, possible_difference, comparisons, status, [], billed_total, settlement.amount_paid, expected_insurer)
