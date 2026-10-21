import json
from pathlib import Path


def test_wrongful_deduction_case_explains_lab_issue_not_lower_copay():
    case_path = Path(__file__).parents[2] / "samples" / "demo_cases" / "b_wrongful_deduction" / "case.json"
    explanation = json.loads(case_path.read_text(encoding="utf-8"))["calculation"]["settlement_explanation"]
    assert "diagnostic lab tests" in explanation
    assert "not a separate error" in explanation
    assert "under-applies co-pay" not in explanation
