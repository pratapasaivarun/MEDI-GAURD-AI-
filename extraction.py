"""Document extraction and normalization for the Medi Gaurd academic prototype.

The pipeline is intentionally code-first: PyMuPDF and Tesseract OCR handle
common fields. Every field retains provenance and confidence.
"""
from __future__ import annotations

import os
import re
import tempfile
from difflib import SequenceMatcher
from datetime import date
from functools import lru_cache
from dataclasses import asdict, dataclass, field
from pathlib import Path
from statistics import median
from typing import Any


OCR_REVIEW_THRESHOLD = 70.0
SUBMISSION_DEADLINE_DAYS = 30


@dataclass
class Evidence:
    document_id: str
    source_name: str
    page: int
    method: str
    text: str
    confidence: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ExtractedField:
    name: str
    value: Any
    confidence: float
    needs_review: bool
    evidence: list[Evidence] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class NormalizedClaim:
    patient_name: ExtractedField | None = None
    hospital_name: ExtractedField | None = None
    policy_number: ExtractedField | None = None
    claim_number: ExtractedField | None = None
    admission_date: ExtractedField | None = None
    discharge_date: ExtractedField | None = None
    bill_date: ExtractedField | None = None
    diagnosis: ExtractedField | None = None
    total_amount: ExtractedField | None = None
    line_items: list[ExtractedField] = field(default_factory=list)
    source_documents: list[dict[str, Any]] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)
    review_fields: list[str] = field(default_factory=list)
    raw_text_by_page: dict[str, str] = field(default_factory=dict)
    duplicate_candidates: list[dict[str, Any]] = field(default_factory=list)
    billing_anomalies: dict[str, list[dict[str, Any]]] = field(default_factory=lambda: {"duplicates": [], "price_outliers": []})
    multiple_bill_count: int = 0
    aggregation_requires_confirmation: bool = False

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["raw_text_by_page"] = self.raw_text_by_page
        return result


def _evidence(document_id: str, source_name: str, page: int, method: str, text: str, confidence: float) -> Evidence:
    return Evidence(document_id, source_name, page, method, text.strip()[:500], confidence)


def _field(name: str, value: Any, evidence: Evidence | None, confidence: float | None = None) -> ExtractedField | None:
    if value is None or str(value).strip() == "":
        return None
    score = float(confidence if confidence is not None else (evidence.confidence if evidence else 100.0))
    return ExtractedField(name, value, score, score < OCR_REVIEW_THRESHOLD, [evidence] if evidence else [])


def _first_match(patterns: list[str], text: str) -> tuple[str | None, str | None]:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(1).strip(), match.group(0).strip()
    return None, None


def parse_amount(raw: str | None) -> float | None:
    if not raw:
        return None
    cleaned = re.sub(r"[^0-9,.]", "", raw)
    if not cleaned:
        return None
    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(",", "")
    elif cleaned.count(",") == 1 and len(cleaned.rsplit(",", 1)[-1]) == 2:
        cleaned = cleaned.replace(",", ".")
    else:
        cleaned = cleaned.replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def check_submission_deadline(bill_date: date | None, deadline_days: int = SUBMISSION_DEADLINE_DAYS) -> dict[str, Any] | None:
    """Return a claimant warning when a bill is close to or past submission deadline."""
    if not isinstance(bill_date, date):
        return None
    days_elapsed = (date.today() - bill_date).days
    if days_elapsed < 0 or days_elapsed < deadline_days - 7:
        return None
    remaining = deadline_days - days_elapsed
    warning = (
        f"Claim submission deadline has passed by {abs(remaining)} day(s)."
        if remaining < 0
        else f"Claim submission deadline is in {remaining} day(s)."
    )
    return {"days_elapsed": days_elapsed, "warning": warning}


def extract_pdf_text(path: Path, document_id: str, source_name: str) -> tuple[list[Evidence], dict[str, str], int]:
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:
        raise RuntimeError("PyMuPDF is required for PDF extraction. Install requirements.txt first.") from exc

    evidence: list[Evidence] = []
    raw_by_page: dict[str, str] = {}
    with fitz.open(path) as document:
        page_count = len(document)
        for index, page in enumerate(document):
            text = page.get_text("text") or ""
            raw_by_page[str(index + 1)] = text
            if text.strip():
                evidence.append(_evidence(document_id, source_name, index + 1, "pymupdf", text, 100.0))
    return evidence, raw_by_page, page_count


