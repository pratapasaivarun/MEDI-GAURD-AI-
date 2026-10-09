"""Claimant and reviewer claim/result screens. Loaded from app.main."""

import app as _app
globals().update(vars(_app))

def _claimant_result_for_claim(claim_id: str, user: dict) -> dict[str, Any] | None:
    """Return only claimant-safe amounts and explanation; hide raw agent/reviewer data."""
    claim = _claim_access(claim_id, user)
    rules = st.session_state.get(f"rules_{claim_id}")
    workflow = st.session_state.get(f"workflow_{claim_id}") or {}
    if not rules:
        with db() as conn:
            row = conn.execute("SELECT result_json FROM rule_evaluations WHERE claim_id=? ORDER BY created_at DESC LIMIT 1", (claim_id,)).fetchone()
        if row:
            try:
                rules = json.loads(row["result_json"])
            except (TypeError, json.JSONDecodeError):
                rules = None
    if not rules and not workflow:
        return None
    decision = workflow.get("decision") or {}
    status = claim["status"] if claim["status"] in {"approved", "partially_approved", "rejected", "manual_review"} else (decision.get("status") or ((rules or {}).get("status", "manual_review")))
    claimant = (rules or {}).get("claimant_result") or {}
    billed = float(claimant.get("amount_billed", 0) or 0)
    covered = float(claimant.get("amount_covered", (rules or {}).get("payable_amount", 0)) or 0)
    responsibility = float(claimant.get("amount_claimant_pays", max(0, billed - covered)) or 0)
    deductible = float(claimant.get("deductible", (rules or {}).get("deductible", 0)) or 0)
    copayment = float(claimant.get("copayment", (rules or {}).get("copayment", 0)) or 0)
    excluded_or_limited = float(claimant.get("amount_excluded_or_limited", 0) or 0)
    not_paid = float(claimant.get("amount_not_covered", responsibility) or 0)
    reasons = decision.get("reasons") or (rules or {}).get("warnings") or []
    reason = _claim_warning_message(reasons[0]) if reasons else "Your claim has been processed and the result is ready to review."
    return {
        "status": status,
        "amount_billed": billed,
        "amount_covered": covered,
        "amount_claimant_pays": responsibility,
        "amount_not_covered": not_paid,
        "deductible": deductible,
        "copayment": copayment,
        "amount_excluded_or_limited": excluded_or_limited,
        "reason": reason,
        "requires_human_review": status == "manual_review",
        "rules": rules or {},
    }


