from __future__ import annotations
import app
import json
from unittest.mock import patch

import agents
import extraction
import fitz
from reports import build_decision_report

app.init_db()

# Reconciliation must fail closed when payable does not match the breakdown.
invalid = app._reconcile_result({"status": "approved", "covered_amount": 1000.0, "deductible": 100.0, "copayment": 100.0, "payable_amount": 900.0, "warnings": []}, 1000.0)
assert invalid["status"] == "manual_review"
assert "calculation_reconciliation_failed" in invalid["warnings"]

# A valid breakdown must remain approved and expose claimant-safe amounts.
valid = app._reconcile_result({"status": "approved", "covered_amount": 1000.0, "deductible": 100.0, "copayment": 90.0, "payable_amount": 810.0, "warnings": []}, 1000.0)
assert valid["status"] == "approved"
assert valid["claimant_result"]["amount_billed"] == 1000.0
assert valid["claimant_result"]["amount_covered"] == 810.0
assert valid["claimant_result"]["amount_claimant_pays"] == 190.0


def decision_state(line_item_results):
    return {
        "normalized_claim": {"total_amount": {"value": 80000}},
        "policy_evidence": [{"clause_id": "policy-clause-1", "text": "Coverage evidence."}],
        "policy_findings": {"findings": [{"clause_id": "policy-clause-1", "text": "Coverage evidence."}], "missing_evidence": []},
        "rule_results": {"status": "partially_approved", "covered_amount": 60000, "deductible": 5000, "copayment": 5500, "payable_amount": 49500, "warnings": [], "line_item_results": line_item_results},
        "llm_calls": 0,
    }


# Valid item notes are retained and the prompt only receives the trimmed item
# fields needed for grounded, concise item-level explanations.
items = [
    {"description": "Cosmetic procedure", "category": "surgery", "status": "excluded", "covered_amount": 0, "applied_rule": "exclusion", "calculation": "not sent"},
    {"description": "Surgery", "category": "surgery", "status": "partial", "covered_amount": 50000, "applied_rule": "sub_limit", "calculation": "not sent"},
    {"description": "Consultation", "category": "consultation", "status": "covered", "covered_amount": 10000, "applied_rule": "standard", "calculation": "not sent"},
]
with patch.object(agents, "_ollama_json", return_value={"status": "approved", "reasons": ["Rule result explained."], "policy_citations": ["policy-clause-1"], "confidence": 0.9, "reviewer_note": "Review complete.", "line_item_notes": [{"item_index": 0, "note": "This item is excluded."}, {"item_index": 1, "note": "This item is capped by the surgery limit."}]}) as call:
    decision_state_result = agents.decision_agent_node(decision_state(items))
    decision = decision_state_result["decision"]
    prompt = json.loads(call.call_args.args[1])
assert decision["line_item_notes"] == [{"item_index": 0, "note": "This item is excluded."}, {"item_index": 1, "note": "This item is capped by the surgery limit."}]
assert decision_state_result["llm_calls"] == 1
assert "line_item_results" in prompt["rules"]
assert set(prompt["rules"]["line_item_results"][0]) == {"item_index", "status", "covered_amount", "applied_rule", "category"}

# Aggregate fallback sends no empty item array to the LLM and always returns a
# safe empty note list.
with patch.object(agents, "_ollama_json", return_value={"status": "approved", "reasons": ["Aggregate calculation explained."], "policy_citations": ["policy-clause-1"], "confidence": 0.9, "reviewer_note": "Review complete."}) as call:
    fallback_decision = agents.decision_agent_node(decision_state([]))["decision"]
    fallback_prompt = json.loads(call.call_args.args[1])
assert fallback_decision["line_item_notes"] == []
assert "line_item_results" not in fallback_prompt["rules"]

# Next-step guidance is deterministic, status-aware, and works when the
# itemized result is unavailable on the aggregate fallback path.
assert agents.recommend_next_steps({"status": "approved"}, {"warnings": []}) == ["No action needed — reimbursement is being processed."]
assert agents.recommend_next_steps(
    {"status": "approved"},
    {"warnings": [], "line_item_results": [], "billing_anomalies": {"duplicates": [], "price_outliers": [{"reason": "amount is 10x the median"}]}},
) == ["Review flagged billing items before proceeding."]
partial_next_steps = agents.recommend_next_steps(
    {"status": "partially_approved"},
    {"payable_amount": 49500, "deductible": 5000, "copayment": 5500, "line_item_results": [{**items[0], "amount": 90000}], "warnings": []},
)
assert "INR 40,500.00" in partial_next_steps[0] and "Cosmetic procedure" in partial_next_steps[0]
rejected_next_steps = agents.recommend_next_steps(
    {"status": "rejected", "policy_citations": ["policy-clause-1"]},
    {"line_item_results": [{**items[1], "applied_rule": "sub_limit"}], "warnings": []},
)
assert "Surgery" in rejected_next_steps[0] and "policy-clause-1" in rejected_next_steps[0]
hard_exclusion_next_steps = agents.recommend_next_steps(
    {"status": "rejected", "policy_citations": ["policy-clause-1"]},
    {"line_item_results": [items[0]], "warnings": []},
)
assert "appeal" not in hard_exclusion_next_steps[0].lower() and "written review" in hard_exclusion_next_steps[0]
manual_next_steps = agents.recommend_next_steps(
    {"status": "manual_review"},
    {"line_item_results": [], "warnings": ["Missing required fields: discharge_summary, admission_date"]},
)
assert "Upload the missing document: discharge summary." in manual_next_steps
assert "Upload the missing document: admission date." in manual_next_steps
fallback_next_steps = agents.recommend_next_steps(
    {"status": "manual_review"},
    {"line_item_results": [], "warnings": ["line_item_reconciliation_failed"]},
)
assert fallback_next_steps == ["Your claim needs manual review; our team will contact you."]