class _TesseractOCR:
    """Small adapter returning the same shape expected by the OCR parser."""
    def predict(self, image_path: str):
        try:
            import pytesseract
            from PIL import Image
            configured_tesseract = os.getenv("TESSERACT_CMD", r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe")
            if Path(configured_tesseract).exists():
                pytesseract.pytesseract.tesseract_cmd = configured_tesseract
        except ImportError as exc:
            raise RuntimeError("Install pytesseract and Tesseract-OCR for image extraction.") from exc
        image = Image.open(image_path)
        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT, config="--psm 6")
        words = []
        heights = []
        for index, (text, confidence) in enumerate(zip(data.get("text", []), data.get("conf", []))):
            text = str(text).strip()
            try:
                confidence = float(confidence)
            except (TypeError, ValueError):
                confidence = -1
            if not text or confidence < 0:
                continue
            left = int(data.get("left", [0] * len(data.get("text", [])))[index] or 0)
            top = int(data.get("top", [0] * len(data.get("text", [])))[index] or 0)
            height = int(data.get("height", [0] * len(data.get("text", [])))[index] or 0)
            if height > 0:
                heights.append(height)
            words.append({"text": text, "confidence": confidence / 100.0, "left": left, "top": top, "height": height})

        # Tesseract returns one token per record. Reconstruct visual lines so
        # parsers receive "Jane Doe" rather than two independent lines.
        line_tolerance = max(8, int((sum(heights) / len(heights) if heights else 16) * 0.55))
        lines = []
        for word in sorted(words, key=lambda item: (item["top"], item["left"])):
            center_y = word["top"] + (word["height"] / 2.0)
            target = next((line for line in lines if abs(center_y - line["center_y"]) <= line_tolerance), None)
            if target is None:
                target = {"center_y": center_y, "words": []}
                lines.append(target)
            target["words"].append(word)
            target["center_y"] = sum(item["top"] + item["height"] / 2.0 for item in target["words"]) / len(target["words"])

        line_texts, line_scores = [], []
        for line in sorted(lines, key=lambda item: item["center_y"]):
            line_words = sorted(line["words"], key=lambda item: item["left"])
            line_texts.append(" ".join(item["text"] for item in line_words))
            line_scores.append(sum(item["confidence"] for item in line_words) / len(line_words))
        return [{"rec_texts": line_texts, "rec_scores": line_scores}]


@lru_cache(maxsize=1)
def _get_ocr():
    """Return the prototype's sole supported OCR backend: Tesseract."""
    return _TesseractOCR()


def _ocr_one_image(ocr, image_path: Path, document_id: str, source_name: str, page: int) -> Evidence | None:
    result = ocr.predict(str(image_path))

    lines: list[str] = []
    confidences: list[float] = []

    def add_candidate(text: Any, score: Any) -> None:
        if text is None or str(text).strip() == "":
            return
        lines.append(str(text).strip())
        try:
            value = float(score)
            confidences.append(value * 100 if value <= 1 else value)
        except (TypeError, ValueError):
            confidences.append(0.0)

    for block in result or []:
        if isinstance(block, dict):
            texts = block.get("rec_texts") or block.get("text") or []
            scores = block.get("rec_scores") or block.get("scores") or []
            for index, text in enumerate(texts):
                add_candidate(text, scores[index] if index < len(scores) else 0.0)
        else:
            for item in block or []:
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    candidate = item[1]
                    if isinstance(candidate, (list, tuple)) and candidate:
                        add_candidate(candidate[0], candidate[1] if len(candidate) > 1 else 0.0)

    text = "\n".join(lines)
    if not text.strip():
        return None
    score = sum(confidences) / len(confidences) if confidences else 0.0
    return _evidence(document_id, source_name, page, "tesseract", text, score)


