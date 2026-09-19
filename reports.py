"""Clear, claimant-facing decision and appeal documents for the local prototype."""
from __future__ import annotations

import io
from datetime import datetime
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from agents import recommend_next_steps


TEAL = colors.HexColor("#0F766E")
INK = colors.HexColor("#102A2B")
MUTED = colors.HexColor("#5D7474")
LINE = colors.HexColor("#CFE1DF")
MINT = colors.HexColor("#EAF8F5")


def _money(value: Any) -> str:
    return f"INR {float(value or 0):,.2f}"


def _value(item: Any) -> Any:
    return item.get("value") if isinstance(item, dict) else item


def _status_label(status: str) -> str:
    return str(status or "manual_review").replace("_", " ").title()


def _outcome_copy(status: str, payable: Any) -> str:
    messages = {
        "approved": f"The current assessment approves an estimated insurer payment of {_money(payable)}.",
        "partially_approved": f"The current assessment partially covers the claim, with an estimated insurer payment of {_money(payable)}.",
        "manual_review": "This claim needs an authorized reviewer to confirm the result before a final decision is issued.",
        "rejected": "The current assessment does not identify covered charges under the available policy information. An authorized reviewer can confirm this result.",
    }
    return messages.get(status, "An authorized reviewer should confirm the current assessment.")


def _reason_copy(value: Any) -> str:
    if str(value) == "line_item_reconciliation_failed":
        return "Itemized charges could not be reconciled to the bill total, so the aggregate bill total was used for this calculation."
    return str(value)


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("ReportTitle", parent=base["Title"], fontName="Helvetica-Bold", fontSize=22, leading=27, textColor=INK, spaceAfter=4),
        "subtitle": ParagraphStyle("ReportSubtitle", parent=base["Normal"], fontSize=9, leading=13, textColor=MUTED),
        "heading": ParagraphStyle("ReportHeading", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=12, leading=16, textColor=INK, spaceBefore=14, spaceAfter=6),
        "body": ParagraphStyle("ReportBody", parent=base["BodyText"], fontSize=9.4, leading=14, textColor=INK, spaceAfter=5),
        "small": ParagraphStyle("ReportSmall", parent=base["Normal"], fontSize=8, leading=11, textColor=MUTED),
        "letter": ParagraphStyle("LetterBody", parent=base["BodyText"], fontSize=10, leading=15, textColor=INK, spaceAfter=10, alignment=TA_LEFT),
    }


def _footer(canvas: Any, doc: Any) -> None:
    canvas.saveState()
    canvas.setStrokeColor(LINE)
    canvas.line(doc.leftMargin, 0.42 * inch, A4[0] - doc.rightMargin, 0.42 * inch)
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 7.5)
    canvas.drawString(doc.leftMargin, 0.27 * inch, "Medi Gaurd AI - decision support document")
    canvas.drawRightString(A4[0] - doc.rightMargin, 0.27 * inch, f"Page {doc.page}")
    canvas.restoreState()


def _document() -> tuple[io.BytesIO, SimpleDocTemplate]:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=0.62 * inch,
        leftMargin=0.62 * inch,
        topMargin=0.58 * inch,
        bottomMargin=0.68 * inch,
        title="Medi Gaurd AI claim document",
        author="Medi Gaurd AI",
    )
    return buffer, doc