# Billing anomalies preserve exact duplicate detection and add fuzzy matching
# and category-aware price outlier checks.
near_duplicate_items = [
    {"description": "MRI Scan - Brain", "amount": 10000, "category": "diagnostics"},
    {"description": "MRI Scan Brain", "amount": 10300, "category": "diagnostics"},
]
assert any("near-duplicate" in item["reason"] for item in extraction.detect_duplicate_charges(near_duplicate_items))
outlier_items = [
    {"description": "Surgery A", "amount": 10000, "category": "surgery"},
    {"description": "Surgery B", "amount": 11000, "category": "surgery"},
    {"description": "Surgery C", "amount": 50000, "category": "surgery"},
]
price_outliers = extraction.detect_price_outliers(outlier_items)
assert len(price_outliers) == 1 and price_outliers[0]["item"]["description"] == "Surgery C"
clean_claim = extraction.normalize_documents([{
    "document_type": "medical_bill",
    "text": "Patient Name: Demo\nHospital: Demo Care\nTotal: 3000\nDoctor consultation: 1000\nPhysician consultation: 1000\nConsultation doctor: 1000",
    "evidence": [],
}])
assert clean_claim.billing_anomalies == {"duplicates": [], "price_outliers": []}

# Out-of-range or covered-item indices returned by the LLM are never exposed.
with patch.object(agents, "_ollama_json", return_value={"status": "approved", "reasons": ["Rule result explained."], "policy_citations": ["policy-clause-1"], "confidence": 0.9, "reviewer_note": "Review complete.", "line_item_notes": [{"item_index": 99, "note": "Invented item."}, {"item_index": 2, "note": "Covered item note."}, {"item_index": 1, "note": "Valid item note."}]}), patch.object(agents, "_record_metrics") as metrics:
    filtered_decision = agents.decision_agent_node(decision_state(items))["decision"]
    groundedness_metric = metrics.call_args.args[0]
assert filtered_decision["line_item_notes"] == [{"item_index": 1, "note": "Valid item note."}]
assert groundedness_metric["policy_citations_dropped"] == 0
assert groundedness_metric["line_item_notes_dropped"] == 2

# Itemized reports retain every item row and its grounded note. Aggregate
# fallback reports deliberately remain in the pre-itemized layout.
report_claim = {
    "claim_number": "CLM-ITEM-001",
    "patient_name": "Demo Patient",
    "hospital_name": "Demo Hospital",
    "policy_number": "POL-ITEM-001",
}
report_normalized = {
    "total_amount": {"value": 90000},
    "line_items": [
        {"description": "Cosmetic", "amount": 20000},
        {"description": "Surgery", "amount": 60000},
        {"description": "Consultation", "amount": 10000},
    ],
}
report_rules = {
    "status": "partially_approved",
    "covered_amount": 60000,
    "deductible": 5000,
    "copayment": 5500,
    "payable_amount": 49500,
    "warnings": [],
    "line_item_results": items,
}
report_workflow = {
    "decision": {
        "status": "partially_approved",
        "reasons": ["Some charges are limited by the policy."],
        "line_item_notes": [
            {"item_index": 0, "note": "This procedure is excluded by the policy."},
            {"item_index": 1, "note": "This charge is capped at the surgery limit."},
        ],
    },
}
itemized_report_text = "".join(page.get_text() for page in fitz.open(stream=build_decision_report(report_claim, report_normalized, report_rules, report_workflow), filetype="pdf"))
assert "Item-wise verification" in itemized_report_text
assert itemized_report_text.count("Cosmetic") == 1
assert itemized_report_text.count("Surgery") == 1
assert itemized_report_text.count("Consultation") == 1
assert "This charge is capped at the surgery limit." in itemized_report_text

fallback_rules = {**report_rules, "line_item_results": []}
fallback_report_text = "".join(page.get_text() for page in fitz.open(stream=build_decision_report(report_claim, report_normalized, fallback_rules, report_workflow), filetype="pdf"))
assert "Item-wise verification" not in fallback_report_text

print("CORE_ADVANCEMENTS_OK")
