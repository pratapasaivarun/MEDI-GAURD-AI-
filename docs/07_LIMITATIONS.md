# Limitations and known risks

- The samples are fictional and the labeled set is small. Expected statuses are prototype labels, not independent insurance expert judgments.
- Retrieval finds most correct clauses within five results, but precision is low. Reviewers must inspect the cited policy page and wording.
- OCR quality depends on scan quality and local Tesseract setup. Scanned or uncertain pages may require manual review.
- Policy wording can be conditional or ambiguous. Missing, conflicting, or unconfirmed terms should remain in manual review.
- The clause exclusion filter can reject a whole passage when a separate sentence contains exclusion wording; a valid coverage sentence may then be missed.
- The app stores local claim metadata and documents. This prototype has not had a production security, privacy, or retention assessment.
- Appeal letters are drafts for human review. They are not legal advice and should not be submitted without checking the facts and policy page.
- Ollama and the embedding model require local installation and machine resources. The deterministic calculation path is independent of Ollama.
- Hosting and deployment have not been tested and are outside the current project scope.

Use only the bundled fictional samples. Do not upload real patient documents or rely on the result for a claim decision.