def _details_table(rows: list[tuple[str, str]], first_column: float = 2.5) -> Table:
    table = Table(rows, colWidths=[first_column * inch, (7.15 - first_column) * inch], repeatRows=0)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), MINT),
        ("TEXTCOLOR", (0, 0), (-1, -1), INK),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("LEADING", (0, 0), (-1, -1), 13),
        ("GRID", (0, 0), (-1, -1), 0.45, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return table


def _line_item_status_label(status: Any) -> str:
    return {
        "covered": "Covered",
        "partial": "Partially covered",
        "excluded": "Excluded",
        "needs_review": "Needs review",
    }.get(str(status), _status_label(str(status or "needs_review")))


def _item_note_map(decision: dict[str, Any], item_count: int) -> dict[int, str]:
    notes: dict[int, str] = {}
    for note in decision.get("line_item_notes") or []:
        if not isinstance(note, dict):
            continue
        try:
            index = int(note.get("item_index"))
        except (TypeError, ValueError):
            continue
        text = str(note.get("note") or "").strip()
        if 0 <= index < item_count and text:
            notes[index] = text
    return notes


def _line_item_table(line_item_results: list[dict[str, Any]], normalized: dict[str, Any], decision: dict[str, Any], styles: dict[str, ParagraphStyle]) -> Table:
    """Build the compact itemized table used by the claimant decision report."""
    source_items = normalized.get("line_items") or []
    notes = _item_note_map(decision, len(line_item_results))
    rows: list[list[Paragraph]] = [[
        Paragraph("<b>Description</b>", styles["small"]),
        Paragraph("<b>Amount Claimed</b>", styles["small"]),
        Paragraph("<b>Amount Approved</b>", styles["small"]),
        Paragraph("<b>Status</b>", styles["small"]),
        Paragraph("<b>Note</b>", styles["small"]),
    ]]
    for index, result in enumerate(line_item_results):
        source = source_items[index] if index < len(source_items) and isinstance(source_items[index], dict) else {}
        description = source.get("description") or result.get("description") or "Line item"
        amount = source.get("amount") or result.get("amount") or 0
        rows.append([
            Paragraph(escape(str(description)), styles["small"]),
            Paragraph(escape(_money(amount)), styles["small"]),
            Paragraph(escape(_money(result.get("covered_amount", 0))), styles["small"]),
            Paragraph(escape(_line_item_status_label(result.get("status"))), styles["small"]),
            Paragraph(escape(notes.get(index, "")), styles["small"]),
        ])
    table = Table(rows, colWidths=[1.38 * inch, 0.94 * inch, 0.98 * inch, 1.0 * inch, 2.85 * inch], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), TEAL),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("TEXTCOLOR", (0, 1), (-1, -1), INK),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.3),
        ("LEADING", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 0.45, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def _claim_total(normalized: dict[str, Any], rules: dict[str, Any]) -> float:
    return float(_value(normalized.get("total_amount")) or rules.get("amount_billed") or rules.get("covered_amount") or 0)


def build_decision_report(claim: dict[str, Any], normalized: dict[str, Any], rules: dict[str, Any], workflow: dict[str, Any] | None = None) -> bytes:
    """Create an easy-to-read PDF that explains the recorded claim outcome."""
    workflow = workflow or {}
    decision = workflow.get("decision", {})
    findings = workflow.get("policy_findings", {})
    status = str(decision.get("status") or rules.get("status") or "manual_review")
    payable = rules.get("payable_amount", 0)
    total = _claim_total(normalized, rules)
    deductible = float(rules.get("deductible", 0) or 0)
    copayment = float(rules.get("copayment", 0) or 0)
    responsibility = max(0, total - float(payable or 0))
    excluded = max(0, responsibility - deductible - copayment)
    styles = _styles()
    buffer, doc = _document()

    story = [
        Paragraph("MEDI GAURD AI", styles["subtitle"]),
        Paragraph("Claim Decision Report", styles["title"]),
        Paragraph(f"Prepared {datetime.now().strftime('%d %b %Y')} | Claim reference: {claim.get('claim_number', 'Not available')}", styles["subtitle"]),
        Spacer(1, 13),
        Paragraph("Outcome summary", styles["heading"]),
        Paragraph(f"<b>Current status: {_status_label(status)}</b><br/>{_outcome_copy(status, payable)}", styles["body"]),
        Spacer(1, 5),
        _details_table([
            ("Claim number", str(claim.get("claim_number") or "Not available")),
            ("Patient", str(claim.get("patient_name") or _value(normalized.get("patient_name")) or "Not available")),
            ("Provider", str(claim.get("hospital_name") or _value(normalized.get("hospital_name")) or "Not available")),
            ("Policy number", str(claim.get("policy_number") or _value(normalized.get("policy_number")) or "Not available")),
        ]),
        Paragraph("Amount breakdown", styles["heading"]),
        _details_table([
            ("Total medical bill", _money(total)),
            ("Covered before cost sharing", _money(rules.get("covered_amount", 0))),
            ("Deductible", _money(deductible)),
            ("Copayment", _money(copayment)),
            ("Estimated insurer payment", _money(payable)),
            ("Estimated claimant responsibility", _money(responsibility)),
            ("Excluded or policy-limited", _money(excluded)),
        ]),
        Paragraph("What this means", styles["heading"]),
        Paragraph(
            f"The estimated claimant responsibility is {_money(responsibility)}. This includes {_money(deductible)} deductible, {_money(copayment)} copayment, and {_money(excluded)} that is excluded or limited by the available policy information.",
            styles["body"],
        ),
    ]
    line_item_results = rules.get("line_item_results") or []
    if line_item_results:
        story.extend([
            Paragraph("Item-wise verification", styles["heading"]),
            _line_item_table(line_item_results, normalized, decision, styles),
        ])
    recommendation_rules = {**rules, "billing_anomalies": normalized.get("billing_anomalies") or {}}
    recommendations = recommend_next_steps(decision, recommendation_rules)
    if recommendations:
        story.append(Paragraph("Recommended next steps", styles["heading"]))
        for recommendation in recommendations:
            story.append(Paragraph(f"- {recommendation}", styles["body"]))
        story.append(Paragraph("This is decision-support information, not legal or insurance advice.", styles["small"]))
    reasons = decision.get("reasons") or rules.get("warnings") or []
    story.append(Paragraph("Explanation and next steps", styles["heading"]))
    if reasons:
        for reason in reasons[:3]:
            story.append(Paragraph(f"- {_reason_copy(reason)}", styles["body"]))
    else:
        story.append(Paragraph("No additional policy warnings were recorded for this assessment.", styles["body"]))
    if status == "manual_review":
        story.append(Paragraph("Next step: ask an authorized reviewer to confirm the required information before relying on this result.", styles["body"]))
    else:
        story.append(Paragraph("Next step: keep this report with the claim documents. An authorized reviewer should confirm the final determination.", styles["body"]))
    evidence = findings.get("retrieved_evidence") or workflow.get("policy_evidence") or []
    story.append(Paragraph("Evidence notes", styles["heading"]))
    if evidence:
        for item in evidence[:3]:
            citation = str(item.get("clause_id") or "Policy evidence")
            text = str(item.get("text") or "").replace("\n", " ").strip()
            story.append(Paragraph(f"<b>{citation}:</b> {text[:480]}", styles["small"]))
    else:
        story.append(Paragraph("No policy excerpts were retained in this session. The calculation and review status are shown above.", styles["small"]))
    story.extend([Spacer(1, 8), Paragraph("This document is decision support only and is not a final insurer determination.", styles["small"])])
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buffer.getvalue()


def _claim_level_appeal_letter(claim: dict[str, Any], rules: dict[str, Any], workflow: dict[str, Any]) -> str:
    """The original aggregate-only letter retained for non-itemized claims."""
    workflow = workflow or {}
    decision = workflow.get("decision", {})
    status = _status_label(str(decision.get("status") or rules.get("status") or "manual_review"))
    reasons = decision.get("reasons") or rules.get("warnings") or ["Please review the claim documents and calculation."]
    reason_lines = "\n".join(f"- {_reason_copy(reason)}" for reason in reasons[:3])
    return (
        f"Subject: Request for review of claim {claim.get('claim_number', '')}\n\n"
        "Dear Claims Review Team,\n\n"
        f"I request a human review of claim {claim.get('claim_number', '')} for {claim.get('patient_name', '')}. "
        f"The current assessment is {status}, with an estimated insurer payment of {_money(rules.get('payable_amount', 0))}.\n\n"
        "Please review the attached medical documents, the applicable policy edition, cited policy evidence, and the recorded calculation. "
        "Please provide the final determination and supporting reasons in writing.\n\n"
        "Key points for review:\n"
        f"{reason_lines}\n\n"
        "Sincerely,\n"
        "Claimant or authorized representative\n"
    )


def _appeal_rule_copy(applied_rule: Any) -> str:
    return {
        "sub_limit": "capped by the applicable sub-limit",
        "exclusion": "excluded under the applicable policy exclusion",
        "waiting_period": "limited by the waiting-period rule",
    }.get(str(applied_rule), f"affected by the {str(applied_rule or 'policy').replace('_', ' ')} rule")


def _policy_clause_texts(workflow: dict[str, Any], citations: list[Any]) -> list[tuple[str, str]]:
    """Resolve grounded citation IDs to the retained policy finding text."""
    finding_by_id = {
        str(finding.get("clause_id")): str(finding.get("text") or "").replace("\n", " ").strip()
        for finding in (workflow.get("policy_findings", {}) or {}).get("findings", [])
        if isinstance(finding, dict) and finding.get("clause_id")
    }
    clauses = []
    for citation in citations:
        clause_id = str(citation or "").strip()
        if clause_id and clause_id in finding_by_id:
            clauses.append((clause_id, finding_by_id[clause_id]))
    return clauses


def build_appeal_letter(claim: dict[str, Any], rules: dict[str, Any], workflow: dict[str, Any] | None = None) -> str:
    """Create a deterministic, item-specific appeal letter when data supports it."""
    workflow = workflow or {}
    line_item_results = rules.get("line_item_results") or []
    if not line_item_results:
        return _claim_level_appeal_letter(claim, rules, workflow)

    appeal_items = [
        (index, item)
        for index, item in enumerate(line_item_results)
        if isinstance(item, dict) and item.get("status") in {"excluded", "partial"}
    ]
    if not appeal_items:
        return _claim_level_appeal_letter(claim, rules, workflow)

    decision = workflow.get("decision", {}) or {}
    normalized = workflow.get("normalized_claim", {}) or {}
    source_items = normalized.get("line_items") or []
    disputed_amount = sum(
        max(0.0, float(item.get("amount", 0) or 0) - float(item.get("covered_amount", 0) or 0))
        for _, item in appeal_items
    )
    item_lines = []
    for index, item in appeal_items:
        source = source_items[index] if index < len(source_items) and isinstance(source_items[index], dict) else {}
        description = str(source.get("description") or item.get("description") or "Line item")
        amount = source.get("amount") or item.get("amount") or 0
        item_lines.append(
            f"- {description}: {_money(amount)} claimed; {_money(item.get('covered_amount', 0))} approved; "
            f"the charge was {_appeal_rule_copy(item.get('applied_rule'))}."
        )

    # Citations are claim-level today. Item notes identify that the decision
    # discussed appeal-worthy rows, while citation IDs still map only to the
    # retained policy findings. Therefore retain all grounded claim citations.
    appeal_indices = {index for index, _ in appeal_items}
    item_notes = decision.get("line_item_notes") or []
    has_item_specific_note = any(
        isinstance(note, dict) and note.get("item_index") in appeal_indices
        for note in item_notes
    )
    citations = list(decision.get("policy_citations") or [])
    clauses = _policy_clause_texts(workflow, citations)
    clause_paragraph = "The decision did not retain a policy clause excerpt for these charges."
    if clauses:
        evidence_intro = "The item-level decision notes refer to the following retained policy clauses:" if has_item_specific_note else "The decision cites the following retained policy clauses:"
        clause_paragraph = evidence_intro + " " + " ".join(
            f"{clause_id}: {text}" for clause_id, text in clauses
        )

    reasons = decision.get("reasons") or rules.get("warnings") or ["Please review the claim documents and calculation."]
    reason_copy = " ".join(_reason_copy(reason) for reason in reasons[:3])
    claim_number = str(claim.get("claim_number") or "")
    return (
        f"Subject: Request for reconsideration of claim {claim_number} — disputed amount {_money(disputed_amount)}\n\n"
        "Dear Claims Review Team,\n\n"
        f"I request reconsideration of claim {claim_number} for {claim.get('patient_name', '')}. "
        f"The current assessment leaves {_money(disputed_amount)} of the itemized charges unpaid.\n\n"
        "The following charges require review:\n"
        f"{'\n'.join(item_lines)}\n\n"
        f"{clause_paragraph}\n\n"
        f"Please reconsider these charges and provide a written final determination. The recorded decision reasons are: {reason_copy}\n\n"
        "Sincerely,\n"
        "Claimant or authorized representative\n"
    )


def build_appeal_letter_pdf(claim: dict[str, Any], rules: dict[str, Any], workflow: dict[str, Any] | None = None) -> bytes:
    """Create a polished, ready-to-review appeal-letter PDF draft."""
    workflow = workflow or {}
    decision = workflow.get("decision", {})
    status = _status_label(str(decision.get("status") or rules.get("status") or "manual_review"))
    styles = _styles()
    buffer, doc = _document()
    reasons = decision.get("reasons") or rules.get("warnings") or ["Please review the claim documents and calculation."]
    story = [
        Paragraph("MEDI GAURD AI", styles["subtitle"]),
        Paragraph("Appeal and Review Request", styles["title"]),
        Paragraph(f"Prepared {datetime.now().strftime('%d %b %Y')} | Claim reference: {claim.get('claim_number', 'Not available')}", styles["subtitle"]),
        Spacer(1, 20),
        Paragraph("To: Claims Review Team", styles["letter"]),
        Paragraph("Subject: Request for review of claim " + str(claim.get("claim_number") or ""), styles["letter"]),
        Paragraph("Dear Claims Review Team,", styles["letter"]),
        Paragraph(
            f"I request a human review of claim <b>{claim.get('claim_number', '')}</b> for <b>{claim.get('patient_name', '')}</b>. "
            f"The current assessment is <b>{status}</b>, with an estimated insurer payment of <b>{_money(rules.get('payable_amount', 0))}</b>.",
            styles["letter"],
        ),
        Paragraph(
            "Please review the attached medical documents, the applicable policy edition, cited policy evidence, and the recorded calculation. Please provide the final determination and supporting reasons in writing.",
            styles["letter"],
        ),
        Paragraph("Key points for review", styles["heading"]),
    ]
    for reason in reasons[:3]:
        story.append(Paragraph(f"- {_reason_copy(reason)}", styles["letter"]))
    story.extend([
        Spacer(1, 10),
        Paragraph("Sincerely,", styles["letter"]),
        Paragraph("Claimant or authorized representative", styles["letter"]),
        Spacer(1, 12),
        Paragraph("This is a prepared draft. Review and personalize it before submitting it to an insurer.", styles["small"]),
    ])
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buffer.getvalue()
