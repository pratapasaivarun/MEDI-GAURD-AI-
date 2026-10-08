"""Canonical category names shared by extraction and claim calculations."""
from __future__ import annotations

ROOM_CATEGORY = "ROOM"
ROOM_RENT_CATEGORY = "ROOM_RENT"
ACCOMMODATION_CATEGORY = "ACCOMMODATION"
DOCTOR_NURSING_CATEGORY = "DOCTOR_NURSING"
NURSING_CATEGORY = "NURSING"
DOCTOR_CATEGORY = "DOCTOR"
CONSULTATION_CATEGORY = "CONSULTATION"
ADMISSION_CATEGORY = "ADMISSION"
OTHER_CATEGORY = "OTHER"


def normalize_category(value: object, default: str = OTHER_CATEGORY) -> str:
    """Return an uppercase category key, independent of input casing."""
    normalized = str(value or "").strip().replace(" ", "_").replace("-", "_").upper()
    return normalized or default
