"""Claimant and reviewer claim/result screens. Loaded from app.main."""

from mediguard.services import application as _app
globals().update(vars(_app))
import logging
from mediguard.services.orchestration import assess_claim
from mediguard.ai.agents import comparison_template_explanation
from mediguard.ui.navigation import queue_page

logger = logging.getLogger(__name__)

_CLAIM_REVIEW_TAB_LABELS = (
    '1 · Choose claim',
    '2 · Add documents',
    '3 · Check extraction',
    '4 · Calculate & review',
    '5 · Compare settlement & draft letters',
)


def _claim_review_tab_key(claim_id: str) -> str:
    return f"claim_review_active_tab_{claim_id}"


def _remember_claim_review_tab(claim_id: str, tab_index: int) -> None:
    if 0 <= tab_index < len(_CLAIM_REVIEW_TAB_LABELS):
        st.session_state[_claim_review_tab_key(claim_id)] = _CLAIM_REVIEW_TAB_LABELS[tab_index]


def _claim_review_tab_default(claim_id: str) -> str:
    selected = st.session_state.get(_claim_review_tab_key(claim_id))
    return selected if selected in _CLAIM_REVIEW_TAB_LABELS else _CLAIM_REVIEW_TAB_LABELS[0]


def _policy_edition_default_index(editions, linked_id: str | None, claim_policy_number: str | None) -> int:
    """Prefer an already linked edition, otherwise a confirmed matching edition."""
    rows = list(editions or [])
    for index, edition in enumerate(rows):
        if linked_id and edition["version_id"] == linked_id:
            return index
    policy_number = str(claim_policy_number or "").strip().casefold()
    matching = [
        index for index, edition in enumerate(rows)
        if policy_number and str(edition["policy_number"] or "").strip().casefold() == policy_number
    ]
    confirmed = [index for index in matching if rows[index]["terms_review_status"] == "confirmed"]
    return (confirmed or matching or [0])[0]


def _render_policy_terms_badge(review_status: str | None) -> None:
    if review_status == "provisional":
        st.warning("Provisional: terms not yet confirmed. Amounts are calculated from source-backed extracted terms and may change after authorized review.")
    elif review_status == "reviewer_confirmed":
        st.success("Reviewer-confirmed policy terms. This remains an estimate, not an insurer decision.")
    elif review_status == "preconfirmed_fictional_sample":
        st.info("Pre-confirmed fictional sample. The fixture source is recorded in the audit trail.")
    elif review_status == "not_available":
        st.warning("Policy terms are unavailable for calculation. See the listed policy or document issue and next step.")

def _claimant_result_for_claim(claim_id: str, user: dict) -> dict[str, Any] | None:
    """Return only claimant-safe amounts and explanation; hide raw agent/reviewer data."""
    claim = _claim_access(claim_id, user)
    rules = None
    workflow = st.session_state.get(f"workflow_{claim_id}") or {}
    # The reviewer can recompute this claim in another browser session. Always
    # prefer the latest persisted rule output over this session's cached copy.
    with db() as conn:
        row = conn.execute("SELECT result_json FROM rule_evaluations WHERE claim_id=? ORDER BY rowid DESC LIMIT 1", (claim_id,)).fetchone()
    if row:
        try:
            rules = json.loads(row["result_json"])
            st.session_state[f"rules_{claim_id}"] = rules
        except (TypeError, json.JSONDecodeError):
            rules = None
    if not rules:
        rules = st.session_state.get(f"rules_{claim_id}")
    if not rules and not workflow:
        return None
    with db() as conn:
        reviewer_decision = conn.execute(
            "SELECT final_status FROM reviewer_decisions WHERE claim_id=? ORDER BY created_at DESC LIMIT 1",
            (claim_id,),
        ).fetchone()
    # The Python rules own the automated status. The LLM workflow supplies
    # explanatory text only; a recorded reviewer decision may supersede it.
    status = reviewer_decision["final_status"] if reviewer_decision else (rules or {}).get("status", "manual_review")
    claimant = (rules or {}).get("claimant_result") or {}
    billed = float(claimant.get("amount_billed", 0) or 0)
    def optional_float(value):
        return float(value) if value is not None else None
    payable_raw = claimant.get("amount_covered", (rules or {}).get("payable_amount"))
    responsibility_raw = claimant.get("amount_claimant_pays", (rules or {}).get("claimant_responsibility"))
    covered = optional_float(payable_raw)
    responsibility = optional_float(responsibility_raw)
    deductible = optional_float(claimant.get("deductible", (rules or {}).get("deductible")))
    copayment = optional_float(claimant.get("copayment", (rules or {}).get("copayment")))
    excluded_or_limited = optional_float(claimant.get("amount_excluded_or_limited"))
    not_paid = optional_float(claimant.get("amount_not_covered", responsibility))
    reasons = (rules or {}).get("warnings") or []
    term_issues = (rules or {}).get("policy_terms_issues") or []
    reason = ("Some policy details need confirmation. See the unresolved items below." if term_issues else (_claim_warning_message(reasons[0]) if reasons else "Your claim has been processed and the result is ready to review."))
    return {
        "status": status,
        "amount_billed": billed,
        "amount_covered": covered,
        "amount_claimant_pays": responsibility,
        "amount_not_covered": not_paid,
        "deductible": deductible,
        "copayment": copayment,
        "amount_excluded_or_limited": excluded_or_limited,
        "covered_before_cost_sharing": optional_float(claimant.get("covered_before_cost_sharing", (rules or {}).get("covered_before_cost_sharing", (rules or {}).get("covered_amount")))),
        "policy_terms_review_status": (rules or {}).get("policy_terms_review_status"),
        "policy_terms_issues": term_issues,
        "reason": reason,
        "requires_human_review": status == "manual_review",
        "rules": rules or {},
    }


def _assess_claimant_submission(claim_id: str, user_id: str) -> dict[str, Any]:
    """Run extraction, Python rules, and settlement comparison without waiting on an LLM."""
    return assess_claim(_app, claim_id, user_id)


