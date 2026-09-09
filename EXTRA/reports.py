"""Downloadable decision artifacts for the local MVP."""
from __future__ import annotations

import io
import json
from typing import Any

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.lib import colors


def _pretty(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, default=str)
    return str(value)


def build_decision_report(claim: dict[str, Any], normalized: dict[str, Any], rules: dict[str, Any], workflow: dict[str, Any] | None = None) -> bytes:
    workflow = workflow or {}
    decision = workflow.get("decision", {})
    findings = workflow.get("policy_findings", {})
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=0.55 * inch, leftMargin=0.55 * inch, topMargin=0.5 * inch, bottomMargin=0.5 * inch)
    styles = getSampleStyleSheet()
    story = [Paragraph("Medi Gaurd AI — Claim Decision Report", styles["Title"]), Spacer(1, 10)]
    story.append(Paragraph("Decision support only. Final determination must be confirmed by an authorized reviewer.", styles["Normal"]))
    story.append(Spacer(1, 10))
    claim_rows = [["Claim", claim.get("claim_number", "")], ["Patient", claim.get("patient_name", "")], ["Hospital", claim.get("hospital_name", "")], ["Policy", claim.get("policy_number", "")], ["Automated status", decision.get("status", rules.get("status", "manual_review"))], ["Payable amount", f"INR {rules.get('payable_amount', 0):,.2f}"]]
    table = Table(claim_rows, colWidths=[1.6 * inch, 5.8 * inch])
    table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.grey), ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EAF2F8")), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.extend([table, Spacer(1, 12), Paragraph("Deterministic calculation", styles["Heading2"])])
    calc_rows = [["Status", rules.get("status", "manual_review")], ["Covered amount", f"INR {rules.get('covered_amount', 0):,.2f}"], ["Deductible", f"INR {rules.get('deductible', 0):,.2f}"], ["Copayment", f"INR {rules.get('copayment', 0):,.2f}"], ["Payable", f"INR {rules.get('payable_amount', 0):,.2f}"], ["Warnings", "; ".join(rules.get("warnings", [])) or "None"]]
    calc_table = Table(calc_rows, colWidths=[1.6 * inch, 5.8 * inch])
    calc_table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.grey), ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F7F7F7")), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.extend([calc_table, Spacer(1, 12), Paragraph("Agent reasons", styles["Heading2"])])
    for reason in decision.get("reasons", []) or ["No agent reasons available."]:
        story.append(Paragraph("• " + str(reason), styles["Normal"]))
    story.extend([Spacer(1, 8), Paragraph(f"Policy source: {workflow.get('policy_source', 'not available')}", styles["Normal"]), Paragraph(f"Evidence items: {len(findings.get('retrieved_evidence', []))}", styles["Normal"])])
    doc.build(story)
    return buffer.getvalue()


def build_appeal_letter(claim: dict[str, Any], rules: dict[str, Any], workflow: dict[str, Any] | None = None) -> str:
    workflow = workflow or {}
    decision = workflow.get("decision", {})
    return f"""Subject: Request for review of claim {claim.get('claim_number', '')}\n\nDear Claims Review Team,\n\nI request a human review of claim {claim.get('claim_number', '')} for {claim.get('patient_name', '')}. The current automated recommendation is '{decision.get('status', rules.get('status', 'manual_review'))}', with a calculated payable amount of INR {rules.get('payable_amount', 0):,.2f}.\n\nPlease review the attached medical documents, the active policy edition, the cited policy evidence, and the deterministic calculation. Please provide the final determination and reasons in writing.\n\nSincerely,\nAuthorized claimant or representative\n"""