def _render_claimant_result(user: dict) -> None:
    claims = user_claims(user["user_id"], user)
    _page_header('CLAIM OUTCOME', 'Your claim result', 'A simple view of the policy review, your estimated responsibility, and next steps.', '✓')
    _claimant_progress(3, "Review your assessment")
    if not claims:
        st.info("You do not have a claim yet.")
        if st.button("Register a claim", type="primary"):
            st.session_state.page = "Register claim"; st.rerun()
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
            st.session_state.page = "Submit documents" if user['role'] == 'claimant' else "Claim review"; st.rerun()
        return
    status = result["status"]
    if status == "manual_review":
        st.warning("Your claim is under review. Some information must be confirmed before a final result can be issued.")
    elif status == "approved":
        st.success("The automated assessment indicates approval based on the information currently available.")
    elif status == "partially_approved":
        st.warning("The automated assessment indicates partial coverage. Some charges were limited or excluded under the policy.")
    elif status == "rejected":
        st.error("The automated assessment indicates that the current policy information does not cover this claim.")
    amount_columns = st.columns(3, gap="medium")
    amount_columns[0].metric("Total bill", f"INR {result['amount_billed']:,.2f}", border=True)
    if result["requires_human_review"]:
        amount_columns[1].metric("Estimated insurance share", "Pending review", border=True)
        amount_columns[2].metric("Estimated amount you pay", "Pending review", border=True)
    else:
        amount_columns[1].metric("Estimated insurance share", f"INR {result['amount_covered']:,.2f}", border=True)
        amount_columns[2].metric("Estimated amount you pay", f"INR {result['amount_claimant_pays']:,.2f}", border=True)
    with st.container(border=True):
        st.markdown("### What this means for you")
        st.write(result["reason"])
        if result["requires_human_review"]:
            st.write("Coverage and your estimated payment are not available until the bill and applicable policy terms are confirmed.")
            st.caption("This is not a final determination. An authorized reviewer must confirm the result.")
        else:
            st.write(
                f"The claimant responsibility of INR {result['amount_claimant_pays']:,.2f} includes "
                f"INR {result['deductible']:,.2f} deductible and INR {result['copayment']:,.2f} copayment. "
                f"INR {result['amount_excluded_or_limited']:,.2f} is excluded or limited by the policy."
            )
            st.caption("Deductible and copayment are policy cost-sharing amounts, not rejected charges. Excluded or policy-limited amounts are charges the policy does not pay.")
            st.caption("This is decision-support information. Final determination should be confirmed by an authorized reviewer.")
    rules = result.get("rules", {})
    workflow = st.session_state.get(f"workflow_{claim_id}") or {}
    # Persisted claim status includes agent failures and reviewer sign-off, even
    # after a new browser session loses its cached workflow.
    workflow = {**workflow, "decision": {**workflow.get("decision", {}), "status": result["status"]}}
    normalized = st.session_state.get(f"normalized_{claim_id}") or {}
    if rules.get("line_item_reconciliation_failed"):
        st.info(str(rules.get("line_item_notice") or _claim_warning_message("line_item_reconciliation_failed")))
    if result["requires_human_review"]:
        st.info("The amount breakdown will be available after the reviewer confirms the required information.")
    else:
        with st.expander("See the amount breakdown", expanded=False):
            st.write(f"Covered amount before deductions: INR {float(rules.get('covered_amount', 0) or 0):,.2f}")
            st.write(f"Deductible: INR {float(result.get('deductible', 0) or 0):,.2f}")
            st.write(f"Copayment: INR {float(result.get('copayment', 0) or 0):,.2f}")
            st.write(f"Excluded or policy-limited amount: INR {float(result.get('amount_excluded_or_limited', 0) or 0):,.2f}")
            st.caption("Claimant responsibility equals deductible, copayment, and any excluded or policy-limited amount.")
            adjustments = []
            for item in rules.get("results", []):
                if item.get("status") in {"partial", "fail"}:
                    adjustments.append({"Policy check": str(item.get("rule_id", "")).replace("_", " ").title(), "Effect": item.get("calculation", "Policy adjustment applied"), "Amount affected": item.get("amount")})
            if adjustments:
                st.markdown("#### Items or rules affecting coverage")
                st.dataframe(adjustments, hide_index=True)
            warnings = rules.get("warnings") or []
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
                    "Status": st.column_config.MarkdownColumn(),
                },
            )
    recommendations = recommend_next_steps(
        workflow.get("decision") or {},
        {**rules, "billing_anomalies": billing_anomalies, "submission_deadline": submission_deadline or {}},
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
    comparison, settlement = get_comparison_for_view(claim_id, user)
    if comparison and settlement:
        with st.container(border=True):
            _render_settlement_comparison(dict(claim), comparison, settlement, user, normalized, rules)
    else:
        st.info("Upload the insurer's settlement letter to compare it and enable a draft.")
    _render_claim_assistant(claim_id, normalized, result, workflow)
    if st.button("Back to dashboard"):
        st.session_state.page = "Dashboard"; st.rerun()


def _render_claim_assistant(claim_id: str, normalized: dict[str, Any], result: dict[str, Any], workflow: dict[str, Any]) -> None:
    """A claimant-facing, evidence-bounded question interface for one claim."""
    with st.container(border=True):
        st.subheader('💬 Ask about this claim', anchor=False)
        st.caption('Ask in plain language. Answers are grounded only in this claim’s documents and decision data. ✨')
        _render_claim_assistant_chat(claim_id, normalized, result, workflow)


def _inr(value: Any) -> str:
    return f"INR {float(value or 0):,.2f}"


def appeal_draft_available(comparison: Any) -> bool:
    """Appeal downloads require a comparison with a possible discrepancy."""
    return comparison is not None and getattr(comparison, "status", None) == "possible_discrepancy"


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
                except Exception as exc:
                    st.error(f'Could not confirm the uploaded bill total: {exc}')
    metrics = st.columns(3, gap='medium')
    metrics[0].metric('Settlement payment', _inr(comparison.actual_insurer_payment), border=True)
    metrics[1].metric('Estimated insurer payment', _inr(comparison.expected_insurer_payment) if comparison.status != 'manual_review' else 'Pending review', border=True)
    metrics[2].metric('Possible difference', _inr(comparison.possible_difference) if comparison.status != 'manual_review' else 'Pending review', border=True)
    if comparison.status == 'manual_review':
        st.warning('The comparison needs an authorized reviewer to confirm the source values and policy evidence.')
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
        explanation = explain_comparison(comparison)
        with st.container(border=True):
            st.markdown('#### What the comparison means')
            st.write(explanation)
    if appeal_draft_available(comparison):
        st.markdown('#### Review documents')
        st.caption('These drafts use the comparison figures and should be checked and personalized before sending.')
        a, b = st.columns(2, gap='medium')
        with a:
            st.download_button('Appeal letter (PDF)', build_comparison_appeal_letter_pdf(claim, comparison, settlement, explanation), file_name=f"{claim.get('claim_number','claim')}-appeal-draft.pdf", mime='application/pdf', key=f"appeal_pdf_{claim.get('claim_id','claim')}")
            st.download_button('Appeal letter (Word)', build_comparison_appeal_letter_docx(claim, comparison, settlement, explanation), file_name=f"{claim.get('claim_number','claim')}-appeal-draft.docx", mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document', key=f"appeal_docx_{claim.get('claim_id','claim')}")
        with b:
            st.download_button('Hospital billing note (PDF)', build_hospital_note_pdf(claim, comparison), file_name=f"{claim.get('claim_number','claim')}-hospital-note.pdf", mime='application/pdf', key=f"hospital_pdf_{claim.get('claim_id','claim')}")
            st.download_button('Hospital billing note (Word)', build_hospital_note_docx(claim, comparison), file_name=f"{claim.get('claim_number','claim')}-hospital-note.docx", mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document', key=f"hospital_docx_{claim.get('claim_id','claim')}")
        with st.expander('Preview appeal letter'):
            st.text(build_comparison_appeal_letter_text(claim, comparison, settlement, explanation))
        with st.expander('Preview hospital note'):
            st.text(build_hospital_note_text(claim, comparison))
    else:
        st.info("Upload the insurer's settlement letter to compare it and enable a draft.")


def _claim_answer_from_saved_data(question: str, result: dict[str, Any], normalized: dict[str, Any], evidence: list[dict[str, Any]]) -> str | None:
    """Answer stable claim facts without depending on model availability."""
    asked = question.lower().strip()
    amount_words = ("how much", "amount", "claim got", "claim receive", "claim received", "payable", "paid", "payout", "covered", "insurance pay", "insurance cover")
    if result.get("status") == "manual_review":
        if any(word in asked for word in amount_words) or "deductible" in asked or "copay" in asked or "co-pay" in asked or any(word in asked for word in ("excluded", "not covered", "limited")):
            return "A coverage or payment estimate is not available yet. An authorized reviewer must confirm the bill details and applicable policy terms first."
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
            if st.button('Register a claim', type='primary'): st.session_state.page = 'Register claim'; st.rerun()
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
                                st.session_state.page = 'Claim result' if has_result else 'Submit documents'
                            else:
                                st.session_state.page = 'Claim review'
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
                st.session_state.page = 'Submit documents' if user['role'] == 'claimant' else 'Claim review'
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
            st.session_state.page = 'Register claim'; st.rerun()
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
                except (ValueError, PermissionError) as exc:
                    st.error(str(exc))
    documents = claim_documents(claim_id, user)
    if documents:
        st.caption(f'{len(documents)} document(s) ready for assessment.')
        if st.button('Submit claim for assessment', type='primary', icon=':material/send:'):
            with st.status('Checking your documents and policy…', expanded=True) as status:
                try:
                    normalized = process_claim_documents(claim_id, user['user_id'])
                    rules = evaluate_saved_claim(claim_id, user['user_id'], normalized)
                    st.session_state[f'normalized_{claim_id}'] = normalized
                    st.session_state[f'rules_{claim_id}'] = rules
                    if any(doc['document_type'] == 'settlement' for doc in claim_documents(claim_id, user)):
                        comparison, settlement = run_settlement_comparison(claim_id, user['user_id'], normalized, rules)
                        st.session_state[f'comparison_{claim_id}'] = comparison
                        st.session_state[f'settlement_{claim_id}'] = settlement
                    else:
                        status.write('Upload the settlement letter to compare the insurer payment with the policy estimate.')
                    if rules['status'] == 'manual_review':
                        status.update(label='Your claim needs a manual review.', state='complete')
                    else:
                        workflow = run_agents_for_claim(claim_id, user['user_id'], normalized, rules, progress_callback=status.write)
                        st.session_state[f'workflow_{claim_id}'] = workflow
                        status.update(label='Assessment complete.', state='complete')
                    st.session_state.page = 'Claim result'
                    st.rerun()
                except Exception as exc:
                    status.update(label='Assessment needs attention.', state='error')
                    st.error('We could not complete the assessment. Your claim has been kept for review. ' + str(exc))
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
    tabs = st.tabs(['1 · Choose claim', '2 · Add documents', '3 · Check extraction', '4 · Calculate & review', '5 · Compare settlement & draft letters'])
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
                    st.success(f'Saved {len(files)} document(s).'); st.rerun()
                except (ValueError, PermissionError) as exc: st.error(str(exc))
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
                except Exception as exc: status.update(label='Extraction failed', state='error'); st.error(str(exc))
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
                    line_rows.append({'description': item.get('description',''), 'amount': item.get('amount',''), 'category': item.get('category','other'), 'source_page': int(source_page)})
                edited_lines = st.data_editor(line_rows, hide_index=True, num_rows='dynamic', key=f'review_lines_editor_{claim_id}', column_config={'description': st.column_config.TextColumn('Description'), 'amount': st.column_config.NumberColumn('Amount (INR)', min_value=0.0, step=1.0), 'category': st.column_config.TextColumn('Category'), 'source_page': st.column_config.NumberColumn('Source page', min_value=1, step=1)})
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
                        st.success(f"Saved reviewer confirmations for {len(edits)} field groups.")
                        st.rerun()
                    except Exception as exc:
                        st.error(f'Could not save reviewer-confirmed bill details: {exc}')
        else: st.info('Run extraction after saving documents.')
    with tabs[3]:
        normalized = st.session_state.get(f'normalized_{claim_id}')
        rules = st.session_state.get(f'rules_{claim_id}')
        if not normalized: st.warning('Complete extraction before analysis.'); return
        if user['role'] in {'reviewer','admin'}:
            st.markdown('### Link the applicable policy edition')
            editions = policy_versions()
            if editions:
                labels = {f"{edition['policy_number']} · {edition['version_label']} · {edition['source_name']} · {edition['status']}": edition['version_id'] for edition in editions}
                linked_id = selected_claim['policy_version_id']
                current_index = next((i for i, value in enumerate(labels.values()) if value == linked_id), 0)
                with st.form(f'link_policy_edition_{claim_id}'):
                    chosen_policy = st.selectbox('Policy edition', list(labels), index=current_index)
                    link_policy = st.form_submit_button('Link edition to this claim')
                if link_policy:
                    try:
                        link_policy_version_to_claim(claim_id, user['user_id'], labels[chosen_policy])
                        st.success('Policy edition linked to this claim.')
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))
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
                except Exception as exc: status.update(label='Rules failed',state='error'); st.error(str(exc))
        if rules:
            result_status = _safe_status(rules['status'])
            st.markdown(deterministic_result_header_html(result_status), unsafe_allow_html=True)
            with st.container(horizontal=True, horizontal_alignment='left'):
                st.metric('Covered',f"INR {rules.get('covered_amount',0):,.2f}", border=True)
                st.metric('Deductible',f"INR {rules.get('deductible',0):,.2f}", border=True)
                st.metric('Copayment',f"INR {rules.get('copayment',0):,.2f}", border=True)
                st.metric('Payable',f"INR {rules.get('payable_amount',0):,.2f}", border=True)
            if rules.get('warnings'): st.warning('; '.join(rules['warnings']))
            with st.expander('Why this result? Rule trace', expanded=True): st.dataframe(rules.get('results',[]), hide_index=True)
            workflow=st.session_state.get(f'workflow_{claim_id}')
            if st.button('Run Policy Agent + Decision Agent', type='primary'):
                with st.status('Retrieving policy evidence...', expanded=True) as status:
                    st.caption('Local AI processing can take 1–2 minutes on CPU. Keep this page open while it completes.')
                    try:
                        started=time.perf_counter(); workflow=run_agents_for_claim(claim_id,user['user_id'],normalized,rules,progress_callback=lambda msg: status.write(msg)); workflow['elapsed_seconds']=round(time.perf_counter()-started,2); st.session_state[f'workflow_{claim_id}']=workflow; status.update(label='Two-agent analysis complete',state='complete')
                    except Exception as exc: status.update(label='Agent workflow failed',state='error'); st.error(str(exc))
            if workflow:
                decision=workflow.get('decision',{}); decision_status = _safe_status(decision.get('status','manual_review')); st.markdown(evidence_recommendation_header_html(decision_status), unsafe_allow_html=True)
                for reason in decision.get('reasons',[]): st.write(f'• {reason}')
                st.caption(f"Policy source: {workflow.get('policy_source','none')} · LLM calls: {workflow.get('llm_calls',0)} · Time: {workflow.get('elapsed_seconds','n/a')}s")
                with st.expander('Policy evidence and agent reasoning'): st.json({'decision':decision,'policy_findings':workflow.get('policy_findings',{})})
                if user['role'] in {'reviewer','admin'}:
                    with st.container(border=True):
                        st.markdown('### Reviewer Sign-off')
                        final=st.selectbox('Final determination',['approved','partially_approved','rejected','manual_review'],format_func=_status_badge,key=f'final_{claim_id}')
                        comments=st.text_area('Reviewer comments',key=f'comments_{claim_id}')
                        if st.button('Confirm sign-off',key=f'save_final_{claim_id}',type='primary'):
                            if not comments.strip(): st.warning('Reviewer comments are required.')
                            else: save_reviewer_decision(claim_id,user['user_id'],decision.get('status','manual_review'),final,comments); st.success('Reviewer decision saved and audited.')
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
            except Exception as exc:
                st.error(f'Settlement comparison could not be completed: {exc}')
        comparison, settlement = get_comparison_for_view(claim_id, user)
        if comparison and settlement:
            _render_settlement_comparison(dict(selected_claim), comparison, settlement, user, normalized, rules)
    st.caption('Decision support only. Final determination must be confirmed by an authorized reviewer.')


