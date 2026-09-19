"""Create synthetic patient-support claim scenarios for MediGuard AI.

All generated material is fictional and intended only for repeatable prototype
tests. Each case folder contains the patient-facing source documents and a
manifest describing the registration fields, any trusted reviewer evidence, and
the expected safe outcome.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


ROOT = Path(__file__).parent / "fixtures" / "claim_scenarios"
STYLES = getSampleStyleSheet()


BASE_POLICY = {
    "annual_limit": 100000,
    "deductible": 5000,
    "copay": 10,
    "room_limit": 5000,
}


SCENARIOS = [
    ("approved", "01_standard_approved", "approved", 80000, "Standard eligible inpatient treatment", {}, {}),
    ("approved", "02_annual_limit_boundary", "approved", 100000, "Treatment within annual policy limit", {}, {}),
    ("approved", "03_below_deductible", "approved", 3000, "Short outpatient observation", {}, {}),
    ("approved", "04_zero_copayment", "approved", 80000, "Eligible surgery with zero copayment policy", {"copay": 0}, {}),
    ("approved", "05_zero_deductible", "approved", 80000, "Eligible surgery with zero deductible policy", {"deductible": 0}, {}),
    ("partially_approved", "01_annual_limit_exceeded", "partially_approved", 140000, "Treatment exceeds annual policy limit", {}, {}),
    ("partially_approved", "02_surgery_sublimit", "partially_approved", 80000, "Surgery subject to category sub-limit", {"sublimit": 60000}, {"coverage_category": "surgery"}),
    ("partially_approved", "03_room_limit_proportional", "partially_approved", 80000, "Inpatient stay with room rent above limit", {}, {"room_charge": 30000, "room_days": 3, "room_linked_charges": 50000}),
    ("partially_approved", "04_waiting_period_partial", "partially_approved", 100000, "Existing condition with unrelated eligible care", {"waiting_period": 12}, {"waiting_period_status": "not_satisfied", "waiting_period_affected_amount": 40000, "unrelated_eligible_amount": 60000, "trusted": True}),
    ("partially_approved", "05_combined_sublimit_costshare", "partially_approved", 100000, "Surgery with a sub-limit, deductible, and copayment", {"sublimit": 70000}, {"coverage_category": "surgery"}),
    ("rejected", "01_confirmed_exclusion", "rejected", 100000, "Cosmetic surgery", {"exclusion": "Cosmetic surgery is excluded."}, {"exclusion_match": {"matched": True, "confidence": 0.99}}),
    ("rejected", "02_out_of_network", "rejected", 100000, "Treatment at a non-network provider", {"network_required": True}, {"network_status": "out_of_network", "trusted": True}),
    ("manual_review", "01_policy_number_mismatch", "manual_review", 80000, "Valid bill with policy number mismatch", {}, {"registered_policy_number": "POL-SYN-MISMATCH-2026"}),
    ("manual_review", "02_missing_policy_terms", "manual_review", 80000, "Policy lacks deductible and copayment terms", {"missing_terms": True}, {}),
    ("manual_review", "03_invalid_bill_total", "manual_review", 0, "Bill does not state a payable total", {}, {}),
    ("manual_review", "04_incomplete_bill_fields", "manual_review", 80000, "Bill missing patient and service-date information", {}, {"incomplete_bill": True}),
    ("manual_review", "05_low_quality_scan", "manual_review", 80000, "Low-quality bill requiring extraction review", {}, {"quality_note": "Create a blurred/low-light derivative during OCR quality testing."}),
    ("manual_review", "06_waiting_period_unconfirmed", "manual_review", 80000, "Policy waiting period cannot be confirmed", {"waiting_period": 12}, {"waiting_period_status": "unknown"}),
    ("manual_review", "07_preauthorization_unconfirmed", "manual_review", 80000, "Policy requires preauthorization but proof is absent", {"preauth_required": True}, {"preauthorization_status": "not_confirmed", "trusted": True}),
    ("manual_review", "08_network_status_unknown", "manual_review", 80000, "Policy requires a network provider but status is unknown", {"network_required": True}, {"network_status": "unknown"}),
    ("manual_review", "09_possible_exclusion", "manual_review", 100000, "Diagnosis may match a policy exclusion", {"exclusion": "Cosmetic surgery is excluded."}, {"exclusion_match": {"matched": False, "confidence": 0.50}}),
    ("manual_review", "10_room_basis_missing", "manual_review", 30000, "Room rent exceeds limit but linked charges are absent", {}, {"room_charge": 30000, "room_days": 3}),
    ("manual_review", "11_multiple_bills_unconfirmed", "manual_review", 80000, "Two bills for one admission need aggregation confirmation", {}, {"multiple_bills": True, "aggregation_confirmed": False}),
    ("manual_review", "12_possible_duplicate_charge", "manual_review", 80000, "Repeated procedure charge needs reviewer confirmation", {}, {"duplicate_suspected": True}),
]


def policy_text(policy_number: str, overrides: dict) -> list[str]:
    terms = {**BASE_POLICY, **overrides}
    rows = [
        "SYNTHETIC POLICY DOCUMENT - FOR ACADEMIC TESTING ONLY",
        f"Policy number: {policy_number}",
        "Policy version: Synthetic Test Edition 2026",
        "Effective date: 2026-01-01",
    ]
    if not terms.get("missing_terms"):
        rows.extend([
            f"Annual limit: INR {terms['annual_limit']}",
            f"Deductible: INR {terms['deductible']}",
            f"Copayment: {terms['copay']}%",
            f"Room limit per day: INR {terms['room_limit']}",
        ])
    else:
        rows.extend(["Annual limit: INR 100000", "Room limit per day: INR 5000"])
    if terms.get("sublimit"):
        rows.append(f"Surgery sub-limit: INR {terms['sublimit']}")
    if terms.get("waiting_period"):
        rows.append(f"Waiting period: {terms['waiting_period']} months")
    if terms.get("network_required"):
        rows.append("Network provider required: yes")
    if terms.get("preauth_required"):
        rows.append("Preauthorization required: yes")
    if terms.get("exclusion"):
        rows.append(f"Exclusion: {terms['exclusion']}")
    rows.append("This fictional document is not an insurance contract.")
    return rows


def bill_text(policy_number: str, total: int, description: str, context: dict) -> list[str]:
    if context.get("incomplete_bill"):
        return [
            "SYNTHETIC MEDICAL BILL - FOR EXTRACTION REVIEW",
            "Hospital invoice: INV-INCOMPLETE-2026",
            "Treatment charges: INR 80000",
            "Important claimant and service-date fields are intentionally absent.",
        ]
    if total <= 0:
        return [
            "SYNTHETIC MEDICAL BILL - FOR EXTRACTION REVIEW",
            "Patient name: Aarav Sharma",
            f"Policy number: {policy_number}",
            "Hospital: Sunrise Care Hospital",
            "Admission date: 2026-08-20",
            "Discharge date: 2026-08-22",
            "Total amount: INR 0",
            "The total is intentionally invalid for a manual-review test.",
        ]
    rows = [
        "SYNTHETIC MEDICAL BILL - FOR ACADEMIC TESTING ONLY",
        "Claim number: CLM-SYN-2026",
        "Patient name: Aarav Sharma",
        f"Policy number: {policy_number}",
        "Hospital: Sunrise Care Hospital",
        "Admission date: 2026-08-20",
        "Discharge date: 2026-08-22",
        f"Diagnosis: {description}",
    ]
    if context.get("room_charge"):
        rows.append(f"Room charge: INR {context['room_charge']}")
        rows.append(f"Room days: {context['room_days']}")
    if context.get("coverage_category") == "surgery":
        rows.append(f"Surgery charges: INR {total}")
    elif context.get("duplicate_suspected"):
        rows.extend(["Procedure charge: INR 40000", "Procedure charge: INR 40000"])
    else:
        rows.append(f"Eligible treatment charges: INR {total}")
    rows.append(f"Total amount: INR {total}")
    rows.append("This fictional bill is not a hospital invoice.")
    return rows


def write_pdf(path: Path, title: str, rows: list[str]) -> None:
    doc = SimpleDocTemplate(str(path), pagesize=A4, rightMargin=20 * mm, leftMargin=20 * mm, topMargin=18 * mm, bottomMargin=18 * mm)
    story = [Paragraph(title, STYLES["Title"]), Spacer(1, 6 * mm)]
    data = [[Paragraph("Field / evidence", STYLES["BodyText"]), Paragraph("Value", STYLES["BodyText"])]]
    for row in rows:
        if ":" in row:
            key, value = row.split(":", 1)
            data.append([Paragraph(key, STYLES["BodyText"]), Paragraph(value.strip(), STYLES["BodyText"])])
        else:
            data.append([Paragraph(row, STYLES["BodyText"]), Paragraph("", STYLES["BodyText"])])
    table = Table(data, colWidths=[58 * mm, 108 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F766E")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#B7D6D1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2FAF8")]),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.append(table)
    doc.build(story)


def write_low_quality_bill(path: Path, policy_number: str) -> None:
    """Create an intentionally low-contrast, blurred OCR-review fixture."""
    image = Image.new("RGB", (1200, 1500), "#c7c1ae")
    draw = ImageDraw.Draw(image)
    rows = [
        "SYNTHETIC LOW-QUALITY MEDICAL BILL",
        "Patient name: Aarav Sharma",
        f"Policy number: {policy_number}",
        "Hospital: Sunrise Care Hospital",
        "Admission date: 2026-08-20",
        "Treatment charges: INR 80000",
        "Total amount: INR 80000",
        "Intentionally degraded OCR test image",
    ]
    y = 170
    for row in rows:
        draw.text((110, y), row, fill="#817b70", stroke_width=1)
        y += 135
    image.filter(ImageFilter.GaussianBlur(radius=2.6)).save(path)


def main() -> None:
    if ROOT.exists():
        shutil.rmtree(ROOT)
    ROOT.mkdir(parents=True)
    index = []
    for category, name, expected, total, description, policy_overrides, context in SCENARIOS:
        folder = ROOT / category / name
        folder.mkdir(parents=True)
        category_code = {
            "approved": "AP",
            "partially_approved": "PA",
            "rejected": "RJ",
            "manual_review": "MR",
        }[category]
        case_number = name.split("_", 1)[0]
        # The extraction patterns support letters, digits, and hyphens. Keep
        # fixture identifiers within that format so positive cases do not
        # accidentally become policy-mismatch tests.
        extracted_policy_number = f"POL-SYN-{category_code}{case_number}-2026"
        registered_policy_number = context.get("registered_policy_number", extracted_policy_number)
        write_pdf(folder / "policy.pdf", "Synthetic Insurance Policy", policy_text(extracted_policy_number, policy_overrides))
        write_pdf(folder / "medical_bill.pdf", "Synthetic Medical Bill", bill_text(extracted_policy_number, total, description, context))
        if name == "05_low_quality_scan":
            write_low_quality_bill(folder / "medical_bill_low_quality.png", extracted_policy_number)
        if context.get("multiple_bills"):
            write_pdf(folder / "medical_bill_2.pdf", "Synthetic Supporting Bill", bill_text(extracted_policy_number, 20000, "Supporting diagnostic services", {}))
        reviewer_context = {key: value for key, value in context.items() if key not in {"registered_policy_number", "incomplete_bill", "quality_note"}}
        manifest = {
            "synthetic_only": True,
            "case_id": name,
            "category": category,
            "expected_status": expected,
            "claim_registration": {
                "claim_number": f"CLM-{name.upper()}-2026",
                "patient_name": "Aarav Sharma",
                "hospital": "Sunrise Care Hospital",
                "policy_number": registered_policy_number,
                "service_date": "2026-08-20",
            },
            "uploaded_policy_number": extracted_policy_number,
            "upload_files": [item.name for item in folder.iterdir() if item.suffix.lower() in {".pdf", ".png", ".jpg", ".jpeg"}],
            "expected_bill_total": total,
            "reviewer_context_required": reviewer_context,
            "note": context.get("quality_note", "Use the two PDF files with the claim registration fields above."),
        }
        (folder / "case.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        index.append({"case_id": name, "category": category, "expected_status": expected, "path": str(folder.relative_to(ROOT))})
    (ROOT / "case_index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    (ROOT / "README.md").write_text(
        "# Synthetic patient-support claim cases\n\n"
        "All files in this directory are fictional academic test material. Each case folder includes a policy PDF, medical bill PDF, and `case.json` manifest.\n\n"
        "Use the fields in `claim_registration` when creating a claim. Some cases require trusted reviewer context; those are explicitly listed in the manifest because source documents alone cannot safely prove network status, preauthorization, waiting-period eligibility, or a confirmed exclusion.\n\n"
        "The app currently supports document upload and deterministic rule evaluation. Reviewer-context-only cases are included for rule-engine and future reviewer-form testing.\n",
        encoding="utf-8",
    )
    print(f"Created {len(index)} synthetic scenarios in {ROOT}")


if __name__ == "__main__":
    main()
