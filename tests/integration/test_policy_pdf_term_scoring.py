from evaluation.scripts.score_policy_terms_from_pdfs import run


def test_source_pdf_policy_term_score_has_independent_denominators(tmp_path, monkeypatch):
    from evaluation.scripts import score_policy_terms_from_pdfs

    monkeypatch.setattr(score_policy_terms_from_pdfs, "OUTPUT", tmp_path / "scores.json")
    result = run(emit=False)
    assert result["cases"] == 30
    assert "no reviewer-confirmed JSON was read" in result["basis"]
    assert set(result["scores"]) == {
        "deductible", "copay_percent", "room_limit_per_day", "icu_limit_per_day",
        "exclusions", "date_window", "annual_limit",
    }
    assert all(score["numerator"] == score["denominator"] == 30 for score in result["scores"].values())
    assert result["failures"] == []
