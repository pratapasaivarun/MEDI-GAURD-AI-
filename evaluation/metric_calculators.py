"""Metric functions for the MediGuard evaluation annotation formats."""
from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from statistics import mean, median
from typing import Any

PENDING = "Not Evaluated — Ground Truth/Data Required"


def _edit_distance(reference: list[Any], hypothesis: list[Any]) -> int:
    previous = list(range(len(hypothesis) + 1))
    for row, ref in enumerate(reference, start=1):
        current = [row]
        for col, hyp in enumerate(hypothesis, start=1):
            current.append(min(current[-1] + 1, previous[col] + 1,
                               previous[col - 1] + (ref != hyp)))
        previous = current
    return previous[-1]


def character_error_rate(reference: str, hypothesis: str) -> float | None:
    normalize = lambda value: " ".join(unicodedata.normalize("NFC", value).split())
    reference = normalize(reference)
    if not reference:
        return None
    return _edit_distance(list(reference), list(normalize(hypothesis))) / len(reference)


def word_error_rate(reference: str, hypothesis: str) -> float | None:
    def tokenize(value: str):
        normalized = " ".join(unicodedata.normalize("NFC", value).split()).casefold()
        return re.findall(r"[\w]+(?:['’][\w]+)?", normalized)
    ref = tokenize(reference)
    if not ref:
        return None
    return _edit_distance(ref, tokenize(hypothesis)) / len(ref)


def retrieval_scores(retrieval_queries: list[dict[str, Any]], retrieved_by_query: dict[str, list[str]], ks=(1, 3, 5)) -> dict[str, Any]:
    rows = []
    precision = defaultdict(list)
    recall = defaultdict(list)
    for item in retrieval_queries:
        query_id = str(item.get("query_id") or "")
        relevant = set(item.get("relevant_clause_ids") or [])
        retrieved = retrieved_by_query.get(query_id, [])
        if not query_id or not relevant:
            continue
        row = {"query_id": query_id, "relevant_count": len(relevant)}
        for k in ks:
            hits = len(set(retrieved[:k]) & relevant)
            row[f"precision_at_{k}"] = hits / k
            precision[k].append(hits / k)
            if k in {3, 5}:
                row[f"recall_at_{k}"] = hits / len(relevant)
                recall[k].append(hits / len(relevant))
        rows.append(row)
    return {
        "annotated_query_count": len(rows),
        "precision_at_1": mean(precision[1]) if precision[1] else PENDING,
        "precision_at_3": mean(precision[3]) if precision[3] else PENDING,
        "precision_at_5": mean(precision[5]) if precision[5] else PENDING,
        "recall_at_3": mean(recall[3]) if recall[3] else PENDING,
        "recall_at_5": mean(recall[5]) if recall[5] else PENDING,
        "per_query": rows,
    }


def decision_scores(rows: list[dict[str, Any]], expected_key="expected_decision", actual_key="actual_decision") -> dict[str, Any]:
    labels = ("approved", "partially_approved", "rejected", "manual_review")
    observed = [(row.get(expected_key), row.get(actual_key)) for row in rows
                if row.get(expected_key) in labels and row.get(actual_key) in labels]
    matrix = {expected: {actual: 0 for actual in labels} for expected in labels}
    for expected, actual in observed:
        matrix[expected][actual] += 1
    correct = sum(expected == actual for expected, actual in observed)
    return {"cases_scored": len(observed), "correct": correct,
            "accuracy": correct / len(observed) if observed else PENDING,
            "accuracy_percent": 100 * correct / len(observed) if observed else PENDING,
            "confusion_matrix_expected_rows_actual_columns": matrix}


def boolean_support_score(reviews: list[dict[str, Any]], key: str) -> dict[str, Any]:
    scored = [row[key] for row in reviews if isinstance(row.get(key), bool)]
    hits = sum(scored)
    return {"scored": len(scored), "supported": hits,
            "percentage": 100 * hits / len(scored) if scored else PENDING}


def appeal_rubric_score(reviews: list[dict[str, Any]]) -> dict[str, Any]:
    fields = ("factual_consistency", "policy_consistency", "disputed_items_relevant",
              "completeness", "fabrication_absent", "clarity", "usefulness")
    complete = [row for row in reviews if all(isinstance(row.get(field), int)
                                               and not isinstance(row.get(field), bool)
                                               and 0 <= row[field] <= 2 for field in fields)]
    per_field = {
        field: mean([row[field] for row in complete]) if complete else PENDING
        for field in fields
    }
    per_letter = [mean([row[field] for field in fields]) for row in complete]
    return {"letters_scored": len(complete), "scale": "0-2 per rubric item; maximum mean 2",
            "mean_overall": mean(per_letter) if per_letter else PENDING,
            "mean_by_rubric_item": per_field}


def latency_summary(seconds: list[float]) -> dict[str, float | int | None]:
    if not seconds:
        return {"runs": 0, "mean_seconds": None, "median_seconds": None,
                "min_seconds": None, "max_seconds": None}
    return {"runs": len(seconds), "mean_seconds": mean(seconds),
            "median_seconds": median(seconds), "min_seconds": min(seconds),
            "max_seconds": max(seconds)}