def extract_image_ocr(path: Path, document_id: str, source_name: str) -> tuple[list[Evidence], dict[str, str], int]:
    """Run the configured OCR backend lazily, rendering scanned PDF pages when necessary."""
    ocr = _get_ocr()
    evidence: list[Evidence] = []
    raw_by_page: dict[str, str] = {}
    if path.suffix.lower() == ".pdf":
        try:
            import fitz
        except ImportError as exc:
            raise RuntimeError("PyMuPDF is required to render scanned PDF pages.") from exc
        with fitz.open(path) as document:
            page_count = len(document)
            for index, page in enumerate(document):
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    tmp_path = Path(tmp.name)
                try:
                    pixmap = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
                    pixmap.save(str(tmp_path))
                    item = _ocr_one_image(ocr, tmp_path, document_id, source_name, index + 1)
                    if item:
                        evidence.append(item)
                        raw_by_page[str(index + 1)] = item.text
                finally:
                    tmp_path.unlink(missing_ok=True)
        return evidence, raw_by_page, page_count

    item = _ocr_one_image(ocr, path, document_id, source_name, 1)
    return ([item] if item else []), ({"1": item.text} if item else {}), 1


def extract_document(path: str | Path, document_id: str, source_name: str) -> tuple[list[Evidence], dict[str, str], int]:
    file_path = Path(path)
    if file_path.suffix.lower() == ".pdf":
        evidence, raw, pages = extract_pdf_text(file_path, document_id, source_name)
        if any(item.text.strip() for item in evidence):
            return evidence, raw, pages
        return extract_image_ocr(file_path, document_id, source_name)
    return extract_image_ocr(file_path, document_id, source_name)


def _infer_line_category(description: str) -> str:
    value = description.lower()
    if any(token in value for token in ("room", "icu", "bed", "accommodation")):
        return "room"
    if any(token in value for token in ("surgery", "procedure", "operation")):
        return "surgery"
    if any(token in value for token in ("medicine", "drug", "pharmacy")):
        return "pharmacy"
    if any(token in value for token in ("diagnostic", "test", "lab", "x-ray", "scan")):
        return "diagnostics"
    if any(token in value for token in ("doctor", "consultation", "physician")):
        return "consultation"
    return "other"



# Matches CPT / procedure codes in two forms:
#   Labelled  – "CPT 99213", "ICD-10 Z00.00", "Procedure Code: 27447"
#   Bare      – standalone 5-digit numeric code, e.g. "27447"
_CPT_PATTERN = re.compile(
    r"\b(?:CPT|ICD[-\s]?(?:10|9)|Procedure\s+Code)[:\s#-]*([A-Z0-9]{2,7}(?:\.[A-Z0-9]{1,4})?)"
    r"|(?<![0-9])([0-9]{5})(?![0-9])",
    re.IGNORECASE,
)


def _extract_cpt_codes(text: str) -> list[str]:
    """Return all unique CPT / ICD procedure codes found in *text*, preserving order."""
    seen: set[str] = set()
    codes: list[str] = []
    for match in _CPT_PATTERN.finditer(text):
        code = (match.group(1) or match.group(2) or "").strip().upper()
        if code and code not in seen:
            seen.add(code)
            codes.append(code)
    return codes