def _render_claimant_result(user: dict) -> None:
    claims = user_claims(user["user_id"], user)
    _page_header('CLAIM OUTCOME', 'Your claim result', 'A simple view of the policy review, your estimated responsibility, and next steps.', '✓')
    _claimant_progress(3, "Review your assessment")
    if not claims:
        st.info("You do not have a claim yet.")
        if st.button("Register a claim", type="primary"):
            queue_page(st.session_state, "Register claim"); st.rerun()
        return
    options = {f"{c['claim_number']} · {c['patient_name']}": c['claim_id'] for c in claims}
    default = next((i for i, value in enumerate(options.values()) if value == st.session_state.get("active_claim")), 0)
    selected = st.selectbox("Choose a claim", list(options), index=default, key="claimant_result_selector")
    claim_id = options[selected]
    st.session_state.active_claim = claim_id
    claim = next(c for c in claims if c["claim_id"] == claim_id)
    result = _claimant_result_for_claim(claim_id, user)
    st.markdown(claim_context_html(claim, (result or {}).get('status', claim['status'])), unsafe_allow_html=True)
    if not result:
        st.info("Your documents have not been analyzed yet.")
        if st.button("Continue claim review", type="primary"):
            queue_page(st.session_state, "Submit documents" if user['role'] == 'claimant' else "Claim review"); st.rerun()
        return
    comparison, settlement = get_comparison_for_view(claim_id, user)
    status = result["status"]
    _render_policy_terms_badge(result.get("policy_terms_review_status"))
    if status == "manual_review":
        st.warning("Manual review is required. The specific unresolved information and next steps are listed below.")
    elif status == "approved":
        st.success("The automated assessment indicates approval based on the information currently available.")
    elif status == "partially_approved":
        st.warning("The automated assessment indicates partial coverage. Some charges were limited or excluded under the policy.")
    elif status == "rejected":
        st.error("The automated assessment indicates that the current policy information does not cover this claim.")
    amount_columns = st.columns(3, gap="medium")
    amount_columns[0].metric("Total bill", f"INR {result['amount_billed']:,.2f}", border=True)
    estimate_range = (result.get("rules") or {}).get("payable_range")
    if estimate_range:
        low = float(estimate_range["lower"])
        high = float(estimate_range["upper"])
        covered_label = f"INR {low:,.2f}–{high:,.2f}"
        pays_label = f"INR {max(0.0, result['amount_billed'] - high):,.2f}–{max(0.0, result['amount_billed'] - low):,.2f}"
    else:
        covered_label = f"INR {result['amount_covered']:,.2f}" if result["amount_covered"] is not None else "Not calculable"
        pays_label = f"INR {result['amount_claimant_pays']:,.2f}" if result["amount_claimant_pays"] is not None else "Not calculable"
    amount_columns[1].metric("Estimated insurance share", covered_label, border=True)
    amount_columns[2].metric("Estimated amount you pay", pays_label, border=True)
    with st.container(border=True):
        st.markdown("### What this means for you")
        st.write(result["reason"])
        for issue in result.get("policy_terms_issues", []):
            st.write(f"• {_claimant_policy_issue(issue)}")
        if result["requires_human_review"]:
            known_coverage = result.get("covered_before_cost_sharing")
            if known_coverage is not None:
                st.write(f"Known eligible amount before unresolved policy terms: INR {known_coverage:,.2f}.")
            st.caption("This is not a final determination. Review the listed term or document issue before relying on the estimate.")
        else:
            st.write(
                f"The claimant responsibility of INR {result['amount_claimant_pays']:,.2f} includes "
                f"INR {result['deductible']:,.2f} deductible and INR {result['copayment']:,.2f} copayment. "
                f"INR {result['amount_excluded_or_limited']:,.2f} is excluded or limited by the policy."
            )
            st.caption("Deductible and copayment are policy cost-sharing amounts, not rejected charges. Excluded or policy-limited amounts are charges the policy does not pay.")
            st.caption("This is decision-support information. Final determination should be confirmed by an authorized reviewer.")
    rules = result.get("rules", {})
    unknown_lines = rules.get("uncategorized_lines") or []
    if unknown_lines:
        st.warning("Uncategorized bill lines are listed below. They are provisionally treated as general covered charges for the upper estimate; any possible category-specific restriction is reflected in the estimate range.")
        for unknown in unknown_lines:
            st.write(f"• {unknown['description']} — INR {float(unknown['amount']):,.2f}")
        if estimate_range:
            st.caption("Estimate range causes: " + "; ".join(estimate_range.get("reasons", [])) + ".")
    workflow = st.session_state.get(f"workflow_{claim_id}") or {}
    # Persisted claim status includes agent failures and reviewer sign-off, even
    # after a new browser session loses its cached workflow.
    workflow = {**workflow, "decision": {**workflow.get("decision", {}), "status": result["status"]}}
    normalized = st.session_state.get(f"normalized_{claim_id}") or {}
    if rules.get("line_item_reconciliation_failed"):
        st.info(str(rules.get("line_item_notice") or _claim_warning_message("line_item_reconciliation_failed")))
    with st.expander("See the amount breakdown", expanded=result["requires_human_review"]):
        if result.get("covered_before_cost_sharing") is not None:
            st.write(f"Known eligible amount before cost sharing: INR {result['covered_before_cost_sharing']:,.2f}")
        st.write(f"Deductible: INR {float(result['deductible']):,.2f}" if result.get("deductible") is not None else "Deductible: not calculable from the available policy terms.")
        st.write(f"Co-payment: INR {float(result['copayment']):,.2f}" if result.get("copayment") is not None else "Co-payment: not calculable from the available policy terms.")
        st.write(f"Estimated insurer payment: INR {result['amount_covered']:,.2f}" if result.get("amount_covered") is not None else "Estimated insurer payment: not calculable from the unresolved terms listed above.")
        st.write(f"Excluded or policy-limited amount: INR {float(result['amount_excluded_or_limited']):,.2f}" if result.get("amount_excluded_or_limited") is not None else "Excluded or policy-limited amount: not calculable until the unresolved terms are reviewed.")
        st.caption("These figures are provisional estimates. An unavailable component is left blank instead of being assumed to be zero.")
        adjustments = []
        for item in rules.get("results", []):
            if item.get("status") in {"partial", "fail", "needs_review"}:
                adjustments.append({"Policy check": _claim_warning_message(item.get("rule_id", "")), "Effect": item.get("calculation", "Policy adjustment applied"), "Amount affected": item.get("amount")})
        if adjustments:
            st.markdown("#### Items or rules affecting coverage")
            st.dataframe(adjustments, hide_index=True)
        warnings = [
            warning for warning in (rules.get("warnings") or [])
            if not result.get("policy_terms_issues")
            or not str(warning).startswith("POLICY_TERMS_UNCONFIRMED:")
        ]
        if warnings:
            st.write("Calculation notes: " + "; ".join(_claim_warning_message(item) for item in warnings))
    billing_anomalies = normalized.get("billing_anomalies") or {}
    bill_date_value = (normalized.get("bill_date") or {}).get("value")
    try:
        bill_date = date.fromisoformat(str(bill_date_value).replace("/", "-")) if bill_date_value else None
    except ValueError:
        bill_date = None
    submission_deadline = check_submission_deadline(bill_date)
    if submission_deadline:
        st.warning(submission_deadline["warning"])
    duplicate_flags = billing_anomalies.get("duplicates") or normalized.get("duplicate_candidates") or []
    outlier_flags = billing_anomalies.get("price_outliers") or []
    if duplicate_flags or outlier_flags:
        anomaly_messages = []
        for duplicate in duplicate_flags[:3]:
            left = (duplicate.get("left") or {}).get("description") or "an item"
            right = (duplicate.get("right") or {}).get("description") or "another item"
            anomaly_messages.append(f"Possible duplicate charge: {left} and {right}.")
        for outlier in outlier_flags[:3]:
            item = outlier.get("item") or {}
            anomaly_messages.append(f"Price check: {item.get('description') or 'An item'} — {outlier.get('reason') or 'unusual amount'}.")
        st.warning("Billing checks need review:\n\n" + "\n\n".join(anomaly_messages))
    line_item_results = rules.get("line_item_results") or []
    if line_item_results:
        source_items = normalized.get("line_items") or []
        notes_by_index: dict[int, str] = {}
        for note in (workflow.get("decision") or {}).get("line_item_notes") or []:
            if not isinstance(note, dict):
                continue
            try:
                item_index = int(note.get("item_index"))
            except (TypeError, ValueError):
                continue
            note_text = str(note.get("note") or "").strip()
            if 0 <= item_index < len(line_item_results) and note_text:
                notes_by_index[item_index] = note_text
        rows = []
        for index, item_result in enumerate(line_item_results):
            source_item = source_items[index] if index < len(source_items) and isinstance(source_items[index], dict) else {}
            rows.append({
                "Description": str(source_item.get("description") or item_result.get("description") or "Line item"),
                "Amount claimed": float(source_item.get("amount") or item_result.get("amount") or 0),
                "Amount approved": float(item_result.get("covered_amount") or 0),
                "Status": _line_item_status_label(item_result.get("status")),
                "Applied rule": str(item_result.get("applied_rule") or "standard").replace("_", " ").title(),
                "Note": " ".join(part for part in [notes_by_index.get(index, ""), *[str(flag.get("note")) for flag in rules.get("history_flags", []) if flag.get("item_index") == index]] if part),
            })
        with st.expander("Item-wise verification", expanded=False):
            st.caption("Each charge is checked against the available policy terms before claim-level deductible and copayment are applied.")
            st.dataframe(
                rows,
                hide_index=True,
                column_config={
                    "Amount claimed": st.column_config.NumberColumn(format="INR %.2f"),
                    "Amount approved": st.column_config.NumberColumn(format="INR %.2f"),
                    "Status": st.column_config.TextColumn(),
                },
            )
    recommendations = _claimant_recommendations(
        workflow.get("decision") or {},
        {**rules, "billing_anomalies": billing_anomalies, "submission_deadline": submission_deadline or {}},
        comparison,
    )
    if recommendations:
        with st.container(border=True):
            st.markdown("### Recommended next steps")
            for index, recommendation in enumerate(recommendations):
                if recommendation.startswith("If your appeal is not resolved"):
                    st.info(recommendation, icon=":material/account_balance:")
                else:
                    st.write(f":material/arrow_forward: {recommendation}")
            confidence = (workflow.get("decision") or {}).get("confidence")
            if confidence is not None:
                st.caption(f"Decision confidence: {float(confidence):.2f} ({confidence_label(float(confidence))})")
            st.caption("This is decision-support information, not legal or insurance advice.")
    with st.container(border=True):
        st.markdown("### Download your claim documents")
        st.caption("Use the decision report to understand the rules-based estimate. An appeal draft is available only from a possible discrepancy comparison.")
        st.download_button(
            "Download decision report (PDF)",
            data=build_decision_report(dict(claim), normalized, rules, workflow),
            file_name=f"{claim['claim_number']}-decision-report.pdf",
            mime="application/pdf",
            icon=":material/download:",
            type="primary",
            use_container_width=True,
            help="A clear summary of the current claim outcome, amounts, reasons, and next steps.",
        )
    if comparison and settlement:
        with st.container(border=True):
            _render_settlement_comparison(dict(claim), comparison, settlement, user, normalized, rules)
    else:
        st.info("Upload the insurer's settlement letter to compare it and enable a draft.")
    _render_claim_assistant(claim_id, normalized, result, workflow)
    if st.button("Back to dashboard"):
        queue_page(st.session_state, "Dashboard"); st.rerun()


