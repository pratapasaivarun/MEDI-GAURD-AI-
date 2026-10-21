"""Run fictional evaluation and adversarial cases through claimant orchestration.

The first pass is always unconfirmed. A second pass uses the committed,
source-page-reviewed synthetic terms only to compare provisional amounts.
Adversarial cases contain no policy by design, so their expected decision is
not labeled; the safe app expectation is a reasoned Manual Review.
"""
from __future__ import annotations

import json
import gc
import os
import tempfile
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "evaluation" / "latest" / "provisional_app_path.json"


class Upload:
    def __init__(self, path: Path):
        self.name = path.name
        self.content = path.read_bytes()

    def getvalue(self) -> bytes:
        return self.content


def _plain(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_plain(item) for item in value]
    return value


def _create_actor(app, role: str, label: str) -> dict:
    user_id = str(uuid.uuid4())
    with app.db() as connection:
        connection.execute(
            "INSERT INTO users(user_id,email,display_name,role,created_at) VALUES(?,?,?,?,?)",
            (user_id, f"{user_id}@fictional.test", label, role, app.utc_now()),
        )
    return dict(app.get_user(user_id))


def _review_terms(app, version_id: str, reviewer_id: str, manifest: dict) -> None:
    terms = manifest["policy_terms_reviewer_confirmed"]
    page = int(terms.get("source_page", 1))
    values = {key: value for key, value in terms.items() if key != "source_page"}
    source_pages = {key: page for key in values}
    status = app.save_policy_terms_review(version_id, reviewer_id, values, source_pages, {})
    if status != "confirmed":
        raise AssertionError(f"Reviewer terms for {manifest['case_id']} did not confirm: {status}")


def _run_one(app, assess_claim, claimant: dict, reviewer: dict, case_dir: Path,
             registration_number: str, expected: dict, manifest: dict | None,
             include_policy: bool) -> dict[str, Any]:
    claim_id = app.create_claim(
        claimant["user_id"], registration_number, f"Fictional {registration_number}",
        "Fictional Evaluation Hospital", "", "2026-08-10",
    )
    for filename in ("bill.pdf", "policy.pdf", "settlement.pdf") if include_policy else ("bill.pdf", "settlement.pdf"):
        path = case_dir / filename
        app.save_document(claim_id, claimant, Upload(path), "policy" if filename == "policy.pdf" else "medical_bill" if filename == "bill.pdf" else "settlement")
    initial = assess_claim(app, claim_id, claimant["user_id"])
    rules = initial["rules"]
    comparison = initial.get("comparison")
    reasons = list(rules.get("warnings") or [])
    reasons.extend(str(item.get("reason")) for item in rules.get("policy_terms_issues") or [] if item.get("reason"))
    if comparison:
        reasons.extend(getattr(comparison, "review_reasons", []) or [])
    actual_payable = rules.get("payable_amount")
    payable_range = rules.get("payable_range")
    actual_status = comparison.status if comparison else rules.get("status")
    expected_payable = expected.get("expected_payable")
    if payable_range:
        low, high = float(payable_range["lower"]), float(payable_range["upper"])
        amount_match = expected_payable is None or low <= float(expected_payable) <= high
        shown_estimate = {"range": [low, high]}
    else:
        amount_match = expected_payable is None or (actual_payable is not None and abs(float(actual_payable) - float(expected_payable)) < 0.01)
        shown_estimate = {"amount": _plain(actual_payable)} if actual_payable is not None else None
    mismatch_causes = []
    if expected.get("expected_status") is not None and actual_status != expected.get("expected_status"):
        mismatch_causes.append("decision status differs from the hand-labeled expected status")
    if not amount_match:
        mismatch_causes.append("expected payable is outside the displayed estimate")
    row: dict[str, Any] = {
        "case_id": expected["case_id"], "expected": expected.get("expected_status", "not labeled for decision; extraction-only fixture"),
        "actual": actual_status, "result_shown": bool(rules), "provisional": True,
        "expected_payable": expected.get("expected_payable"), "provisional_payable": _plain(actual_payable),
        "provisional_payable_range": _plain(payable_range),
        "displayed_estimate": shown_estimate,
        "amount_or_range_shown": shown_estimate is not None,
        "mismatch_causes": mismatch_causes,
        "provisional_difference": _plain(getattr(comparison, "possible_difference", None)),
        "policy_terms_missing": rules.get("policy_terms_missing", []),
        "specific_reasons": list(dict.fromkeys(reasons)),
        "policy_version_linked": bool(app.active_policy_for_claim(claim_id, initial["normalized"])) if include_policy else False,
    }
    if include_policy and manifest:
        active = app.active_policy_for_claim(claim_id, initial["normalized"])
        if active:
            _review_terms(app, active["version_id"], reviewer["user_id"], manifest)
            confirmed = assess_claim(app, claim_id, claimant["user_id"])
            confirmed_rules = confirmed["rules"]
            confirmed_comparison = confirmed.get("comparison")
            row.update({
                "confirmed_actual": confirmed_comparison.status if confirmed_comparison else confirmed_rules.get("status"),
                "confirmed_payable": _plain(confirmed_rules.get("payable_amount")),
                "confirmed_difference": _plain(getattr(confirmed_comparison, "possible_difference", None)),
                "provisional_amounts_equal_confirmed": (
                    _plain(actual_payable) == _plain(confirmed_rules.get("payable_amount"))
                    and _plain(getattr(comparison, "possible_difference", None)) == _plain(getattr(confirmed_comparison, "possible_difference", None))
                ),
                "provisional_status_equal_confirmed": actual_status == (confirmed_comparison.status if confirmed_comparison else confirmed_rules.get("status")),
            })
    return row


