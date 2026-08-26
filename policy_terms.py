"""Deterministic extraction of financial policy terms from policy evidence."""
from __future__ import annotations

import re
from decimal import Decimal
from typing import Any, Iterable


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    return value

from rules import PolicyTerms

_MONEY = r"(?:INR|Rs\.?|₹)?\s*([0-9][0-9,]*(?:\.\d+)?)"


def _number(value: str) -> Decimal:
    return Decimal(value.replace(",", "").strip())


def _evidence_rows(source: Any) -> list[dict[str, Any]]:
    if isinstance(source, str):
        return [{"text": source, "page": None, "source_name": "policy"}]
    rows = []
    for item in source or []:
        if hasattr(item, "to_dict"):
            item = item.to_dict()
        rows.append({
            "text": str(item.get("text", "")),
            "page": item.get("page"),
            "source_name": item.get("source_name", "policy"),
        })
    return rows


def _find(rows: list[dict[str, Any]], patterns: list[str], label: str, value_cast) -> dict[str, Any] | None:
    for row in rows:
        text = row["text"]
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                return {
                    "term": label,
                    "value": value_cast(match.group(1)),
                    "confidence": 0.95,
                    "source_text": text.strip(),
                    "source_page": row.get("page"),
                    "source_name": row.get("source_name", "policy"),
                    "method": "deterministic_regex",
                }
    return None


def extract_policy_terms(source: Any) -> dict[str, Any]:
    """Extract terms without an LLM so calculations remain reproducible."""
    rows = _evidence_rows(source)
    terms: dict[str, dict[str, Any]] = {}
    terms["annual_limit"] = _find(rows, [rf"annual\s+(?:policy\s+)?limit\s*[:\-]?\s*{_MONEY}"], "annual_limit", _number)
    terms["deductible"] = _find(rows, [rf"deductible\s*[:\-]?\s*{_MONEY}"], "deductible", _number)
    terms["copay_percent"] = _find(rows, [r"copay(?:ment)?\s*[:\-]?\s*([0-9]+(?:\.\d+)?)\s*(?:%|percent)"], "copay_percent", Decimal)
    terms["room_limit_per_day"] = _find(rows, [rf"room\s+(?:and\s+board\s+)?limit\s*[:\-]?\s*{_MONEY}\s*(?:per\s*day)?"], "room_limit_per_day", _number)
    terms["waiting_period_months"] = _find(rows, [r"waiting\s+period\s*[:\-]?\s*([0-9]+)\s*months?"], "waiting_period_months", int)
    # Capture simple category-specific limits such as "Surgery sub-limit: INR 100000".
    sub_limit_rows = []
    for row in rows:
        match = re.search(r"([A-Za-z][A-Za-z /-]{2,40})\s+sub[- ]?limit\s*[:\-]?\s*" + _MONEY, row["text"], flags=re.IGNORECASE)
        if match:
            category = re.sub(r"\s+", " ", match.group(1)).strip().lower()
            sub_limit_rows.append({"category": category, "value": _number(match.group(2)), "source_text": row["text"].strip(), "source_page": row.get("page"), "source_name": row.get("source_name", "policy")})
    if sub_limit_rows:
        terms["sub_limits"] = {"term": "sub_limits", "value": {item["category"]: str(item["value"]) for item in sub_limit_rows}, "confidence": 0.90, "source_text": "\n".join(item["source_text"] for item in sub_limit_rows[:5]), "source_page": sub_limit_rows[0].get("source_page"), "source_name": sub_limit_rows[0].get("source_name", "policy"), "method": "deterministic_regex"}
    combined_text = "\n".join(row["text"] for row in rows)

    if re.search(r"pre[- ]?authorization\s+required|required\s+pre[- ]?authorization|required\s+pre[- ]?approval|prior approval", combined_text, re.IGNORECASE):
        terms["preauthorization_required"] = {"term": "preauthorization_required", "value": True, "confidence": 0.90, "source_text": "pre-authorization requirement detected", "source_page": None, "source_name": rows[0].get("source_name", "policy"), "method": "deterministic_regex"}
    if re.search(r"network hospitals? only|in[- ]network only|network provider required", combined_text, re.IGNORECASE):
        terms["network_required"] = {"term": "network_required", "value": True, "confidence": 0.90, "source_text": "network restriction detected", "source_page": None, "source_name": rows[0].get("source_name", "policy"), "method": "deterministic_regex"}
    exclusions = [row["text"].strip() for row in rows if re.search(r"exclusion|excluded|non[- ]payable", row["text"], re.IGNORECASE)]
    if exclusions:
        terms["exclusions"] = {"term": "exclusions", "value": exclusions[:20], "confidence": 0.85, "source_text": "\n".join(exclusions[:3]), "source_page": rows[0].get("page"), "source_name": rows[0].get("source_name", "policy"), "method": "deterministic_keyword"}

    present = {key: value for key, value in terms.items() if value is not None}
    missing = [key for key, value in terms.items() if value is None]
    validation_errors: list[str] = []
    for name in ("annual_limit", "deductible", "copay_percent", "room_limit_per_day"):
        item = present.get(name)
        if item is not None and Decimal(str(item["value"])) < 0:
            validation_errors.append(f"{name} must not be negative")
    copay = present.get("copay_percent")
    if copay is not None and not (Decimal("0") <= Decimal(str(copay["value"])) <= Decimal("100")):
        validation_errors.append("copay_percent must be between 0 and 100")
    confidence = min((item["confidence"] for item in present.values()), default=0.0)
    if validation_errors:
        confidence = 0.0
    policy_terms = PolicyTerms(
        annual_limit=present["annual_limit"]["value"] if "annual_limit" in present else None,
        deductible=present["deductible"]["value"] if "deductible" in present else None,
        copay_percent=present["copay_percent"]["value"] if "copay_percent" in present else None,
        room_limit_per_day=present["room_limit_per_day"]["value"] if "room_limit_per_day" in present else None,
        waiting_period_months=present["waiting_period_months"]["value"] if "waiting_period_months" in present else None,
        sub_limits={key: Decimal(str(value)) for key, value in present.get("sub_limits", {}).get("value", {}).items()} if present.get("sub_limits") else {},
    )
    return {
        "terms": policy_terms,
        "terms_json": {key: {**value, "value": _json_value(value["value"])} for key, value in present.items()},
        "missing_terms": missing,
        "validation_errors": validation_errors,
        "confidence": confidence,
        "source_count": len(rows),
    }


