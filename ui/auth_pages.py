"""Authentication and welcome screens. Loaded lazily from app.main."""

import app as _app
globals().update(vars(_app))

def _render_welcome() -> None:
    """Opening screen only; it does not alter login or claim workflow state."""
    st.markdown('''<div class="mg-opening">
      <div class="mg-opening-orb orb-one"></div><div class="mg-opening-orb orb-two"></div>
      <div class="mg-opening-logo"><svg viewBox="0 0 64 64" aria-hidden="true"><path d="M32 5 54 13v16c0 14.5-9.4 25.2-22 30C19.4 54.2 10 43.5 10 29V13L32 5Z" fill="currentColor"/><path d="M32 16v30M20 31h24" stroke="#073b3a" stroke-width="5" stroke-linecap="round"/><path d="M22 42c3.1 4.2 8.4 6.9 10 7.5 1.6-.6 6.9-3.3 10-7.5" fill="none" stroke="#073b3a" stroke-width="3" stroke-linecap="round"/></svg></div>
      <div class="mg-opening-brand">MEDIGUARD AI</div>
      <h1>Healthcare claims,<br><em>made understandable.</em></h1>
      <p>Upload documents, understand coverage, and make every decision with evidence you can review.</p>
      <div class="mg-opening-chips"><span>🩺 Care-first</span><span>📄 Evidence-led</span><span>🔐 Privacy-aware</span></div>
    </div>''', unsafe_allow_html=True)
    st.markdown('<div class="mg-role-label">CHOOSE YOUR WORKSPACE</div>', unsafe_allow_html=True)
    entry = st.radio(
        'Choose your workspace',
        ['User / claimant', 'Admin / reviewer'],
        horizontal=True,
        label_visibility='collapsed',
        format_func=lambda role: '👤 User — sign in or create account' if role == 'User / claimant' else '🛡️ Admin — secure sign in',
    )
    _, action, _ = st.columns([1, 1, 1])
    with action:
        label = 'Continue as user' if entry == 'User / claimant' else 'Continue as admin'
        if st.button(label, type='primary', icon=':material/arrow_forward:', use_container_width=True):
            st.session_state.entry_role = 'claimant' if entry == 'User / claimant' else 'staff'
            st.session_state.welcome_seen = True
            st.rerun()
    st.caption('Built for clearer conversations between patients, providers, and reviewers.')


def _render_login() -> None:
    reset_token = st.query_params.get('reset_token')
    setup_token = st.query_params.get('setup_token')
    if reset_token or setup_token:
        st.subheader('Reset password' if reset_token else 'Set up reviewer account')
        with st.form('complete_account_setup'):
            password = st.text_input('New password', type='password')
            confirmation = st.text_input('Confirm new password', type='password')
            submitted = st.form_submit_button('Save password', type='primary')
        if submitted:
            try:
                if password != confirmation:
                    raise ValueError('Passwords do not match.')
                if reset_token:
                    complete_password_reset(reset_token, password)
                else:
                    complete_reviewer_setup(setup_token, password)
                st.query_params.clear()
                st.success('Password saved. You can now sign in.')
            except ValueError as exc:
                st.error(str(exc))
        if st.button('Back to sign in'):
            st.query_params.clear()
            st.rerun()
        return
    staff_portal = st.session_state.get('entry_role') == 'staff'
    left, right = st.columns([1.1, 1], gap='large')
    with left:
        st.markdown('''<div class="mg-landing">
        <div class="mg-landing-badge">✨ Evidence-first claim support</div>
        <div class="mg-landing-art" aria-hidden="true"><span>🩺</span><span>📄</span><span>🛡️</span><span>💚</span></div>
        <div class="mg-shield large">M</div><h1>Clarity for every claim.</h1>
        <p class="mg-tagline">Bring your bill and policy together in one guided, evidence-led review.</p>
        <div class="mg-landing-points"><span>📄 Extract</span><span>🔎 Verify</span><span>✓ Decide</span></div>
        <p class="mg-promise">Transparent calculations. Human confirmation.</p>
        </div>''', unsafe_allow_html=True)
    with right:
        portal_title = 'Admin sign in' if staff_portal else 'Welcome back'
        portal_copy = 'Use your authorized administrator or reviewer credentials.' if staff_portal else 'Sign in to continue your claim review.'
        portal_label = 'ADMINISTRATOR PORTAL' if staff_portal else 'USER WORKSPACE'
        st.markdown(auth_portal_html(portal_label, portal_title, portal_copy), unsafe_allow_html=True)
        if staff_portal:
            login_tab, reset_tab = st.tabs(['Secure sign in', 'Reset password'])
        else:
            login_tab, register_tab, reset_tab = st.tabs(['Sign in', 'Create account', 'Reset password'])
        with login_tab:
            with st.form('login'):
                email = st.text_input('Email', placeholder='you@example.com')
                password = st.text_input('Password', type='password')
                st.checkbox('Remember me', value=True)
                submitted = st.form_submit_button('Sign in', type='primary')
            if submitted:
                user_row = authenticate_password(email, password)
                if user_row is None:
                    st.error("That email or password doesn't match our records.")
                elif staff_portal and user_row['role'] not in {'admin', 'reviewer'}:
                    st.error('These credentials are for a user account. Select the User workspace to continue.')
                elif not staff_portal and user_row['role'] != 'claimant':
                    st.error('These credentials are for an administrator or reviewer. Select the Admin workspace to continue.')
                else:
                    st.session_state.user = dict(user_row)
                    st.session_state.page = 'Dashboard'
                    st.rerun()
        if not staff_portal:
            with register_tab:
                with st.form('register'):
                    name = st.text_input('Full name')
                    email = st.text_input('Email', key='reg_email')
                    p1 = st.text_input('Password', type='password')
                    p2 = st.text_input('Confirm password', type='password')
                    st.caption('Use at least 10 characters. New self-registered accounts are Claimants.')
                    submitted = st.form_submit_button('Create account', type='primary')
                if submitted:
                    try:
                        if p1 != p2: raise ValueError('Passwords do not match.')
                        st.session_state.user = dict(register_user(email, name, p1))
                        st.session_state.page = 'Dashboard'; st.rerun()
                    except (ValueError, PermissionError) as exc: st.error(str(exc))
        with reset_tab:
            st.caption('For privacy, this response does not reveal whether an email exists.')
            with st.form('reset_request'):
                email = st.text_input('Account email', key='reset_email')
                submitted = st.form_submit_button('Send reset link', type='primary')
            if submitted:
                request = create_password_reset_request(email)
                st.success('If this email exists, a reset link has been issued.')
                _render_password_reset_link(request)
        if st.button('← Choose a different workspace', key='change_workspace'):
            st.session_state.pop('entry_role', None)
            st.session_state.welcome_seen = False
            st.rerun()


