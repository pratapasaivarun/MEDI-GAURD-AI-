"""Run the live explanation-quality evaluator repeatedly without editing docs."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from evaluation.scripts import score_explanation_quality


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "docs" / "results_tables"
RUNS = 5


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    original_output = score_explanation_quality.OUTPUT
    original_report = score_explanation_quality.REPORT
    first_output = OUTPUT_DIR / "llm_explanation_run_01.json"
    with tempfile.TemporaryDirectory(prefix="mediguard-explanation-repeat-") as temp_dir:
        score_explanation_quality.REPORT = Path(temp_dir) / "report.md"
        score_explanation_quality.REPORT.write_text("", encoding="utf-8")
        if not first_output.exists():
            raise FileNotFoundError(
                "Run 1 raw evaluation output is missing; refusing to label later runs as a five-run set."
            )
        first_result = json.loads(first_output.read_text(encoding="utf-8"))
        print(
            json.dumps({
                "run": 1,
                "raw_result": str(first_output.relative_to(ROOT)),
                "amounts": sum(
                    int(row["checks"]["correct_numbers"]) for row in first_result["results"]
                ),
                "citations": sum(
                    int(row["checks"]["correct_clause_cited"]) for row in first_result["results"]
                ),
                "third_check": sum(
                    int(row["checks"]["no_unsupported_claim"]) for row in first_result["results"]
                ),
                "total": first_result["earned_checks"],
                "denominator": first_result["check_count"],
                "fallbacks": sum(
                    bool(row["template_fallback_used"]) for row in first_result["results"]
                ),
                "note": "Scoring and raw JSON completed in prior wrapper attempt; only report-file update failed.",
            }, ensure_ascii=False),
            flush=True,
        )
        for run_number in range(2, RUNS + 1):
            score_explanation_quality.OUTPUT = (
                OUTPUT_DIR / f"llm_explanation_run_{run_number:02d}.json"
            )
            print(f"Starting explanation-quality run {run_number}/{RUNS}.", flush=True)
            result = score_explanation_quality.main()
            if result != 0:
                raise RuntimeError(f"Explanation-quality run {run_number} returned {result}.")
            saved = json.loads(score_explanation_quality.OUTPUT.read_text(encoding="utf-8"))
            print(
                json.dumps({
                    "run": run_number,
                    "raw_result": str(score_explanation_quality.OUTPUT.relative_to(ROOT)),
                    "amounts": sum(
                        int(row["checks"]["correct_numbers"]) for row in saved["results"]
                    ),
                    "citations": sum(
                        int(row["checks"]["correct_clause_cited"]) for row in saved["results"]
                    ),
                    "third_check": sum(
                        int(row["checks"]["no_unsupported_claim"]) for row in saved["results"]
                    ),
                    "total": saved["earned_checks"],
                    "denominator": saved["check_count"],
                    "fallbacks": sum(
                        bool(row["template_fallback_used"]) for row in saved["results"]
                    ),
                }, ensure_ascii=False),
                flush=True,
            )
    score_explanation_quality.OUTPUT = original_output
    score_explanation_quality.REPORT = original_report
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
