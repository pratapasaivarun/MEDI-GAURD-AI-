# MediGuard AI demo guide

All three cases in `samples/demo_cases/` use synthetic people, providers, policies, bills, and settlements. Every document is labelled **FICTIONAL SAMPLE**. Do not replace them with real patient data.

## Start the app

1. Install the pinned dependencies with `python -m pip install -r requirements.txt` and install the Tesseract OCR system package if scanned-page OCR is needed.
2. Copy `.env.example` to `.env`. Keep `MEDIGUARD_CORE_DEMO=false` and leave Ollama stopped for the deterministic demo.
3. Run `streamlit run app.py`.
4. Create a claimant account, create a claim with the values in the selected `case.json`, and upload its `bill.pdf`, `policy.pdf`, and `settlement.pdf`.
5. Review the extracted fields, confirm policy terms using page 1 as their source, run the deterministic rules, then open the settlement comparison.

## Cases and expected outcomes

- **`a_match`** — the bill and settlement reconcile with the room cap, proportionate doctor/nursing deduction, INR 10,000 deductible, and 10% co-pay. Expected status: `no_discrepancy`; no appeal draft.
- **`b_wrongful_deduction`** — the insurer deducts INR 3,000 for lab tests as outside the pre-hospitalization window, while the bill dates the tests during the stay and policy page 1 says diagnostic investigations are payable during hospitalization. The letter also under-applies co-pay by INR 300, so the net patient-share difference is INR 2,700 after the 10% co-pay adjustment. Expected status: `possible_discrepancy`; appeal PDF and DOCX drafts are available for review.
- **`c_manual_review`** — the bill has a second scanned page and the settlement's stated bill total differs by INR 1,000. Expected status: `manual_review`; no appeal draft.

The app uses its template explanation when Ollama is off. OCR and policy retrieval remain dependent on the local Tesseract and embedding setup. The tests exercise the app's document processing, reviewer term confirmation, rules, and settlement comparison functions with Ollama disabled.

These results demonstrate workflow behavior on fictional inputs. They are not insurer decisions or evidence of clinical/financial accuracy on real claims.
