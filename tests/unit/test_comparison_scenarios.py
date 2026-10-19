from evaluation.scripts.run_comparison_scenarios import run_scenarios


def test_expected_comparison_scenarios_match_actual_results():
    results = run_scenarios()
    assert len(results) == 7
    assert all(row["passed"] for row in results), results
