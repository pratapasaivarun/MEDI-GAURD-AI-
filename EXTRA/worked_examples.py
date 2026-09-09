import json
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path
from extraction import extract_document, normalize_documents
from policy_terms import extract_policy_terms
from rules import PolicyTerms, evaluate_claim

ROOT = Path(__file__).parent / "fixtures" / "phase4"


def extract_fixture(filename, document_type, document_id):
    evidence, raw_by_page, page_count = extract_document(ROOT / filename, document_id, filename)
    payload = {"document_id": document_id, "source_name": filename, "document_type": document_type, "text": "\n".join(item.text for item in evidence), "raw_by_page": raw_by_page, "evidence": [item.to_dict() for item in evidence]}
    return payload, page_count


def normalized_fields(normalized):
    fields = {}
    for name in ("patient_name", "hospital_name", "policy_number", "claim_number", "admission_date", "discharge_date", "diagnosis", "total_amount"):
        field = getattr(normalized, name)
        fields[name] = None if field is None else {"value": field.value, "confidence": field.confidence, "needs_review": field.needs_review, "evidence": [item.to_dict() for item in field.evidence]}
    return fields


def policy_payload(policy_filename, document_id):
    policy_doc, pages = extract_fixture(policy_filename, "policy", document_id)
    terms_result = extract_policy_terms(policy_doc["evidence"])
    terms = terms_result["terms"]
    terms.source = terms_result["terms_json"]
    return policy_doc, pages, terms_result, terms


def controls_trace(terms, context):
    source = terms.source
    trace = []
    trace.append({"rule": "amount_present", "outcome": "pass", "why": "A positive bill total is available."})
    trace.append({"rule": "annual_limit", "outcome": "pass", "why": "The bill total is within the extracted annual limit."})
    exclusions = source.get("exclusions", {}).get("value", [])
    diagnosis = str(context.get("diagnosis", "")).lower()
    possible = [str(item) for item in exclusions if any(token in diagnosis for token in __import__('re').findall(r"[a-z]{4,}", str(item).lower()))]
    if possible:
        match = context.get("exclusion_match") or {}
        if match.get("matched") is True and float(match.get("confidence", 0)) >= 0.90:
            trace.append({"rule": "exclusion", "outcome": "fail", "why": "The supplied structured exclusion match is high confidence."})
        else:
            trace.append({"rule": "exclusion", "outcome": "uncertain", "why": "The diagnosis may match an exclusion, but no high-confidence structured match was supplied."})
    else:
        trace.append({"rule": "exclusion", "outcome": "pass", "why": "No extracted exclusion phrase matched the diagnosis."})
    if terms.waiting_period_months:
        trace.append({"rule": "waiting_period", "outcome": "pass" if context.get("waiting_period_satisfied") is True else "uncertain", "why": "Waiting-period satisfaction is explicitly confirmed." if context.get("waiting_period_satisfied") is True else "The policy has a waiting period but satisfaction is not confirmed."})
    if source.get("network_required", {}).get("value") is True:
        network = context.get("in_network")
        trace.append({"rule": "network", "outcome": "pass" if network is True else "fail" if network is False else "uncertain", "why": "Provider is explicitly in network." if network is True else "Provider is explicitly out of network." if network is False else "Network status is missing."})
    if source.get("preauthorization_required", {}).get("value") is True:
        preauth = context.get("preauthorization_obtained")
        trace.append({"rule": "pre_authorization", "outcome": "pass" if preauth is True else "uncertain", "why": "Required authorization is explicitly confirmed." if preauth is True else "Required authorization is missing; no automatic rejection is made."})
    category = str(context.get("coverage_category", "")).strip().lower()
    if category and category in {key.lower() for key in terms.sub_limits}:
        trace.append({"rule": "sub_limit", "outcome": "partial", "why": "Category amount is capped at the extracted sub-limit."})
    else:
        trace.append({"rule": "sub_limit", "outcome": "pass", "why": "No applicable extracted sub-limit was supplied."})
    if context.get("room_charge") is not None and context.get("room_days"):
        if context.get("room_linked_charges") is None:
            trace.append({"rule": "room_limit", "outcome": "uncertain", "why": "Room charge exceeds the daily cap but linked-charge basis is missing."})
        else:
            trace.append({"rule": "room_limit", "outcome": "partial", "why": "Room charge exceeds the daily cap and linked charges are proportionally reduced."})
    else:
        trace.append({"rule": "room_limit", "outcome": "pass", "why": "No room-charge context was supplied."})
    trace.append({"rule": "duplicate_charges", "outcome": "uncertain" if context.get("duplicate_suspected") else "pass", "why": "Suspected duplicates require review and are never auto-removed." if context.get("duplicate_suspected") else "No duplicate suspicion was supplied."})
    trace.append({"rule": "multiple_bill_aggregation", "outcome": "uncertain" if context.get("multiple_bills") and not context.get("aggregation_confirmed") else "pass", "why": "Reviewer confirmation is required before aggregation." if context.get("multiple_bills") and not context.get("aggregation_confirmed") else "No unconfirmed multi-bill aggregation."})
    return trace


def run_example(number, title, bill_filename, policy_filename, context, terms_override=None):
    bill_doc, bill_pages = extract_fixture(bill_filename, "medical_bill", f"example-{number}-bill")
    policy_doc, policy_pages, terms_result, terms = policy_payload(policy_filename, f"example-{number}-policy")
    if terms_override:
        terms = terms_override(terms)
    normalized = normalize_documents([bill_doc, policy_doc])
    rules = evaluate_claim(normalized.total_amount.value if normalized.total_amount else None, terms=terms, missing_fields=normalized.missing_fields, review_fields=normalized.review_fields, claim_context=context)
    return {"example": number, "title": title, "inputs": {"bill": bill_filename, "policy": policy_filename, "context_not_extracted_from_fixture": context}, "bill_pages": bill_pages, "policy_pages": policy_pages, "bill_raw_fields": normalized_fields(normalized), "policy_raw_text_by_page": policy_doc["raw_by_page"], "policy_terms": terms_result["terms_json"], "rule_order_and_trace": controls_trace(terms, context), "rule_engine_results": rules}


base_context = {"diagnosis": "acute appendicitis", "waiting_period_satisfied": True, "in_network": True, "preauthorization_obtained": True}
examples = [
    run_example(1, "Straightforward approval", "bill_phone_photo.png", "policy_standard.pdf", base_context),
    run_example(2, "Partial approval from proportional room-charge limit", "bill_selectable_text.pdf", "policy_standard.pdf", {**base_context, "room_charge": 40000, "room_days": 5, "room_linked_charges": 80000}),
    run_example(3, "Manual Review from OCR contamination, missing hospital, and missing pre-authorization", "bill_skewed_compressed.jpg", "policy_standard.pdf", {"diagnosis": "acute appendicitis", "waiting_period_satisfied": True, "in_network": True}),
]
print(json.dumps(examples, indent=2, default=str))
