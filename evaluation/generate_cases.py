"""Materialize fictional PDF fixtures from committed hand labels.

This generator never edits labels and is not an evaluator. Review and commit
samples/evaluation_cases/ground_truth.json before generating PDFs.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
LABELS = ROOT / "samples" / "evaluation_cases" / "ground_truth.json"
OUT = ROOT / "samples" / "evaluation_cases" / "cases"
STYLES = getSampleStyleSheet()
LAYOUTS = ("pipe_table", "colon_labels", "aligned_columns", "narrative", "key_value", "wrapped_rows")


def _write_policy(path: Path, row: dict) -> None:
    lines = [
        "FICTIONAL SAMPLE POLICY — NOT AN INSURANCE CONTRACT",
        "Policy number: POL-EVAL-FICTIONAL-2026",
        f"Annual limit: INR {max(10000, row['billed'])}",
        f"Deductible: INR {row['deductible']}",
        f"Co-pay: {row['copay_percent']}%",
        "Room limit per day: INR 5000",
        "Pharmacy and medicines are payable during hospitalization.",
        "Diagnostic investigations are payable during hospitalization.",
        "The listed case policy terms are reviewer-confirmed synthetic labels.",
    ]
    if row["case_id"] == "edge_05":
        lines.append("Pre-hospitalization expenses are covered up to 30 days before admission; post-hospitalization expenses are covered up to 60 days after discharge. Treatment outside these date windows is excluded.")
    doc = SimpleDocTemplate(str(path), pagesize=A4)
    doc.build([Paragraph(line, STYLES["BodyText"]) for line in lines])


def _write_bill(path: Path, row: dict, scanned: bool) -> None:
    if scanned:
        image = Image.new("RGB", (1250, 1700), "white")
        draw = ImageDraw.Draw(image)
        text = [
            "FICTIONAL SAMPLE HOSPITAL BILL — NOT A REAL CLAIM",
            "Patient: Sample Patient",
            "Policy number: POL-EVAL-FICTIONAL-2026",
            "Admission date: 10 Aug 2026",
            "Discharge date: 14 Aug 2026",
            "Description | Date | Qty | Rate | Amount" if row["case_id"] == "edge_05" else f"Treatment charges: INR {row['billed']}",
            f"Eligible treatment | 01 Jun 2026 | 1 | {row['billed']} | {row['billed']}" if row["case_id"] == "edge_05" else "",
            f"Grand Total: INR {row['billed']}",
        ]
        font_path = Path(r"C:\Windows\Fonts\arial.ttf")
        font = ImageFont.truetype(str(font_path), 42) if font_path.exists() else ImageFont.load_default()
        text = [line for line in text if line]
        for i, line in enumerate(text):
            draw.text((70, 80 + i * 185), line, fill="black", font=font)
        image_path = path.with_suffix(".png")
        image.save(image_path)
        doc = canvas.Canvas(str(path), pagesize=A4)
        doc.drawImage(str(image_path), 0, 0, width=A4[0], height=A4[1])
        doc.save()
        image_path.unlink()
        return
    c = canvas.Canvas(str(path), pagesize=A4)
    y = A4[1] - 50 * mm
    lines = [
        "FICTIONAL SAMPLE HOSPITAL BILL - NOT A REAL CLAIM",
        "Patient name: Sample Patient",
        "Policy number: POL-EVAL-FICTIONAL-2026",
        "Admission date: 10 Aug 2026",
        "Discharge date: 14 Aug 2026",
        "Description | Date | Qty | Rate | Amount",
        f"Eligible treatment | 12 Aug 2026 | 1 | {row['eligible']} | {row['eligible']}",
    ]
    if row.get("excluded_amount", 0):
        lines.append(f"Cosmetic surgery | 12 Aug 2026 | 1 | {row['excluded_amount']} | {row['excluded_amount']}")
    lines.extend([f"Sub Total: INR {row['billed']}", "Tax: INR 0", f"Grand Total: INR {row['billed']}"])
    c.setFont("Helvetica", 12)
    for line in lines:
        c.drawString(18 * mm, y, line)
        y -= 9 * mm
    c.save()


def _settlement_text(row: dict) -> str:
    amount = row["insurer_paid"]
    claim = f"Claim No: CLM-EVAL-{row['case_id'].replace('_', '-').upper()}"
    if row["group"] == "manual_review" and row["layout"] == "missing_paid_label":
        paid = "Payment details: pending review"
    elif row["group"] == "manual_review" and row["layout"] == "conflicting_paid_amounts":
        paid = "Amount Paid: 25000\nAmount Paid: 24000"
    else:
        paid = f"Amount Paid: INR {amount}"
    eligible = int(row["eligible"])
    deductible = min(int(row["deductible"]), eligible)
    copay = (eligible - deductible) * int(row["copay_percent"]) // 100
    if int(row["copay_percent"]) and (eligible - deductible) * int(row["copay_percent"]) % 100:
        copay = round((eligible - deductible) * int(row["copay_percent"]) / 100)
    if row["group"] == "discrepancy":
        deductible += 1000
    deductions = []
    if row.get("excluded_amount", 0):
        deductions.append(("Exclusion", int(row["excluded_amount"]), "Not covered by fictional policy"))
    if deductible:
        deductions.append(("Deductible", deductible, "Policy deductible"))
    if copay:
        deductions.append(("Co-pay", copay, "Policy co-pay"))
    style = row["layout"]
    if style in {"pipe_table", "wrapped_rows"}:
        deduction_text = "Deductions\n" + "\n".join(f"{name} | INR {value} | {reason}" for name, value, reason in deductions)
    elif style == "colon_labels":
        deduction_text = "Deductions:\n" + "\n".join(f"{name}: INR {value} - {reason}" for name, value, reason in deductions)
    elif style == "aligned_columns":
        deduction_text = "Deductions\n" + "\n".join(f"{name}    INR {value}    {reason}" for name, value, reason in deductions)
    elif style == "narrative":
        deduction_text = "Deductions\n" + "\n".join(f"{name} | {value} | {reason}" for name, value, reason in deductions)
    else:
        deduction_text = "Deductions details\n" + "\n".join(f"{name}: {value}" for name, value, _ in deductions)
    if not deductions:
        deduction_text = "Deductions: none"
    if row["layout"] == "unreadable_deductions":
        deduction_text = "Deductions\n[unreadable scan block]"
    claim_line = "Claim No: CLM-EVAL-WRONG-2026" if row["layout"] == "mismatched_claim_id" else claim
    if row["layout"] in {"missing_paid_label", "mismatched_claim_id", "unreadable_deductions", "scanned_letter", "conflicting_paid_amounts"}:
        deduction_text = {
            "missing_paid_label": "Deductions: none",
            "mismatched_claim_id": "Deductions: none",
            "unreadable_deductions": "Deductions\n[unreadable scan block]",
            "scanned_letter": "Deductions: none",
            "conflicting_paid_amounts": "Deductions: none",
        }[row["layout"]]
    return "\n".join(["FICTIONAL SAMPLE SETTLEMENT — NOT A REAL CLAIM", claim_line, f"Bill Total: INR {row['billed']}", paid, deduction_text])


def _write_settlement(path: Path, row: dict) -> None:
    text = _settlement_text(row)
    doc = SimpleDocTemplate(str(path), pagesize=A4)
    doc.build([Paragraph(line.replace("&", "&amp;"), STYLES["BodyText"]) for line in text.splitlines()])


def generate() -> int:
    source = json.loads(LABELS.read_text(encoding="utf-8"))
    if source.get("synthetic_only") is not True or "hand-calculated" not in source.get("label", ""):
        raise SystemExit("Ground truth is not marked as fictional hand-labeled data.")
    for row in source["cases"]:
        folder = OUT / row["case_id"]
        folder.mkdir(parents=True, exist_ok=True)
        scanned = row["case_id"] in {"manual_04", "edge_05"}
        _write_policy(folder / "policy.pdf", row)
        _write_bill(folder / "bill.pdf", row, scanned)
        _write_settlement(folder / "settlement.pdf", row)
        (folder / "expected-results.json").write_text(json.dumps(row, indent=2) + "\n", encoding="utf-8")
        (folder / "case.json").write_text(json.dumps({
            "label": "FICTIONAL SAMPLE", "case_id": row["case_id"],
            "claim_id": f"CLM-EVAL-{row['case_id'].replace('_', '-').upper()}",
            "policy_terms_reviewer_confirmed": {
                "annual_limit": max(10000, row["billed"]),
                "deductible": row["deductible"],
                "copay_percent": row["copay_percent"],
                "room_limit_per_day": 5000,
                "source_page": 1,
            },
            "scanned_bill": scanned,
            "settlement_layout": row["layout"],
        }, indent=2) + "\n", encoding="utf-8")
    print(f"Generated {len(source['cases'])} fictional cases in {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(generate())
