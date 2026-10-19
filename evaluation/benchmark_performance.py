import time
import json
from pathlib import Path

print("=" * 70)
print("MEDIGUARD AI -- END-TO-END PERFORMANCE & LATENCY BENCHMARK")
print("=" * 70)

# Step 1: Benchmark Document Processing
start_ext = time.perf_counter()
from mediguard.ingestion.extraction import extract_document, normalize_documents
bill_file = Path("demo_assets/approved_bill.pdf")
evidence, raw_by_page, page_count = extract_document(bill_file, "bench-1", bill_file.name)
doc_payload = [{
    "document_id": "bench-1",
    "source_name": bill_file.name,
    "document_type": "medical_bill",
    "text": "\n".join(e.text for e in evidence),
    "evidence": [e.to_dict() for e in evidence],
    "raw_by_page": raw_by_page
}]
normalized = normalize_documents(doc_payload)
ext_time = time.perf_counter() - start_ext
print(f"\n1. Document Extraction & Normalization:")
print(f"   Time Taken: {ext_time:.3f} seconds")
print(f"   Pages Processed: {page_count}")
print(f"   Line Items Extracted: {len(normalized.line_items)}")

# Step 2: Benchmark Deterministic Rule Engine
start_rules = time.perf_counter()
from mediguard.engine.rules import evaluate_claim, PolicyTerms
from decimal import Decimal
terms = PolicyTerms(
    annual_limit=Decimal("500000"),
    deductible=Decimal("5000"),
    copay_percent=Decimal("10"),
    room_limit_per_day=Decimal("5000"),
    waiting_period_months=0
)
rule_result = evaluate_claim(
    total_amount=normalized.total_amount.value if normalized.total_amount else 80000.0,
    terms=terms,
    line_items=normalized.line_items
)
rules_time = time.perf_counter() - start_rules
print(f"\n2. Deterministic Rule Engine Calculation:")
print(f"   Time Taken: {rules_time * 1000:.3f} ms")
print(f"   Claim Status: {rule_result['status']}")
print(f"   Payable Amount: INR {rule_result['payable_amount']}")

# Step 3: Benchmark Vector Policy Retrieval (ChromaDB RAG)
start_rag = time.perf_counter()
from mediguard.policy.policy_index import index_policy_documents, retrieve_policy_evidence
policy_file = Path("demo_assets/approved_policy.pdf")
p_evidence, p_raw, p_pages = extract_document(policy_file, "bench-pol-1", policy_file.name)
policy_text_str = "\n".join(e.text for e in p_evidence)
p_payload = [{
    "document_id": "bench-pol-1",
    "source_name": policy_file.name,
    "text": policy_text_str,
    "evidence": [e.to_dict() for e in p_evidence],
    "raw_by_page": p_raw
}]
indexed = index_policy_documents(p_payload, "bench-version-1")
retrieved_clauses = retrieve_policy_evidence("bench-version-1", "hospitalization and room rent limit", limit=4)
rag_time = time.perf_counter() - start_rag
print(f"\n3. RAG Vector Indexing & Clause Retrieval (ChromaDB + BGE-small):")
print(f"   Time Taken: {rag_time:.3f} seconds")
print(f"   Chunks Indexed: {indexed['chunks_indexed']}")
print(f"   Clauses Retrieved: {len(retrieved_clauses)}")

# Step 4: Benchmark Ollama Local LLM Decision Agent Call
start_llm = time.perf_counter()
from mediguard.ai.agents import run_claim_workflow, warm_ollama
warm_ollama()
final_state = run_claim_workflow(
    normalized_claim=normalized.to_dict(),
    policy_text=policy_text_str,
    rule_results=rule_result,
    claim={"total_amount": 80000.0, "patient_name": "Ananya Rao", "policy_number": "POLDEMOAPPROVEDX"},
    policy_id="bench-version-1"
)
llm_time = time.perf_counter() - start_llm
decision = final_state.get("decision", {})
print(f"\n4. Agentic Workflow & Ollama LLM Inference:")
print(f"   Time Taken: {llm_time:.3f} seconds")
print(f"   Total LLM Calls Made: {final_state.get('llm_calls', 0)}")
print(f"   Decision Status: {decision.get('status')}")
print(f"   Confidence Score: {decision.get('confidence')}")

# Step 5: Benchmark PDF Report Generation
start_pdf = time.perf_counter()
from mediguard.reporting.reports import build_decision_report
report_pdf = build_decision_report(
    claim={"claim_id": "BENCH-001", "claim_number": "CLM-BENCH-001", "patient_name": "Ananya Rao", "policy_number": "POLDEMOAPPROVEDX"},
    normalized=normalized.to_dict(),
    rules=rule_result,
    workflow=final_state
)
pdf_time = time.perf_counter() - start_pdf
print(f"\n5. PDF Report Generator (reports.py):")
print(f"   Time Taken: {pdf_time * 1000:.3f} ms")
print(f"   PDF Size Generated: {len(report_pdf)} bytes")

total_time = ext_time + rules_time + rag_time + llm_time + pdf_time
print(f"\n" + "=" * 70)
print(f"TOTAL END-TO-END CLAIM PROCESSING TIME: {total_time:.3f} SECONDS")
print(f"TOTAL LLM CALLS MADE: {final_state.get('llm_calls', 0)}")
print("=" * 70)
