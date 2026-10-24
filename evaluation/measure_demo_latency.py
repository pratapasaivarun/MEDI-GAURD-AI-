"""Measure service-path first-result latency for the three fictional demos."""
from __future__ import annotations

import importlib.util
import csv
import json
import os
import statistics
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "docs" / "results_tables"
CASE_NAMES = ("a_match", "b_wrongful_deduction", "c_manual_review")
RUNS = 10

sys.path.insert(0, str(ROOT))


def percentile_95(values: list[float]) -> float:
    ordered = sorted(values)
    position = 0.95 * (len(ordered) - 1)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def load_demo_fixture():
    test_path = ROOT / "tests" / "integration" / "test_phase4_demo_cases.py"
    spec = importlib.util.spec_from_file_location("phase4_demo_cases", test_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load app-path fixture from {test_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def tesseract_version() -> str:
    configured = os.getenv("TESSERACT_CMD", r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    completed = subprocess.run(
        [configured, "--version"],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.splitlines()[0]


def main() -> int:
    measurements: dict[str, list[float]] = {case: [] for case in CASE_NAMES}
    run_results: list[dict[str, Any]] = []
    fixture = load_demo_fixture()
    from _pytest.monkeypatch import MonkeyPatch
    from mediguard.ingestion import extraction

    real_get_ocr = extraction._get_ocr.__wrapped__
    for case in CASE_NAMES:
        for run_number in range(1, RUNS + 1):
            with tempfile.TemporaryDirectory(prefix="mediguard-latency-") as tmp:
                monkeypatch = MonkeyPatch()
                try:
                    execute = fixture.run_case.__wrapped__(monkeypatch, Path(tmp))
                    monkeypatch.setattr(extraction, "_get_ocr", real_get_ocr)
                    started = time.perf_counter()
                    result = execute(case)
                    elapsed = time.perf_counter() - started
                    manifest, _normalized, _rules, comparison = result[:4]
                    ocr_evidence = result[7]
                    expected_status = manifest["expected"]["expected_status"]
                    if comparison.status != expected_status:
                        raise RuntimeError(
                            f"{case} run {run_number} status {comparison.status!r} "
                            f"did not match saved fixture status {expected_status!r}"
                        )
                    if case == "c_manual_review" and not any(
                        evidence.method == "tesseract" for evidence in ocr_evidence
                    ):
                        raise RuntimeError(
                            "c_manual_review did not produce Tesseract evidence; OCR-inclusive timing cannot be reported"
                        )
                    measurements[case].append(elapsed)
                    run_results.append({
                        "case": case,
                        "run": run_number,
                        "time_to_first_result_seconds": elapsed,
                        "status": comparison.status,
                        "ocr_evidence_methods": sorted({evidence.method for evidence in ocr_evidence}),
                    })
                finally:
                    monkeypatch.undo()

    summaries = []
    for case in CASE_NAMES:
        values = measurements[case]
        summaries.append({
            "case": case,
            "runs": len(values),
            "median_seconds": statistics.median(values),
            "min_seconds": min(values),
            "max_seconds": max(values),
            "p95_seconds": percentile_95(values),
            "observations_seconds": values,
        })

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "runs_per_case": RUNS,
        "ollama": "off (test fixture points OLLAMA_HOST at 127.0.0.1:1)",
        "tesseract_version": tesseract_version(),
        "measurement": (
            "service path from saving the three demo documents through extraction, "
            "rules, and settlement comparison; excludes app/database initialization"
        ),
        "ocr_included": (
            "Yes. c_manual_review calls the configured Tesseract OCR backend for its scanned bill page; "
            "the runner verifies tesseract evidence on every measured run."
        ),
        "percentile_method": "linear interpolation at index 0.95 * (n - 1)",
        "results": summaries,
        "runs": run_results,
    }
    json_path = OUTPUT_DIR / "latency_raw.json"
    csv_path = OUTPUT_DIR / "table_5_latency.csv"
    json_path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=(
                "case", "runs", "median_seconds", "min_seconds", "max_seconds",
                "p95_seconds", *(f"run_{index}" for index in range(1, RUNS + 1)),
            ),
        )
        writer.writeheader()
        for row in summaries:
            writer.writerow({
                key: row[key]
                for key in ("case", "runs", "median_seconds", "min_seconds", "max_seconds", "p95_seconds")
            } | {
                f"run_{index}": row["observations_seconds"][index - 1]
                for index in range(1, RUNS + 1)
            })
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
