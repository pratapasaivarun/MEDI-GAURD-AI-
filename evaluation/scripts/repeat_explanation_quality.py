"""Run the live explanation-quality evaluator once and preserve its raw output."""
from __future__ import annotations

import json
from pathlib import Path

from evaluation.scripts import score_explanation_quality


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "docs" / "results_tables"
OUTPUT = OUTPUT_DIR / "llm_explanation_single_run.json"
REPORT = OUTPUT_DIR / "llm_explanation_single_run.md"


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("", encoding="utf-8")
    original_output = score_explanation_quality.OUTPUT
    original_report = score_explanation_quality.REPORT
    try:
        score_explanation_quality.OUTPUT = OUTPUT
        score_explanation_quality.REPORT = REPORT
        result = score_explanation_quality.main()
        if result != 0:
            return result
        saved = json.loads(OUTPUT.read_text(encoding="utf-8"))
        saved["evaluation_type"] = "live LLM, single run, variable"
        OUTPUT.write_text(json.dumps(saved, indent=2) + "\n", encoding="utf-8")
        report_text = REPORT.read_text(encoding="utf-8")
        report_text = report_text.replace(
            "`evaluation/latest/explanation_quality.json`",
            "`docs/results_tables/llm_explanation_single_run.json`",
        )
        REPORT.write_text(
            "**Run classification: live LLM, single run, variable. No aggregate is claimed.**\n\n"
            + report_text.lstrip().rstrip()
            + "\n",
            encoding="utf-8",
        )
        summary = {
            "evaluation": saved["evaluation_type"],
            "raw_result": str(OUTPUT.relative_to(ROOT)),
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
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    finally:
        score_explanation_quality.OUTPUT = original_output
        score_explanation_quality.REPORT = original_report


if __name__ == "__main__":
    raise SystemExit(main())