def _render_claim_assistant(claim_id: str, normalized: dict[str, Any], result: dict[str, Any], workflow: dict[str, Any]) -> None:
    """A claimant-facing, evidence-bounded question interface for one claim."""
    with st.container(border=True):
        st.subheader('💬 Ask about this claim', anchor=False)
        st.caption('Ask in plain language. Answers are grounded only in this claim’s documents and decision data. ✨')
        _render_claim_assistant_chat(claim_id, normalized, result, workflow)


def _inr(value: Any) -> str:
    return f"INR {float(value or 0):,.2f}"


def _claimant_recommendations(decision: dict[str, Any], rules: dict[str, Any], comparison: Any) -> list[str]:
    recommendations = recommend_next_steps(decision, rules)
    if comparison and comparison.status == "possible_discrepancy":
        return [
            f"The settlement differs from the policy-based estimate by {_inr(comparison.possible_difference)}. Review the Settlement comparison below and check the appeal draft."
        ] + [text for text in recommendations if "No action is needed" not in text]
    return recommendations


def _claimant_policy_issue(issue: dict[str, Any]) -> str:
    """Translate source-review diagnostics into claimant-readable wording."""
    labels = {
        "annual_limit": "Annual coverage limit",
        "deductible": "Deductible",
        "copay_percent": "Co-payment rate",
        "room_limit_per_day": "Daily room limit",
        "icu_limit_per_day": "Daily ICU limit",
        "exclusions": "Policy exclusions",
        "date_window": "Pre- and post-hospitalization period",
        "matching_policy": "Policy number",
        "active_policy_terms": "Linked policy edition",
    }
    term = str(issue.get("term") or "Policy detail").strip()
    label = labels.get(term, term.replace("_", " ").strip().capitalize())
    reason = str(issue.get("reason") or "This policy detail needs review.").strip()
    reason = re.sub(rf"^{re.escape(term)}:\s*", "", reason, flags=re.IGNORECASE)
    reason = re.sub(
        r";?\s*the\s+(\d+(?:\.\d+)?)-confidence candidate was not applied, and no current bill line matches it\.\s*Confirm this term to check whether the result changes\.?",
        r". The extracted value has confidence \1 and needs review before it can be used.",
        reason,
        flags=re.IGNORECASE,
    )
    reason = reason.lstrip(" .;:").strip()
    reason = re.sub(r"\bconfidence candidate\b", "extracted value", reason, flags=re.IGNORECASE)
    page = issue.get("page")
    source = f" Source: policy page {page}." if page else " The policy page could not be identified."
    return f"{label}: {reason}{source}"


def appeal_draft_available(comparison: Any) -> bool:
    """Appeal downloads require a comparison with a possible discrepancy."""
    return comparison is not None and getattr(comparison, "status", None) == "possible_discrepancy"


@st.fragment(run_every="2s")
def _render_background_analysis(claim_id: str, user_id: str, role: str, comparison) -> None:
    """Poll persisted analysis only; reruns never make model requests."""
    job = claim_analysis_job(claim_id, user_id)
    explanation = (job or {}).get("explanation") or comparison_template_explanation(comparison)
    with st.container(border=True):
        st.markdown('#### What the comparison means')
        st.write(explanation)
        if not job or job["status"] in {"queued", "running"}:
            st.caption('Optional explanation is being prepared in the background. The Python calculation above is already available.')
        elif job["status"] == "fallback":
            st.caption('Showing the rules-based explanation because optional analysis was unavailable or did not pass checks.')
        if role in {"reviewer", "admin"} and job and job.get("deductions"):
            st.markdown('#### Reviewer-only deduction analysis')
            st.dataframe([{
                "Deduction": row.get("deduction_id"),
                "Assessment": row.get("assessment"),
                "Clause": row.get("clause_id") or "No supporting clause identified",
                "Rationale": row.get("rationale"),
            } for row in job["deductions"]], hide_index=True)
        candidate = (job or {}).get("reviewer_candidate")
        if role in {"reviewer", "admin"} and candidate:
            st.warning('The optional analysis disagreed with the Python comparison and is shown only for reviewer assessment.')
            with st.expander('Reviewer-only conflicting analysis'):
                st.write(candidate.get("explanation", ""))
                if candidate.get("deductions"):
                    st.dataframe([{
                        "Deduction": row.get("deduction_id"),
                        "Assessment": row.get("assessment"),
                        "Clause": row.get("clause_id") or "No supporting clause identified",
                        "Rationale": row.get("rationale"),
                    } for row in candidate["deductions"]], hide_index=True)