def _extract_line_items(text: str, evidence: list[Evidence]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    pattern = re.compile(r"^\s*([A-Za-z][A-Za-z /&()'_-]{2,80})\s*[:\-]\s*(?:INR|Rs\.?|₹|USD|\$)?\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)\s*$", re.IGNORECASE)
    for line in text.splitlines():
        match = pattern.match(line.strip())
        if not match:
            continue
        description = re.sub(r"\s+", " ", match.group(1)).strip()
        if re.search(r"^(total|grand total|amount payable|net payable|subtotal|discount|tax)\b", description, re.IGNORECASE):
            continue
        if re.search(r"\b(?:policy|claim|member|patient|insured|certificate|uhid|invoice|bill)\b", description, re.IGNORECASE) or re.match(r"^(?:POL|CLM)[-/]", description, re.IGNORECASE):
            continue
        amount = parse_amount(match.group(2))
        if amount is None or amount <= 0:
            continue
        source = next((item for item in evidence if line.strip().lower() in item.text.lower()), evidence[0] if evidence else None)
        confidence = source.confidence if source else 0.0
        # Extract any CPT / ICD-10 procedure code that appears on the same line.
        cpt_codes = _extract_cpt_codes(line)
        items.append({
            "description": description,
            "amount": amount,
            "category": _infer_line_category(description),
            "cpt_codes": cpt_codes,
            "date": None,
            "confidence": confidence,
            "needs_review": confidence < OCR_REVIEW_THRESHOLD,
            "evidence": [source.to_dict()] if source else [],
        })
    return items


def detect_duplicate_charges(line_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for index, left in enumerate(line_items):
        for right in line_items[index + 1:]:
            left_desc = re.sub(r"\W+", " ", str(left.get("description", "")).lower()).strip()
            right_desc = re.sub(r"\W+", " ", str(right.get("description", "")).lower()).strip()
            if left_desc and left_desc == right_desc and money_equal(left.get("amount"), right.get("amount")):
                candidates.append({"left": left, "right": right, "reason": "same normalized description and amount"})
                continue
            # Keep the exact path above intact, then identify likely OCR or
            # phrasing variants with closely matching charges.
            fuzzy_left = re.sub(r"\s+", " ", str(left.get("description", "")).lower()).strip()
            fuzzy_right = re.sub(r"\s+", " ", str(right.get("description", "")).lower()).strip()
            try:
                left_amount = float(left.get("amount"))
                right_amount = float(right.get("amount"))
            except (TypeError, ValueError):
                continue
            ratio = SequenceMatcher(None, fuzzy_left, fuzzy_right).ratio() if fuzzy_left and fuzzy_right else 0.0
            amount_close = max(left_amount, right_amount) > 0 and abs(left_amount - right_amount) <= max(left_amount, right_amount) * 0.05
            if ratio > 0.85 and amount_close:
                candidates.append({"left": left, "right": right, "reason": f"near-duplicate descriptions ({ratio:.2f} similarity) with amounts within 5%"})
    return candidates


def detect_price_outliers(line_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Find unusually high charges within categories large enough to compare."""
    grouped: dict[str, list[tuple[dict[str, Any], float]]] = {}
    for item in line_items:
        try:
            amount = float(item.get("amount"))
        except (TypeError, ValueError):
            continue
        if amount <= 0:
            continue
        category = str(item.get("category") or "other")
        grouped.setdefault(category, []).append((item, amount))

    outliers: list[dict[str, Any]] = []
    for category, entries in grouped.items():
        if len(entries) < 3:
            continue
        category_median = float(median(amount for _, amount in entries))
        if category_median <= 0:
            continue
        for item, amount in entries:
            if amount > 3 * category_median:
                outliers.append({"item": item, "reason": f"amount is {amount / category_median:.2f}x the median for category {category}"})
    return outliers


def money_equal(left: Any, right: Any) -> bool:
    try:
        return round(float(left), 2) == round(float(right), 2)
    except (TypeError, ValueError):
        return False


def normalize_documents(documents: list[dict[str, Any]]) -> NormalizedClaim:
    claim = NormalizedClaim()
    typed_bill_documents = [doc for doc in documents if doc.get("document_type") == "medical_bill"]
    typed_non_policy_documents = [doc for doc in documents if doc.get("document_type") != "policy"]
    # Policy text must never contribute financial claim fields. The legacy test
    # harness omits document_type, so preserve its behavior by treating
    # untyped documents as claim documents.
    claim_documents = typed_bill_documents or typed_non_policy_documents
    all_text = "\n".join(doc.get("text", "") for doc in claim_documents)
    evidence = []
    for doc in claim_documents:
        for item in doc.get("evidence", []):
            evidence.append(Evidence(**item) if isinstance(item, dict) else item)
    best = evidence[0] if evidence else None

    def find(patterns: list[str], name: str, amount: bool = False) -> ExtractedField | None:
        raw, matched = _first_match(patterns, all_text)
        if raw and not amount:
            # OCR can merge adjacent visual lines. Never accept another labeled
            # field as the value of the current field; leave it missing so rules
            # route the claim to Manual Review instead of trusting contamination.
            contamination = re.search(r"(?:patient|hospital|provider|facility|policy|claim|admission|discharge|diagnosis|total|amount)\s*(?:name|no|number|id|date)?\s*[:#-]", raw, flags=re.IGNORECASE)
            if contamination:
                raw = None
                matched = None
        value = parse_amount(raw) if amount else raw
        ev = next((x for x in evidence if matched and matched.lower() in x.text.lower()), best)
        return _field(name, value, ev)

    claim.patient_name = find([r"(?:patient|member|insured)\s*name\s*(?:[:#-]\s*)?([^\n]+)", r"(?<![A-Za-z-])patient\s*(?:[:#-]\s*)?([^\n]+)"], "patient_name")
    claim.hospital_name = find([
        # Digital PDFs commonly place this compound label and its value on
        # adjacent lines; match it before the looser hospital/provider rule.
        r"hospital\s*/\s*provider\s*(?:[:#-]\s*)?([^\n]+)",
        r"(?:hospital|provider|facility)\s*(?:name)?\s*(?:[:#-]\s*)?([^\n]+)",
    ], "hospital_name")
    claim.policy_number = find([
        r"(?:policy|member)\s*(?:no|number|id)\.?\s*(?:of\s+(?:the\s+)?patient\s*)?(?:[:#-]\s*)?([A-Z0-9/-]+)",
        r"policy\s*(?:no|number)\.?\s*(?:of\s+(?:the\s+)?insured\s*)?(?:[:#-]\s*)?([A-Z0-9/-]+)",
    ], "policy_number")
    claim.claim_number = find([r"claim\s*(?:no|number|id)\.?\s*(?:[:#-]\s*)?([A-Z0-9/-]+)"], "claim_number")
    date_value = r"([0-9]{1,4}[./-][0-9]{1,2}[./-][0-9]{1,4}|[0-9]{1,2}\s+[A-Za-z]{3,9}\s+[0-9]{4})"
    claim.admission_date = find([rf"(?:admission(?:\s+date)?|admit|date\s+of\s+admission)\s*(?:[:#-]\s*)?{date_value}"], "admission_date")
    claim.discharge_date = find([rf"(?:discharge(?:\s+date)?|date\s+of\s+discharge)\s*(?:[:#-]\s*)?{date_value}"], "discharge_date")
    claim.bill_date = find([rf"(?:bill|invoice)\s*date\s*(?:[:#-]\s*)?{date_value}"], "bill_date")
    claim.diagnosis = find([r"diagnosis\s*(?:[:#-]\s*)?([^\n]+)"], "diagnosis")
    claim.total_amount = find([
        r"(?:net\s+bill\s+amount|gross\s+bill\s+amount|grand\s+total|total\s+amount|net\s+payable|amount\s+payable|invoice\s+total|bill\s+total|total)\s*(?:[:#-]\s*)?(?:rs\.?|inr|₹|\$)?\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)",
        r"(?:net\s+bill\s+amount|gross\s+bill\s+amount|grand\s+total|total\s+amount|net\s+payable|amount\s+payable|invoice\s+total|bill\s+total|total)\s*(?:[:#-]\s*)?([0-9][0-9,]*(?:\.[0-9]{1,2})?)\s*(?:rs\.?|inr|₹|\$)?",
    ], "total_amount", amount=True)
    claim.line_items = _extract_line_items(all_text, evidence)
    claim.duplicate_candidates = detect_duplicate_charges(claim.line_items)
    claim.billing_anomalies = {
        "duplicates": claim.duplicate_candidates,
        "price_outliers": detect_price_outliers(claim.line_items),
    }
    claim.multiple_bill_count = len(typed_bill_documents)
    claim.aggregation_requires_confirmation = len(typed_bill_documents) > 1
    # Do not infer total_amount from the largest currency amount. Policy limits
    # and line items can be larger than the actual bill total; missing explicit
    # totals must remain Manual Review.

    for required in ("patient_name", "hospital_name", "total_amount"):
        if getattr(claim, required) is None:
            claim.missing_fields.append(required)
    for name in ("patient_name", "hospital_name", "policy_number", "claim_number", "admission_date", "discharge_date", "bill_date", "diagnosis", "total_amount"):
        item = getattr(claim, name)
        if item and item.needs_review:
            claim.review_fields.append(name)

    claim.source_documents = [{k: v for k, v in doc.items() if k not in {"text", "evidence"}} for doc in documents]
    claim.raw_text_by_page = {f"{doc.get('document_id')}:{page}": text for doc in documents for page, text in doc.get("raw_by_page", {}).items()}
    return claim


def run_extraction(documents: list[dict[str, Any]]) -> dict[str, Any]:
    normalized = normalize_documents(documents)
    return normalized.to_dict()
