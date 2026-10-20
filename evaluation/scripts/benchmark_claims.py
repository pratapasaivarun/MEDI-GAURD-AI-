"""Measure the ten explanation-evaluation claims with Ollama off and on."""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from statistics import mean, median
from typing import Any

import psutil
import requests

from evaluation.run_all import CASES_DIR, LABELS_PATH, build_claim
from mediguard.ai.agents import OLLAMA_HOST, OLLAMA_MODEL, explain_comparison
from mediguard.engine.comparison import compare
from mediguard.engine.models import Clause
from mediguard.ingestion.settlement import parse_settlement

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "evaluation" / "latest" / "performance.json"


class MemorySampler:
    def __init__(self) -> None:
        self.stop_event = threading.Event()
        self.app_peak = 0
        self.ollama_peak = 0
        self._thread = threading.Thread(target=self._sample, daemon=True)

    def _sample(self) -> None:
        app = psutil.Process(os.getpid())
        while not self.stop_event.is_set():
            try:
                self.app_peak = max(self.app_peak, app.memory_info().rss)
            except psutil.Error:
                pass
            ollama_rss = 0
            for process in psutil.process_iter(["name", "memory_info"]):
                try:
                    name = (process.info.get("name") or "").casefold()
                    if "ollama" in name or "llama" in name:
                        ollama_rss += process.info["memory_info"].rss
                except (psutil.Error, KeyError, TypeError):
                    continue
            self.ollama_peak = max(self.ollama_peak, ollama_rss)
            self.stop_event.wait(0.2)

    def __enter__(self) -> "MemorySampler":
        self._thread.start()
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.stop_event.set()
        self._thread.join()


def _run_case(row: dict[str, Any], use_llm: bool) -> tuple[float, dict[str, Any]]:
    started = time.perf_counter()
    claim, terms = build_claim(row)
    settlement_path = CASES_DIR / row["case_id"] / "settlement.pdf"
    settlement = parse_settlement(settlement_path.read_bytes(), settlement_path.name)
    comparison = compare(claim, settlement, terms)
    category = next(item for item in comparison.categories if item.category == "DEDUCTIBLE")
    category.clause = Clause(f"Deductible: INR {row['deductible']}", 1)
    snapshot = (
        comparison.status,
        str(comparison.expected_patient_share),
        str(comparison.actual_patient_share),
        str(comparison.possible_difference),
        str(comparison.expected_insurer_payment),
        str(comparison.actual_insurer_payment),
    )
    explanation = explain_comparison(comparison, use_llm=use_llm)
    unchanged = snapshot == (
        comparison.status,
        str(comparison.expected_patient_share),
        str(comparison.actual_patient_share),
        str(comparison.possible_difference),
        str(comparison.expected_insurer_payment),
        str(comparison.actual_insurer_payment),
    )
    return time.perf_counter() - started, {
        "case": row["case_id"], "status": comparison.status,
        "possible_difference": str(comparison.possible_difference),
        "comparison_unchanged": unchanged,
        "explanation_chars": len(explanation),
    }


def main() -> int:
    labels = json.loads(LABELS_PATH.read_text(encoding="utf-8"))
    cases = [row for row in labels["cases"] if row["group"] == "discrepancy"][:10]
    if len(cases) != 10:
        raise SystemExit("The benchmark requires the ten fictional discrepancy cases.")
    tag_response = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=3)
    tag_response.raise_for_status()
    if not any(item.get("name") == OLLAMA_MODEL for item in tag_response.json().get("models", [])):
        raise SystemExit(f"Configured Ollama model is unavailable: {OLLAMA_MODEL}")

    output: dict[str, Any] = {
        "dataset": "first 10 discrepancy cases in samples/evaluation_cases/ground_truth.json",
        "synthetic_only": True,
        "ollama_model": OLLAMA_MODEL,
        "ollama_mode": "warm model; warm-up/load time excluded from per-claim timings",
    }
    for name, use_llm in (("off", False), ("on", True)):
        durations: list[float] = []
        rows: list[dict[str, Any]] = []
        with MemorySampler() as sampler:
            for case in cases:
                elapsed, result = _run_case(case, use_llm)
                durations.append(elapsed)
                rows.append({**result, "seconds": round(elapsed, 3)})
        output[name] = {
            "case_count": len(rows),
            "total_seconds": round(sum(durations), 3),
            "mean_seconds_per_claim": round(mean(durations), 3),
            "median_seconds_per_claim": round(median(durations), 3),
            "min_seconds_per_claim": round(min(durations), 3),
            "max_seconds_per_claim": round(max(durations), 3),
            "peak_app_rss_mib": round(sampler.app_peak / (1024 ** 2), 1),
            "peak_ollama_rss_mib": round(sampler.ollama_peak / (1024 ** 2), 1),
            "cases": rows,
        }
    output["decision_outputs_identical"] = all(
        off["status"] == on["status"]
        and off["possible_difference"] == on["possible_difference"]
        and off["comparison_unchanged"] and on["comparison_unchanged"]
        for off, on in zip(output["off"]["cases"], output["on"]["cases"])
    )
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in output.items() if key not in {"off", "on"}}, indent=2))
    for mode in ("off", "on"):
        print(mode, json.dumps({key: value for key, value in output[mode].items() if key != "cases"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
