# Medi Gaurd AI — Core MVP Simplification

## Active core flow

The active prototype now presents only four pages:

1. Dashboard
2. Register claim
3. Claim review
4. Claim result

The core user journey is:

```text
Register claim
  -> upload one medical bill and one policy
  -> extract and normalize
  -> automatically index and activate the matching uploaded policy
  -> run deterministic coverage rules
  -> run Policy Agent and Decision Agent
  -> show claimant-safe result
```

## Deferred features

Production-only MFA, encryption, backups, secrets management, PaddleOCR, and policy-edition comparison are retained under `deferred/`; they are out of scope for the local academic demonstration.

## Core safeguards retained

The core prototype retains active-policy matching, calculation reconciliation, OCR confidence review, missing-field review, line-item quality gates, Manual Review fallback, deterministic financial authority, policy evidence retrieval, and claimant-safe amount/result data. LangGraph has two nodes: a deterministic Policy Agent that retrieves clauses, and a Decision Agent that makes the sole LLM call.

## Demo limitations

The supplied demonstration policies have no pre-authorization or network restriction and a zero-month waiting period; benefit exhaustion is represented only by the annual-limit cap. More detailed pre-authorization, network, and prior-benefit-balance integrations are out of scope for this academic prototype.

## Verification

After simplification, the live Windows project passed:

```text
SIMPLE_CORE_PYCOMPILE_OK
SUMMARY total=24 pass=24 fail=0 timeout=0
```

No database records, stored documents, fixtures, or rollback files were deleted by this simplification.
