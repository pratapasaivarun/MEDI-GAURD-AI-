"""Policy-edition comparison utility; out of scope for the academic prototype."""
from __future__ import annotations

import difflib
import re
from typing import Any


def compare_policy_text(old_text: str, new_text: str) -> dict[str, Any]:
    old_lines = [line.strip() for line in (old_text or "").splitlines() if line.strip()]
    new_lines = [line.strip() for line in (new_text or "").splitlines() if line.strip()]
    matcher = difflib.SequenceMatcher(a=old_lines, b=new_lines)
    added: list[str] = []
    removed: list[str] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag in {"replace", "delete"}:
            removed.extend(old_lines[i1:i2])
        if tag in {"replace", "insert"}:
            added.extend(new_lines[j1:j2])
    return {"added": added, "removed": removed, "added_count": len(added), "removed_count": len(removed), "similarity_percent": round(matcher.ratio() * 100, 2), "unified_diff": list(difflib.unified_diff(old_lines, new_lines, fromfile="older_policy", tofile="newer_policy", lineterm="")), "changed_terms": compare_terms(old_text, new_text)}


def compare_terms(old_text: str, new_text: str) -> list[dict[str, Any]]:
    patterns = {"annual_limit": r"(?:annual policy limit|policy limit)\s*[:=-]?\s*(?:inr|rs\.?|₹)?\s*([0-9,]+)", "deductible": r"deductible\s*[:=-]?\s*(?:inr|rs\.?|₹)?\s*([0-9,]+)", "copayment": r"copayment\s*[:=-]?\s*([0-9]+(?:\.[0-9]+)?)\s*percent", "waiting_period": r"waiting period\s*[:=-]?\s*([^\n.]+)"}
    changes = []
    for name, pattern in patterns.items():
        old, new = re.search(pattern, old_text or "", re.I), re.search(pattern, new_text or "", re.I)
        old_value, new_value = old.group(1).strip() if old else None, new.group(1).strip() if new else None
        if old_value != new_value:
            changes.append({"term": name, "older": old_value, "newer": new_value})
    return changes
