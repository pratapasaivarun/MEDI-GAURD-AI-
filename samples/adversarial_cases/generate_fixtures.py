"""Render the fixed synthetic casebook as PDFs without running any parser."""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parent
CASES_DIR = ROOT / "cases"


def _text_pdf(path: Path, text: str) -> None:
    pdf = canvas.Canvas(str(path), pagesize=letter)
    width, height = letter
    y = height - 54
    for line in text.splitlines():
        pdf.drawString(48, y, line[:110])
        y -= 22
        if y < 48:
            pdf.showPage()
            y = height - 54
    pdf.save()


def _scan_pdf(path: Path, text: str) -> None:
    image = Image.new("L", (360, 460), color=250)
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    y = 18
    for line in text.splitlines():
        draw.text((18, y), line[:50], fill=35, font=font)
        y += 28
    image.save(path, "PDF", resolution=90.0)


def main() -> None:
    casebook = json.loads((ROOT / "casebook.json").read_text(encoding="utf-8"))
    for case in casebook["cases"]:
        folder = CASES_DIR / case["case_id"]
        folder.mkdir(parents=True, exist_ok=True)
        bill_path = folder / "bill.pdf"
        if case.get("bill_representation") == "low_resolution_scan":
            _scan_pdf(bill_path, case["bill_text"])
        else:
            _text_pdf(bill_path, case["bill_text"])
        _text_pdf(folder / "settlement.pdf", case["settlement_text"])
        (folder / "expected-results.json").write_text(
            json.dumps({"case_id": case["case_id"], "expected": case["expected"], "hand_label": case["hand_label"]}, indent=2) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
