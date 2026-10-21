"""Compare provisional app results with Ollama disabled and enabled.

Every case runs through document upload and the claimant orchestration path in
an isolated temporary database. Only the explanation call changes between
the two modes; the rules/comparison snapshot is captured before either call.
"""
from __future__ import annotations

import json
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "evaluation" / "latest" / "provisional_ollama_equivalence.json"


class Upload:
    def __init__(self, path: Path):
        self.name = path.name
        self._content = path.read_bytes()

    def getvalue(self) -> bytes:
        return self._content


def actor(app, role: str, display: str) -> dict[str, Any]:
    user_id = str(uuid.uuid4())
    with app.db() as conn:
        conn.execute(
            "INSERT INTO users(user_id,email,display_name,role,created_at) VALUES(?,?,?,?,?)",
            (user_id, f"{user_id}@fictional.test", display, role, app.utc_now()),
        )
    return dict(app.get_user(user_id))


def main() -> int:
    os.environ.setdefault("TESSERACT_CMD", r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    with tempfile.TemporaryDirectory(prefix="mediguard-provisional-ollama-") as temp:
        scratch = Path(temp)
        os.environ["MEDIGUARD_DB_PATH"] = str(scratch / "claims.db")
        os.environ["MEDIGUARD_STORAGE_DIR"] = str(scratch / "storage")
        os.environ["CHROMA_DIR"] = str(scratch / "chroma")
        os.environ["MEDIGUARD_TRUSTED_FIXTURES"] = "false"

        import sys
        sys.path.insert(0, str(ROOT))
        from mediguard.ai import agents
        from mediguard.policy import policy_index
        from mediguard.services import application as app
        from mediguard.services.orchestration import assess_claim

        app.init_db()
        claimant = actor(app, "claimant", "Synthetic LLM Check Claimant")
        rows: list[dict[str, Any]] = []
        llm_calls: list[str] = []
        original = agents._ollama_json

        def counted(*args: Any, **kwargs: Any) -> dict[str, Any]:
            llm_calls.append(str(kwargs.get("agent_name", "explanation")))
            return original(*args, **kwargs)

        agents._ollama_json = counted
        try:
            cases: list[tuple[Path, dict[str, Any], str]] = []
            demo_dir = ROOT / "samples" / "demo_cases"
            for name in ("a_match", "b_wrongful_deduction", "c_manual_review"):
                folder = demo_dir / name
                manifest = json.loads((folder / "case.json").read_text(encoding="utf-8"))
                cases.append((folder, manifest, manifest["claim_number"]))
            eval_dir = ROOT / "samples" / "evaluation_cases" / "cases"
            for case in json.loads((ROOT / "samples" / "evaluation_cases" / "ground_truth.json").read_text(encoding="utf-8"))["cases"]:
                if case["group"] != "discrepancy":
                    continue
                folder = eval_dir / case["case_id"]
                manifest = json.loads((folder / "case.json").read_text(encoding="utf-8"))
                cases.append((folder, manifest, manifest["claim_id"]))

            for folder, manifest, claim_number in cases:
                claim_id = app.create_claim(
                    claimant["user_id"], claim_number, manifest.get("patient_name", "Fictional Patient"),
                    manifest.get("hospital_name", "Fictional Hospital"), manifest.get("policy_number", ""),
                    "2026-08-10",
                )
                for filename, kind in (("bill.pdf", "medical_bill"), ("policy.pdf", "policy"), ("settlement.pdf", "settlement")):
                    app.save_document(claim_id, claimant, Upload(folder / filename), kind)
                assessed = assess_claim(app, claim_id, claimant["user_id"])
                comparison = assessed.get("comparison")
                rules = assessed["rules"]
                if comparison is None:
                    raise AssertionError(f"{manifest['case_id']}: claimant app path produced no comparison")
                snapshot = {
                    "status": comparison.status,
                    "payable_amount": str(rules.get("payable_amount")),
                    "expected_insurer_payment": str(comparison.expected_insurer_payment),
                    "actual_insurer_payment": str(comparison.actual_insurer_payment),
                    "possible_difference": str(comparison.possible_difference),
                    "patient_share": str(comparison.expected_patient_share),
                }
                calls_before = len(llm_calls)
                off = agents.explain_comparison(comparison, use_llm=False)
                off_calls = len(llm_calls) - calls_before
                on = agents.explain_comparison(comparison, use_llm=True)
                on_calls = len(llm_calls) - calls_before - off_calls
                unchanged = snapshot == {
                    "status": comparison.status,
                    "payable_amount": str(rules.get("payable_amount")),
                    "expected_insurer_payment": str(comparison.expected_insurer_payment),
                    "actual_insurer_payment": str(comparison.actual_insurer_payment),
                    "possible_difference": str(comparison.possible_difference),
                    "patient_share": str(comparison.expected_patient_share),
                }
                rows.append({
                    "case_id": manifest["case_id"], "kind": "demo" if folder.parent.name == "demo_cases" else "discrepancy",
                    "provisional": True, **snapshot, "decision_unchanged": unchanged,
                    "off_explanation_grounded": agents.validate_comparison_explanation(off, comparison),
                    "on_explanation_grounded": agents.validate_comparison_explanation(on, comparison),
                    "off_mode_model_calls": off_calls, "on_mode_model_calls": on_calls,
                    "manual_review_reasons": list(comparison.review_reasons or []),
                })
        finally:
            agents._ollama_json = original
            policy_index.close_policy_index()

        numerator = sum(bool(row["decision_unchanged"] and row["off_explanation_grounded"] and row["on_explanation_grounded"]) for row in rows)
        output = {
            "dataset": "3 fictional demos + 10 fictional discrepancy cases",
            "path": "claimant upload -> process documents -> provisional assessment/comparison -> explanation",
            "reviewer_confirmation_before_result": False,
            "ollama_host": os.getenv("OLLAMA_HOST", "http://localhost:11434"),
            "cases": rows,
            "decision_and_number_grounding": {"numerator": numerator, "denominator": len(rows), "pass": numerator == len(rows)},
            "model_calls_on": sum(row["on_mode_model_calls"] for row in rows),
            "model_calls_off": sum(row["off_mode_model_calls"] for row in rows),
        }
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps({key: value for key, value in output.items() if key != "cases"}, indent=2))
        print(json.dumps([{
            "case_id": row["case_id"], "status": row["status"], "decision_unchanged": row["decision_unchanged"],
            "grounded_off_on": row["off_explanation_grounded"] and row["on_explanation_grounded"],
            "calls_on": row["on_mode_model_calls"], "reason": row["manual_review_reasons"],
        } for row in rows], indent=2, ensure_ascii=False))
        print(f"Results: {OUTPUT}")
        return 0 if numerator == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
