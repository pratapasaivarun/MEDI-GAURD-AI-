# MediGuard AI demo guide

All three cases in `samples/demo_cases/` use synthetic people, providers, policies, bills, and settlements. Every document is labelled **FICTIONAL SAMPLE**. Do not replace them with real patient data.

## Start the app

1. Install the pinned dependencies with `python -m pip install -r requirements.txt` and install the Tesseract OCR system package if scanned-page OCR is needed.
2. Copy `.env.example` to `.env`. Keep `MEDIGUARD_CORE_DEMO=false` and leave Ollama stopped for the deterministic demo.
3. Run `streamlit run app.py`.
4. Create a claimant account, create a claim with the values in the selected `case.json`, and upload its `bill.pdf`, `policy.pdf`, and `settlement.pdf`.
5. Submit the claim for assessment. The result and settlement comparison should appear with a **Provisional: terms not yet confirmed** badge; no reviewer setup is required to see it.
6. In the reviewer workspace, inspect every extracted term and source page, correct any value that needs it, and choose **Confirm all terms**. The app recomputes linked claims. Refresh the claimant result to see the **Reviewer-confirmed** badge; amounts should remain the same when the extracted terms were correct.

## Cases and expected outcomes

- **`a_match`** — the bill and settlement reconcile with the room cap, proportionate doctor/nursing deduction, INR 10,000 deductible, and 10% co-pay. Expected status: `no_discrepancy`; no appeal draft.
- **`b_wrongful_deduction`** — the insurer applies an INR 3,000 investigation deduction as outside the pre-hospitalization window, while the bill dates the tests during the stay and policy page 1 says diagnostic investigations are payable during hospitalization. The letter also under-applies co-pay by INR 300, so the net patient-share difference is INR 2,700 after the 10% co-pay adjustment. Expected status: `possible_discrepancy`; appeal PDF and DOCX drafts are available for review.
- **`c_manual_review`** — the bill has a second scanned page and the settlement's stated bill total differs by INR 1,000. Expected status: `manual_review`; no appeal draft.

The app uses its template explanation when Ollama is off. OCR and policy retrieval remain dependent on the local Tesseract and embedding setup. Provisional terms with missing, conflicting, low-confidence, or claim-relevant unconfirmed values are listed with a source page and review reason. The app does not assume a missing policy term is zero.

These results demonstrate workflow behavior on fictional inputs. They are not insurer decisions or evidence of clinical/financial accuracy on real claims.