def main() -> int:
    os.environ.setdefault("TESSERACT_CMD", r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    temporary = tempfile.TemporaryDirectory(prefix="mediguard-provisional-app-eval-", ignore_cleanup_errors=True)
    work = Path(temporary.name)
    os.environ["MEDIGUARD_DB_PATH"] = str(work / "claims.db")
    os.environ["MEDIGUARD_STORAGE_DIR"] = str(work / "storage")
    os.environ["CHROMA_DIR"] = str(work / "chroma")
    os.environ["MEDIGUARD_TRUSTED_FIXTURES"] = "false"

    import sys
    sys.path.insert(0, str(ROOT))
    from mediguard.services import application as app
    from mediguard.services.orchestration import assess_claim
    from mediguard.policy import policy_index

    app.init_db()
    claimant = _create_actor(app, "claimant", "Synthetic Evaluation Claimant")
    reviewer = _create_actor(app, "reviewer", "Synthetic Evaluation Reviewer")
    labels = json.loads((ROOT / "samples" / "evaluation_cases" / "ground_truth.json").read_text(encoding="utf-8"))
    cases_dir = ROOT / "samples" / "evaluation_cases" / "cases"
    labeled_rows = []
    for expected in labels["cases"]:
        case_dir = cases_dir / expected["case_id"]
        manifest = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
        labeled_rows.append(_run_one(app, assess_claim, claimant, reviewer, case_dir,
                                     manifest["claim_id"], expected, manifest, True))

    adversarial = json.loads((ROOT / "samples" / "adversarial_cases" / "casebook.json").read_text(encoding="utf-8"))
    adversarial_rows = []
    for case in adversarial["cases"]:
        case_dir = ROOT / "samples" / "adversarial_cases" / "cases" / case["case_id"]
        expected = {"case_id": case["case_id"], "expected_status": "Manual Review (safe app expectation: the casebook has no policy document or decision label)"}
        adversarial_rows.append(_run_one(app, assess_claim, claimant, reviewer, case_dir,
                                         case["expected"].get("claim_reference") or case["case_id"],
                                         expected, None, False))

    output = {
        "dataset": "30 fictional evaluation cases plus 10 fictional adversarial extraction cases",
        "path": "claimant upload -> process_claim_documents -> evaluate_saved_claim -> run_settlement_comparison",
        "reviewer_confirmation_before_first_result": False,
        "evaluation_cases": labeled_rows,
        "evaluation_status_match": {"numerator": sum(row["actual"] == row["expected"] for row in labeled_rows), "denominator": len(labeled_rows)},
        "evaluation_amount_or_range_shown": {"numerator": sum(row["amount_or_range_shown"] for row in labeled_rows), "denominator": len(labeled_rows)},
        "evaluation_result_shown": {"numerator": sum(row["result_shown"] for row in labeled_rows), "denominator": len(labeled_rows)},
        "evaluation_provisional_equals_confirmed": {"numerator": sum(row.get("provisional_amounts_equal_confirmed", False) and row.get("provisional_status_equal_confirmed", False) for row in labeled_rows), "denominator": len(labeled_rows)},
        "adversarial_cases": adversarial_rows,
        "adversarial_result_shown": {"numerator": sum(row["result_shown"] for row in adversarial_rows), "denominator": len(adversarial_rows)},
        "adversarial_decision_labels": "The casebook labels extraction and settlement parsing only; it supplies no policy PDF or final decision labels. Manual Review is the correct safe app outcome because no policy edition is supplied.",
        "embedding_backend": {"configured": policy_index.EMBEDDING_MODEL, "active": "deferred until optional policy search"},
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "evaluation_status_match": output["evaluation_status_match"],
        "evaluation_amount_or_range_shown": output["evaluation_amount_or_range_shown"],
        "evaluation_result_shown": output["evaluation_result_shown"],
        "evaluation_provisional_equals_confirmed": output["evaluation_provisional_equals_confirmed"],
        "adversarial_result_shown": output["adversarial_result_shown"],
        "cases": [{"case_id": row["case_id"], "expected": row["expected"], "actual": row["actual"],
                   "result_shown": row["result_shown"], "reasons": row["specific_reasons"],
                   "expected_payable": row["expected_payable"], "displayed_estimate": row["displayed_estimate"],
                   "mismatch_causes": row["mismatch_causes"],
                   "missing_terms": row["policy_terms_missing"],
                   "provisional_equals_confirmed": row.get("provisional_amounts_equal_confirmed")} for row in (*labeled_rows, *adversarial_rows)],
        "embedding_backend": output["embedding_backend"],
        "results_path": str(OUTPUT),
    }, indent=2, ensure_ascii=False))
    gc.collect()
    temporary.cleanup()
    return 0 if output["evaluation_result_shown"]["numerator"] == 30 and output["adversarial_result_shown"]["numerator"] == 10 else 1


if __name__ == "__main__":
    raise SystemExit(main())
