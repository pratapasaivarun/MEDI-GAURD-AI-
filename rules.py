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
    icu_limit_per_day: Decimal | None = None
    pre_hospitalization_days: int | None = None
    post_hospitalization_days: int | None = None
    daycare_procedures: list[str] = field(default_factory=list)
    previous_claims_total: Decimal | None = None
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


def verify_patient_name_match(bill_name: str | None, policy_name: str | None) -> dict[str, Any]:
    """Verify identity consistency between bill patient name and policy holder name."""
    if not bill_name or not policy_name:
        return {"result": "MISSING", "status": "manual_review", "warning": "Patient name missing on bill or policy; reviewer confirmation required."}
    
    b_clean = re.sub(r"^(mr|mrs|ms|dr|master|sri|smt)\b\.?\s*", "", str(bill_name).strip(), flags=re.IGNORECASE)
    p_clean = re.sub(r"^(mr|mrs|ms|dr|master|sri|smt)\b\.?\s*", "", str(policy_name).strip(), flags=re.IGNORECASE)
    
    b_norm = re.sub(r"[^\w\s]", "", b_clean).upper()
    p_norm = re.sub(r"[^\w\s]", "", p_clean).upper()
    
    b_tokens = b_norm.split()
    p_tokens = p_norm.split()
    
    if not b_tokens or not p_tokens:
        return {"result": "MISSING", "status": "manual_review", "warning": "Patient name missing or invalid after normalization."}
        
    if b_norm == p_norm or set(b_tokens) == set(p_tokens):
        return {"result": "MATCH", "status": "approved", "warning": None}
    
    if len(b_tokens) == len(p_tokens):
        matches = True
        for bt, pt in zip(b_tokens, p_tokens):
            if bt == pt or (len(bt) == 1 and pt.startswith(bt)) or (len(pt) == 1 and bt.startswith(pt)):
                continue
            else:
                matches = False
                break
        if matches:
            return {"result": "MINOR_VARIATION", "status": "approved", "warning": None}
            
    import difflib
    ratio = difflib.SequenceMatcher(None, b_norm, p_norm).ratio()
    if ratio >= 0.85:
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


def _evaluate_claim_total_only(total_amount: Any, terms: PolicyTerms | None = None, review_fields: list[str] | None = None, missing_fields: list[str] | None = None, policy_terms_missing: list[str] | None = None, claim_context: dict[str, Any] | None = None) -> dict[str, Any]:
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
        if item_explicit.get("matched") is True and float(item_explicit.get("confidence", 0)) >= 0.90:
            if tokens and tokens.intersection(item_tokens):
                return True, False
        if claim_explicit.get("matched") is True and float(claim_explicit.get("confidence", 0)) >= 0.90:
            if tokens and tokens.issubset(item_tokens):
                return True, False
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
    if matched_limit is not None:
        remaining = money(claim_context.get("_sub_limit_remaining", matched_limit))
        eligible = min(amount, max(Decimal("0"), remaining))
        if eligible < amount:
            return {**result, "status": "partial", "covered_amount": float(eligible), "applied_rule": "sub_limit", "calculation": f"INR {amount} is capped at the remaining {category} sub-limit of INR {eligible}."}
    return result


