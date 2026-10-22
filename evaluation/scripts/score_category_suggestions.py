"""Measure BGE-small top-1 category prototype accuracy on reviewed labels.

The script deliberately scores only valid, explicit line-item category labels.
It does not tune prototypes or fill missing labels. Adversarial cases without
category annotations are reported as not verifiable.
"""
from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
GROUND_TRUTH = ROOT / "samples" / "evaluation_cases" / "ground_truth.json"
PROTOTYPES = ROOT / "config" / "category_prototypes.yaml"
ADVERSARIAL = ROOT / "samples" / "adversarial_cases" / "casebook.json"
RESULT_PATH = ROOT / "evaluation" / "latest" / "category_suggestion_evaluation.json"


def _cosine(left: list[float], right: list[float]) -> float:
    denominator = math.sqrt(sum(x * x for x in left) * sum(y * y for y in right))
    return sum(x * y for x, y in zip(left, right)) / denominator if denominator else 0.0


def score() -> dict[str, Any]:
    with GROUND_TRUTH.open(encoding="utf-8") as handle:
        cases = json.load(handle)["cases"]
    with PROTOTYPES.open(encoding="utf-8") as handle:
        prototypes: dict[str, str] = yaml.safe_load(handle)

    allowed = set(prototypes)
    rows = [
        (case["case_id"], item)
        for case in cases
        for item in (case.get("expected_line_items") or [])
        if isinstance(item, dict) and item.get("category")
    ]
    descriptions = list(dict.fromkeys(str(item.get("description") or "") for _, item in rows))

    from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

    embed = SentenceTransformerEmbeddingFunction(model_name="BAAI/bge-small-en-v1.5")
    prototype_vectors = embed(list(prototypes.values()))
    description_vectors = dict(zip(descriptions, embed(descriptions)))

    evaluated = []
    invalid_labels = []
    for case_id, item in rows:
        expected = str(item["category"]).upper()
        if expected not in allowed:
            invalid_labels.append({"case_id": case_id, "expected": expected})
            continue
        vector = description_vectors[str(item.get("description") or "")]
        similarities = [_cosine(vector, prototype) for prototype in prototype_vectors]
        predicted = list(prototypes)[max(range(len(similarities)), key=similarities.__getitem__)]
        evaluated.append({"case_id": case_id, "description": item.get("description"),
                          "expected": expected, "predicted": predicted, "match": predicted == expected})

    adversarial_labels = 0
    if ADVERSARIAL.exists():
        with ADVERSARIAL.open(encoding="utf-8") as handle:
            adversarial = json.load(handle)
        adversarial_cases = adversarial.get("cases", adversarial) if isinstance(adversarial, dict) else adversarial
        adversarial_labels = sum(
            1 for case in adversarial_cases
            for item in (case.get("expected_line_items") or [])
            if isinstance(item, dict) and item.get("category")
        )

    correct = sum(row["match"] for row in evaluated)
    result = {
        "method": "BGE-small cosine similarity against fixed config prototypes; top-1",
        "threshold": 0.90,
        "correct": correct,
        "denominator": len(evaluated),
        "accuracy": correct / len(evaluated) if evaluated else None,
        "label_distribution": dict(Counter(str(item["category"]).upper() for _, item in rows)),
        "invalid_labels": invalid_labels,
        "adversarial_category_labels": adversarial_labels,
        "enabled": bool(evaluated) and correct / len(evaluated) >= 0.90 and not invalid_labels,
        "cases": evaluated,
    }
    return result


if __name__ == "__main__":
    report = score()
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"BGE-small category prototype score: {report['correct']}/{report['denominator']}")
    print(f"Invalid category labels: {len(report['invalid_labels'])}; adversarial category labels: {report['adversarial_category_labels']}")
    print(f"Suggester enabled: {report['enabled']}; details: {RESULT_PATH.relative_to(ROOT)}")