def needs_bill_total_confirmation(settlement: SettlementData) -> bool:
    return any(
        str(reason).startswith("SETTLEMENT_TOTAL_FROM_BILL:")
        and "user confirmation required" in str(reason).lower()
        for reason in settlement.review_reasons
    )


def _render_settlement_comparison(
    claim: dict[str, Any],
    comparison,
    settlement: SettlementData,
    user: dict | None = None,
    normalized: dict[str, Any] | None = None,
    rules: dict[str, Any] | None = None,
) -> None:
    """Render the same evidence-bounded settlement comparison for both roles."""
    st.markdown('### Settlement comparison')
    st.caption('This compares the settlement letter with a deterministic policy estimate. It is decision support, not an insurer determination.')
    if rules:
        _render_policy_terms_badge(rules.get("policy_terms_review_status"))
    if needs_bill_total_confirmation(settlement):
        st.warning('The settlement letter has no bill total. The uploaded hospital bill total is proposed; confirm it before relying on a comparison.')
        checked = st.checkbox(
            'I confirm the uploaded hospital bill total should be used for this comparison.',
            key=f"confirm_bill_total_checkbox_{claim.get('claim_id', 'claim')}",
        )
        if st.button(
            'Confirm bill total and compare',
            type='primary',
            disabled=not checked,
            key=f"confirm_bill_total_button_{claim.get('claim_id', 'claim')}",
        ):
            if not user or not normalized or not rules:
                st.error('The claim details are not available to complete this confirmation. Reopen the claim and try again.')
            else:
                try:
                    confirmed_comparison, confirmed_settlement = run_settlement_comparison(
                        claim['claim_id'], user['user_id'], normalized, rules,
                        confirm_inferred_bill_total=True,
                    )
                    st.session_state[f"comparison_{claim['claim_id']}"] = confirmed_comparison
                    st.session_state[f"settlement_{claim['claim_id']}"] = confirmed_settlement
                    st.rerun()
                except Exception:
                    logger.exception("Bill-total confirmation failed")
                    st.error('The bill total could not be confirmed. Check the source page and try again.')
    metrics = st.columns(3, gap='medium')
    metrics[0].metric('Settlement payment', _inr(comparison.actual_insurer_payment) if comparison.actual_insurer_payment is not None else 'Not identified', border=True)
    metrics[1].metric('Estimated insurer payment', _inr(comparison.expected_insurer_payment) if comparison.expected_insurer_payment is not None else 'Not calculable', border=True)
    metrics[2].metric('Possible difference', _inr(comparison.possible_difference) if comparison.possible_difference is not None else 'Not calculable', border=True)
    if comparison.status == 'manual_review':
        st.warning('Manual review is needed because at least one comparison input is unresolved. An authorized reviewer should resolve the specific issue listed below before relying on the comparison.')
        for reason in comparison.review_reasons:
            st.write(f'• {reason}')
    elif comparison.status == 'possible_discrepancy':
        st.warning('The documents show a possible settlement discrepancy. Ask an authorized reviewer to confirm it before relying on this estimate.')
    else:
        st.success('No discrepancy was identified from the available settlement and policy data.')
    if comparison.categories:
        st.dataframe([{
            'Category': row.category.replace('_', ' ').title(),
            'Insurer deduction': float(row.insurer_deducted),
            'Policy-supported deduction': float(row.engine_disallowed),
            'Difference': float(row.difference),
            'Result': row.status.replace('_', ' ').title(),
            'Insurer reason': row.insurer_reason,
            'Note': row.review_note or '',
            'Policy evidence': f"{row.clause.section or 'Clause'} · page {row.clause.page}" if row.clause else 'Not linked',
        } for row in comparison.categories], hide_index=True)
    explanation = None
    if comparison.status != 'manual_review':
        explanation = comparison_template_explanation(comparison)
        if user and claim.get("claim_id"):
            _render_background_analysis(str(claim["claim_id"]), str(user["user_id"]), str(user["role"]), comparison)
        else:
            with st.container(border=True):
                st.markdown('#### What the comparison means')
                st.write(explanation)
    if appeal_draft_available(comparison):
        st.markdown('#### Review documents')
        provisional_appeal = bool(rules and rules.get("policy_terms_review_status") == "provisional")
        if provisional_appeal:
            st.warning('PROVISIONAL DRAFT: policy terms are not reviewer-confirmed. This draft is watermarked and must be reviewed before use.')
        else:
            st.caption('These drafts use the comparison figures and should be checked and personalized before sending.')
        a, b = st.columns(2, gap='medium')
        with a:
            st.download_button('Appeal letter (PDF)', build_comparison_appeal_letter_pdf(claim, comparison, settlement, explanation, provisional=provisional_appeal), file_name=f"{claim.get('claim_number','claim')}-appeal-draft.pdf", mime='application/pdf', key=f"appeal_pdf_{claim.get('claim_id','claim')}")
            st.download_button('Appeal letter (Word)', build_comparison_appeal_letter_docx(claim, comparison, settlement, explanation, provisional=provisional_appeal), file_name=f"{claim.get('claim_number','claim')}-appeal-draft.docx", mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document', key=f"appeal_docx_{claim.get('claim_id','claim')}")
        with b:
            st.download_button('Hospital billing note (PDF)', build_hospital_note_pdf(claim, comparison, provisional=provisional_appeal), file_name=f"{claim.get('claim_number','claim')}-hospital-note.pdf", mime='application/pdf', key=f"hospital_pdf_{claim.get('claim_id','claim')}")
            st.download_button('Hospital billing note (Word)', build_hospital_note_docx(claim, comparison, provisional=provisional_appeal), file_name=f"{claim.get('claim_number','claim')}-hospital-note.docx", mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document', key=f"hospital_docx_{claim.get('claim_id','claim')}")
        with st.expander('Preview appeal letter'):
            st.text(build_comparison_appeal_letter_text(claim, comparison, settlement, explanation, provisional=provisional_appeal))
        with st.expander('Preview hospital note'):
            st.text(build_hospital_note_text(claim, comparison, provisional=provisional_appeal))
    elif comparison.status == 'manual_review':
        st.info('An appeal draft is unavailable until the listed comparison issue can be resolved from the source documents.')
    else:
        st.info('No appeal draft is available because no possible settlement discrepancy was identified.')


def _claim_answer_from_saved_data(question: str, result: dict[str, Any], normalized: dict[str, Any], evidence: list[dict[str, Any]]) -> str | None:
    """Answer stable claim facts without depending on model availability."""
    asked = question.lower().strip()
    amount_words = ("how much", "amount", "claim got", "claim receive", "claim received", "payable", "paid", "payout", "covered", "insurance pay", "insurance cover")
    if result.get("status") == "manual_review":
        if any(word in asked for word in amount_words) or "deductible" in asked or "copay" in asked or "co-pay" in asked or any(word in asked for word in ("excluded", "not covered", "limited", "why", "review", "status")):
            reason = str(result.get("reason") or "A source value could not be verified.")
            return f"A coverage or payment estimate is not available yet. Reason: {reason} Next step: ask an authorized reviewer to check the named source value or document issue."
    if any(word in asked for word in amount_words):
        return (
            f"The insurance-covered payable amount is {_inr(result.get('amount_covered'))}. "
            f"The total bill is {_inr(result.get('amount_billed'))}, and the claimant responsibility is {_inr(result.get('amount_claimant_pays'))}."
        )
    if "deductible" in asked:
        return f"The deductible is {_inr(result.get('deductible'))}. It is included in the claimant responsibility."
    if "copay" in asked or "co-pay" in asked:
        return f"The copayment is {_inr(result.get('copayment'))}. It is included in the claimant responsibility."
    if any(word in asked for word in ("excluded", "not covered", "limited")):
        return f"The excluded or policy-limited amount is {_inr(result.get('amount_excluded_or_limited'))}."
    if any(word in asked for word in ("status", "approved", "decision", "result")):
        status = _status_badge(str(result.get('status', 'manual_review')))
        return f"The current claim status is {status}. {result.get('reason') or 'An authorized reviewer should confirm the final determination.'}"
    if re.search(r"\bpatient\b", asked):
        patient = normalized.get('patient_name', {})
        patient = patient.get('value') if isinstance(patient, dict) else patient
        return f"The claim patient is {patient}." if patient else None
    if any(word in asked for word in ("hospital", "provider")):
        hospital = normalized.get('hospital_name', {})
        hospital = hospital.get('value') if isinstance(hospital, dict) else hospital
        return f"The listed provider is {hospital}." if hospital else None
    if any(word in asked for word in ("policy", "coverage", "waiting period", "room limit")) and evidence:
        source = evidence[0]
        clause = " ".join(str(source.get('text', '')).split())
        citation = str(source.get('clause_id') or 'retrieved policy evidence')
        if clause:
            return f"The most relevant policy evidence ({citation}) says: {clause[:550]}"
    return None


def _render_claim_assistant_chat(claim_id: str, normalized: dict[str, Any], result: dict[str, Any], workflow: dict[str, Any]) -> None:
    """The interactive portion is kept separate to retain the result card structure."""
    history_key = f'claim_questions_{claim_id}'
    st.session_state.setdefault(history_key, [])
    for message in st.session_state[history_key]:
        with st.chat_message(message['role']):
            st.write(message['content'])
    with st.form(f'claim_question_form_{claim_id}', border=False):
        question = st.text_input('Your question', placeholder='Why is my claim under review?', key=f'claim_question_input_{claim_id}')
        asked = st.form_submit_button('Ask AI assistant', type='primary', icon=':material/send:')
    if not asked or not question.strip():
        return
    st.session_state[history_key].append({'role': 'user', 'content': question})
    with st.chat_message('user'):
        st.write(question)
    with st.chat_message('assistant', avatar=':material/psychology:'):
        evidence: list[dict[str, Any]] = []
        try:
            evidence = workflow.get('policy_evidence') or retrieve_policy_evidence(saved_policy_text(claim_id), normalized, limit=3, query=question)
        except Exception:
            evidence = []
        answer = _claim_answer_from_saved_data(question, result, normalized, evidence)
        if answer is None:
            try:
                snippets = '\n'.join(f"- {str(item.get('text', ''))[:500]}" for item in evidence)
                if not snippets:
                    raise ValueError('No policy evidence is available for this claim.')
                answer = str(_ollama_json(
                    'You are a medical-insurance claim assistant. Answer only from the supplied claim result and policy evidence. Be concise, use plain language, do not invent coverage, and recommend manual review when evidence is insufficient. The answer field must contain a complete, non-empty answer.',
                    f"Question: {question}\n\nClaim result: {json.dumps(result, ensure_ascii=False)}\n\nPolicy evidence:\n{snippets}",
                    agent_name='claimant_assistant',
                    response_schema={'type': 'object', 'properties': {'answer': {'type': 'string'}}, 'required': ['answer']},
                    caller='claim_pages.py:_render_claim_assistant_chat',
                    prompt_version='claimant_qa_v1',
                    claim_id=claim_id,
                ).get('answer', '')).strip()
                if not answer:
                    raise ValueError('The assistant did not return an answer.')
            except Exception:
                answer = 'I cannot verify that from the available claim evidence. Please request a manual review so an authorized reviewer can confirm it.'
        st.write(answer)
    st.session_state[history_key].append({'role': 'assistant', 'content': answer})


def _render_dashboard(user: dict) -> None:
    claims = user_claims(user['user_id'], user)
    review_count = sum(1 for c in claims if c['status'] in {'manual_review','ready_for_review','partially_approved'})
    approved = sum(1 for c in claims if c['status'] == 'approved')
    _page_header('OVERVIEW', f'Welcome back, {user["display_name"]}', 'See the status of every claim, then move directly to the next step.', '◈')
    st.markdown('<div class="mg-welcome-note"><span>👋</span><div><b>Your claims, made clearer.</b><small>Track progress, review evidence, and take the next step with confidence.</small></div><span class="mg-welcome-spark">✦</span></div>', unsafe_allow_html=True)
    with st.container(horizontal=True, horizontal_alignment='left'):
        st.metric('Total claims', len(claims), border=True)
        st.metric('Needs attention', review_count, border=True)
        st.metric('Approval estimates', approved, border=True, help='Automated assessments marked approved. An authorized reviewer confirms the final determination.')
    with st.container(border=True):
        st.markdown('<div class="mg-section-title">Your claims</div><p class="mg-card-copy">Open a claim to continue the guided review.</p>', unsafe_allow_html=True)
        if not claims:
            st.info("You haven't registered a claim yet. Register your first claim to get started.")
            if st.button('Register a claim', type='primary'): queue_page(st.session_state, 'Register claim'); st.rerun()
        else:
            cols = st.columns(2, gap='medium')
            for i, claim in enumerate(claims[:8]):
                with cols[i % 2]:
                    with st.container(border=True):
                        st.markdown(claim_row_html(claim), unsafe_allow_html=True)
                        x,y = st.columns([3,1])
                        saved_result = _claimant_result_for_claim(claim['claim_id'], user)
                        claim_total = saved_result['amount_billed'] if saved_result else None
                        x.write(f"INR {float(claim_total or 0):,.2f}" if claim_total else 'Amount pending')
                        if y.button('Open', key=f"open_{claim['claim_id']}"):
                            st.session_state.active_claim = claim['claim_id']
                            if user['role'] == 'claimant':
                                has_result = claim['status'] in {'approved', 'partially_approved', 'rejected', 'manual_review'}
                                queue_page(st.session_state, 'Claim result' if has_result else 'Submit documents')
                            else:
                                queue_page(st.session_state, 'Claim review')
                            st.rerun()
    if user['role'] in {'reviewer','admin'}:
        queue = reviewer_queue(user)
        with st.container(border=True):
            st.markdown('<div class="mg-section-title">Review queue</div><p class="mg-card-copy">Claims awaiting an authorized review.</p>', unsafe_allow_html=True)
            if queue:
                st.dataframe([{'Claim': c['claim_number'], 'Patient': c['patient_name'], 'Status': _status_badge(c['status']), 'Priority': c['review_priority'] if 'review_priority' in c.keys() else 0} for c in queue], hide_index=True)
            else: st.info('No claims are waiting for review.')


def _render_register(user: dict) -> None:
    _page_header('NEW CLAIM', 'Register a claim', 'Start with the essentials. You can attach the bill and policy in the next step.', '+')
    if user['role'] == 'claimant':
        _claimant_progress(1, "Register your claim")
    with st.container(border=True):
        st.markdown('<div class="mg-section-title">📝 Claim details</div><p class="mg-card-copy">Fields marked by the workflow are checked against uploaded documents later.</p>', unsafe_allow_html=True)
        left,right = st.columns(2, gap='large')
        with left:
            st.markdown('### Claim Details')
            claim_number = st.text_input('Claim number', placeholder='CLM-2026-0001')
            patient = st.text_input('Patient name', placeholder='Full name')
            policy = st.text_input('Policy number', placeholder='POL-DEMO-2026-001', help='Enter exactly as shown on your policy document.')
        with right:
            st.markdown('### Service Details')
            hospital = st.text_input('Hospital / provider', placeholder='Hospital name')
            incident_date = st.date_input('Admission or service date')
            st.caption('Prototype workflow: inpatient hospitalization claims.')
        st.divider()
        if st.button('Save claim and continue', type='primary', icon=':material/arrow_forward:'):
            if not claim_number.strip() or not patient.strip(): st.error('Claim number and patient name are required.')
            else:
                claim_id = create_claim(user['user_id'], claim_number, patient, hospital, policy, str(incident_date))
                st.session_state.active_claim = claim_id
                queue_page(st.session_state, 'Submit documents' if user['role'] == 'claimant' else 'Claim review')
                st.success('Claim registered. Continue to upload documents.')
                st.rerun()


def _render_claim_submission(user: dict) -> None:
    """Claimant-only submission flow; internal extraction and rules remain hidden."""
    require_role(user, 'claimant')
    claims = user_claims(user['user_id'], user)
    _page_header('DOCUMENTS', 'Submit claim documents', 'Add the policy and bill. We will extract the key details and show a clear result.', '↑')
    _claimant_progress(2, "Add your documents")
    if not claims:
        st.info('Register a claim first, then return here to add documents.')
        if st.button('Register a claim', type='primary', icon=':material/add_circle:'):
            queue_page(st.session_state, 'Register claim'); st.rerun()
        return
    options = {f"{claim['claim_number']} · {claim['patient_name']}": claim['claim_id'] for claim in claims}
    labels = list(options)
    default = next((i for i, value in enumerate(options.values()) if value == st.session_state.get('active_claim')), 0)
    selected = st.selectbox('Choose a claim', labels, index=default, key='claimant_submission_selector')
    claim_id = options[selected]
    st.session_state.active_claim = claim_id
    with st.container(border=True):
        st.markdown('<div class="mg-section-title">📎 1. Add your documents</div><p class="mg-card-copy">Upload the hospital bill, policy, and insurer settlement letter for a complete comparison.</p>', unsafe_allow_html=True)
        st.caption("For real claims, use one applicable policy edition at a time. Do not combine a short copy and a complete copy as if they were one edition; ingest and link the version that applies to the claim, then confirm its terms from the source pages.")
        st.caption("Privacy notice: documents are stored in this prototype's configured private local storage and processed locally for this claim. Upload only what is needed for your assessment.")
        upload_columns = st.columns(3, gap='medium')
        with upload_columns[0]:
            policy_files = st.file_uploader('Insurance policy', type=['pdf', 'png', 'jpg', 'jpeg'], accept_multiple_files=True, key=f'claimant_policy_{claim_id}')
        with upload_columns[1]:
            bill_files = st.file_uploader('Medical bill and supporting documents', type=['pdf', 'png', 'jpg', 'jpeg'], accept_multiple_files=True, key=f'claimant_bill_{claim_id}')
        with upload_columns[2]:
            settlement_file = st.file_uploader('Insurer settlement letter', type=['pdf', 'txt'], accept_multiple_files=False, key=f'claimant_settlement_{claim_id}')
        if st.button('Save documents', type='primary', icon=':material/save:'):
            files = [(file, 'policy') for file in (policy_files or [])] + [(file, 'medical_bill') for file in (bill_files or [])]
            if settlement_file:
                files.append((settlement_file, 'settlement'))
            if not files:
                st.warning('Upload at least one medical bill or policy document.')
            else:
                try:
                    for uploaded, kind in files:
                        save_document(claim_id, user, uploaded, kind)
                    st.success('Documents saved. Submit them when you are ready for assessment.')
                except (ValueError, PermissionError):
                    logger.exception("Claim document upload was rejected")
                    st.error('One or more files could not be saved. Check the supported file type, size and file contents.')
    documents = claim_documents(claim_id, user)
    if documents:
        st.caption(f'{len(documents)} document(s) ready for assessment.')
        if st.button('Submit claim for assessment', type='primary', icon=':material/send:'):
            with st.status('Checking your documents and policy…', expanded=True) as status:
                try:
                    assessment = _assess_claimant_submission(claim_id, user['user_id'])
                    normalized = assessment['normalized']
                    rules = assessment['rules']
                    st.session_state[f'normalized_{claim_id}'] = normalized
                    st.session_state[f'rules_{claim_id}'] = rules
                    if 'comparison' in assessment:
                        st.session_state[f'comparison_{claim_id}'] = assessment['comparison']
                        st.session_state[f'settlement_{claim_id}'] = assessment['settlement']
                    else:
                        status.write('Upload the settlement letter to compare the insurer payment with the policy estimate.')
                    status.update(label='Assessment complete. The rules-based result is ready; explanation help is available on the result screen.', state='complete')
                    queue_page(st.session_state, 'Claim result')
                    st.rerun()
                except Exception:
                    logger.exception("Claim assessment failed")
                    status.update(label='Assessment needs attention.', state='error')
                    st.error('We could not complete the assessment. Your claim has been kept for review. Check the documents and try again.')
    else:
        st.info('Upload a policy and a medical bill to begin.')


def _render_claim_review(user: dict) -> None:
    require_role(user, 'reviewer', 'admin')
    claims = user_claims(user['user_id'], user)
    _page_header('REVIEW WORKSPACE', 'Claim review', 'Move from documents to evidence, calculations, and an authorized decision in four clear steps.', '◫')
    if not claims:
        st.info('No claims yet. Register a claim to start the workflow.'); return
    options = {f"{c['claim_number']} · {c['patient_name']}": c['claim_id'] for c in claims}
    labels = list(options); default = next((i for i,v in enumerate(options.values()) if v == st.session_state.get('active_claim')), 0)
    selected = st.selectbox('Selected claim', labels, index=default); claim_id = options[selected]; st.session_state.active_claim = claim_id
    selected_claim = next(c for c in claims if c['claim_id'] == claim_id)
    st.markdown(claim_context_html(selected_claim, selected_claim['status']), unsafe_allow_html=True)
    reviewer_rules = st.session_state.get(f"rules_{claim_id}")
    if not reviewer_rules:
        with db() as conn:
            stored_rules = conn.execute("SELECT result_json FROM rule_evaluations WHERE claim_id=? ORDER BY created_at DESC LIMIT 1", (claim_id,)).fetchone()
        if stored_rules:
            try:
                reviewer_rules = json.loads(stored_rules["result_json"])
            except (TypeError, json.JSONDecodeError):
                reviewer_rules = None
    if reviewer_rules:
        _render_policy_terms_badge(reviewer_rules.get("policy_terms_review_status"))
    tabs = st.tabs(_CLAIM_REVIEW_TAB_LABELS, default=_claim_review_tab_default(claim_id))
    with tabs[0]:
        st.markdown('### Your review path')
        path_columns = st.columns(4, gap='small')
        for column, icon, title, detail in zip(path_columns, [':material/folder_open:', ':material/upload_file:', ':material/document_scanner:', ':material/calculate:'], ['Choose', 'Add', 'Check', 'Decide'], ['Select the claim above.', 'Upload bill and policy.', 'Confirm extracted fields.', 'Run rules and sign off.']):
            with column:
                with st.container(border=True):
                    st.markdown(f'{icon}\n\n**{title}**\n\n{detail}')
    with tabs[1]:
        st.markdown('### Add source documents')
        st.caption('Keep policy and bill separate so the evidence trail stays clear.')
        pcol,bcol,scol = st.columns(3)
        with pcol: policy_files = st.file_uploader('Policy documents', type=['pdf','png','jpg','jpeg'], accept_multiple_files=True, key=f'pol_{claim_id}')
        with bcol: bill_files = st.file_uploader('Medical bill / supporting documents', type=['pdf','png','jpg','jpeg'], accept_multiple_files=True, key=f'bill_{claim_id}')
        with scol: settlement_file = st.file_uploader('Insurer settlement letter', type=['pdf','txt'], key=f'reviewer_settlement_{claim_id}')
        if st.button('Save uploaded documents', type='primary'):
            files = [(f,'policy') for f in (policy_files or [])] + [(f,'medical_bill') for f in (bill_files or [])]
            if settlement_file: files.append((settlement_file, 'settlement'))
            if not files: st.warning('Upload at least one policy or medical bill.')
            else:
                try:
                    for uploaded, kind in files: save_document(claim_id, user, uploaded, kind)
                    try:
                        assessed = _assess_claimant_submission(claim_id, user['user_id'])
                        st.session_state[f'normalized_{claim_id}'] = assessed['normalized']
                        st.session_state[f'rules_{claim_id}'] = assessed['rules']
                        if 'comparison' in assessed:
                            st.session_state[f'comparison_{claim_id}'] = assessed['comparison']
                            st.session_state[f'settlement_{claim_id}'] = assessed['settlement']
                    except Exception:
                        logger.exception("Automatic claim assessment after upload failed")
                        st.warning('Your files were saved, but automatic assessment could not finish. Reopen the claim to retry it.')
                    _remember_claim_review_tab(claim_id, 1)
                    st.success(f'Saved {len(files)} document(s). Automatic assessment has started.'); st.rerun()
                except (ValueError, PermissionError):
                    logger.exception("Reviewer document upload was rejected")
                    st.error('One or more files could not be saved. Check the supported file type, size and file contents.')
        docs = claim_documents(claim_id, user)
        if docs: st.dataframe([{'File':d['original_name'],'Type':d['document_type'].replace('_',' ').title(),'Status':_status_badge(d['processing_status'])} for d in docs], hide_index=True)
        else: st.info('Your saved documents will appear here.')
    docs = claim_documents(claim_id, user)
    with tabs[2]:
        normalized = st.session_state.get(f'normalized_{claim_id}')
        if st.button('Run extraction', type='primary'):
            with st.status('Reading documents and normalizing fields...', expanded=True) as status:
                try:
                    normalized = process_claim_documents(claim_id, user['user_id']); st.session_state[f'normalized_{claim_id}'] = normalized; status.update(label='Extraction complete', state='complete')
                except Exception:
                    logger.exception("Reviewer document extraction failed")
                    status.update(label='Extraction failed', state='error')
                    st.error('Document extraction did not finish. Check the uploaded files and try again.')
            _remember_claim_review_tab(claim_id, 2)
            st.rerun()
        if normalized:
            missing = normalized.get('missing_fields',[]) + normalized.get('review_fields',[])
            if missing: st.warning('Some fields need your input before analysis: ' + ', '.join(missing))
            fields=[]
            for key in ('patient_name','hospital_name','policy_number','claim_number','admission_date','discharge_date','diagnosis','total_amount'):
                item=normalized.get(key)
                if item: fields.append({'Field':key.replace('_',' ').title(),'Value':str(item['value']),'Confidence':round(float(item['confidence']),1),'Review':'Yes' if item['needs_review'] else 'No'})
            with st.container(horizontal=True, horizontal_alignment='left'):
                st.metric('Fields extracted', len(fields), border=True)
                st.metric('Needs review', len(missing), border=True)
                st.metric('Line items', len(normalized.get('line_items',[])), border=True)
            with st.expander('Extracted summary', expanded=True): st.dataframe(fields, hide_index=True)
            with st.expander(f"Line items ({len(normalized.get('line_items',[]))}"): st.dataframe([{k:i.get(k) for k in ('description','amount','category','confidence','needs_review')} for i in normalized.get('line_items',[])], hide_index=True)
            with st.expander('Field-by-field evidence'): st.json(normalized)
            bill_docs = [doc for doc in docs if doc['document_type'] == 'medical_bill']
            if bill_docs:
                st.markdown('### Reviewer-confirmed bill details')
                st.caption('Correct missing or inaccurate values against the original bill. Save the source page with each correction; these confirmed values are stored in SQLite and used by the rules.')
                bill_docs_by_id = {doc['document_id']: doc for doc in bill_docs}
                source_doc_id = st.selectbox('Bill document used for confirmations', list(bill_docs_by_id), format_func=lambda document_id: bill_docs_by_id[document_id]['original_name'], key=f'review_bill_source_{claim_id}')
                source_doc = bill_docs_by_id[source_doc_id]
                field_rows = []
                review_field_names = ('patient_name','hospital_name','policy_number','claim_number','admission_date','discharge_date','bill_date','diagnosis','total_amount')
                for name in review_field_names:
                    item = normalized.get(name) or {}
                    evidence = item.get('evidence') or []
                    source_page = next((row.get('page') for row in evidence if isinstance(row, dict) and row.get('page')), 1)
                    field_rows.append({'Field': name, 'Value': str(item.get('value') or ''), 'Source page': int(source_page)})
                edited_fields = st.data_editor(field_rows, hide_index=True, num_rows='fixed', key=f'review_fields_editor_{claim_id}', column_config={'Field': st.column_config.TextColumn('Field', disabled=True), 'Value': st.column_config.TextColumn('Confirmed value'), 'Source page': st.column_config.NumberColumn('Source page', min_value=1, step=1)})
                line_rows = []
                for item in normalized.get('line_items') or []:
                    evidence = item.get('evidence') or []
                    source_page = next((row.get('page') for row in evidence if isinstance(row, dict) and row.get('page')), 1)
                    line_rows.append({'description': item.get('description',''), 'amount': item.get('amount',''), 'date': item.get('date') or '', 'category': item.get('category','other'), 'source_page': int(source_page)})
                edited_lines = st.data_editor(line_rows, hide_index=True, num_rows='dynamic', key=f'review_lines_editor_{claim_id}', column_config={'description': st.column_config.TextColumn('Description'), 'amount': st.column_config.NumberColumn('Amount (INR)', min_value=0.0, step=1.0), 'date': st.column_config.TextColumn('Service date (DD/MM/YYYY)'), 'category': st.column_config.TextColumn('Category'), 'source_page': st.column_config.NumberColumn('Source page', min_value=1, step=1)})
                if st.button('Save reviewer-confirmed bill details', type='primary', key=f'save_extraction_review_{claim_id}'):
                    try:
                        records = edited_fields.to_dict('records') if hasattr(edited_fields, 'to_dict') else edited_fields
                        edits = {}
                        for row in records:
                            name = str(row.get('Field') or '')
                            value = str(row.get('Value') or '').strip()
                            if value:
                                edits[name] = {'value': value, 'page': int(row.get('Source page') or 1), 'document_id': source_doc['document_id']}
                        line_records = edited_lines.to_dict('records') if hasattr(edited_lines, 'to_dict') else edited_lines
                        line_records = [row for row in line_records if str(row.get('description') or '').strip() or row.get('amount') not in (None, '')]
                        if line_records:
                            first = line_records[0]
                            edits['line_items'] = {'value': line_records, 'page': int(first.get('source_page') or 1), 'document_id': source_doc['document_id']}
                        save_claim_extraction_review(claim_id, user['user_id'], edits)
                        normalized = apply_claim_extraction_reviews(claim_id, normalized)
                        st.session_state[f'normalized_{claim_id}'] = normalized
                        st.session_state.pop(f'rules_{claim_id}', None)
                        st.session_state.pop(f'workflow_{claim_id}', None)
                        _remember_claim_review_tab(claim_id, 2)
                        st.success(f"Saved reviewer confirmations for {len(edits)} field groups.")
                        st.rerun()
                    except Exception:
                        logger.exception("Reviewer bill-detail confirmation failed")
                        st.error('The confirmed bill details could not be saved. Check the values and source page.')
        else: st.info('Run extraction after saving documents.')
    with tabs[3]:
        normalized = st.session_state.get(f'normalized_{claim_id}')
        rules = st.session_state.get(f'rules_{claim_id}')
        if not normalized:
            st.warning('Complete extraction before analysis.')
        else:
            if user['role'] in {'reviewer','admin'}:
                st.markdown('### Link the applicable policy edition')
                editions = policy_versions()
                if editions:
                    labels = {f"{edition['policy_number']} · {edition['version_label']} · {edition['source_name']} · {edition['status']}": edition['version_id'] for edition in editions}
                    linked_id = selected_claim['policy_version_id']
                    current_index = _policy_edition_default_index(
                        editions, linked_id, selected_claim['policy_number']
                    )
                    with st.form(f'link_policy_edition_{claim_id}'):
                        chosen_policy = st.selectbox('Policy edition', list(labels), index=current_index)
                        link_policy = st.form_submit_button('Link edition to this claim')
                    if link_policy:
                        try:
                            link_policy_version_to_claim(claim_id, user['user_id'], labels[chosen_policy])
                            _remember_claim_review_tab(claim_id, 3)
                            st.success('Policy edition linked to this claim.')
                            st.rerun()
                        except Exception:
                            logger.exception("Policy edition could not be linked to the claim")
                            st.error('The policy edition could not be linked. Check your access and selected policy.')
                    linked_policy = next((edition for edition in editions if edition['version_id'] == linked_id), None)
                    if linked_policy:
                        st.caption(f"Linked edition: {linked_policy['version_label']} · Term review: {linked_policy['terms_review_status']}")
                    else:
                        st.warning('No policy edition is linked. Link the correct edition before calculating.')
                else:
                    st.info('Ingest the applicable policy edition in Policy management, then link it here.')
            if st.button('Run deterministic coverage rules', type='primary'):
                with st.status('Applying policy rules...', expanded=True) as status:
                    try: rules=evaluate_saved_claim(claim_id,user['user_id'],normalized); st.session_state[f'rules_{claim_id}']=rules; status.update(label='Rules complete',state='complete')
                    except Exception:
                        logger.exception("Claim rules evaluation failed")
                        status.update(label='Rules failed',state='error')
                        st.error('The policy calculation could not be completed. Review the confirmed policy terms and bill details.')
                _remember_claim_review_tab(claim_id, 3)
                st.rerun()
            if rules:
                result_status = _safe_status(rules['status'])
                st.markdown(deterministic_result_header_html(result_status), unsafe_allow_html=True)
                with st.container(horizontal=True, horizontal_alignment='left'):
                    for label, key in (('Known eligible before unresolved terms', 'covered_before_cost_sharing'), ('Deductible', 'deductible'), ('Copayment', 'copayment'), ('Estimated insurer payment', 'payable_amount')):
                        value = rules.get(key)
                        st.metric(label, f"INR {float(value):,.2f}" if value is not None else 'Not calculable', border=True)
                if rules.get('warnings'): st.warning('; '.join(rules['warnings']))
                with st.expander('Why this result? Rule trace', expanded=True): st.dataframe(rules.get('results',[]), hide_index=True)
                if user['role'] in {'reviewer','admin'}:
                    with st.container(border=True):
                        st.markdown('### Reviewer Sign-off')
                        st.caption('The Python rules provide the automated estimate. Reviewer sign-off records your determination separately.')
                        final=st.selectbox('Final determination',['approved','partially_approved','rejected','manual_review'],format_func=_status_badge,key=f'final_{claim_id}')
                        comments=st.text_area('Reviewer comments',key=f'comments_{claim_id}')
                        if st.button('Confirm sign-off',key=f'save_final_{claim_id}',type='primary'):
                            if not comments.strip(): st.warning('Reviewer comments are required.')
                            else: save_reviewer_decision(claim_id,user['user_id'],rules.get('status','manual_review'),final,comments); st.success('Reviewer decision saved and audited.')
            else: st.info('Run deterministic rules before starting the agents.')
    with tabs[4]:
        normalized = st.session_state.get(f'normalized_{claim_id}')
        rules = st.session_state.get(f'rules_{claim_id}')
        comparison, settlement = get_comparison_for_view(claim_id, user)
        settlement_docs = [doc for doc in claim_documents(claim_id, user) if doc['document_type'] == 'settlement']
        if not settlement_docs:
            st.info('Upload and save the insurer settlement letter in Add documents first.')
        elif not normalized or not rules:
            st.info('Run extraction and deterministic coverage rules before comparing the settlement.')
        elif st.button('Run settlement comparison', type='primary', key=f'run_settlement_comparison_{claim_id}'):
            try:
                comparison, settlement = run_settlement_comparison(claim_id, user['user_id'], normalized, rules)
                st.session_state[f'comparison_{claim_id}'] = comparison
                st.session_state[f'settlement_{claim_id}'] = settlement
                _remember_claim_review_tab(claim_id, 4)
                st.rerun()
            except Exception:
                logger.exception("Settlement comparison failed")
                st.error('The settlement comparison could not be completed. Check the settlement amount and deductions.')
        comparison, settlement = get_comparison_for_view(claim_id, user)
        if comparison and settlement:
            _render_settlement_comparison(dict(selected_claim), comparison, settlement, user, normalized, rules)
    st.caption('Decision support only. Final determination must be confirmed by an authorized reviewer.')


