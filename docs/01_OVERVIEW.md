# MediGuard AI overview

MediGuard AI is a college demonstration prototype that reads fictional hospital bills, insurance policies, and insurer settlement letters. It calculates a policy-based estimate with Python rules and compares that estimate with the insurer's letter. A reviewer confirms policy terms and evidence before the app shows a result.

It is for demonstrating document extraction, policy evidence, deterministic calculations, settlement comparison, and a patient-support explanation workflow. It does not make insurer decisions and must not be used for real claims or real patient information.

The key rule is: **Python decides; the LLM only explains.** Model output cannot set or change amounts, status, or appeal eligibility. If the model is unavailable or its response is invalid, a checked template explains the existing Python result.

Start with the root [README](../README.md), then follow the numbered guides. All bundled documents are fictional samples.
