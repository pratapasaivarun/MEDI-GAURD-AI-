from mediguard.services.application import _claim_warning_message
from mediguard.ui.claim_pages import _claimant_policy_issue


def test_claimant_policy_issue_uses_plain_language_and_source_page_once():
    message = _claimant_policy_issue({
        "term": "deductible",
        "page": 2,
        "reason": "Deductible: page not identified; the 0.60-confidence candidate was not applied, and no current bill line matches it. Confirm this term to check whether the result changes.",
    })
    assert "confidence candidate" not in message
    assert "extracted value has confidence 0.60" in message
    assert message.count("policy page 2") == 1


def test_claimant_calculation_notes_translate_internal_rule_codes():
    assert _claim_warning_message("room_limit_applied") == (
        "The daily room limit reduced the amount covered for room charges."
    )


