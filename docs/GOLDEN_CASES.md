# Golden claim cases — hand calculation specification

All amounts are INR. Unless stated otherwise, policy terms are explicitly confirmed, proportionate deduction is off, there are no other caps, and arithmetic follows: item coverage limits, sum insured, deductible, then co-pay. These expected values were calculated by hand before running the implementation against them.

| # | Case and hand calculation | Expected result |
|---:|---|---|
| 1 | Basic cover: eligible bill 10,000; no deductible; 0% co-pay. | Insurer 10,000; patient 0. |
| 2 | Deductible: 10,000 eligible − 2,000 deductible. | Insurer 8,000; patient 2,000. |
| 3 | Co-pay: 10,000 eligible × 10% = 1,000 patient co-pay. | Insurer 9,000; patient 1,000. |
| 4 | Combined: (10,000 − 2,000 deductible) × 10% = 800 co-pay; 8,000 − 800. | Insurer 7,200; patient 2,800. |
| 5 | Room exactly at cap: 4 days × 5,000/day = 20,000 cap; room bill 20,000. | Eligible 20,000; no room reduction. |
| 6 | Room above cap: 4 × 5,000 = 20,000; room bill 24,000. | Eligible 20,000; room reduction 4,000. |
| 7 | ICU daily cap: 2 days × 6,000 = 12,000; ICU bill 15,000. | Eligible 12,000; ICU reduction 3,000. |
| 8 | Confirmed exclusion: cosmetic surgery 50,000; policy explicitly excludes it. | Eligible 0; full 50,000 excluded. |
| 9 | Category sub-limit: investigation bill 8,000; confirmed limit 5,000. | Eligible 5,000; reduction 3,000. |
| 10 | Sum insured: eligible lines 8,000 + 7,000; annual limit 10,000. | Eligible 10,000; insurer 10,000 before cost sharing. |
| 11 | Zero bill: total 0, regardless of policy limits. | Manual review; payout 0. |
| 12 | Bill equals deductible: eligible 2,000 − deductible 2,000. | Insurer 0; patient 2,000. |
| 13 | Bill exactly equals sub-limit: investigation 5,000; sub-limit 5,000. | Eligible 5,000; reduction 0. |
| 14 | Pre-hospital edge included: admission 10 Aug; 2-day window begins 8 Aug; expense 8 Aug. | Covered 4,000. |
| 15 | Pre-hospital one day outside: admission 10 Aug; 2-day window; expense 7 Aug. | Excluded 4,000; eligible 0. |
| 16 | Stay boundaries: expense on admission (10 Aug) or discharge (12 Aug). | Both are within the inpatient dates. |
| 17 | Combination: room bill 24,000 capped to 20,000 plus pharmacy 8,000; eligible 28,000; deductible 3,000; 10% co-pay on 25,000 = 2,500. | Insurer 22,500; patient 9,500 (bill 32,000 − 22,500). |

Date cases assume policy wording explicitly covers the stated pre-hospital window and inpatient dates. Proportional deduction is omitted because scope can depend on policy wording; uncertain terms require reviewer confirmation.

**Verify after implementation:** `python -m pytest -q tests/test_golden_cases.py tests/test_comparison_golden_cases.py`.
