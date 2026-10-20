# Adversarial synthetic cases

These ten fictional, hand-labeled cases probe unusual bill layouts, OCR noise, boundary amounts, ambiguous settlement language, multiple deductions, missing fields, and claim-reference variants. `casebook.json` contains the original input text and expected outputs; its labels were fixed and committed before running the parser against them. Regenerate the PDF test inputs with `python samples/adversarial_cases/generate_fixtures.py`. Every person, claim, provider, policy and amount is fictional.
