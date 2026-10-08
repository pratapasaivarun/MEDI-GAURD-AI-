# `unsafe_allow_html` audit

**Audited:** 2026-10-09
**Scope:** all `unsafe_allow_html=True` calls in root `app.py` (21 calls at audit time). The calls use application-authored markup. Claim, patient, policy, and status values are escaped or allowlisted before interpolation.

## Call-by-call review

| `app.py` line | Markup/use | User or document value interpolated? | Handling / test |
|---:|---|---|---|
| 1573 | Brand header | No | Static application markup. |
| 1578 | Reusable page heading | Yes; callers may include account display names or other app values. | `page_header_html` applies `html.escape` to icon, eyebrow, title, and subtitle. `test_page_header_escapes_untrusted_title`. |
| 1653 | Welcome illustration | No | Static application markup and inline SVG. |
| 1654 | Workspace role label | No | Static application markup. |
| 1707 | Login splash content | No | Static application markup and inline SVG. |
| 1712 | Login portal title/copy | No; currently selected from fixed role-specific strings. | `auth_portal_html` escapes each interpolated string. `test_auth_portal_markup_escapes_interpolated_values`. |
| 1768 | Sidebar workspace label | No | Static application markup. |
| 1789 | Sidebar spacer | No | Static application markup. |
| 1790 | Sidebar account label | No | Static application markup. |
| 1795 | Reviewer-gate sidebar note | No | Static application markup. |
| 1858 | Claimant result context | Yes; claim number, patient name, policy number, and status come from saved claim/workflow data. | `claim_context_html` escapes text and attributes; status is allowlisted then escaped. `test_claimant_claim_context_rendering_escapes_claim_values`. |
| 2170 | Dashboard welcome note | No | Static application markup. |
| 2176 | Dashboard section heading | No | Static application markup. |
| 2185 | Claim row | Yes; claim number, patient name, and hospital are saved user/document values. | `claim_row_html` escapes text and attributes; status is allowlisted then escaped. `test_review_queue_claim_row_rendering_escapes_claim_values`. |
| 2201 | Review queue heading | No | Static application markup. |
| 2212 | Claim registration heading | No | Static application markup. |
| 2253 | Document upload heading | No | Static application markup. |
| 2317 | Reviewer selected-claim context | Yes; saved claim and status values. | Reuses `claim_context_html`; `test_reviewer_claim_context_rendering_escapes_claim_values`. |
| 2446 | Deterministic result heading | Yes; status originates from calculation output. | Status is constrained to `_safe_status`, then escaped; `test_deterministic_status_markup_uses_allowlisted_status`. |
| 2462 | Agent recommendation heading | Yes; status originates in model-assisted workflow output. | Status is constrained to `_safe_status`, then escaped; `test_agent_status_markup_uses_allowlisted_status`. |
| 2672 | App CSS | No | Static stylesheet authored in the application. |

## Verification

The seven rendering-helper tests insert `<script>alert(1)</script>` into each relevant interpolated value and assert the escaped spelling appears while a raw `<script>` tag does not. Status-heading tests supply the payload as the status and verify it falls back to the allowlisted `manual_review` class and label.

This audit covers `app.py` only, as requested. It does not claim that every HTML surface in third-party libraries or generated PDF/DOCX output has been security-tested.
