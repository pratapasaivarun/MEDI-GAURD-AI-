from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont
import json

ROOT = Path(__file__).parent / "fixtures" / "phase4"
ROOT.mkdir(parents=True, exist_ok=True)

BILL_LINES = [
    "MEDICAL BILL - SYNTHETIC FIXTURE",
    "Claim Number: CLM-SYN-1001",
    "Patient Name: Alex Morgan",
    "Hospital: North Star General Hospital",
    "Policy Number: POL-SYN-1001",
    "Admission Date: 2026-07-10",
    "Discharge Date: 2026-07-13",
    "Diagnosis: Acute appendicitis",
    "Room charges: INR 18000",
    "Doctor consultation: INR 12000",
    "Surgery and procedure: INR 85000",
    "Medicines: INR 14000",
    "Diagnostic tests: INR 16000",
    "Total Amount: INR 145000",
]


def draw_bill(path: Path, scale=2, rotate=0, brightness=1.0, quality=95):
    image = Image.new("RGB", (900, 1250), "white")
    draw = ImageDraw.Draw(image)
    font_path = "C:/Windows/Fonts/arial.ttf"
    try:
        font = ImageFont.truetype(font_path, 30)
    except OSError:
        font = ImageFont.load_default()
    y = 45
    for line in BILL_LINES:
        draw.text((55, y), line, fill="black", font=font)
        y += 78
    image = ImageEnhance.Brightness(image).enhance(brightness)
    if rotate:
        image = image.rotate(rotate, expand=True, fillcolor=(230, 230, 230))
    if brightness < 0.8:
        image = image.filter(ImageFilter.GaussianBlur(0.6))
    image.save(path, quality=quality, optimize=True)


def draw_pdf(path: Path, pages):
    c = canvas.Canvas(str(path), pagesize=A4)
    width, height = A4
    for page in pages:
        y = height - 70
        for line in page:
            c.drawString(55, y, line)
            y -= 24
        c.showPage()
    c.save()


def image_only_pdf(path: Path, image_path: Path):
    c = canvas.Canvas(str(path), pagesize=A4)
    c.drawImage(str(image_path), 40, 80, width=515, height=710, preserveAspectRatio=True, anchor='c')
    c.showPage()
    c.save()


def main():
    draw_pdf(ROOT / "bill_selectable_text.pdf", [BILL_LINES])
    draw_bill(ROOT / "bill_phone_photo.png", rotate=2, brightness=1.0)
    draw_bill(ROOT / "bill_low_light.jpg", rotate=-1.5, brightness=0.55, quality=55)
    draw_bill(ROOT / "bill_skewed_compressed.jpg", rotate=4, brightness=0.95, quality=25)
    draw_pdf(ROOT / "bill_multi_page.pdf", [BILL_LINES[:10], BILL_LINES[10:] + ["Discharge Summary: Stable at discharge."]])
    image_only_pdf(ROOT / "bill_scanned_image_only.pdf", ROOT / "bill_phone_photo.png")
    policy_base = [
        "SYNTHETIC HEALTH POLICY",
        "Policy Number: POL-SYN-1001",
        "Annual Policy Limit: INR 500000",
        "Deductible: INR 10000",
        "Copayment: 10 percent",
        "Room and Board Limit: INR 5000 per day",
        "Waiting period: 12 months",
        "Network hospital required.",
        "Pre-authorization required for surgery.",
        "Required documents: discharge summary and itemized bill.",
        "Exclusion: cosmetic surgery.",
    ]
    draw_pdf(ROOT / "policy_standard.pdf", [policy_base])
    policy_variant = [
        "SYNTHETIC HEALTH POLICY - VARIANT EDITION",
        "Policy Number: POL-SYN-1001",
        "Maximum annual benefit: INR 600000",
        "Patient contribution: 15 percent after a deductible of INR 12000",
        "Daily accommodation cap: INR 7000",
        "Pre-existing illness waiting period: 24 months",
        "Cashless treatment applies only at listed network providers.",
        "Surgery requires prior authorization.",
        "Submit itemized hospital invoice and discharge record.",
        "Not covered: cosmetic procedures and experimental treatment.",
    ]
    draw_pdf(ROOT / "policy_variant_wording.pdf", [policy_variant])
    manifest = {
        "synthetic_only": True,
        "fixtures": [
            {"file": "bill_selectable_text.pdf", "type": "medical_bill", "pages": 1, "expected": {"patient_name": "Alex Morgan", "hospital_name": "North Star General Hospital", "policy_number": "POL-SYN-1001", "total_amount": 145000.0}},
            {"file": "bill_phone_photo.png", "type": "medical_bill", "pages": 1, "expected": {"patient_name": "Alex Morgan", "hospital_name": "North Star General Hospital", "policy_number": "POL-SYN-1001", "total_amount": 145000.0}},
            {"file": "bill_low_light.jpg", "type": "medical_bill", "pages": 1, "expected": {"patient_name": "Alex Morgan", "hospital_name": "North Star General Hospital", "policy_number": "POL-SYN-1001", "total_amount": 145000.0}, "expected_behavior": "correct_or_manual_review"},
            {"file": "bill_skewed_compressed.jpg", "type": "medical_bill", "pages": 1, "expected": {"patient_name": "Alex Morgan", "hospital_name": "North Star General Hospital", "policy_number": "POL-SYN-1001", "total_amount": 145000.0}, "expected_behavior": "correct_or_manual_review"},
            {"file": "bill_multi_page.pdf", "type": "medical_bill", "pages": 2, "expected": {"patient_name": "Alex Morgan", "hospital_name": "North Star General Hospital", "policy_number": "POL-SYN-1001", "total_amount": 145000.0}},
            {"file": "bill_scanned_image_only.pdf", "type": "medical_bill", "pages": 1, "expected": {"patient_name": "Alex Morgan", "hospital_name": "North Star General Hospital", "policy_number": "POL-SYN-1001", "total_amount": 145000.0}, "expected_behavior": "correct_or_manual_review"},
            {"file": "policy_standard.pdf", "type": "policy", "pages": 1, "expected_terms": ["annual_limit", "deductible", "copay_percent", "room_limit_per_day", "waiting_period_months"]},
            {"file": "policy_variant_wording.pdf", "type": "policy", "pages": 1, "expected_behavior": "extract_or_manual_review"},
        ],
    }
    (ROOT / "ground_truth.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"PHASE4_FIXTURES_CREATED count={len(manifest['fixtures'])} synthetic_only={manifest['synthetic_only']}")

if __name__ == "__main__":
    main()