def evaluate_claim(total_amount: Any, terms: PolicyTerms | None = None, review_fields: list[str] | None = None, missing_fields: list[str] | None = None, policy_terms_missing: list[str] | None = None, claim_context: dict[str, Any] | None = None, line_items: list[dict] | None = None) -> dict[str, Any]:
    """Evaluate a claim, using line items when they are available.

    Legacy callers that only provide ``total_amount`` keep the original
    calculation path. New callers receive one transparent result per item and
    aggregate those eligible amounts before applying deductible and copayment.
    """
    terms = terms or PolicyTerms()
    review_fields = review_fields or []
    missing_fields = missing_fields or []
    policy_terms_missing = policy_terms_missing or []
    claim_context = claim_context or {}

    warnings: list[str] = []
    control_warnings: list[str] = []
    hard_reject = False
    review_required = bool(missing_fields or review_fields)

    # 1. Patient Name Matching Validation
    bill_patient_name = claim_context.get("bill_patient_name") or claim_context.get("patient_name")
    policy_holder_name = claim_context.get("policy_holder_name") or claim_context.get("insured_name")
    if bill_patient_name or policy_holder_name:
        name_match = verify_patient_name_match(bill_patient_name, policy_holder_name)
        if name_match["result"] == "MISMATCH":
            review_required = True
            control_warnings.append(name_match["warning"])
        elif name_match["result"] == "MISSING":
            review_required = True
            control_warnings.append(name_match["warning"])

    # 2. Cumulative Sum Insured Check
    prev_claims_raw = terms.previous_claims_total if terms.previous_claims_total is not None else claim_context.get("previous_claims_total")
    if claim_context.get("previous_claims_uncertain") is True:
        review_required = True
        control_warnings.append("Previous claims history is uncertain; reviewer confirmation required.")
    
    effective_annual_limit = money(terms.annual_limit) if terms.annual_limit is not None else Decimal("0")
    if prev_claims_raw is not None:
        prev_claims = money(prev_claims_raw)
        remaining_sum_insured = max(Decimal("0"), effective_annual_limit - prev_claims)
        if prev_claims >= effective_annual_limit:
            hard_reject = True
            control_warnings.append("Annual sum insured is fully exhausted by previous claims.")
        effective_annual_limit = remaining_sum_insured

    # 3. Daycare Procedure Whitelist Check (for 0-night stays)
    stay_nights = claim_context.get("length_of_stay_nights")
    if stay_nights is None:
        stay_nights = claim_context.get("length_of_stay", 1)
    if stay_nights == 0 or claim_context.get("is_daycare") is True:
        proc_name = claim_context.get("procedure") or claim_context.get("diagnosis")
        daycare_res = validate_daycare_procedure(proc_name, terms.daycare_procedures, length_of_stay_nights=stay_nights)
        if daycare_res["status"] == "excluded":
            hard_reject = True
            control_warnings.append(daycare_res["notice"])
        elif daycare_res["status"] == "manual_review":
            review_required = True
            control_warnings.append(daycare_res["notice"])

    if not line_items:
        legacy = _evaluate_claim_total_only(total_amount, terms, review_fields, missing_fields, policy_terms_missing, claim_context)
        legacy["line_item_results"] = []
        legacy["line_item_reconciliation_failed"] = False
        legacy["line_item_notice"] = None
        if control_warnings:
            legacy.setdefault("warnings", []).extend(control_warnings)
            if hard_reject:
                legacy["status"] = "rejected"
            elif review_required:
                legacy["status"] = "manual_review"
        return legacy

    stated_total = money(total_amount)
    extracted_total = sum((money(item.get("amount")) for item in line_items), Decimal("0"))
    allowed_difference = max(Decimal("1.00"), stated_total * Decimal("0.05"))
    if stated_total > 0 and (extracted_total <= 0 or abs(extracted_total - stated_total) > allowed_difference):
        legacy = _evaluate_claim_total_only(total_amount, terms, review_fields, missing_fields, policy_terms_missing, claim_context)
        legacy["line_item_results"] = []
        legacy["line_item_reconciliation_failed"] = True
        legacy["line_item_notice"] = "Itemized charges could not be reconciled to the bill total, so the aggregate bill total was used for this calculation."
        legacy.setdefault("warnings", []).append("line_item_reconciliation_failed")
        if control_warnings:
            legacy.setdefault("warnings", []).extend(control_warnings)
            if hard_reject:
                legacy["status"] = "rejected"
            elif review_required:
                legacy["status"] = "manual_review"
        return legacy

    if policy_terms_missing or terms.annual_limit is None or terms.deductible is None or terms.copay_percent is None:
        result = _evaluate_claim_total_only(total_amount, terms, review_fields, missing_fields, policy_terms_missing, claim_context)
        result["line_item_results"] = []
        result["line_item_reconciliation_failed"] = False
        result["line_item_notice"] = None
        return result

    if missing_fields:
        warnings.append("Missing required fields: " + ", ".join(missing_fields))
    if review_fields:
        warnings.append("Fields require review: " + ", ".join(review_fields))

    # 4. Automated Line Item Duplicate Detection
    duplicate_info = detect_line_item_duplicates(line_items)

    sub_limit_remaining = {name.lower(): money(value) for name, value in terms.sub_limits.items()}
    waiting_remaining = money(claim_context["waiting_period_affected_amount"]) if claim_context.get("waiting_period_affected_amount") is not None else None
    line_item_results: list[dict] = []
    
    for idx, item in enumerate(line_items):
        item_context = dict(claim_context)
        category = str(item.get("category") or "").strip().lower()
        if category in sub_limit_remaining:
            item_context["_sub_limit_remaining"] = sub_limit_remaining[category]
        if waiting_remaining is not None:
            item_context["_waiting_period_amount_for_item"] = waiting_remaining
            
        evaluated = evaluate_line_item(item, terms, item_context)
        
        # Check duplicate flag for this item
        dup_entry = duplicate_info[idx]
        if dup_entry["duplicate"]:
            evaluated["status"] = "excluded"
            evaluated["covered_amount"] = 0.0
            evaluated["applied_rule"] = "duplicate_detection"
            evaluated["calculation"] = dup_entry["notice"]
            warnings.append("duplicate_line_item_detected")

        line_item_results.append(evaluated)
        if category in sub_limit_remaining:
            sub_limit_remaining[category] = max(Decimal("0"), sub_limit_remaining[category] - money(evaluated["covered_amount"]))
        if waiting_remaining is not None:
            waiting_remaining = max(Decimal("0"), waiting_remaining - money(item.get("amount")))
        if evaluated["status"] == "needs_review":
            review_required = True

    # Apply the effective annual limit (after cumulative previous claims deduction)
    annual_remaining = effective_annual_limit
    for item_result in line_item_results:
        eligible = money(item_result["covered_amount"])
        if eligible > annual_remaining:
            item_result["covered_amount"] = float(max(Decimal("0"), annual_remaining))
            if item_result["status"] != "excluded":
                item_result["status"] = "partial"
                item_result["applied_rule"] = "annual_limit"
                item_result["calculation"] = f"The remaining annual policy limit leaves INR {annual_remaining} eligible for this item."
            warnings.append("annual_limit_exceeded")
        annual_remaining = max(Decimal("0"), annual_remaining - money(item_result["covered_amount"]))

    covered_before_limit = sum((money(item["covered_amount"]) for item in line_item_results), Decimal("0"))
    if any(item["status"] == "partial" for item in line_item_results):
        warnings.append("item_level_policy_adjustment")

    if terms.source.get("preauthorization_required", {}).get("value") is True and claim_context.get("preauthorization_obtained") is not True:
        review_required = True
        control_warnings.append("Policy requires pre-authorization confirmation.")
    if terms.source.get("network_required", {}).get("value") is True:
        if claim_context.get("in_network") is False:
            hard_reject = True
            control_warnings.append("Policy requires a network provider and this provider is out of network.")
        elif claim_context.get("in_network") is not True:
            review_required = True
            control_warnings.append("Policy requires network-provider confirmation.")
    if claim_context.get("duplicate_suspected") is True:
        review_required = True
        control_warnings.append("Possible duplicate charges require reviewer confirmation; charges were not removed automatically.")
    if claim_context.get("multiple_bills") is True and claim_context.get("aggregation_confirmed") is not True:
        review_required = True
        control_warnings.append("Multiple bills require reviewer confirmation before aggregation.")

    deductible = min(money(terms.deductible), covered_before_limit)
    after_deductible = max(Decimal("0"), covered_before_limit - deductible)
    copayment = (after_deductible * money(terms.copay_percent) / Decimal("100")).quantize(MONEY, rounding=ROUND_HALF_UP)
    payable = max(Decimal("0"), after_deductible - copayment)
    results = [
        RuleResult("line_item_coverage", RULE_VERSION, "pass", {"line_items": len(line_item_results)}, f"sum(line_item_covered_amounts) = {covered_before_limit}", covered_before_limit),
        RuleResult("deductible", RULE_VERSION, "pass", {"eligible_before_deductible": float(covered_before_limit), "deductible": float(terms.deductible)}, f"{covered_before_limit} - {deductible} = {after_deductible}", deductible),
        RuleResult("copayment", RULE_VERSION, "pass", {"after_deductible": float(after_deductible), "copay_percent": float(terms.copay_percent)}, f"{after_deductible} x {terms.copay_percent}% = {copayment}", copayment),
        RuleResult("payable_amount", RULE_VERSION, "pass", {"eligible_after_deductible": float(after_deductible), "copayment": float(copayment)}, f"{after_deductible} - {copayment} = {payable}", payable),
    ]
    warnings.extend(control_warnings)
    status = "partially_approved" if any(item["status"] in {"partial", "excluded"} for item in line_item_results) else "approved"
    if hard_reject:
        status = "rejected"
    elif review_required:
        status = "manual_review"
    return {"status": status, "rule_version": RULE_VERSION, "results": [item.to_dict() for item in results], "line_item_reconciliation_failed": False, "line_item_notice": None, "line_item_results": line_item_results, "covered_amount": float(covered_before_limit), "deductible": float(deductible), "copayment": float(copayment), "payable_amount": float(payable), "warnings": warnings, "policy_terms": terms.source}