def terms_from_json(payload: dict[str, Any] | None) -> tuple[PolicyTerms, list[str], float]:
    payload = payload or {}
    def value(name: str):
        item = payload.get(name)
        return item.get("value") if item else None
    missing = [name for name in ("annual_limit", "deductible", "copay_percent") if name not in payload]
    confidence = min((float(item.get("confidence", 0)) for item in payload.values()), default=0.0)
    for name in ("annual_limit", "deductible", "copay_percent", "room_limit_per_day"):
        raw = value(name)
        if raw is not None and Decimal(str(raw)) < 0:
            missing.append(f"invalid_{name}")
    copay = value("copay_percent")
    if copay is not None and not (Decimal("0") <= Decimal(str(copay)) <= Decimal("100")):
        missing.append("invalid_copay_percent")
    def decimal_value(name: str):
        raw = value(name)
        return Decimal(str(raw)) if raw is not None else None
    raw_waiting = value("waiting_period_months")
    raw_sub_limits = value("sub_limits") or {}
    if not isinstance(raw_sub_limits, dict):
        raw_sub_limits = {}
    return PolicyTerms(
        annual_limit=decimal_value("annual_limit"), deductible=decimal_value("deductible"), copay_percent=decimal_value("copay_percent"),
        room_limit_per_day=decimal_value("room_limit_per_day"), waiting_period_months=int(raw_waiting) if raw_waiting is not None else None,
        sub_limits={str(key): Decimal(str(raw)) for key, raw in raw_sub_limits.items()},
    ), missing, confidence
