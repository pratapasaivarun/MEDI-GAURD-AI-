# Synthetic patient-support claim cases

All files in this directory are fictional academic test material. Each case folder includes a policy PDF, medical bill PDF, and `case.json` manifest.

Use the fields in `claim_registration` when creating a claim. Some cases require trusted reviewer context; those are explicitly listed in the manifest because source documents alone cannot safely prove network status, preauthorization, waiting-period eligibility, or a confirmed exclusion.

The app currently supports document upload and deterministic rule evaluation. Reviewer-context-only cases are included for rule-engine and future reviewer-form testing.
