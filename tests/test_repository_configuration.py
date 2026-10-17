from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_unused_backup_key_and_crypto_dependency_are_removed():
    assert "MEDIGUARD_BACKUP_KEY" not in (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "cryptography" not in (ROOT / "requirements.txt").read_text(encoding="utf-8").lower()


def test_evaluation_docs_explain_legacy_phase4_fixture_gap():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "fixtures/phase4/ground_truth.json" in readme
    assert "FileNotFoundError" in readme
    assert "pytest fixtures" in readme


def test_decision_log_says_claimed_amount_never_sets_paid_amount():
    decisions = (ROOT / "docs" / "DECISIONS.md").read_text(encoding="utf-8")
    assert "`Claimed amount` and `Amount claimed` are not payment evidence" in decisions
    assert "remain fallbacks for both the claim total and paid amount" not in decisions
