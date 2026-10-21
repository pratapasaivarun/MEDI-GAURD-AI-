from types import SimpleNamespace

from mediguard.ui.claim_pages import _claimant_recommendations


def test_possible_discrepancy_recommendation_points_to_comparison_and_appeal():
    comparison = SimpleNamespace(status="possible_discrepancy", possible_difference=2700)
    recommendations = _claimant_recommendations(
        {"status": "partially_approved"}, {"status": "partially_approved"}, comparison
    )
    assert recommendations[0] == (
        "The settlement differs from the policy-based estimate by INR 2,700.00. "
        "Review the Settlement comparison below and check the appeal draft."
    )
    assert not any("No action is needed" in item for item in recommendations)
