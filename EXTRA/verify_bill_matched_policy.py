from pathlib import Path
from extraction import extract_document
from policy_terms import extract_policy_terms

path = Path('fixtures/phase4/policy_bill_matched_usd.pdf')
evidence, raw_by_page, _ = extract_document(path, 'policy-bill-matched', path.name)
text = '\n'.join(item.text for item in evidence)
parsed = extract_policy_terms([item.to_dict() for item in evidence])
terms = parsed.get('terms')
Path('policy_bill_matched_text.txt').write_text(text, encoding='utf-8')
print('PAGES=', len(raw_by_page))
print('TEXT_CHARS=', len(text))
required = ('annual_limit', 'deductible', 'copay_percent', 'room_limit_per_day', 'waiting_period_months')
print('MISSING=', [key for key in required if getattr(terms, key, None) is None])
print('TERMS=', terms)
print('PARSED_METADATA=', {key: value for key, value in parsed.items() if key != 'terms'})
