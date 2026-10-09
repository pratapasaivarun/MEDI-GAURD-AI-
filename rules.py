"""Deterministic claim rules.

Calculation order: non-payable categories, room cap, proportionate reduction,
exclusions and other item rules, sum-insured limit, deductible, then co-pay.
The LLM is not used by this module.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import Decimal, ROUND_HALF_UP
import re
from typing import Any

from models import (
    BillData,
    ClaimResult,
    LineItem as TypedLineItem,
    LineResult as TypedLineResult,
    PolicyTerms as TypedPolicyTerms,
)
from category_names import (
    ROOM_CATEGORY, ROOM_RENT_CATEGORY, ACCOMMODATION_CATEGORY,
    DOCTOR_NURSING_CATEGORY, NURSING_CATEGORY, DOCTOR_CATEGORY,
    CONSULTATION_CATEGORY, normalize_category,
)

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
    icu_limit_per_day: Decimal | None = None
    pre_hospitalization_days: int | None = None
    post_hospitalization_days: int | None = None
    daycare_procedures: list[str] = field(default_factory=list)
    previous_claims_total: Decimal | None = None
    waiting_period_months: int | None = None
    sub_limits: dict[str, Decimal] = field(default_factory=dict)
    source: dict[str, Any] = field(default_factory=dict)
    proportionate_deduction: bool = True


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


def verify_patient_name_match(bill_name: str | None, policy_name: str | None) -> dict[str, Any]:
    """Verify identity consistency between bill patient name and policy holder name."""
    if not bill_name or not policy_name:
        return {"result": "MISSING", "status": "manual_review", "warning": "Patient name missing on bill or policy; reviewer confirmation required."}
    
    b_clean = re.sub(r"^(mr|mrs|ms|dr|master|sri|smt)\b\.?\s*", "", str(bill_name).strip(), flags=re.IGNORECASE)
    p_clean = re.sub(r"^(mr|mrs|ms|dr|master|sri|smt)\b\.?\s*", "", str(policy_name).strip(), flags=re.IGNORECASE)
    
    b_norm = re.sub(r"\s+", " ", re.sub(r"[^\w\s]", "", b_clean).upper()).strip()
    p_norm = re.sub(r"\s+", " ", re.sub(r"[^\w\s]", "", p_clean).upper()).strip()
    
    b_tokens = b_norm.split()
    p_tokens = p_norm.split()
    
    if not b_tokens or not p_tokens:
        return {"result": "MISSING", "status": "manual_review", "warning": "Patient name missing or invalid after normalization."}
        
    if b_norm == p_norm:
        return {"result": "MATCH", "status": "approved", "warning": None}
    # Indian claim documents commonly abbreviate given or middle names. The
    # surname must remain an exact match; short-token edit-distance matches are
    # never accepted.
    if b_tokens[-1] == p_tokens[-1] and len(b_tokens) == len(p_tokens):
        token_matches = all(
            left == right
            or (len(left) == 1 and right.startswith(left))
            or (len(right) == 1 and left.startswith(right))
            for left, right in zip(b_tokens[:-1], p_tokens[:-1])
        )
        if token_matches:
            return {"result": "MINOR_VARIATION", "status": "approved", "warning": None}
            
    return {
        "result": "MISMATCH",
        "status": "manual_review",
        "warning": f"Patient name on bill ('{bill_name}') does not match policy holder ('{policy_name}'); reviewer confirmation required."
    }


def parse_date_flexible(date_str: Any) -> Any:
    if not date_str:
        return None
    from datetime import datetime
    clean = str(date_str).strip()
    for fmt in ("%Y-%m-%d", "%d-%b-%Y", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d", "%d %b %Y"):
        try:
            return datetime.strptime(clean, fmt).date()
        except ValueError:
            pass
    return None


def validate_expense_date_window(expense_date_str: Any, admission_date_str: Any, discharge_date_str: Any, pre_days: int | None, post_days: int | None, category: str = "") -> dict[str, Any]:
    exp_date = parse_date_flexible(expense_date_str)
    adm_date = parse_date_flexible(admission_date_str)
    dis_date = parse_date_flexible(discharge_date_str)
    
    if not exp_date or not adm_date or not dis_date:
        return {"valid": False, "status": "needs_review", "rule": "pre_post_window", "notice": "Expense or admission/discharge dates missing/ambiguous; requires reviewer verification."}
    
    from datetime import timedelta
    cat_lower = str(category).lower()
    
    is_pre = "pre" in cat_lower or exp_date < adm_date
    is_post = "post" in cat_lower or exp_date > dis_date
    
    if is_pre and pre_days is not None:
        min_pre_date = adm_date - timedelta(days=pre_days)
        if min_pre_date <= exp_date <= adm_date:
            return {"valid": True, "status": "covered", "rule": "pre_hospitalization", "notice": f"Expense date ({exp_date}) is within the {pre_days}-day pre-hospitalization window."}
        else:
            return {"valid": False, "status": "excluded", "rule": "pre_hospitalization", "notice": f"Expense date ({exp_date}) is outside the {pre_days}-day pre-hospitalization window (admission: {adm_date})."}
            
    if is_post and post_days is not None:
        max_post_date = dis_date + timedelta(days=post_days)
        if dis_date <= exp_date <= max_post_date:
            return {"valid": True, "status": "covered", "rule": "post_hospitalization", "notice": f"Expense date ({exp_date}) is within the {post_days}-day post-hospitalization window."}
        else:
            return {"valid": False, "status": "excluded", "rule": "post_hospitalization", "notice": f"Expense date ({exp_date}) is outside the {post_days}-day post-hospitalization window (discharge: {dis_date})."}
            
    return {"valid": True, "status": "covered", "rule": "hospitalization_period", "notice": "Expense date is within standard hospitalization period."}


def detect_line_item_duplicates(line_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen_exact: dict[tuple, int] = {}
    results = []
    
    for idx, item in enumerate(line_items):
        if item.get("allow_duplicate") or item.get("legitimate_repeat"):
            results.append({"index": idx, "duplicate": False, "certainty": "legitimate", "notice": None})
            continue
            
        desc = re.sub(r"[^\w\s]", "", str(item.get("description") or "").lower()).strip()
        amt = money(item.get("amount"))
        date = str(item.get("date") or item.get("expense_date") or "").strip()
        qty = item.get("quantity") or 1
        
        key = (desc, amt, date, qty)
        if key in seen_exact and amt > 0:
            results.append({
                "index": idx,
                "duplicate": True,
                "certainty": "high",
                "notice": f"Exact duplicate line item detected (matches item #{seen_exact[key] + 1})."
            })
        else:
            if amt > 0 and desc:
                seen_exact[key] = idx
            results.append({"index": idx, "duplicate": False, "certainty": "none", "notice": None})
            
    return results


def validate_daycare_procedure(procedure_name: str | None, Whitelist: list[str], length_of_stay_nights: int = 0) -> dict[str, Any]:
    if length_of_stay_nights > 0:
        return {"valid": True, "status": "covered", "notice": "Inpatient hospitalization (> 24h stay); daycare whitelist check not required."}
    
    if not procedure_name or not Whitelist:
        return {"valid": False, "status": "manual_review", "notice": "Daycare procedure or policy whitelist unconfirmed; reviewer verification required."}
        
    p_norm = re.sub(r"[^\w\s]", "", str(procedure_name).lower()).strip()
    
    for item in Whitelist:
        w_norm = re.sub(r"[^\w\s]", "", str(item).lower()).strip()
        if p_norm == w_norm or w_norm in p_norm or p_norm in w_norm:
            return {"valid": True, "status": "covered", "notice": f"Procedure '{procedure_name}' is covered under Daycare Policy Whitelist."}
            
    return {"valid": False, "status": "excluded", "notice": f"Procedure '{procedure_name}' is not listed in the policy daycare whitelist for 0-night stays."}


def _item_matches_exclusion(item: dict[str, Any], terms: PolicyTerms, claim_context: dict[str, Any]) -> tuple[bool, bool]:
    """Return (confirmed, possible) for a policy exclusion scoped to one item."""
    exclusions = terms.source.get("exclusions", {}).get("value", [])
    if not exclusions:
        return False, False
    item_text = " ".join(str(item.get(key, "")) for key in ("description", "category", "diagnosis")).lower()
    item_tokens = set(re.findall(r"[a-z0-9]{3,}", item_text))
    item_explicit = item.get("exclusion_match") or {}
    claim_explicit = claim_context.get("exclusion_match") or {}
    for exclusion in exclusions:
        ex_clean = str(exclusion).lower().strip()
        if not ex_clean:
            continue
        if ex_clean in item_text:
            return True, False
        tokens = set(re.findall(r"[a-z0-9]{3,}", ex_clean))
        if tokens and tokens.issubset(item_tokens):
            return True, False
        # Fuzzy exclusion signals are never converted into a financial denial.
        # Diagnosis-level matches are routed to reviewer confirmation upstream.
    return False, False


def evaluate_line_item(item: dict, terms: PolicyTerms, claim_context: dict | None = None) -> dict:
    """Evaluate one extracted bill item before claim-level cost sharing.

    The returned amount is the item amount eligible for coverage. Deductible and
    copayment are intentionally not applied here because they apply once to the
    combined claim total.
    """
    claim_context = claim_context or {}
    amount = money(item.get("amount"))
    category = str(item.get("category") or "").strip().lower()
    description = str(item.get("description") or "Unspecified item")
    desc_lower = description.lower()

    result = {
        "description": description,
        "category": category or "uncategorized",
        "amount": float(amount),
        "status": "covered",
        "covered_amount": float(amount),
        "applied_rule": "standard",
        "calculation": f"INR {amount} is eligible before claim-level deductible and copayment.",
    }
    if amount <= 0:
        return {**result, "status": "needs_review", "covered_amount": 0.0, "applied_rule": "amount_validation", "calculation": "A positive line-item amount is required."}
    if item.get("needs_review"):
        return {**result, "status": "needs_review", "applied_rule": "extraction_review", "calculation": "The extracted line item requires reviewer confirmation."}

    confirmed_exclusion, possible_exclusion = _item_matches_exclusion(item, terms, claim_context)
    if confirmed_exclusion:
        return {**result, "status": "excluded", "covered_amount": 0.0, "applied_rule": "exclusion", "calculation": "This item matches a confirmed policy exclusion."}
    if possible_exclusion:
        return {**result, "status": "needs_review", "applied_rule": "exclusion", "calculation": "This item may match a policy exclusion and requires reviewer confirmation."}

    # ICU Limit Check
    is_icu = category == "icu" or "icu" in desc_lower or "intensive care" in desc_lower
    if is_icu:
        icu_limit = terms.icu_limit_per_day or terms.sub_limits.get("icu")
        if claim_context.get("icu_limit_uncertain") is True or (icu_limit is None and claim_context.get("has_icu_stay") is True):
            return {**result, "status": "needs_review", "applied_rule": "icu_limit", "calculation": "ICU limit information is unavailable or ambiguous; requires reviewer confirmation."}
        if icu_limit is not None:
            days = item.get("days") or item.get("quantity") or claim_context.get("icu_days") or 1
            allowed_icu = money(icu_limit) * int(days)
            if amount > allowed_icu:
                return {
                    **result,
                    "status": "partial",
                    "covered_amount": float(allowed_icu),
                    "applied_rule": "icu_limit",
                    "calculation": f"INR {amount} billed ICU charge capped at daily limit of INR {icu_limit} x {days} day(s) = INR {allowed_icu}.",
                }

    # Pre / Post Hospitalization Window Validation
    item_date = item.get("date") or item.get("expense_date")
    if (terms.pre_hospitalization_days is not None or terms.post_hospitalization_days is not None or "pre" in category or "post" in category) and item_date:
        window_res = validate_expense_date_window(
            expense_date_str=item_date,
            admission_date_str=claim_context.get("admission_date"),
            discharge_date_str=claim_context.get("discharge_date"),
            pre_days=terms.pre_hospitalization_days,
            post_days=terms.post_hospitalization_days,
            category=category or desc_lower,
        )
        if window_res["status"] == "excluded":
            return {**result, "status": "excluded", "covered_amount": 0.0, "applied_rule": window_res["rule"], "calculation": window_res["notice"]}
        elif window_res["status"] == "needs_review":
            return {**result, "status": "needs_review", "applied_rule": window_res["rule"], "calculation": window_res["notice"]}

    # Waiting Period Validation
    if terms.waiting_period_months and claim_context.get("waiting_period_satisfied") is False:
        affected_amount = claim_context.get("_waiting_period_amount_for_item")
        if affected_amount is None:
            affected_categories = {str(value).lower() for value in claim_context.get("waiting_period_affected_categories", [])}
            applies = bool(claim_context.get("waiting_period_applies")) or (category and category in affected_categories)
            if not applies:
                return {**result, "status": "needs_review", "applied_rule": "waiting_period", "calculation": f"The {terms.waiting_period_months}-month waiting period needs item-level confirmation."}
            affected_amount = amount
        affected = min(amount, money(affected_amount))
        eligible = amount - affected
        if affected >= amount:
            return {**result, "status": "excluded", "covered_amount": 0.0, "applied_rule": "waiting_period", "calculation": "This item is within an unsatisfied waiting period."}
        return {**result, "status": "partial", "covered_amount": float(eligible), "applied_rule": "waiting_period", "calculation": f"INR {affected} is excluded by the waiting period; INR {eligible} remains eligible."}
    if terms.waiting_period_months and claim_context.get("waiting_period_satisfied") is not True:
        return {**result, "status": "needs_review", "applied_rule": "waiting_period", "calculation": f"The {terms.waiting_period_months}-month waiting period needs confirmation."}

    # Category Sub-Limits Validation
    matched_limit = next((limit for name, limit in terms.sub_limits.items() if name.lower() == category), None)
    if category == "icu" and (terms.icu_limit_per_day or terms.sub_limits.get("icu")) is not None:
        matched_limit = None  # ICU limits are daily and were applied with the ICU stay length above.
    if matched_limit is not None:
        remaining = money(claim_context.get("_sub_limit_remaining", matched_limit))
        eligible = min(amount, max(Decimal("0"), remaining))
        if eligible < amount:
            return {**result, "status": "partial", "covered_amount": float(eligible), "applied_rule": "sub_limit", "calculation": f"INR {amount} is capped at the remaining {category} sub-limit of INR {eligible}."}
    return result


def evaluate_claim(
    total_amount: Any,
    terms: PolicyTerms | None = None,
    review_fields: list[str] | None = None,
    missing_fields: list[str] | None = None,
    policy_terms_missing: list[str] | None = None,
    claim_context: dict[str, Any] | None = None,
    line_items: list[dict] | None = None,
) -> dict[str, Any] | ClaimResult:
    """Evaluate a claim through one item-based calculation path.

    Aggregate-only claims become a single synthetic ``OTHER`` item. Itemized
    totals must reconcile within 1%; duplicates remain included and are flagged
    for reviewer confirmation. Every amount is computed with ``Decimal`` and
    converted only in this legacy dictionary response for JSON compatibility.
    """
    if isinstance(total_amount, BillData):
        bill = total_amount
        typed_terms = terms
        if not isinstance(typed_terms, TypedPolicyTerms):
            raise TypeError("BillData evaluation requires models.PolicyTerms.")
        source = {
            "exclusions": {"value": list(typed_terms.exclusions)},
            "non_payable_categories": {"value": list(typed_terms.non_payable_categories)},
        }
        legacy_terms = PolicyTerms(
            annual_limit=typed_terms.sum_insured,
            deductible=Decimal("0"),
            copay_percent=typed_terms.copay_percent,
            room_limit_per_day=typed_terms.room_rent_cap_per_day,
            icu_limit_per_day=typed_terms.icu_limit_per_day,
            source=source,
            proportionate_deduction=typed_terms.proportionate_deduction,
        )
        context = dict(claim_context or {})
        context.setdefault("room_days", bill.room_days)
        context.setdefault("icu_days", bill.room_days)
        typed_items = list(bill.line_items) or [TypedLineItem("Claim total", "OTHER", bill.total_amount, source="user")]
        for field_name, needs_review in bill.field_flags.items():
            if needs_review:
                review_fields = [*(review_fields or []), field_name]
        output = evaluate_claim(
            bill.total_amount,
            terms=legacy_terms,
            review_fields=review_fields,
            missing_fields=missing_fields,
            claim_context=context,
            line_items=[
                {
                    "description": item.description,
                    "category": item.category,
                    "amount": item.amount,
                    "date": item.date.isoformat() if item.date else None,
                    "source": item.source,
                    "needs_review": item.needs_review,
                }
                for item in typed_items
            ],
        )
        typed_lines = []
        for item, result in zip(typed_items, output["line_item_results"]):
            rule = result.get("applied_rule")
            reason_code = {
                "non_payable": "NON_PAYABLE",
                "room_limit": "ROOM_CAP",
            "icu_limit": "ICU_CAP",
                "proportionate_deduction": "PROPORTIONATE",
                "exclusion": "EXCLUSION",
                "needs_review": "REVIEW",
            }.get(rule, "OK")
            clause = typed_terms.clauses.get(item.category) or typed_terms.clauses.get(reason_code.lower())
            allowed = money(result.get("covered_amount"))
            typed_lines.append(TypedLineResult(item, allowed, max(Decimal("0"), item.amount - allowed), reason_code, clause))
        eligible = sum((line.allowed for line in typed_lines), Decimal("0"))
        insurer_share = money(output["payable_amount"])
        return ClaimResult(
            lines=typed_lines,
            eligible_total=eligible,
            copay=money(output["copayment"]),
            patient_share=max(Decimal("0"), bill.total_amount - insurer_share),
            insurer_share=insurer_share,
            status="manual_review" if output["status"] == "manual_review" else "computed",
            review_reasons=list(output.get("warnings", [])) if output["status"] == "manual_review" else [],
            admission_date=bill.admission_date,
            discharge_date=bill.discharge_date,
        )

    terms = terms or PolicyTerms()
    review_fields = list(review_fields or [])
    missing_fields = list(missing_fields or [])
    policy_terms_missing = list(policy_terms_missing or [])
    context = dict(claim_context or {})
    warnings: list[str] = []
    control_warnings: list[str] = []
    review_required = bool(missing_fields or review_fields or policy_terms_missing)
    hard_reject = False

    total = money(context.get("net_amount", total_amount))
    supplied_items = list(line_items or [])
    synthetic = not supplied_items
    items = supplied_items or [{"description": "Claim total", "category": "other", "amount": total, "source": "user"}]
    if total <= 0:
        return {"status": "manual_review", "rule_version": RULE_VERSION, "results": [], "line_item_results": [], "covered_amount": 0.0, "deductible": 0.0, "copayment": 0.0, "payable_amount": 0.0, "warnings": ["total_amount_missing_or_invalid"]}
    if policy_terms_missing or terms.annual_limit is None or terms.deductible is None or terms.copay_percent is None:
        missing = policy_terms_missing or ["annual_limit", "deductible", "copay_percent"]
        return {"status": "manual_review", "rule_version": RULE_VERSION, "results": [], "line_item_results": [], "covered_amount": 0.0, "deductible": 0.0, "copayment": 0.0, "payable_amount": 0.0, "warnings": ["Required policy terms missing: " + ", ".join(missing)], "policy_terms_missing": missing, "policy_terms": terms.source}

    if missing_fields:
        warnings.append("Missing required fields: " + ", ".join(missing_fields))
    if review_fields:
        warnings.append("Fields require review: " + ", ".join(review_fields))

    bill_name = context.get("bill_patient_name") or context.get("patient_name")
    policy_name = context.get("policy_holder_name") or context.get("insured_name")
    if bill_name or policy_name:
        match = verify_patient_name_match(bill_name, policy_name)
        if match["result"] in {"MISMATCH", "MISSING"}:
            review_required = True
            control_warnings.append(match["warning"])

    # Diagnosis matches are never treated as definitive financial denials.
    exclusions = terms.source.get("exclusions", {}).get("value", [])
    diagnosis_tokens = set(re.findall(r"[a-z0-9]{3,}", str(context.get("diagnosis") or "").lower()))
    for exclusion in exclusions:
        exclusion_tokens = set(re.findall(r"[a-z0-9]{3,}", str(exclusion).lower()))
        if exclusion_tokens and exclusion_tokens.issubset(diagnosis_tokens):
            review_required = True
            control_warnings.append("DIAGNOSIS_EXCLUSION: diagnosis may match an exclusion; reviewer confirmation is required.")
            break

    extracted_total = sum((money(item.get("amount")) for item in items), Decimal("0"))
    mismatch = not synthetic and abs(extracted_total - total) > total * Decimal("0.01")
    if mismatch:
        review_required = True
        warnings.append("TOTAL_MISMATCH: itemized charges differ from the bill total by more than 1%.")

    duplicates = detect_line_item_duplicates(items)
    if any(entry["duplicate"] for entry in duplicates):
        review_required = True
        warnings.append("POSSIBLE_DUPLICATE: identical charges were retained and require reviewer confirmation.")
    if context.get("duplicate_suspected") is True:
        review_required = True
        control_warnings.append("Possible duplicate charges require reviewer confirmation; charges were not removed automatically.")
    if context.get("multiple_bills") is True and context.get("aggregation_confirmed") is not True:
        review_required = True
        control_warnings.append("Multiple bills require reviewer confirmation before aggregation.")
    if context.get("previous_claims_uncertain") is True:
        review_required = True
        control_warnings.append("Previous claims history is uncertain; reviewer confirmation required.")

    annual_limit = money(terms.annual_limit)
    previous = terms.previous_claims_total if terms.previous_claims_total is not None else context.get("previous_claims_total")
    if previous is not None:
        annual_limit = max(Decimal("0"), annual_limit - money(previous))
        if annual_limit == 0:
            hard_reject = True
            control_warnings.append("Annual sum insured is fully exhausted by previous claims.")

    if terms.source.get("preauthorization_required", {}).get("value") is True and context.get("preauthorization_obtained") is not True:
        review_required = True
        control_warnings.append("Policy requires pre-authorization confirmation.")
    if terms.source.get("network_required", {}).get("value") is True:
        if context.get("in_network") is False:
            hard_reject = True
            control_warnings.append("Policy requires a network provider and this provider is out of network.")
        elif context.get("in_network") is not True:
            review_required = True
            control_warnings.append("Policy requires network-provider confirmation.")

    stay_nights = context.get("length_of_stay_nights", context.get("length_of_stay", 1))
    if stay_nights == 0 or context.get("is_daycare") is True:
        daycare = validate_daycare_procedure(context.get("procedure") or context.get("diagnosis"), terms.daycare_procedures, int(stay_nights or 0))
        if daycare["status"] == "excluded":
            hard_reject = True
            control_warnings.append(daycare["notice"])
        elif daycare["status"] == "manual_review":
            review_required = True
            control_warnings.append(daycare["notice"])

    duplicate_info = detect_line_item_duplicates(items)
    room_categories = {ROOM_CATEGORY, ROOM_RENT_CATEGORY, ACCOMMODATION_CATEGORY}
    room_items = [item for item in items if normalize_category(item.get("category"), "") in room_categories or re.search(r"\b(room|accommodation)\b", str(item.get("description") or ""), re.I)]
    room_total = sum((money(item.get("amount")) for item in room_items), Decimal("0"))
    room_days = int(context.get("room_days") or 0)
    room_cap = money(terms.room_limit_per_day) * room_days if terms.room_limit_per_day is not None and room_days > 0 else None
    ratio_basis = room_total
    if synthetic and context.get("room_charge") is not None:
        ratio_basis = money(context["room_charge"])
    room_ratio = min(Decimal("1"), room_cap / ratio_basis) if room_cap is not None and ratio_basis > room_cap and ratio_basis else Decimal("1")

    line_results: list[dict[str, Any]] = []
    total_room_reduction = Decimal("0")
    non_payables = {str(value).lower() for value in terms.source.get("non_payable_categories", {}).get("value", [])}
    for index, item in enumerate(items):
        amount = money(item.get("amount"))
        category = str(item.get("category") or "other").lower()
        if category in non_payables or any(term in str(item.get("description") or "").lower() for term in non_payables):
            evaluated = {"description": item.get("description", "Unspecified item"), "category": category, "amount": float(amount), "status": "excluded", "covered_amount": 0.0, "applied_rule": "non_payable", "calculation": "This category is listed as non-payable in the reviewed policy terms."}
        else:
            evaluated = evaluate_line_item(item, terms, context)

        if item in room_items and room_cap is not None:
            previously_allowed = sum((money(row.get("covered_amount")) for row in line_results if normalize_category(row.get("category"), "") in room_categories), Decimal("0"))
            line_allowance = max(Decimal("0"), room_cap - previously_allowed)
            allowed_room = min(money(evaluated.get("covered_amount")), line_allowance)
            if allowed_room < money(evaluated.get("covered_amount")):
                evaluated.update(status="partial", covered_amount=float(allowed_room), applied_rule="room_limit", calculation=f"Room charge capped at INR {room_cap} for {room_days} day(s).")
            total_room_reduction += money(evaluated.get("amount")) - money(evaluated.get("covered_amount"))

        if terms.proportionate_deduction and room_ratio < 1 and normalize_category(category, "") in {DOCTOR_NURSING_CATEGORY, NURSING_CATEGORY, DOCTOR_CATEGORY, CONSULTATION_CATEGORY}:
            before = money(evaluated.get("covered_amount"))
            allowed = (before * room_ratio).quantize(MONEY, rounding=ROUND_HALF_UP)
            if allowed < before:
                evaluated.update(status="partial", covered_amount=float(allowed), applied_rule="proportionate_deduction", calculation=f"Room-linked charges scaled by {room_ratio} because the room cap was exceeded.")

        # Legacy aggregate context has no room line to apportion the documented
        # room and linked reductions across; apply that adjustment to its single
        # synthetic line while preserving the unified pipeline.
        if synthetic and index == 0 and context.get("room_charge") is not None and room_days and terms.room_limit_per_day is not None:
            billed_room = money(context["room_charge"])
            cap = money(terms.room_limit_per_day) * int(room_days)
            direct = max(Decimal("0"), billed_room - cap)
            linked = money(context.get("room_linked_charges") or 0)
            linked_reduction = (linked * (Decimal("1") - min(Decimal("1"), cap / billed_room))).quantize(MONEY, rounding=ROUND_HALF_UP) if billed_room else Decimal("0")
            adjustment = direct + linked_reduction
            if adjustment:
                evaluated["covered_amount"] = float(max(Decimal("0"), money(evaluated.get("covered_amount")) - adjustment))
                evaluated.update(status="partial", applied_rule="room_limit", calculation=f"Room and linked-charge reduction: INR {adjustment}.")

        if duplicate_info[index]["duplicate"]:
            evaluated["possible_duplicate"] = True
        line_results.append(evaluated)
        if evaluated.get("status") == "needs_review":
            review_required = True

    covered = sum((money(item.get("covered_amount")) for item in line_results), Decimal("0"))
    pre_limit = covered
    remaining = annual_limit
    for item in line_results:
        allowed = money(item.get("covered_amount"))
        if allowed > remaining:
            item["covered_amount"] = float(max(Decimal("0"), remaining))
            item.update(status="partial", applied_rule="sum_insured", calculation=f"The remaining sum insured leaves INR {remaining} eligible for this item.")
        remaining = max(Decimal("0"), remaining - money(item.get("covered_amount")))
    covered = sum((money(item.get("covered_amount")) for item in line_results), Decimal("0"))
    deductible = min(money(terms.deductible), covered)
    after_deductible = max(Decimal("0"), covered - deductible)
    copayment = (after_deductible * money(terms.copay_percent) / Decimal("100")).quantize(MONEY, rounding=ROUND_HALF_UP)
    payable = max(Decimal("0"), after_deductible - copayment)
    status = "partially_approved" if any(item.get("status") in {"partial", "excluded"} for item in line_results) or total > annual_limit or mismatch else "approved"
    if hard_reject:
        status = "rejected"
    elif review_required:
        status = "manual_review"
    warnings.extend(control_warnings)
    if total > annual_limit:
        warnings.append("annual_limit_exceeded")
    if any(item.get("applied_rule") == "room_limit" for item in line_results):
        warnings.append("room_limit_applied")
    if terms.proportionate_deduction and room_ratio < 1:
        warnings.append("room_limit_proportional_applied")
    rule_results = [
        RuleResult("line_item_coverage", RULE_VERSION, "pass", {"line_items": len(line_results)}, f"sum(allowed line items) = {covered}", covered),
        RuleResult("deductible", RULE_VERSION, "pass", {"eligible_before_deductible": float(covered), "deductible": float(deductible)}, f"{covered} - {deductible} = {after_deductible}", deductible),
        RuleResult("copayment", RULE_VERSION, "pass", {"after_deductible": float(after_deductible), "copay_percent": float(terms.copay_percent)}, f"{after_deductible} x {terms.copay_percent}% = {copayment}", copayment),
        RuleResult("payable_amount", RULE_VERSION, "pass", {"eligible_after_deductible": float(after_deductible), "copayment": float(copayment)}, f"{after_deductible} - {copayment} = {payable}", payable),
    ]
    return {"status": status, "rule_version": RULE_VERSION, "results": [row.to_dict() for row in rule_results], "line_item_reconciliation_failed": mismatch, "line_item_notice": "Itemized charges differ from the bill total by more than 1%; reviewer confirmation is required." if mismatch else None, "line_item_results": line_results, "covered_amount": float(covered), "deductible": float(deductible), "copayment": float(copayment), "payable_amount": float(payable), "patient_share": float(max(Decimal("0"), total - payable)), "warnings": warnings, "policy_terms": terms.source}

