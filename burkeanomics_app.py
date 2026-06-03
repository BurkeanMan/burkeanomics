import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import json
import math
from datetime import datetime, timedelta
from calculations import calculate_per_capita, calculate_en_masse, calculate_breakdown
from export import (
    build_report_html,
    figs_to_html_fragments,
    normalize_pdf_filename,
    render_pdf_with_playwright,
)
from supabase_client import (
    is_logged_in, current_user, is_admin,
    sign_in, sign_up, sign_out,
    send_password_reset, update_password,
    list_universes, save_universe, load_universe, delete_universe,
    get_default_universe, set_default_universe,
)

# Apply any pending JSON import before widgets are instantiated
if "_import_pending" in st.session_state:
    _pending = st.session_state.pop("_import_pending")
    for _k, _v in _pending.items():
        st.session_state[_k] = _v
    # Keep the save-name input in sync with the loaded universe name
    if "universe_name" in _pending:
        st.session_state["sb_uni_save_name"] = _pending["universe_name"]

# ── Cookie-backed auth persistence ────────────────────────────────────────────
# st.context.cookies reads the browser's cookies from the HTTP request headers —
# no JS iframe, no URL gymnastics. Works on every page reload automatically.
if "sb_user" not in st.session_state:
    _c_ref = st.context.cookies.get("sb_refresh_token", "")
    if _c_ref:
        try:
            from supabase_client import get_supabase
            _r = get_supabase().auth.refresh_session(_c_ref)
            if _r and _r.session and _r.user:
                st.session_state["sb_access_token"] = _r.session.access_token
                st.session_state["sb_refresh_token"] = _r.session.refresh_token
                st.session_state["sb_user"] = {"id": _r.user.id, "email": _r.user.email}
                st.session_state["_write_cookies"] = True
        except Exception:
            st.session_state["_clear_cookies"] = True

_recovery_token   = st.query_params.get("sb_recovery", "")
_invite_token     = st.query_params.get("sb_invite", "")
_recovery_refresh = st.query_params.get("sb_refresh", "")

st.set_page_config(
    page_title="Burkeanomics Simulator", layout="wide", initial_sidebar_state="collapsed"
)

# One silent rerun for React hydration.
if st.session_state.get("_init_count", 0) < 1:
    st.session_state["_init_count"] = 1
    st.rerun()

# Write or clear browser cookies via inline JS based on auth events.
if st.session_state.pop("_write_cookies", False):
    _exp = (datetime.now() + timedelta(days=30)).strftime("%a, %d %b %Y %H:%M:%S GMT")
    _tok = st.session_state.get("sb_access_token", "")
    _ref = st.session_state.get("sb_refresh_token", "")
    st.html(
        f'<script>'
        f'document.cookie="sb_access_token={_tok};path=/;expires={_exp};SameSite=Strict";'
        f'document.cookie="sb_refresh_token={_ref};path=/;expires={_exp};SameSite=Strict";'
        f'</script>',
        unsafe_allow_javascript=True,
    )
if st.session_state.pop("_clear_cookies", False):
    st.html(
        '<script>'
        'document.cookie="sb_access_token=;path=/;expires=Thu, 01 Jan 1970 00:00:01 GMT;SameSite=Strict";'
        'document.cookie="sb_refresh_token=;path=/;expires=Thu, 01 Jan 1970 00:00:01 GMT;SameSite=Strict";'
        '</script>',
        unsafe_allow_javascript=True,
    )

# Auto-load the global default universe on first meaningful page load.
# Skipped if the user has already triggered an import this session.
if "_global_default_loaded" not in st.session_state:
    st.session_state["_global_default_loaded"] = True
    if "_import_pending" not in st.session_state:
        _def_uni = get_default_universe()
        if _def_uni:
            _def_pending = dict(_def_uni["params"])
            _def_pending["universe_name"] = _def_uni["name"]
            st.session_state["_import_pending"] = _def_pending
            st.rerun()

# Detect screen width via JS; sets ?sw=m (mobile) or ?sw=p (tablet/desktop) on first load.
_sw = st.query_params.get("sw", "p")
_is_mobile = _sw == "m"
st.html(
    """<script>
(function() {
    var url = new URL(window.location.href);

    // Mobile detection: set ?sw= query param and redirect once
    var w = window.innerWidth;
    var target = w < 768 ? 'm' : 'p';
    if (url.searchParams.get('sw') !== target) {
        url.searchParams.set('sw', target);
        window.location.replace(url.toString());
        return;
    }

    // TOC link → open matching expander (with retry for React hydration lag)
    var hashToLabel = {
        '#throttles':   'Electron Throttles',
        '#brainpower':  'BrainPower',
        '#brains':      'Brains',
        '#power':       'Power',
        '#population':  'Populations'
    };
    function findDetails(label) {
        var all = document.querySelectorAll('details');
        for (var i = 0; i < all.length; i++) {
            var s = all[i].querySelector('summary');
            if (s && s.textContent.indexOf(label) >= 0) return all[i];
        }
        return null;
    }
    function scrollToAnchor(id) {
        var el = document.getElementById(id);
        if (el) el.scrollIntoView({behavior: 'smooth'});
    }
    function openExpander(hash, attempt) {
        attempt = attempt || 0;
        var label = hashToLabel[hash];
        if (!label) return;
        var det = findDetails(label);
        if (!det) {
            if (attempt < 8) setTimeout(function() { openExpander(hash, attempt + 1); }, 250);
            return;
        }
        if (!det.open) {
            det.querySelector('summary').click();
            // Verify it actually opened; retry if React swallowed the click
            setTimeout(function() {
                if (!det.open && attempt < 8) {
                    openExpander(hash, attempt + 1);
                } else {
                    scrollToAnchor(hash.slice(1));
                }
            }, 200);
        } else {
            scrollToAnchor(hash.slice(1));
        }
    }
    window.addEventListener('hashchange', function() {
        setTimeout(function() { openExpander(window.location.hash); }, 80);
    });

    // Supabase puts auth tokens in the hash fragment for recovery and invite flows.
    // Convert to query params so Streamlit can read them, then strip the hash.
    (function() {
        var h = window.location.hash;
        if (!h) return;
        var p = new URLSearchParams(h.slice(1));
        var type = p.get('type'), at = p.get('access_token'), rt = p.get('refresh_token') || '';
        if (!at) return;
        var u = new URL(window.location.href);
        u.hash = '';
        u.searchParams.set('sb_refresh', rt);
        if (type === 'recovery') {
            u.searchParams.set('sb_recovery', at);
        } else if (type === 'invite') {
            u.searchParams.set('sb_invite', at);
        }
        window.location.replace(u.toString());
    })();
})();
</script>""",
    unsafe_allow_javascript=True,
)

# ── Invite form (shown when user arrives via Supabase invite email) ────────────
if _invite_token:
    _invite_email = ""
    try:
        from supabase_client import get_supabase
        _sb = get_supabase()
        _sb.auth.set_session(_invite_token, _recovery_refresh)
        _invite_user = _sb.auth.get_user()
        if _invite_user and _invite_user.user:
            _invite_email = _invite_user.user.email
    except Exception:
        pass
    st.title("👋 Welcome to the Burkeanomics Simulator")
    st.markdown("You've been invited!")
    if _invite_email:
        st.markdown(f"**Email:** {_invite_email}")
    st.markdown("Set a password to create your account.")
    _np1 = st.text_input("Password", type="password", key="pw_new1")
    _np2 = st.text_input("Confirm password", type="password", key="pw_new2")
    if st.button("Create account", key="pw_invite_btn"):
        if not _np1:
            st.error("Enter a password.")
        elif _np1 != _np2:
            st.error("Passwords don't match.")
        elif len(_np1) < 6:
            st.error("Password must be at least 6 characters.")
        else:
            try:
                update_password(_invite_token, _recovery_refresh, _np1)
                try:
                    sign_in(_invite_email, _np1)
                    st.session_state["_write_cookies"] = True
                    st.query_params.clear()
                    st.rerun()
                except Exception:
                    st.query_params.clear()
                    st.success("✅ Success! Your password is now set. Click the **›** arrow at the top-left to open the sidebar, then sign in under **Account**.")
            except Exception as _e:
                st.error(f"Setup failed: {_e}")
    st.stop()

# ── Password recovery form (shown when user arrives via reset-email link) ──────
if _recovery_token:
    st.title("🔐 Set New Password")
    _np1 = st.text_input("New password", type="password", key="pw_new1")
    _np2 = st.text_input("Confirm new password", type="password", key="pw_new2")
    if st.button("Update password", key="pw_update_btn"):
        if not _np1:
            st.error("Enter a new password.")
        elif _np1 != _np2:
            st.error("Passwords don't match.")
        elif len(_np1) < 6:
            st.error("Password must be at least 6 characters.")
        else:
            try:
                update_password(_recovery_token, _recovery_refresh, _np1)
                st.query_params.clear()
                st.success("Password updated! You can now sign in.")
            except Exception as _e:
                st.error(f"Update failed: {_e}")
    st.stop()

st.title("🧠 Burkeanomics Simulator")
# layout: version | generate | download | references
_ver_col, _gen_col, _dl_col, _ref_col = st.columns([2, 1, 1, 3])
with _ver_col:
    st.markdown(
        "<p style='font-size:14px; font-weight:600; color:#555; margin-top:8px;'>Burkeanomics Simulator d2.85</p>",
        unsafe_allow_html=True,
    )
with _gen_col:
    if st.button(
        "PDF TBD",
        key="generate_pdf_btn_top",
        disabled=st.session_state.get("_generate_pdf_pending", False),
    ):
        st.session_state["_generate_pdf_pending"] = True
with _dl_col:
    if st.session_state.get("_pdf_ready", False) and st.session_state.get("_pdf_bytes") is not None:
        _dl_mime = st.session_state.get("_pdf_mime", "application/pdf")
        _dl_label = "Download PDF" if _dl_mime == "application/pdf" else "Download Report (HTML)"
        st.download_button(
            _dl_label,
            data=st.session_state["_pdf_bytes"],
            file_name=st.session_state.get("_pdf_filename", "universe.pdf"),
            mime=_dl_mime,
            key="download_pdf_top",
            on_click=lambda: st.session_state.update({
                "_pdf_ready": False,
                "_pdf_bytes": None,
                "_pdf_filename": None,
                "_pdf_mime": None,
            }),
        )
with _ref_col:
    with st.expander("References"):
        st.markdown(
            "• [Bcon 300 — Burkean Economics](https://www.bnation.us/econ-300-burkean-economics)  \n"
            "• [Bcon 301 — Particle Physics Model of Socionomic Systems](https://www.bnation.us/econ-301)  \n"
            "• [Bcon 302 — BrainPower Charts](https://www.bnation.us/302-bp-charts)  \n"
            "• [Bcon 304 — Human Dualities](https://www.bnation.us/304-human-dualities)"
        )

# ====================== DEFAULTS ======================
if "universe_name" not in st.session_state:
    st.session_state["universe_name"] = "Cal Energy Economy"

_EXPORT_PREFIXES = (
    "th_", "iq_", "b_", "p_", "pop_", "adults_",
    "households", "energy", "base_iq", "top_execs_", "ai_iq_",
    "rpf_", "te_factor_", "ai_factor_", "universe_name", "universe_desc",
    "note_", "url_", "dark_mode",
)

# ====================== WELCOME SIDEBAR ======================
with st.sidebar.expander("👋 Welcome to Burkeanomics", expanded=False):
    st.markdown("""
Burkean Economics is a novel form of behavioral economics that models our very human world as a collection of particles.

There are four classes of Burkean particles: **Electrons** and three kinds of **Nucleons**. Like particle physics, they interact with each other in understandable ways — both within their class and across classes.

Burkeanomics models the economic world around you, with **you at the center**:

- **Electrons** — families and singles like you
- **GovNukes** — governmental agencies
- **Providers** — schools, hospitals, businesses
- **SinSayers** — religions, movements, and moral arbiters

Use the parameters lower in this sidebar and the Electron Throttles in the dashboard to tune the three control cases — **cCon Left**, **Center**, and **dCon Right** — and see how each case plays out.
                
You are well advised to familize yourself with the pages under the References panel atop the dashboard. Those will familiarize you with the Burkean ontology, terminology and theory.
""")
    st.markdown("**Questions or feedback?** [Let us know →](https://tally.so/r/aQaAz2)", unsafe_allow_html=False)

# ====================== ACCOUNT SIDEBAR ======================
with st.sidebar.expander("🔐 Account", expanded=not is_logged_in()):
    if is_logged_in():
        st.caption(f"Signed in as **{current_user()['email']}**")
        if st.button("Sign Out", key="sb_signout"):
            sign_out()
            st.session_state["_clear_cookies"] = True
            st.rerun()
    else:
        _sb_email = st.text_input("Email", key="sb_email")
        _sb_pw = st.text_input("Password", type="password", key="sb_pw")
        if st.button("Sign In", key="sb_signin_btn"):
            try:
                sign_in(_sb_email, _sb_pw)
                st.session_state["_write_cookies"] = True
                st.rerun()
            except Exception as _e:
                st.error(f"Sign in failed: {_e}")
        with st.expander("Forgot password?"):
            _reset_email = st.text_input("Email", key="sb_reset_email")
            if st.button("Send reset email", key="sb_reset_btn"):
                if _reset_email:
                    try:
                        send_password_reset(_reset_email)
                        st.success("Check your email for a reset link.")
                    except Exception as _e:
                        st.error(f"Failed: {_e}")
                else:
                    st.error("Enter your email.")
        st.caption("Alpha access is by invitation. [Request access →](mailto:david@bnation.us?subject=Burkeanomics%20Sim%20Alpha%20Access%20Request)")

# ====================== MY UNIVERSES SIDEBAR ======================
if is_logged_in():
    with st.sidebar.expander("💾 My Universes", expanded=False):
        _universes = list_universes()
        if _universes:
            _uni_labels = [("✓ " if u.get("is_default") else "") + u["name"] for u in _universes]
            _label_to_uni = dict(zip(_uni_labels, _universes))
            _sel_label = st.selectbox("Saved universes", _uni_labels, key="sb_uni_select")
            _sel_uni_data = _label_to_uni[_sel_label]
            _sel_uni_id = _sel_uni_data["id"]
            _sel_uni_name = _sel_uni_data["name"]
            _lc, _dc = st.columns(2)
            with _lc:
                if st.button("Load", key="sb_uni_load", use_container_width=True):
                    _loaded = load_universe(_sel_uni_id)
                    if _loaded:
                        _pending = dict(_loaded["params"])
                        _pending["universe_name"] = _loaded["name"]
                        st.session_state["_import_pending"] = _pending
                        st.session_state["sb_uni_save_name"] = _sel_uni_name
                        st.rerun()
            with _dc:
                if st.button("Delete", key="sb_uni_delete", use_container_width=True):
                    delete_universe(_sel_uni_id)
                    st.rerun()
            if is_admin():
                if _sel_uni_data.get("is_default"):
                    st.caption("✓ Global default")
                else:
                    if st.button("⭐ Set as Default", key="sb_set_default", use_container_width=True):
                        set_default_universe(_sel_uni_id)
                        st.rerun()
            st.markdown("---")
        # Reset save field whenever the loaded universe changes
        _cur_uni_name = st.session_state.get("universe_name", "")
        if st.session_state.get("_last_uni_name") != _cur_uni_name:
            st.session_state["_last_uni_name"] = _cur_uni_name
            st.session_state["sb_uni_save_name"] = _cur_uni_name
        _save_name = st.text_input(
            "Save current universe as",
            key="sb_uni_save_name",
        )
        if st.button("💾 Save", key="sb_uni_save", use_container_width=True):
            if _save_name.strip():
                _params = {k: v for k, v in st.session_state.items()
                           if k.startswith(_EXPORT_PREFIXES)}
                _params["universe_name"] = _save_name.strip()
                _old_name = st.session_state.get("universe_name", "")
                save_universe(_save_name.strip(), _params, old_name=_old_name)
                st.session_state["universe_name"] = _save_name.strip()
                st.session_state["_last_uni_name"] = _save_name.strip()
                st.success(f"Saved '{_save_name.strip()}'")
            else:
                st.error("Enter a name first.")

# ====================== RESET ======================
st.sidebar.header("⚙️ Parameters")
st.sidebar.checkbox("🌙 Dark Mode", key="dark_mode", value=False)
if st.sidebar.button("🔄 Reset"):
    _reset_prefixes = (
        "th_",
        "iq_",
        "b_",
        "p_",
        "pop_",
        "adults_",
        "households",
        "energy",
        "base_iq",
        "top_execs",
        "ai_iq",
        "rpf_",
        "te_factor_",
        "ai_factor_",
        "universe_name",
        "universe_desc",
        "note_",
        "url_",
        "dark_mode",
        "_uploader_key",
    )
    for key in list(st.session_state.keys()):
        if key.startswith(_reset_prefixes):
            del st.session_state[key]
    st.rerun()

# ====================== SIDEBAR ======================

def _ch(t):
    return st.markdown(
        f"<p style='text-align:center;font-size:0.8rem;font-weight:600;color:#888;margin:0 0 4px 0'>{t}</p>",
        unsafe_allow_html=True,
    )

with st.sidebar.expander("**🌐 Constants**", expanded=False):
    st.caption("Anchors Everything")
    households = st.number_input(
        "Electrons", value=13970000, step=10000, key="households"
    )
    st.text_input("↳ Note", placeholder="e.g. CA households, c2025", key="note_households", label_visibility="collapsed")
    st.text_input("↳ Source URL", placeholder="https://...", key="url_households", label_visibility="collapsed")
    _u = st.session_state.get("url_households", "")
    if _u.startswith(("http://", "https://")):
        st.markdown(f"[↗ open source]({_u})")
    energy = st.number_input(
        "Electron Power per Capita", value=6378, step=10, key="energy"
    )
    st.markdown(
        f"<p style='text-align:center;font-size:0.85em;color:#888;margin-top:-8px'>${energy:,.0f}</p>",
        unsafe_allow_html=True,
    )
    st.text_input("↳ Note", placeholder="e.g. Median CA household energy spend", key="note_energy", label_visibility="collapsed")
    st.text_input("↳ Source URL", placeholder="https://...", key="url_energy", label_visibility="collapsed")
    _u = st.session_state.get("url_energy", "")
    if _u.startswith(("http://", "https://")):
        st.markdown(f"[↗ open source]({_u})")
    base_iq = st.number_input("Base IQ", value=100, step=1, key="base_iq")
    st.text_input("↳ Note", placeholder="e.g. Population mean IQ", key="note_base_iq", label_visibility="collapsed")
    st.text_input("↳ Source URL", placeholder="https://...", key="url_base_iq", label_visibility="collapsed")
    _u = st.session_state.get("url_base_iq", "")
    if _u.startswith(("http://", "https://")):
        st.markdown(f"[↗ open source]({_u})")

with st.sidebar.expander("**🧬 Per Capita Attributes**", expanded=False):
    # ── Brains per Class ──────────────────────────────────────────────────────
    st.markdown(
        "<p style='text-align:center;font-weight:600;margin:4px 0'>Brains per Class</p>",
        unsafe_allow_html=True,
    )
    st.caption("L & R: factors × Center values")
    _bh1, _bh2, _bh3 = st.columns(3)
    with _bh1:
        _ch("cCon Left")
    with _bh2:
        _ch("Center")
    with _bh3:
        _ch("dCon Right")

    st.markdown("**Electrons**")
    _base_iq0 = st.session_state.get("base_iq", 100)
    _ecols = st.columns(3)
    with _ecols[0]:
        _adults_c = st.number_input(
            "Adults/Electron", min_value=1.0, max_value=2.0, value=1.3, step=0.1,
            format="%.1f", key="adults_e_c"
        )
        st.caption(f"PC IQ: {round(_adults_c * _base_iq0):,}")
    with _ecols[1]:
        _adults_center = st.number_input(
            "Adults/Electron", min_value=1.0, max_value=2.0, value=1.5, step=0.1,
            format="%.1f", key="adults_e_center"
        )
        st.caption(f"PC IQ: {round(_adults_center * _base_iq0):,}")
    with _ecols[2]:
        _adults_d = st.number_input(
            "Adults/Electron", min_value=1.0, max_value=2.0, value=1.8, step=0.1,
            format="%.1f", key="adults_e_d"
        )
        st.caption(f"PC IQ: {round(_adults_d * _base_iq0):,}")

    st.markdown("**GovNukes**")
    _te_g0 = st.session_state.get("top_execs_g_center", 10)
    _ai_g0 = st.session_state.get("ai_iq_g_center", 150)
    gcols = st.columns(3)
    with gcols[0]:
        _te_f_gc = st.number_input(
            "Top Execs ×", value=1.0, step=0.05, format="%.2f", key="te_factor_g_c"
        )
        st.caption(f"= {round(_te_g0 * _te_f_gc):,}")
        _ai_f_gc = st.number_input(
            "AI IQ ×", value=1.0, step=0.05, format="%.2f", key="ai_factor_g_c"
        )
        st.caption(f"= {round(_ai_g0 * _ai_f_gc):,}")
        st.caption(f"**PC IQ: {round(_te_g0 * _te_f_gc * _ai_g0 * _ai_f_gc):,}**")
    with gcols[1]:
        _te_gc = st.number_input(
            "Top Execs", value=10, step=1, key="top_execs_g_center"
        )
        st.caption(f"= {_te_gc:,}")
        _ai_gc = st.number_input(
            "AI Enhanced IQ", value=150, step=5, key="ai_iq_g_center"
        )
        st.caption(f"= {_ai_gc:,}")
        st.caption(f"**PC IQ: {round(_te_gc * _ai_gc):,}**")
    with gcols[2]:
        _te_f_gd = st.number_input(
            "Top Execs ×", value=1.0, step=0.05, format="%.2f", key="te_factor_g_d"
        )
        st.caption(f"= {round(_te_g0 * _te_f_gd):,}")
        _ai_f_gd = st.number_input(
            "AI IQ ×", value=1.17, step=0.05, format="%.2f", key="ai_factor_g_d"
        )
        st.caption(f"= {round(_ai_g0 * _ai_f_gd):,}")
        st.caption(f"**PC IQ: {round(_te_g0 * _te_f_gd * _ai_g0 * _ai_f_gd):,}**")

    st.markdown("**Providers**")
    _te_p0 = st.session_state.get("top_execs_p_center", 10)
    _ai_p0 = st.session_state.get("ai_iq_p_center", 225)
    pcols = st.columns(3)
    with pcols[0]:
        _te_f_pc = st.number_input(
            "Top Execs ×", value=1.0, step=0.05, format="%.2f", key="te_factor_p_c"
        )
        st.caption(f"= {round(_te_p0 * _te_f_pc):,}")
        _ai_f_pc = st.number_input(
            "AI IQ ×", value=0.8, step=0.05, format="%.2f", key="ai_factor_p_c"
        )
        st.caption(f"= {round(_ai_p0 * _ai_f_pc):,}")
        st.caption(f"**PC IQ: {round(_te_p0 * _te_f_pc * _ai_p0 * _ai_f_pc):,}**")
    with pcols[1]:
        _te_pc = st.number_input(
            "Top Execs", value=15, step=1, key="top_execs_p_center"
        )
        st.caption(f"= {_te_pc:,}")
        _ai_pc = st.number_input(
            "AI Enhanced IQ", value=150, step=5, key="ai_iq_p_center"
        )
        st.caption(f"= {_ai_pc:,}")
        st.caption(f"**PC IQ: {round(_te_pc * _ai_pc):,}**")
    with pcols[2]:
        _te_f_pd = st.number_input(
            "Top Execs ×", value=1.0, step=0.05, format="%.2f", key="te_factor_p_d"
        )
        st.caption(f"= {round(_te_p0 * _te_f_pd):,}")
        _ai_f_pd = st.number_input(
            "AI IQ ×", value=1.7, step=0.05, format="%.2f", key="ai_factor_p_d"
        )
        st.caption(f"= {round(_ai_p0 * _ai_f_pd):,}")
        st.caption(f"**PC IQ: {round(_te_p0 * _te_f_pd * _ai_p0 * _ai_f_pd):,}**")

    st.markdown("**SinSayers**")
    _te_s0 = st.session_state.get("top_execs_s_center", 10)
    _ai_s0 = st.session_state.get("ai_iq_s_center", 150)
    scols = st.columns(3)
    with scols[0]:
        _te_f_sc = st.number_input(
            "Top Execs ×", value=1.0, step=0.05, format="%.2f", key="te_factor_s_c"
        )
        st.caption(f"= {round(_te_s0 * _te_f_sc):,}")
        _ai_f_sc = st.number_input(
            "AI IQ ×", value=1.0, step=0.05, format="%.2f", key="ai_factor_s_c"
        )
        st.caption(f"= {round(_ai_s0 * _ai_f_sc):,}")
        st.caption(f"**PC IQ: {round(_te_s0 * _te_f_sc * _ai_s0 * _ai_f_sc):,}**")
    with scols[1]:
        _te_sc = st.number_input(
            "Top Execs", value=10, step=1, key="top_execs_s_center"
        )
        st.caption(f"= {_te_sc:,}")
        _ai_sc = st.number_input(
            "AI Enhanced IQ", value=150, step=5, key="ai_iq_s_center"
        )
        st.caption(f"= {_ai_sc:,}")
        st.caption(f"**PC IQ: {round(_te_sc * _ai_sc):,}**")
    with scols[2]:
        _te_f_sd = st.number_input(
            "Top Execs ×", value=1.0, step=0.05, format="%.2f", key="te_factor_s_d"
        )
        st.caption(f"= {round(_te_s0 * _te_f_sd):,}")
        _ai_f_sd = st.number_input(
            "AI IQ ×", value=1.17, step=0.05, format="%.2f", key="ai_factor_s_d"
        )
        st.caption(f"= {round(_ai_s0 * _ai_f_sd):,}")
        st.caption(f"**PC IQ: {round(_te_s0 * _te_f_sd * _ai_s0 * _ai_f_sd):,}**")

    # ── Power per Class ───────────────────────────────────────────────────────
    st.markdown(
        "<hr style='margin:12px 0 6px 0;border:none;border-top:1px solid #ddd;'><p style='text-align:center;font-weight:600;margin:0 0 4px 0'>Power per Class</p>",
        unsafe_allow_html=True,
    )
    _epwr = st.session_state.get("energy", 6378)
    _ph1, _ph2, _ph3 = st.columns(3)
    with _ph1:
        _ch("cCon Left")
    with _ph2:
        _ch("Center")
    with _ph3:
        _ch("dCon Right")

    st.markdown("**GovNukes**")
    _cg = _epwr * st.session_state.get("rpf_g", 36667)
    gpow = st.columns(3)
    with gpow[0]:
        st.caption(f"Center: ${_cg:,.0f}")
        _lgf = st.number_input("Factor", value=1.3, step=0.05, key="p_g_c")
        st.caption(f"= ${_cg * _lgf:,.0f}")
    with gpow[1]:
        st.caption(f"PC Electron: ${_epwr:,.0f}")
        _cgf = st.number_input(
            "Power Factor", value=36667, step=100, format="%d", key="rpf_g"
        )
        st.caption(f"= ${_epwr * _cgf:,.0f}")
    with gpow[2]:
        st.caption(f"Center: ${_cg:,.0f}")
        _rgf = st.number_input("Factor", value=0.54, step=0.05, key="p_g_d")
        st.caption(f"= ${_cg * _rgf:,.0f}")

    st.markdown("**Providers**")
    _cp = _epwr * st.session_state.get("rpf_p", 10000)
    ppow = st.columns(3)
    with ppow[0]:
        st.caption(f"Center: ${_cp:,.0f}")
        _lpf = st.number_input("Factor", value=0.5, step=0.05, key="p_p_c")
        st.caption(f"= ${_cp * _lpf:,.0f}")
    with ppow[1]:
        st.caption(f"PC Electron: ${_epwr:,.0f}")
        _cpf = st.number_input(
            "Power Factor", value=10000, step=100, format="%d", key="rpf_p"
        )
        st.caption(f"= ${_epwr * _cpf:,.0f}")
    with ppow[2]:
        st.caption(f"Center: ${_cp:,.0f}")
        _rpf2 = st.number_input("Factor", value=0.8, step=0.05, key="p_p_d")
        st.caption(f"= ${_cp * _rpf2:,.0f}")

    st.markdown("**SinSayers**")
    _cs = _epwr * st.session_state.get("rpf_s", 5000)
    spow = st.columns(3)
    with spow[0]:
        st.caption(f"Center: ${_cs:,.0f}")
        _lsf = st.number_input("Factor", value=1.5, step=0.05, key="p_s_c")
        st.caption(f"= ${_cs * _lsf:,.0f}")
    with spow[1]:
        st.caption(f"PC Electron: ${_epwr:,.0f}")
        _csf = st.number_input(
            "Power Factor", value=5000, step=100, format="%d", key="rpf_s"
        )
        st.caption(f"= ${_epwr * _csf:,.0f}")
    with spow[2]:
        st.caption(f"Center: ${_cs:,.0f}")
        _rsf = st.number_input("Factor", value=0.9, step=0.05, key="p_s_d")
        st.caption(f"= ${_cs * _rsf:,.0f}")

with st.sidebar.expander("**👥 Nucleons per Electron**", expanded=False):
    st.caption("Population structure per scenario")
    col_e = st.columns(3)
    with col_e[0]:
        _ch("cCon Left")
        st.number_input("GovNukes", value=14, step=1, key="pop_g_c")
        st.number_input("Providers", value=35, step=1, key="pop_p_c")
        st.number_input("SinSayers", value=60, step=1, key="pop_s_c")
    with col_e[1]:
        _ch("Center")
        st.number_input("GovNukes", value=13, step=1, key="pop_g_center")
        st.number_input("Providers", value=40, step=1, key="pop_p_center")
        st.number_input("SinSayers", value=50, step=1, key="pop_s_center")
    with col_e[2]:
        _ch("dCon Right")
        st.number_input("GovNukes", value=8, step=1, key="pop_g_d")
        st.number_input("Providers", value=55, step=1, key="pop_p_d")
        st.number_input("SinSayers", value=15, step=1, key="pop_s_d")

with st.sidebar.expander("**🏷️ Metadata**", expanded=False):
    st.text_input(
        "Universe Name", placeholder="e.g. Cal Energy Economy", key="universe_name"
    )

    st.markdown("---")
    # Export
    _export_data = {
        k: v for k, v in st.session_state.items() if k.startswith(_EXPORT_PREFIXES)
    }
    _fname = (st.session_state.get("universe_name", "universe") or "universe").replace(
        " ", "_"
    ) + ".json"
    st.download_button(
        "⬇ Export Universe JSON",
        data=json.dumps(_export_data, indent=2),
        file_name=_fname,
        mime="application/json",
    )

    # Import — two-run pattern: store pending, rerun, apply at top before widgets render
    _uploader_key = st.session_state.get("_uploader_key", "uploader_0")
    _uploaded = st.file_uploader(
        "⬆ Import Universe JSON",
        type="json",
        key=_uploader_key,
        label_visibility="collapsed",
    )
    if _uploaded is not None:
        try:
            _loaded = json.load(_uploaded)
            st.session_state["_import_pending"] = _loaded
            # Rotate the uploader key so it resets after import (prevents re-import loop)
            st.session_state["_uploader_key"] = f"uploader_{abs(hash(_uploaded.name))}"
            st.rerun()
        except Exception as e:
            st.error(f"Import failed: {e}")

st.sidebar.caption("d2.85")

# ====================== CALCULATIONS ======================

# ====================== DASH ======================
# ====================== MECHANISMS ======================
_MECHS = ["taxes", "suppliers", "gateways", "regulations", "monetary"]
_MECH_LBL = {
    "taxes": "Tax Rates",
    "suppliers": "Suppliers",
    "gateways": "Gateways",
    "regulations": "Regulations",
    "monetary": "Monetary Policy",
}
# (min label, max label) — shown as slider direction
_MECH_DIR = {
    "taxes": ("Lower", "Higher"),
    "suppliers": ("Competition", "Monopoly"),
    "gateways": ("Choice", "Bureaucrats"),
    "regulations": ("Benign Neglect", "Mandates"),
    "monetary": ("Firm", "Loose"),
}
# (val_c, val_center, val_d, weight)
_MECH_DEF = {
    "taxes": (65, 55, 20, 3),
    "suppliers": (85, 45, 30, 1),
    "gateways": (80, 45, 30, 1),
    "regulations": (90, 45, 30, 1),
    "monetary": (0, 0, 0, 0),
}
_MSFX = {"c": 0, "center": 1, "d": 2}
_MTH = {"c": "th_ccon", "center": "th_center", "d": "th_dcon"}


def _th_from_mechs(sfx):
    tw = ws = 0
    for m in _MECHS:
        w = st.session_state.get(f"mech_weight_{m}", _MECH_DEF[m][3])
        v = st.session_state.get(f"mech_{m}_{sfx}", _MECH_DEF[m][_MSFX[sfx]])
        tw += w
        ws += w * v
    return min(99, max(0, round(ws / tw))) if tw else 50


def _sync_th(sfx):
    st.session_state[_MTH[sfx]] = _th_from_mechs(sfx)


def _sync_all_th():
    for sfx in ("c", "center", "d"):
        st.session_state[_MTH[sfx]] = _th_from_mechs(sfx)


def _scale_mechs(sfx):
    new_th = st.session_state.get(_MTH[sfx], 50)
    old_th = _th_from_mechs(sfx)
    for m in _MECHS:
        old_v = st.session_state.get(f"mech_{m}_{sfx}", _MECH_DEF[m][_MSFX[sfx]])
        if old_th == 0:
            w = st.session_state.get(f"mech_weight_{m}", _MECH_DEF[m][3])
            st.session_state[f"mech_{m}_{sfx}"] = new_th if w > 0 else 0
        else:
            st.session_state[f"mech_{m}_{sfx}"] = min(
                99, max(0, round(old_v * new_th / old_th))
            )


SCENARIOS = [("cCon (Left)", "Left"), ("Center", "Center"), ("dCon (Right)", "Right")]

# ====================== CHARTS ======================
_FOOTER = "© 2026 David Burkean • Sharing is caring • Commercial use by permission • All Rights Reserved"
_FOOTER_ANNOTATION = dict(
    text=_FOOTER,
    xref="paper",
    yref="paper",
    x=0.5,
    y=-0.28,
    showarrow=False,
    font=dict(size=10, color="#666"),
    align="center",
)

_universe = st.session_state.get("universe_name", "").strip()
st.header(
    f"Health & Wealth of the {_universe}"
    if _universe
    else "Health & Wealth of the [Universe]"
)
st.markdown(
    "<style>section[data-testid='stMain'] details summary p { font-weight:600; font-size:0.95rem; } section[data-testid='stSidebar'] div[data-testid='stNumberInput'] label { text-align:center; display:block; width:100%; }</style>",
    unsafe_allow_html=True,
)
with st.expander("📋 Overview of this Target Universe", expanded=False):
    _desc_val = st.session_state.get("universe_desc", "")
    if is_logged_in():
        st.text_area(
            "",
            placeholder="Describe this universe's scenario, assumptions, and goals…",
            key="universe_desc",
            height=160,
            label_visibility="collapsed",
        )
        if st.button("💾 Save Universe", key="overview_save_btn"):
            _ov_name = st.session_state.get("universe_name", "").strip()
            if _ov_name:
                _ov_params = {k: v for k, v in st.session_state.items()
                              if k.startswith(_EXPORT_PREFIXES)}
                _ov_params["universe_name"] = _ov_name
                save_universe(_ov_name, _ov_params, old_name=_ov_name)
                st.success(f"Saved '{_ov_name}'")
            else:
                st.error("No universe name set — save from the sidebar first.")
    else:
        if _desc_val:
            st.markdown(_desc_val)
        else:
            st.caption("No overview provided for this universe.")
st.markdown(
    "<div style='display:flex;flex-wrap:wrap;gap:6px;padding:2px 0 14px 0;font-size:14px;font-weight:600;justify-content:center;'>"
    "<a href='#throttles' style='color:#1155cc;text-decoration:none;'>Throttles</a>"
    "<span style='color:#bbb'>&nbsp;•&nbsp;</span>"
    "<a href='#brainpower' style='color:#1155cc;text-decoration:none;'>BrainPower</a>"
    "<span style='color:#bbb'>&nbsp;•&nbsp;</span>"
    "<a href='#brains' style='color:#1155cc;text-decoration:none;'>Brains</a>"
    "<span style='color:#bbb'>&nbsp;•&nbsp;</span>"
    "<a href='#power' style='color:#1155cc;text-decoration:none;'>Power</a>"
    "<span style='color:#bbb'>&nbsp;•&nbsp;</span>"
    "<a href='#population' style='color:#1155cc;text-decoration:none;'>Populations</a>"
    "<span style='color:#bbb'>&nbsp;•&nbsp;</span>"
    "<a href='#tables' style='color:#1155cc;text-decoration:none;'>Tables</a>"
    "</div>",
    unsafe_allow_html=True,
)

def _build_universe_3d(show_arrows=False, show_mono=False, height=540):
    sfx_map = {"cCon (Left)": "c", "Center": "center", "dCon (Right)": "d"}
    scen_labels = [("Left", "cCon (Left)"), ("Center", "Center"), ("Right", "dCon (Right)")]

    scens = {}
    for lbl, scen_key in scen_labels:
        sfx = sfx_map[scen_key]
        _dfpc = calculate_per_capita(scen_key).set_index("Class")
        _pw_e = float(_dfpc.loc["Electrons (throttled)", "Power ($)"])
        _pw_g = float(_dfpc.loc["GovNukes", "Power ($)"])
        _pw_p = float(_dfpc.loc["Providers", "Power ($)"])
        _pw_s = float(_dfpc.loc["SinSayers", "Power ($)"])
        _nlo = min(_pw_g, _pw_p, _pw_s)
        _nhi = max(_pw_g, _pw_p, _pw_s)
        def _sz_nuke(v, lo=_nlo, hi=_nhi):
            t = max(0.0, (v - lo) / max(hi - lo, 1e-9))
            return round(0.10 + t * 0.45, 4)
        _pe = max(_pw_e, 1)
        scens[lbl] = {
            "r_e": 0.06, "r_g": _sz_nuke(_pw_g), "r_p": _sz_nuke(_pw_p), "r_s": _sz_nuke(_pw_s),
            "n_g": st.session_state.get(f"pop_g_{sfx}", 13),
            "n_p": st.session_state.get(f"pop_p_{sfx}", 40),
            "n_s": st.session_state.get(f"pop_s_{sfx}", 50),
            "mult_g": round(_pw_g / _pe),
            "mult_p": round(_pw_p / _pe),
            "mult_s": round(_pw_s / _pe),
            "disp_g": round(_sz_nuke(_pw_g) / 0.06),
            "disp_p": round(_sz_nuke(_pw_p) / 0.06),
            "disp_s": round(_sz_nuke(_pw_s) / 0.06),
            "pe": round(_pe),
        }

    max_n_g = max(v["n_g"] for v in scens.values())
    max_n_p = max(v["n_p"] for v in scens.values())
    max_n_s = max(v["n_s"] for v in scens.values())

    d = json.dumps({
        "scens": scens,
        "maxNG": max_n_g, "maxNP": max_n_p, "maxNS": max_n_s,
        "arrows": show_arrows, "mono": show_mono,
    })
    H = height - 8

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#0d1b2a;overflow:hidden;font-family:sans-serif}}
canvas{{display:block}}
#lg{{position:absolute;bottom:8px;left:10px;color:#dde;font-size:16px;line-height:1.9;pointer-events:none;
     background:rgba(0,8,20,0.60);border-radius:8px;padding:10px 18px}}
#lg table{{border-collapse:collapse;width:100%}}
#lg td.nm{{text-align:left;padding-right:14px}}
#lg td.hd{{text-align:right;padding-left:14px;color:#6688aa;font-size:13px;line-height:1.4;vertical-align:bottom}}
#lg td.xv{{text-align:right;padding-left:14px;color:#ffffff}}
#lg td.qt{{text-align:right;padding-left:14px;color:#ffffff}}
#lg td.rb{{border-right:1px solid #334455;padding-right:10px}}
#lg-scale{{margin-top:4px;font-size:13px;color:#556677;text-align:center}}
#footer{{position:absolute;bottom:8px;right:12px;color:#8899aa;font-size:16px;pointer-events:none;text-align:right;line-height:1.6}}
#wintitle{{position:absolute;top:6px;left:0;width:100%;text-align:center;color:#aaccee;font-size:18px;font-weight:600;pointer-events:none;z-index:8}}
#btns{{position:absolute;top:32px;left:50%;transform:translateX(-50%);display:flex;gap:6px;pointer-events:auto;z-index:10}}
#sb{{position:absolute;top:62px;left:0;width:100%;text-align:center;color:#99aabb;font-size:18px;pointer-events:none;z-index:9}}
#fsbtn{{position:absolute;top:6px;right:8px;background:#1e3a5f;color:#aaccee;border:1px solid #335577;
        border-radius:4px;padding:3px 8px;font-size:15px;cursor:pointer;pointer-events:auto;z-index:10;line-height:1}}
.sbtn{{background:#1e3a5f;color:#aaccee;border:1px solid #335577;border-radius:4px;
       padding:3px 12px;font-size:12px;cursor:pointer;font-weight:600}}
.sbtn.active{{background:#2255aa;color:#ffffff;border-color:#4477cc}}
</style>
</head><body>
<div id="wintitle">Power per Capita</div>
<div id="btns">
  <button class="sbtn active" id="btn-Left" onclick="switchScen('Left')">Left</button>
  <button class="sbtn" id="btn-Center" onclick="switchScen('Center')">Center</button>
  <button class="sbtn" id="btn-Right" onclick="switchScen('Right')">Right</button>
</div>
<div id="sb">Bubble Size = $$$ Power &nbsp;|&nbsp; &#9888; Nucleons Thousands &times; Larger IRL</div>
<button id="fsbtn" onclick="toggleFS()" title="Fullscreen">&#x26F6;</button>
<div id="lg"><table>
  <tr><td class="nm"></td><td class="hd rb" colspan="2">Size</td><td class="hd">Qty</td><td class="hd">Total</td></tr>
  <tr><td class="nm"></td><td class="hd rb" style="font-size:11px">Shown</td><td class="hd" style="font-size:11px">Actual</td><td class="hd"></td><td class="hd"></td></tr>
  <tr><td class="nm" style="color:#aaccee">Electrons</td><td class="xv rb">1&times;</td><td class="xv">1&times;</td><td class="qt">1</td><td class="xv">1&times;</td></tr>
  <tr><td class="nm" style="color:#FFD700">GovNukes</td><td class="xv rb" id="lg-g-sz-disp"></td><td class="xv" id="lg-g-sz"></td><td class="qt" id="lg-g-qt"></td><td class="xv" id="lg-g-tt"></td></tr>
  <tr><td class="nm" style="color:#66cc66">Providers</td><td class="xv rb" id="lg-p-sz-disp"></td><td class="xv" id="lg-p-sz"></td><td class="qt" id="lg-p-qt"></td><td class="xv" id="lg-p-tt"></td></tr>
  <tr><td class="nm" style="color:#cc4444">SinSayers</td><td class="xv rb" id="lg-s-sz-disp"></td><td class="xv" id="lg-s-sz"></td><td class="qt" id="lg-s-qt"></td><td class="xv" id="lg-s-tt"></td></tr>
</table>
<div id="lg-scale"></div>
</div>
<div id="footer">&copy; 2026 David Burkean &bull; Sharing is caring &bull; Commercial use by permission &bull; All Rights Reserved</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script>
const D={d};
const W=window.innerWidth,H={H};
let curScen='Left';
const LERP=0.042;

const renderer=new THREE.WebGLRenderer({{antialias:true}});
renderer.setSize(W,H);renderer.setPixelRatio(window.devicePixelRatio||1);
document.body.appendChild(renderer.domElement);
const scene=new THREE.Scene();
scene.background=new THREE.Color(0x0d1b2a);
scene.fog=new THREE.FogExp2(0x0d1b2a,0.040);
const camera=new THREE.PerspectiveCamera(55,W/H,0.01,100);
camera.position.set(0,1.5,8);
scene.add(new THREE.AmbientLight(0x334466,2.5));
const ptLight=new THREE.PointLight(0x88aaff,3,10);scene.add(ptLight);
const dirLight=new THREE.DirectionalLight(0xffffff,0.4);dirLight.position.set(4,6,4);scene.add(dirLight);

function gauss(){{
  let u=0,v=0;while(!u)u=Math.random();while(!v)v=Math.random();
  return Math.sqrt(-2*Math.log(u))*Math.cos(2*Math.PI*v);
}}
function loosePt(r0,sig){{
  const th=2*Math.PI*Math.random(),ph=Math.acos(2*Math.random()-1);
  const r=Math.max(0.3,r0+gauss()*sig);
  return[r*Math.sin(ph)*Math.cos(th),r*Math.sin(ph)*Math.sin(th),r*Math.cos(ph)];
}}
// Unit-sphere + scale so we can tween size
function mkSphere(initR,color,x,y,z,opacity,emInt){{
  const m=new THREE.Mesh(
    new THREE.SphereGeometry(1,10,8),
    new THREE.MeshPhongMaterial({{color,emissive:color,emissiveIntensity:emInt||0.25,
      transparent:true,opacity,shininess:55}})
  );
  m.scale.setScalar(initR);m.position.set(x,y,z);scene.add(m);return m;
}}
function mkLabel(letter,col){{
  const cv=document.createElement('canvas');cv.width=cv.height=64;
  const cx=cv.getContext('2d');
  cx.fillStyle=col;cx.font='500 24px Georgia, serif';
  cx.textAlign='center';cx.textBaseline='middle';cx.fillText(letter,32,32);
  const sp=new THREE.Sprite(new THREE.SpriteMaterial({{map:new THREE.CanvasTexture(cv),transparent:true,depthTest:false}}));
  return sp;
}}
function updateArrow(arr,from,to){{
  const dir=new THREE.Vector3().subVectors(to,from);
  const len=dir.length();if(len<0.15)return;
  arr.position.copy(from);arr.setDirection(dir.normalize());
  arr.setLength(len,Math.min(0.30,len*0.36),Math.min(0.15,len*0.18));
}}

const UE=new THREE.Vector3(0,0,0);

// UE — focal Electron, stays fixed
// UE — plasma globe: hot-pink sphere + glow halos + electric arcs
const ueMesh=mkSphere(0.03,0xff44cc,0,0,0,1.0,2.2);
[{{r:0.10,c:0xff44cc,o:0.40}},{{r:0.24,c:0xcc44ff,o:0.16}},{{r:0.52,c:0x4455ff,o:0.06}}].forEach(g=>{{
  const m=new THREE.Mesh(new THREE.SphereGeometry(1,14,10),
    new THREE.MeshBasicMaterial({{color:g.c,transparent:true,opacity:g.o,
      blending:THREE.AdditiveBlending,depthWrite:false}}));
  m.scale.setScalar(g.r);scene.add(m);
}});
const _ARC_N=12,_ARC_S=8;
const _arcs=[];
const _arcCols=[0xaaddff,0xaaddff,0xaaddff,0xaaddff,0xaaddff,
                0xbb77ff,0xbb77ff,0xbb77ff,0xff66cc,0xff66cc,0xccaaff,0x88ccff];
for(let i=0;i<_ARC_N;i++){{
  const geo=new THREE.BufferGeometry();
  geo.setAttribute('position',new THREE.BufferAttribute(new Float32Array((_ARC_S+1)*3),3));
  const mat=new THREE.LineBasicMaterial({{color:_arcCols[i],transparent:true,opacity:0,
    blending:THREE.AdditiveBlending,depthTest:false,depthWrite:false}});
  const line=new THREE.Line(geo,mat);scene.add(line);
  const th=Math.random()*Math.PI*2,ph=Math.acos(2*Math.random()-1);
  _arcs.push({{line,geo,
    dx:Math.sin(ph)*Math.cos(th),dy:Math.sin(ph)*Math.sin(th),dz:Math.cos(ph),
    len:0.7+Math.random()*0.8,
    life:Math.floor(Math.random()*18),maxLife:10+Math.floor(Math.random()*18)}});
}}
function _arcTick(){{
  for(const a of _arcs){{
    a.life++;
    if(a.life>=a.maxLife){{
      const th=Math.random()*Math.PI*2,ph=Math.acos(2*Math.random()-1);
      a.dx=Math.sin(ph)*Math.cos(th);a.dy=Math.sin(ph)*Math.sin(th);a.dz=Math.cos(ph);
      a.len=0.7+Math.random()*0.8;a.life=0;a.maxLife=10+Math.floor(Math.random()*18);
    }}
    const p=a.geo.attributes.position.array;
    let px=a.dx*0.035,py=a.dy*0.035,pz=a.dz*0.035;
    const st=a.len/_ARC_S;
    for(let i=0;i<=_ARC_S;i++){{
      const jit=0.06*(1-i/_ARC_S*0.4);
      p[i*3]  =px+(Math.random()-.5)*jit;
      p[i*3+1]=py+(Math.random()-.5)*jit;
      p[i*3+2]=pz+(Math.random()-.5)*jit;
      px+=a.dx*st;py+=a.dy*st;pz+=a.dz*st;
    }}
    a.geo.attributes.position.needsUpdate=true;
    a.line.material.opacity=Math.sin(a.life/a.maxLife*Math.PI)*0.90;
  }}
}}
let ueLabel=null;
if(D.mono){{
  ueLabel=mkLabel('E','#FFD700');ueLabel.scale.set(0.10,0.10,1);scene.add(ueLabel);
}}

// Background Electrons — scattered, slow Brownian
const bgEs=[];
const initScR=D.scens.Left.r_e;
for(let i=0;i<30;i++){{
  const[x,y,z]=loosePt(3.8+Math.random()*3.2,1.4);
  const sz=initScR*(0.65+Math.random()*0.7);
  const mesh=mkSphere(sz,0x7799bb,x,y,z,0.42,0.14);
  const eo={{mesh,vx:(Math.random()-.5)*.004,vy:(Math.random()-.5)*.004,vz:(Math.random()-.5)*.004,sz}};
  if(D.mono){{
    const sl=mkLabel('E','#FFD700');sl.scale.set(sz*2.8,sz*2.8,1);scene.add(sl);eo.label=sl;
  }}
  bgEs.push(eo);
}}

// Nucleons — created at max count, hidden extras fade in/out
const nkns=[];
function addGroup(maxN,r0,sig,initR3d,col,type,letter){{
  const sc0=D.scens.Left;
  for(let i=0;i<maxN;i++){{
    const[x,y,z]=loosePt(r0,sig);
    const szF=Math.max(0.55,Math.min(1.55,1+gauss()*0.18));
    const initOp=(type==='g'&&i<sc0.n_g)||(type==='p'&&i<sc0.n_p)||(type==='s'&&i<sc0.n_s)?0.90:0.0;
    const mesh=mkSphere(initR3d*szF,col,x,y,z,initOp,0.30);
    const obj={{mesh,r0,type,szF,
      curScale:initR3d*szF,targetScale:initR3d*szF,
      curOpacity:initOp,targetOpacity:initOp,
      arrowPhase:Math.random()*Math.PI*2,
      vx:(Math.random()-.5)*.009,vy:(Math.random()-.5)*.009,vz:(Math.random()-.5)*.009}};
    if(D.mono){{
      const lc=letter==='G'?'#ff3333':'#ffffff';
      const sl=mkLabel(letter,lc);
      sl.scale.set(initR3d*szF*3.2,initR3d*szF*3.2,1);scene.add(sl);obj.label=sl;obj.labelSz=initR3d*szF*3.2;
    }}
    if(D.arrows&&initOp>0){{
      const dv=new THREE.Vector3(1,0,0);
      function mkArr(origin,c){{
        const a=new THREE.ArrowHelper(dv,origin,1,c,0.30,0.15);
        a.line.material.transparent=true;a.cone.material.transparent=true;
        scene.add(a);return a;
      }}
      if(type==='g'){{
        const arr=mkArr(UE.clone(),col);obj.arrow={{ref:arr,from:'ue',to:'n'}};
      }}else if(type==='p'){{
        const arr=mkArr(new THREE.Vector3(x,y,z),col);obj.arrow={{ref:arr,from:'n',to:'ue'}};
      }}else{{
        const a1=mkArr(UE.clone(),col),a2=mkArr(new THREE.Vector3(x,y,z),col);
        obj.arrowPair=[{{ref:a1,from:'ue',to:'n'}},{{ref:a2,from:'n',to:'ue'}}];
      }}
    }}
    nkns.push(obj);
  }}
}}
addGroup(D.maxNG,1.8,0.55,D.scens.Left.r_g,0xFFD700,'g','G');
addGroup(D.maxNP,3.0,0.90,D.scens.Left.r_p,0x228B22,'p','P');
addGroup(D.maxNS,4.2,1.20,D.scens.Left.r_s,0x8B0000,'s','S');

function fmtKX(n){{if(n>=1000)return Math.round(n/1000)+'Kx';return n+'×';}}
function fmtN(n){{return n.toLocaleString();}}
function fmtUSD(n){{return '$'+n.toLocaleString();}}
function updateLegend(name){{
  const sc=D.scens[name];
  document.getElementById('lg-g-sz-disp').textContent=sc.disp_g+'×';
  document.getElementById('lg-g-sz').textContent=fmtKX(sc.mult_g);
  document.getElementById('lg-g-qt').textContent=fmtN(sc.n_g);
  document.getElementById('lg-g-tt').textContent=fmtKX(sc.mult_g*sc.n_g);
  document.getElementById('lg-p-sz-disp').textContent=sc.disp_p+'×';
  document.getElementById('lg-p-sz').textContent=fmtKX(sc.mult_p);
  document.getElementById('lg-p-qt').textContent=fmtN(sc.n_p);
  document.getElementById('lg-p-tt').textContent=fmtKX(sc.mult_p*sc.n_p);
  document.getElementById('lg-s-sz-disp').textContent=sc.disp_s+'×';
  document.getElementById('lg-s-sz').textContent=fmtKX(sc.mult_s);
  document.getElementById('lg-s-qt').textContent=fmtN(sc.n_s);
  document.getElementById('lg-s-tt').textContent=fmtKX(sc.mult_s*sc.n_s);
  document.getElementById('lg-scale').textContent='1× = '+fmtUSD(sc.pe);
}}
updateLegend('Left');

// Scenario switch — update tween targets
function switchScen(name){{
  curScen=name;
  document.querySelectorAll('.sbtn').forEach(b=>b.classList.remove('active'));
  document.getElementById('btn-'+name).classList.add('active');
  updateLegend(name);
  const sc=D.scens[name];
  let gi=0,pi=0,si=0;
  for(const n of nkns){{
    if(n.type==='g'){{
      n.targetScale=sc.r_g*n.szF;n.targetOpacity=gi<sc.n_g?0.90:0.0;gi++;
    }}else if(n.type==='p'){{
      n.targetScale=sc.r_p*n.szF;n.targetOpacity=pi<sc.n_p?0.90:0.0;pi++;
    }}else{{
      n.targetScale=sc.r_s*n.szF;n.targetOpacity=si<sc.n_s?0.90:0.0;si++;
    }}
  }}
}}

const _tmpV=new THREE.Vector3();
let t=0;
function animate(){{
  requestAnimationFrame(animate);t+=0.004;
  camera.position.x=8*Math.sin(t*.38);
  camera.position.z=8*Math.cos(t*.38);
  camera.position.y=1.5+1.1*Math.sin(t*.16);
  camera.lookAt(0,0,0);

  // UE label — front-facing surface
  if(D.mono&&ueLabel){{
    _tmpV.copy(camera.position).normalize().multiplyScalar(0.06);
    ueLabel.position.set(_tmpV.x,_tmpV.y,_tmpV.z);
  }}
  _arcTick();

  // Background electron Brownian
  for(const e of bgEs){{
    e.vx+=(Math.random()-.5)*.0022;e.vy+=(Math.random()-.5)*.0022;e.vz+=(Math.random()-.5)*.0022;
    e.vx*=.980;e.vy*=.980;e.vz*=.980;
    e.mesh.position.x+=e.vx;e.mesh.position.y+=e.vy;e.mesh.position.z+=e.vz;
    if(D.mono&&e.label){{
      _tmpV.subVectors(camera.position,e.mesh.position).normalize().multiplyScalar(e.sz*0.85);
      e.label.position.copy(e.mesh.position).add(_tmpV);
    }}
  }}

  // Nucleon Brownian + tween
  for(const n of nkns){{
    // Lerp scale and opacity (morph)
    n.curScale+=(n.targetScale-n.curScale)*LERP;
    n.curOpacity+=(n.targetOpacity-n.curOpacity)*LERP;
    n.mesh.scale.setScalar(n.curScale);
    n.mesh.material.opacity=n.curOpacity;
    n.mesh.visible=n.curOpacity>0.01;

    if(!n.mesh.visible){{
      if(D.mono&&n.label)n.label.visible=false;
      if(D.arrows&&n.arrow)n.arrow.ref.visible=false;
      if(D.arrows&&n.arrowPair){{n.arrowPair[0].ref.visible=false;n.arrowPair[1].ref.visible=false;}}
      continue;
    }}
    if(D.mono&&n.label)n.label.visible=true;

    // Brownian motion — loose spring, soft outer fence at r>6.5
    n.vx+=(Math.random()-.5)*.003;n.vy+=(Math.random()-.5)*.003;n.vz+=(Math.random()-.5)*.003;
    const p=n.mesh.position;
    const r=Math.sqrt(p.x*p.x+p.y*p.y+p.z*p.z);
    const k=.003*(n.r0-r)/Math.max(r,.1);
    n.vx+=p.x*k;n.vy+=p.y*k;n.vz+=p.z*k;
    if(r>6.5){{const pull=0.008*(6.5-r)/r;n.vx+=p.x*pull;n.vy+=p.y*pull;n.vz+=p.z*pull;}}
    n.vx*=.974;n.vy*=.974;n.vz*=.974;
    p.x+=n.vx;p.y+=n.vy;p.z+=n.vz;

    // Monogram: offset toward camera onto sphere surface
    if(D.mono&&n.label){{
      _tmpV.subVectors(camera.position,p).normalize().multiplyScalar(n.curScale*0.85);
      n.label.position.copy(p).add(_tmpV);
      const ls=n.curScale*3.2;n.label.scale.set(ls,ls,1);
    }}
    // Arrows — pulsing energy
    if(D.arrows){{
      const nv=new THREE.Vector3(p.x,p.y,p.z);
      const pulse=0.20+0.80*(0.5+0.5*Math.sin(t*5.5+n.arrowPhase));
      function applyPulse(a){{
        a.line.material.opacity=pulse;a.cone.material.opacity=pulse;
      }}
      if(n.arrow){{
        n.arrow.ref.visible=true;applyPulse(n.arrow.ref);
        const fr=n.arrow.from==='ue'?UE:nv,to=n.arrow.to==='ue'?UE:nv;
        updateArrow(n.arrow.ref,fr,to);
      }}
      if(n.arrowPair){{
        n.arrowPair[0].ref.visible=true;n.arrowPair[1].ref.visible=true;
        applyPulse(n.arrowPair[0].ref);applyPulse(n.arrowPair[1].ref);
        updateArrow(n.arrowPair[0].ref,UE,nv);updateArrow(n.arrowPair[1].ref,nv,UE);
      }}
    }}
  }}
  renderer.render(scene,camera);
}}
animate();
let _fakeFS=false;
const _fsRoot=document.documentElement;
const _isIOS=/iPhone|iPad|iPod/.test(navigator.userAgent)&&!window.MSStream;
function _enterFakeFS(){{
  _fakeFS=true;
  document.getElementById('fsbtn').textContent='✕';
  const w=window.innerWidth,h=window.screen.height;
  window.parent.postMessage({{isStreamlitMessage:true,type:'streamlit:setFrameHeight',height:h+60}},'*');
  renderer.domElement.style.cssText='position:fixed;top:0;left:0;width:100%;height:100%;z-index:5';
  renderer.setSize(w,h);camera.aspect=w/h;camera.updateProjectionMatrix();
}}
function _exitFakeFS(){{
  _fakeFS=false;
  document.getElementById('fsbtn').textContent='⛶';
  window.parent.postMessage({{isStreamlitMessage:true,type:'streamlit:setFrameHeight',height:{H}+8}},'*');
  renderer.domElement.style.cssText='';
  renderer.setSize(window.innerWidth,{H});camera.aspect=window.innerWidth/{H};camera.updateProjectionMatrix();
}}
function toggleFS(){{
  if(_fakeFS){{_exitFakeFS();return;}}
  const isFS=document.fullscreenElement||document.webkitFullscreenElement;
  if(isFS){{const ex=document.exitFullscreen||document.webkitExitFullscreen;if(ex)ex.call(document);return;}}
  if(_isIOS){{_enterFakeFS();return;}}
  const req=_fsRoot.requestFullscreen||_fsRoot.webkitRequestFullscreen;
  try{{
    if(req)req.call(_fsRoot).then(()=>{{document.getElementById('fsbtn').textContent='✕';}}).catch(()=>_enterFakeFS());
    else _enterFakeFS();
  }}catch(e){{_enterFakeFS();}}
}}
function _onFSChange(){{
  const isFS=document.fullscreenElement||document.webkitFullscreenElement;
  const w=window.innerWidth,h=isFS?window.innerHeight:{H};
  renderer.setSize(w,h);camera.aspect=w/h;camera.updateProjectionMatrix();
  if(!isFS&&!_fakeFS)document.getElementById('fsbtn').textContent='⛶';
}}
document.addEventListener('fullscreenchange',_onFSChange);
document.addEventListener('webkitfullscreenchange',_onFSChange);
window.addEventListener('resize',()=>{{
  if(_fakeFS||document.fullscreenElement||document.webkitFullscreenElement)return;
  const w=window.innerWidth;renderer.setSize(w,{H});camera.aspect=w/{H};camera.updateProjectionMatrix();
}});
</script>
</body></html>"""



st.markdown('<div id="throttles"></div>', unsafe_allow_html=True)
with st.expander("Electron Throttles", expanded=not _is_mobile):
    st.markdown(
        "<style>div.stSlider > label { display:block; text-align:center; width:100%; }</style>",
        unsafe_allow_html=True,
    )
    _et_l, _et_c, _et_r = st.columns(3)
    with _et_l:
        st.slider(
            "Left · cCon",
            0,
            99,
            75,
            1,
            format="%d%% cCon",
            key="th_ccon",
            on_change=lambda: _scale_mechs("c"),
        )
    with _et_c:
        st.slider(
            "Center",
            0,
            99,
            50,
            1,
            format="%d%% cCon",
            key="th_center",
            on_change=lambda: _scale_mechs("center"),
        )
    with _et_r:
        st.slider(
            "Right · dCon",
            0,
            99,
            25,
            1,
            format="%d%% cCon",
            key="th_dcon",
            on_change=lambda: _scale_mechs("d"),
        )
    with st.expander("Mechanisms", expanded=False):
        st.markdown(
            "<style>section[data-testid='stMain'] div[data-testid='stNumberInput'] input{text-align:center}</style>",
            unsafe_allow_html=True,
        )
        _mh = st.columns([1.5, 0.8, 2.6, 2.6, 2.6])
        for _mc, _mt in zip(
            _mh, ["", "Weight", "Left · cCon", "Center", "Right · dCon"]
        ):
            _mc.markdown(
                f"<div style='text-align:center;font-weight:600'>{_mt}</div>",
                unsafe_allow_html=True,
            )
        for _m in _MECHS:
            _lo, _hi = _MECH_DIR[_m]
            _dir_lbl = f"← {_lo}  ·  {_hi} →"
            _mc = st.columns([1.5, 0.8, 2.6, 2.6, 2.6])
            _mc[0].markdown(
                f"<div style='text-align:left;font-weight:600;padding-top:28px'>{_MECH_LBL[_m]}</div>",
                unsafe_allow_html=True,
            )
            _mc[1].number_input(
                "wt",
                min_value=0,
                max_value=5,
                value=_MECH_DEF[_m][3],
                step=1,
                key=f"mech_weight_{_m}",
                on_change=_sync_all_th,
                label_visibility="collapsed",
            )
            _mc[2].slider(
                _dir_lbl,
                0,
                99,
                _MECH_DEF[_m][0],
                format="%d%% cCon",
                key=f"mech_{_m}_c",
                on_change=lambda: _sync_th("c"),
            )
            _mc[3].slider(
                _dir_lbl,
                0,
                99,
                _MECH_DEF[_m][1],
                format="%d%% cCon",
                key=f"mech_{_m}_center",
                on_change=lambda: _sync_th("center"),
            )
            _mc[4].slider(
                _dir_lbl,
                0,
                99,
                _MECH_DEF[_m][2],
                format="%d%% cCon",
                key=f"mech_{_m}_d",
                on_change=lambda: _sync_th("d"),
            )
    st.markdown(
        "<p style='text-align:center;font-weight:600;font-size:1.0em;margin:16px 0 4px 0'>IQ Control</p>",
        unsafe_allow_html=True,
    )
    _tiq_data = []
    for _s, _label in SCENARIOS:
        _dfem_t = calculate_en_masse(_s).set_index("Class")
        _e_iq_t = float(_dfem_t.loc["Electrons (throttled)", "Total IQ"])
        _unth_iq_t = float(_dfem_t.loc["Electrons (unthrottled)", "Total IQ"])
        _n_iq_t = _unth_iq_t - _e_iq_t  # IQ suppressed by throttle
        _tiq_data.append((_label, _e_iq_t, _n_iq_t, _unth_iq_t))
    _tiq_y_max = max(d[3] for d in _tiq_data) * 1.18
    _tiq_lbl_clr = "white" if st.session_state.get("dark_mode", False) else "black"
    _tiq_xlbls = ["Left\ncCon", "Center", "Right\ndCon"]
    _tiq_cols = st.columns(3)
    for _ci, ((_label, _e_iq_t, _n_iq_t, _tot_t), _col_w, _xlbl) in enumerate(
        zip(_tiq_data, _tiq_cols, _tiq_xlbls)
    ):
        _fig_t = go.Figure()
        _fig_t.add_trace(
            go.Bar(
                x=[_xlbl],
                y=[_e_iq_t],
                marker_color="#00008B",
                text=[f"<b>Electron<br>Controlled</b><br>{_e_iq_t:,.0f}"],
                textposition="inside",
                textfont=dict(color="white", size=9),
                showlegend=False,
            )
        )
        _fig_t.add_trace(
            go.Bar(
                x=[_xlbl],
                y=[_n_iq_t],
                marker_color="#FFD700",
                text=[f"<b>Nucleon<br>Controlled</b><br>{_n_iq_t:,.0f}"],
                textposition="inside",
                textfont=dict(color="#333", size=9),
                showlegend=False,
            )
        )
        _fig_t.add_annotation(
            x=_xlbl,
            y=_tot_t,
            text=f"<b>{_tot_t:,.0f}</b>",
            showarrow=False,
            yshift=10,
            font=dict(size=10, color=_tiq_lbl_clr),
        )
        _fig_t.update_layout(
            barmode="stack",
            height=280,
            showlegend=False,
            margin=dict(t=38, b=40, l=50 if _ci == 0 else 10, r=10),
            yaxis=dict(
                showticklabels=_ci == 0,
                showgrid=True,
                gridcolor="#ddd",
                range=[1, _tiq_y_max],
                tickformat=",",
            ),
            xaxis=dict(showticklabels=True),
            plot_bgcolor="white",
        )
        if _ci == 0:
            _fig_t.add_annotation(
                xref="paper", yref="paper", x=0, y=1,
                text="IQ<br>Points", showarrow=False,
                xanchor="center", yanchor="bottom", xshift=-26,
                align="center", font=dict(size=10))
        with _col_w:
            st.plotly_chart(_fig_t, use_container_width=True)

compare_df = pd.DataFrame(
    [
        {
            "Scenario": label,
            "Total tBP (Trillions Smart $)": calculate_breakdown(scen)[1],
        }
        for scen, label in SCENARIOS
    ]
)
_totals = compare_df["Total tBP (Trillions Smart $)"]
_lv, _cv, _rv = list(_totals)
_pct_lc = round((_cv - _lv) / _lv * 100)
_pct_cr = round((_rv - _cv) / _cv * 100)
_pct_lr = round((_rv - _lv) / _lv * 100)
_ac = "#cc2200"

# Theme-aware colors — driven by sidebar toggle
_is_dark = st.session_state.get("dark_mode", False)
_val_color = "white" if _is_dark else "black"  # bar total labels
_desc_color = "white" if _is_dark else "#555555"  # case description headers

# Arc start/end points — just above bar value labels
_lv_y, _cv_y, _rv_y = _lv + 1.5, _cv + 1.5, _rv + 1.5
# Peaks — halved from original to reduce arc height
_peak_lc = max(_lv_y, _cv_y) + 1.1
_peak_cr = max(_cv_y, _rv_y) + 1.1
_peak_lr = max(_lv_y, _cv_y, _rv_y) + 1.9
_y_min = round(min(_totals) - 2)
_y_max = round(max(_totals) + 4.0)  # headroom for arc peaks + labels

# Case description headers — dynamic from throttle settings
_th_c = st.session_state.get("th_ccon", 75) / 100
_th_ctr = st.session_state.get("th_center", 50) / 100
_th_d = st.session_state.get("th_dcon", 25) / 100


def _case_hdr(th, is_dcon=False):
    pct = round(th * 100)
    code = f"D{pct}" if is_dcon else f"C{100 - pct}"
    qual = (
        "Massive cCon"
        if th >= 0.76
        else (
            "Strong cCon"
            if th >= 0.6
            else "Moderate cCon" if th >= 0.4 else "Minimal cCon"
        )
    )
    return f"<b>{code}: {pct}% cCon</b><br>{qual}"


_case_hdrs = [_case_hdr(_th_c), _case_hdr(_th_ctr), _case_hdr(_th_d, True)]
_tick_labels = ["Left<br>cCon", "Center", "Right<br>dCon"]
_xaxis_cfg = dict(title="", ticktext=_tick_labels, tickvals=["Left", "Center", "Right"])

fig_main = px.bar(
    compare_df,
    x="Scenario",
    y="Total tBP (Trillions Smart $)",
    color="Scenario",
    color_discrete_map={"Left": "#1f77b4", "Center": "#888888", "Right": "#d62728"},
)
fig_main.update_traces(texttemplate="")  # labels via annotations for dark-mode safety
fig_main.update_layout(
    height=520,
    bargap=0.25,
    showlegend=False,
    title=dict(
        text="Gross Total<br>BrainPower", x=0.5, xanchor="center", font=dict(size=16)
    ),
    xaxis=_xaxis_cfg,
    yaxis=dict(
        range=[_y_min, _y_max],
        tickprefix="S$",
        ticksuffix="T",
        tickformat=".0f",
        title="",
    ),
    margin=dict(b=160, t=140),
)

# Bar value labels — no box, theme-aware color
for label_col, total in zip(["Left", "Center", "Right"], list(_totals)):
    fig_main.add_annotation(
        x=label_col,
        y=total,
        xref="x",
        yref="y",
        text=f"<b>S${total:.1f}T</b>",
        showarrow=False,
        yanchor="bottom",
        yshift=6,
        font=dict(size=15, color=_val_color),
    )

# Case description headers above plot area
for (_, label), hdr in zip(SCENARIOS, _case_hdrs):
    fig_main.add_annotation(
        x=label,
        y=1.03,
        xref="x",
        yref="paper",
        text=hdr,
        showarrow=False,
        yanchor="bottom",
        font=dict(size=11, color=_desc_color),
        align="center",
    )


# Growth arcs — cubic bezier (C) with control points close to endpoints → steep entry/exit
def _add_arc(fig, x0, y0, x1, y1, peak, cx_inset, pct_label, label_x, ac):
    fig.add_shape(
        type="path",
        path=f"M {x0},{y0} C {x0+cx_inset},{peak} {x1-cx_inset},{peak} {x1},{y1}",
        xref="x",
        yref="y",
        line=dict(color=ac, width=2),
    )
    ax = (x1 - cx_inset) * 0.15 + x1 * 0.85
    ay = peak * 0.15 + y1 * 0.85
    fig.add_annotation(
        x=x1,
        y=y1,
        ax=ax,
        ay=ay,
        xref="x",
        yref="y",
        axref="x",
        ayref="y",
        text="",
        showarrow=True,
        arrowhead=2,
        arrowwidth=2,
        arrowcolor=ac,
    )
    fig.add_annotation(
        x=label_x,
        y=peak,
        xref="x",
        yref="y",
        text=f"<b>+{pct_label}%</b>",
        showarrow=False,
        font=dict(color=ac, size=13),
        yanchor="top",
        yshift=-10,
    )


_add_arc(fig_main, 0, _lv_y, 1, _cv_y, _peak_lc, 0.12, _pct_lc, 0.5, _ac)
_add_arc(fig_main, 1, _cv_y, 2, _rv_y, _peak_cr, 0.12, _pct_cr, 1.7, _ac)
_add_arc(fig_main, 0, _lv_y, 2, _rv_y, _peak_lr, 0.18, _pct_lr, 1.0, _ac)

fig_main.add_annotation(**_FOOTER_ANNOTATION)

# ---- Chart 2: Stacked BP by Class ----
stack_data = []
for scen, label in SCENARIOS:
    df, _ = calculate_breakdown(scen)
    for _, row in df.iterrows():
        stack_data.append(
            {
                "Scenario": label,
                "Class": row["Class"],
                "tBP": row["tBP"],
                "Label": row["Class"],
            }
        )
stack_df = pd.DataFrame(stack_data)
_y_max_stack = round(max(_totals) + 3)
fig_stacked = px.bar(
    stack_df,
    x="Scenario",
    y="tBP",
    color="Class",
    text="Label",
    category_orders={"Class": ["SinSayers", "GovNukes", "Providers", "Electrons"]},
    color_discrete_sequence=["#8B0000", "#FFD700", "#228B22", "#00008B"],
)
fig_stacked.update_traces(
    texttemplate="%{text}<br>S$%{y:.1f}T",
    textposition="inside",
    textfont=dict(size=12, color="white", weight="bold"),
)
for trace in fig_stacked.data:
    if trace.name == "GovNukes":
        trace.textfont.color = "#8B0000"
    if trace.name in ["GovNukes", "Providers", "SinSayers"]:
        _nuke_bg = {
            "GovNukes": "#FFD700",
            "Providers": "#228B22",
            "SinSayers": "#8B0000",
        }
        trace.marker.pattern.shape = "x"
        trace.marker.pattern.bgcolor = _nuke_bg[trace.name]
        trace.marker.pattern.fgcolor = (
            "rgba(0,0,0,0.12)" if trace.name == "GovNukes" else "rgba(255,255,255,0.32)"
        )
        trace.marker.pattern.size = 8
fig_stacked.update_layout(
    height=520,
    barmode="stack",
    showlegend=False,
    title=dict(
        text="Class Based<br>BrainPower", x=0.5, xanchor="center", font=dict(size=16)
    ),
    uniformtext=dict(minsize=8, mode="hide"),
    xaxis=_xaxis_cfg,
    yaxis=dict(
        range=[0.1, _y_max_stack],
        tickprefix="S$",
        ticksuffix="T",
        tickformat=".0f",
        title="",
    ),
    margin=dict(b=160, t=140),
)
for _, (scen, label) in enumerate(SCENARIOS):
    _, total = calculate_breakdown(scen)
    fig_stacked.add_annotation(
        x=label,
        y=total,
        xref="x",
        yref="y",
        text=f"<b>S${total:.1f}T</b>",
        showarrow=False,
        yanchor="bottom",
        yshift=6,
        font=dict(size=15, color=_val_color),
        align="center",
    )
for (_, label), hdr in zip(SCENARIOS, _case_hdrs):
    fig_stacked.add_annotation(
        x=label,
        y=1.03,
        xref="x",
        yref="paper",
        text=hdr,
        showarrow=False,
        yanchor="bottom",
        font=dict(size=11, color=_desc_color),
        align="center",
    )
fig_stacked.add_annotation(**_FOOTER_ANNOTATION)

# ---- Chart 3: Electrons vs Nucleons BP (new) ----
_labs3 = ["Left", "Center", "Right"]
_x3e = [f"{lbl}\nElectrons" for lbl in _labs3]
_x3n = [f"{lbl}\nNucleons" for lbl in _labs3]
_x3_order = [x for pair in zip(_x3e, _x3n) for x in pair]

_bp_ev, _bp_gv, _bp_pv, _bp_sv = [], [], [], []
for scen, _ in SCENARIOS:
    _dfb, _ = calculate_breakdown(scen)
    _dfb = _dfb.set_index("Class")
    _bp_ev.append(_dfb.loc["Electrons", "tBP"])
    _bp_gv.append(_dfb.loc["GovNukes", "tBP"])
    _bp_pv.append(_dfb.loc["Providers", "tBP"])
    _bp_sv.append(_dfb.loc["SinSayers", "tBP"])
_bp_nv = [_bp_gv[i] + _bp_pv[i] + _bp_sv[i] for i in range(3)]

fig_en = go.Figure()
fig_en.add_trace(
    go.Bar(
        name="Electrons",
        x=_x3e,
        y=_bp_ev,
        marker_color="#00008B",
        text=["Electrons"] * 3,
        texttemplate="%{text}<br>S$%{y:.1f}T",
        textposition="outside",
        textfont=dict(color=_val_color, size=11),
    )
)
fig_en.add_trace(
    go.Bar(
        name="SinSayers",
        x=_x3n,
        y=_bp_sv,
        marker_color="#8B0000",
        text=["SinSayers"] * 3,
        texttemplate="%{text}<br>S$%{y:.1f}T",
        textposition="inside",
        textfont=dict(color="white", size=11),
    )
)
fig_en.add_trace(
    go.Bar(
        name="GovNukes",
        x=_x3n,
        y=_bp_gv,
        marker_color="#FFD700",
        text=["GovNukes"] * 3,
        texttemplate="%{text}<br>S$%{y:.1f}T",
        textposition="inside",
        textfont=dict(color="#8B0000", size=11),
    )
)
fig_en.add_trace(
    go.Bar(
        name="Providers",
        x=_x3n,
        y=_bp_pv,
        marker_color="#228B22",
        text=["Providers"] * 3,
        texttemplate="%{text}<br>S$%{y:.1f}T",
        textposition="inside",
        textfont=dict(color="white", size=11),
    )
)
for x3n_lbl, n_tot in zip(_x3n, _bp_nv):
    fig_en.add_annotation(
        x=x3n_lbl,
        y=n_tot,
        xref="x",
        yref="y",
        text=f"<b>S${n_tot:.1f}T</b>",
        showarrow=False,
        yanchor="bottom",
        yshift=4,
        font=dict(size=12, color=_val_color),
    )
for i, lbl in enumerate(_labs3):
    fig_en.add_annotation(
        x=(2 * i + 1) / 6,
        y=1.04,
        xref="paper",
        yref="paper",
        text=f"<b>{lbl}</b>",
        showarrow=False,
        yanchor="bottom",
        font=dict(size=13, color=_desc_color),
    )
for sep in [1.5, 3.5]:
    fig_en.add_vline(x=sep, line_width=1, line_color="#bbb")
fig_en.update_layout(
    barmode="stack",
    height=500,
    showlegend=False,
    title=dict(
        text="Electrons v Nucleons<br>BrainPower",
        x=0.5,
        xanchor="center",
        font=dict(size=16),
    ),
    uniformtext=dict(minsize=8, mode="hide"),
    xaxis=dict(
        categoryorder="array",
        categoryarray=_x3_order,
        ticktext=["Electrons", "Nucleons"] * 3,
        tickvals=_x3_order,
    ),
    yaxis=dict(
        title="", range=[0.1, max(max(_bp_nv), max(_bp_ev)) * 1.12],
        tickprefix="S$", ticksuffix="T", tickformat=".0f"
    ),
    margin=dict(b=80, t=130),
)
fig_en.add_annotation(**_FOOTER_ANNOTATION)

# ---- Chart: Total IQ (log scale, new) ----
_iq_ev, _iq_nv = [], []
for scen, _ in SCENARIOS:
    _dfem = calculate_en_masse(scen)
    _iq_ev.append(
        float(_dfem[_dfem["Class"] == "Electrons (throttled)"]["Total IQ"].values[0])
    )
    _iq_nv.append(
        float(
            _dfem[_dfem["Class"].isin(["GovNukes", "Providers", "SinSayers"])][
                "Total IQ"
            ].sum()
        )
    )

fig_iq = go.Figure()
fig_iq.add_trace(
    go.Bar(
        name="Electrons",
        x=_labs3,
        y=_iq_ev,
        marker_color="#00008B",
        text=[f"Electrons<br>{v:,.0f}" for v in _iq_ev],
        textposition="inside",
        textfont=dict(color="white", size=10),
    )
)
fig_iq.add_trace(
    go.Bar(
        name="Nucleons",
        x=_labs3,
        y=_iq_nv,
        marker_color="#4477bb",
        text=[f"Nucleons<br>{v:,.0f}" for v in _iq_nv],
        textposition="inside",
        textfont=dict(color="white", size=10),
    )
)
# Convert data values to approximate paper y on the log scale
# (xref="x"/yref="y" with categorical axis is unreliable for shapes/annotations;
#  all-paper coords sidestep this entirely)
_all_iq = _iq_ev + _iq_nv
_iq_log_span = math.log10(max(_all_iq)) - math.log10(min(_all_iq))
_iq_log_lo = math.log10(min(_all_iq)) - 0.05 * _iq_log_span
_iq_log_hi = math.log10(max(_all_iq)) + 0.05 * _iq_log_span


def _iq_py(v):
    return (math.log10(v) - _iq_log_lo) / (_iq_log_hi - _iq_log_lo)


_e_ys = [_iq_py(v) for v in _iq_ev]  # Electrons bar top paper y
_n_ys = [_iq_py(v) for v in _iq_nv]  # Nucleons bar top paper y

# Paper x positions (categorical axis spans [-0.5, 2.5] → paper_x = (axis_x+0.5)/3)
# bar centers: Electrons at i-0.2, Nucleons at i+0.2; right edge of Electrons at i
_e_cx = [0.100, 0.433, 0.767]  # Electrons bar centers in paper x
_e_rx = [0.167, 0.500, 0.833]  # Electrons bar right edges in paper x
_n_cx = [0.233, 0.567, 0.900]  # Nucleons bar centers in paper x

_iq_mult_lc = _iq_ev[1] / _iq_ev[0]
_iq_mult_lr = _iq_ev[2] / _iq_ev[0]

# Blue arcs; small filled circle at destination endpoint
_lc_P = [(_e_cx[0], _e_ys[0]), (0.16, 1.05), (0.34, 1.05), (_e_cx[1], _e_ys[1])]
_lr_P = [(_e_cx[0], _e_ys[0]), (0.25, 1.25), (0.65, 1.25), (_e_cx[2], _e_ys[2])]
for _arc_P in [_lc_P, _lr_P]:
    fig_iq.add_shape(
        type="path",
        path=f"M {_arc_P[0][0]:.3f},{_arc_P[0][1]:.3f} C {_arc_P[1][0]},{_arc_P[1][1]} {_arc_P[2][0]},{_arc_P[2][1]} {_arc_P[3][0]:.3f},{_arc_P[3][1]:.3f}",
        xref="paper",
        yref="paper",
        line=dict(color="#1155cc", width=2),
    )
    cx, cy = _arc_P[3]
    fig_iq.add_shape(
        type="circle",
        x0=cx - 0.004,
        y0=cy - 0.009,
        x1=cx + 0.004,
        y1=cy + 0.009,
        xref="paper",
        yref="paper",
        fillcolor="#1155cc",
        line_color="#1155cc",
    )
# Labels below arcs, at x-midpoint of each arc span
fig_iq.add_annotation(
    x=(_e_cx[0] + _e_cx[1]) / 2,
    y=1.05,
    xref="paper",
    yref="paper",
    text=f"<b>{_iq_mult_lc:.0f}X</b>",
    showarrow=False,
    font=dict(color="#1155cc", size=13),
    yanchor="top",
)
fig_iq.add_annotation(
    x=(_e_cx[0] + _e_cx[2]) / 2,
    y=1.25,
    xref="paper",
    yref="paper",
    text=f"<b>{_iq_mult_lr:.0f}X</b>",
    showarrow=False,
    font=dict(color="#1155cc", size=13),
    yanchor="top",
)

# Red bezier curves: S-curve Nucleons→Electrons; filled circle at Electrons endpoint
for i, (e_val, n_val) in enumerate(zip(_iq_ev, _iq_nv)):
    ey, ny = _e_ys[i], _n_ys[i]
    ex_r, nx_c = _e_rx[i], _n_cx[i]
    mid_y = (ey + ny) / 2
    growth_str = f"{e_val / n_val / 1000:.1f}K X"
    # L-curve: rise vertically from N center, then turn left to E right edge
    fig_iq.add_shape(
        type="path",
        path=f"M {nx_c:.3f},{ny:.3f} C {nx_c:.3f},{ey:.3f} {ex_r+0.01:.3f},{ey:.3f} {ex_r:.3f},{ey:.3f}",
        xref="paper",
        yref="paper",
        line=dict(color="#cc2200", width=1.5),
    )
    fig_iq.add_shape(
        type="circle",
        x0=ex_r - 0.004,
        y0=ey - 0.009,
        x1=ex_r + 0.004,
        y1=ey + 0.009,
        xref="paper",
        yref="paper",
        fillcolor="#cc2200",
        line_color="#cc2200",
    )
    fig_iq.add_annotation(
        x=nx_c,
        y=mid_y,
        xref="paper",
        yref="paper",
        text=f"<b>{growth_str}</b><br>Electron<br>Advantage",
        showarrow=False,
        font=dict(color="#cc2200", size=13),
        xanchor="left",
        xshift=4,
    )
fig_iq.update_layout(
    barmode="group",
    height=540,
    showlegend=False,
    uniformtext=dict(minsize=8, mode="hide"),
    title=dict(text="Total Applicable IQ", x=0.5, xanchor="center", font=dict(size=16)),
    yaxis=dict(type="log", title=""),
    xaxis=dict(tickvals=_labs3, ticktext=_labs3),
    margin=dict(b=100, t=150),
)
fig_iq.add_annotation(
    xref="paper",
    yref="paper",
    x=0,
    y=1,
    text="IQ<br>Points",
    showarrow=False,
    xanchor="center",
    yanchor="bottom",
    xshift=-42,
    align="center",
    font=dict(size=12),
)
fig_iq.add_annotation(**_FOOTER_ANNOTATION)


# ---- Chart: Power Per Capita (log scale, new) ----
def _fmt_pwr(v):
    if v >= 1e9:
        return f"${v/1e9:.0f}B"
    if v >= 1e6:
        return f"${v/1e6:.0f}M"
    return f"${v:,.0f}"


_pw_cls = ["Electrons", "GovNukes", "Providers", "SinSayers"]
_pw_clr = {
    "Electrons": "#00008B",
    "GovNukes": "#FFD700",
    "Providers": "#228B22",
    "SinSayers": "#8B0000",
}
_pw_vals = {c: [] for c in _pw_cls}
_pw_x_cats = []
for scen, lbl in SCENARIOS:
    _dfpc = calculate_per_capita(scen).set_index("Class")
    _pw_vals["Electrons"].append(float(_dfpc.loc["Electrons (throttled)", "Power ($)"]))
    _pw_vals["GovNukes"].append(float(_dfpc.loc["GovNukes", "Power ($)"]))
    _pw_vals["Providers"].append(float(_dfpc.loc["Providers", "Power ($)"]))
    _pw_vals["SinSayers"].append(float(_dfpc.loc["SinSayers", "Power ($)"]))
    for c in _pw_cls:
        _pw_x_cats.append(f"{lbl}\n{c}")

_pw_txt_clr = {
    "Electrons": "white",
    "GovNukes": "#333333",
    "Providers": "white",
    "SinSayers": "white",
}
fig_pw = go.Figure()
for cls in _pw_cls:
    _x_cls = [f"{lbl}\n{cls}" for lbl in _labs3]
    fig_pw.add_trace(
        go.Bar(
            name=cls,
            x=_x_cls,
            y=_pw_vals[cls],
            marker_color=_pw_clr[cls],
            text=[f"{cls}<br>{_fmt_pwr(v)}" for v in _pw_vals[cls]],
            textposition="inside",
            textfont=dict(color=_pw_txt_clr[cls], size=9),
        )
    )
# GovNukes/Electrons ratio arrows — bezier arcs from 50%-between-E-and-G to GovNukes top-left
_all_pw_vals = [v for cls in _pw_cls for v in _pw_vals[cls]]
_pw_log_span = math.log10(max(_all_pw_vals)) - math.log10(min(_all_pw_vals))
_pw_log_lo = math.log10(min(_all_pw_vals)) - 0.05 * _pw_log_span
_pw_log_hi = math.log10(max(_all_pw_vals)) + 0.05 * _pw_log_span


def _pw_py(v):
    return (math.log10(v) - _pw_log_lo) / (_pw_log_hi - _pw_log_lo)


# PPC paper x positions (12 cats, axis [-0.5,11.5]): E at cats 0,4,8; G at cats 1,5,9
_pw_e_xs = [0.5 / 12, 4.5 / 12, 8.5 / 12]  # Electron bar centers
_pw_g_lxs = [
    1.1 / 12,
    5.1 / 12,
    9.1 / 12,
]  # GovNuke left edges (bar width 0.8, left = cat-0.4)
for i, lbl in enumerate(_labs3):
    e_v = _pw_vals["Electrons"][i]
    g_v = _pw_vals["GovNukes"][i]
    e_py = _pw_py(e_v)
    g_py = _pw_py(g_v)
    sx = _pw_e_xs[i]  # start: horizontally centered on Electrons column
    gx = _pw_g_lxs[i]  # end: top-left corner of GovNukes bar
    mid_y = (e_py + g_py) / 2
    # L-curve: rise vertically from E center, then turn horizontal to G left edge top.
    # P0=(sx,e_py) P1=(sx,g_py) P2=(gx-0.01,g_py) P3=(gx,g_py)
    # Tangent at start: upward. Tangent at end: rightward (P3-P2=(0.01,0)).
    path = f"M {sx:.4f},{e_py:.3f} C {sx:.4f},{g_py:.3f} {gx-0.01:.4f},{g_py:.3f} {gx:.4f},{g_py:.3f}"
    fig_pw.add_shape(
        type="path",
        path=path,
        xref="paper",
        yref="paper",
        line=dict(color="#cc2200", width=1.5),
    )
    fig_pw.add_shape(
        type="circle",
        x0=gx - 0.003,
        y0=g_py - 0.009,
        x1=gx + 0.003,
        y1=g_py + 0.009,
        xref="paper",
        yref="paper",
        fillcolor="#cc2200",
        line_color="#cc2200",
    )
    ratio_str = f"{round((g_v/e_v)/1000)}K X"
    # Label: above arrow end, to the left of arrowhead
    fig_pw.add_annotation(
        x=gx - 0.005,
        y=g_py,
        xref="paper",
        yref="paper",
        text=f"<b>{ratio_str}</b>",
        showarrow=False,
        font=dict(color="#cc2200", size=11),
        xanchor="right",
        yanchor="bottom",
    )
for i, lbl in enumerate(_labs3):
    fig_pw.add_annotation(
        x=(4 * i + 1.5) / 12,
        y=1.04,
        xref="paper",
        yref="paper",
        text=f"<b>{lbl}</b>",
        showarrow=False,
        yanchor="bottom",
        font=dict(size=13, color=_desc_color),
    )
for sep in [3.5, 7.5]:
    fig_pw.add_vline(x=sep, line_width=1, line_color="#bbb")
fig_pw.update_layout(
    barmode="group",
    height=540,
    showlegend=False,
    uniformtext=dict(minsize=7, mode="hide"),
    yaxis=dict(
        type="log",
        title="",
        tickvals=[1e3, 1e4, 1e5, 1e6, 1e7, 1e8, 1e9],
        ticktext=["$1K", "$10K", "$100K", "$1M", "$10M", "$100M", "$1B"],
    ),
    xaxis=dict(categoryorder="array", categoryarray=_pw_x_cats, showticklabels=False),
    title=dict(text="Power per Capita", x=0.5, xanchor="center", font=dict(size=16)),
    margin=dict(b=120, t=100),
)
fig_pw.add_annotation(**_FOOTER_ANNOTATION)

# ---- Render sections ----
st.markdown('<div id="brainpower"></div>', unsafe_allow_html=True)
with st.expander("BrainPower", expanded=not _is_mobile):
    st.plotly_chart(fig_main, use_container_width=True)
    st.plotly_chart(fig_stacked, use_container_width=True)
    st.plotly_chart(fig_en, use_container_width=True)

st.markdown('<div id="brains"></div>', unsafe_allow_html=True)
with st.expander("Brains", expanded=False):
    st.plotly_chart(fig_iq, use_container_width=True)
    # Per-class en masse Total IQ charts
    _niq_defs = [
        ("GovNukes", "#FFD700", "#333333"),
        ("Providers", "#228B22", "white"),
        ("SinSayers", "#8B0000", "white"),
    ]
    _niq_data = {cls: [] for cls, _, _ in _niq_defs}
    _niq_xlbls = ["Left\ncCon", "Center", "Right\ndCon"]
    for _s, _ in SCENARIOS:
        _dfem_n = calculate_en_masse(_s).set_index("Class")
        for cls, _, _ in _niq_defs:
            _niq_data[cls].append(float(_dfem_n.loc[cls, "Total IQ"]))
    _niq_ymax = max(v for cls, _, _ in _niq_defs for v in _niq_data[cls]) * 1.1
    _niq_cols = st.columns(3)
    for _ni, ((cls, _bc, _tc), _cw) in enumerate(zip(_niq_defs, _niq_cols)):
        _fig_niq = go.Figure()
        _fig_niq.add_trace(
            go.Bar(
                x=_niq_xlbls,
                y=_niq_data[cls],
                marker_color=_bc,
                text=[f"{v:,.0f}" for v in _niq_data[cls]],
                textposition="inside",
                textfont=dict(color=_tc, size=10),
                showlegend=False,
            )
        )
        _fig_niq.update_layout(
            title=dict(
                text=f"{cls}' Total IQ", x=0.5, xanchor="center", font=dict(size=14)
            ),
            height=280,
            showlegend=False,
            margin=dict(t=55, b=40, l=60 if _ni == 0 else 10, r=10),
            yaxis=dict(
                range=[1, _niq_ymax], showticklabels=_ni == 0, title="", tickformat=","
            ),
            plot_bgcolor="white",
        )
        if _ni == 0:
            _fig_niq.add_annotation(
                xref="paper",
                yref="paper",
                x=0,
                y=1,
                text="IQ<br>Points",
                showarrow=False,
                xanchor="center",
                yanchor="bottom",
                xshift=-32,
                align="center",
                font=dict(size=10),
            )
        with _cw:
            st.plotly_chart(_fig_niq, use_container_width=True)

st.markdown('<div id="power"></div>', unsafe_allow_html=True)
with st.expander("Power", expanded=False):
    _3d_ck1, _3d_ck2 = st.columns(2)
    with _3d_ck1:
        _3d_arrows = st.checkbox("Arrows", key="uni_3d_arrows")
    with _3d_ck2:
        _3d_mono = st.checkbox("Monograms", key="uni_3d_mono")
    st.iframe(
        _build_universe_3d(show_arrows=_3d_arrows, show_mono=_3d_mono, height=820),
        height=820,
    )
    st.plotly_chart(fig_pw, use_container_width=True)
    # Per-class per capita power charts
    _npc_defs = [
        ("GovNukes", "#FFD700", "#333333"),
        ("Providers", "#228B22", "white"),
        ("SinSayers", "#8B0000", "white"),
    ]
    _npc_data = {cls: [] for cls, _, _ in _npc_defs}
    for _s, _ in SCENARIOS:
        _dfpc_n = calculate_per_capita(_s).set_index("Class")
        for cls, _, _ in _npc_defs:
            _npc_data[cls].append(float(_dfpc_n.loc[cls, "Power ($)"]))
    _ps_ymax = max(max(_npc_data["Providers"]), max(_npc_data["SinSayers"])) * 1.1
    _g_ymax = max(_npc_data["GovNukes"]) * 1.1
    _npc_cols = st.columns(3)
    for (cls, _bc, _tc), _cw in zip(_npc_defs, _npc_cols):
        _yrange = [1, _g_ymax] if cls == "GovNukes" else [1, _ps_ymax]
        _fig_npc = go.Figure()
        _fig_npc.add_trace(
            go.Bar(
                x=_labs3,
                y=_npc_data[cls],
                marker_color=_bc,
                text=[f"${v:,.0f}" for v in _npc_data[cls]],
                textposition="inside",
                textfont=dict(color=_tc, size=10),
                showlegend=False,
            )
        )
        _fig_npc.update_layout(
            title=dict(
                text=f"{cls}' Per Capita Power",
                x=0.5,
                xanchor="center",
                font=dict(size=14),
            ),
            height=280,
            showlegend=False,
            margin=dict(t=55, b=40, l=60, r=10),
            yaxis=dict(
                tickprefix="$",
                tickformat=",.0f",
                range=_yrange,
            ),
            plot_bgcolor="white",
        )
        with _cw:
            st.plotly_chart(_fig_npc, use_container_width=True)

# ====================== POPULATION ======================
st.markdown('<div id="population"></div>', unsafe_allow_html=True)
with st.expander("Populations", expanded=False):
    _hh = st.session_state.get("households", 13970000)
    _fig_epop = go.Figure()
    _fig_epop.add_trace(
        go.Bar(
            x=_labs3,
            y=[_hh] * 3,
            marker_color="#00008B",
            text=[f"{_hh:,.0f}"] * 3,
            textposition="inside",
            textfont=dict(color="white", size=11),
            showlegend=False,
        )
    )
    _fig_epop.update_layout(
        title=dict(text="Electrons", x=0.5, xanchor="center", font=dict(size=14)),
        height=240,
        showlegend=False,
        margin=dict(t=55, b=40, l=70, r=10),
        yaxis=dict(tickformat=",", range=[1, _hh * 1.15]),
        plot_bgcolor="white",
    )
    _, _ep_m, _ = st.columns([1, 2, 1])
    with _ep_m:
        st.plotly_chart(_fig_epop, use_container_width=True)
    _pop_g = [
        st.session_state.get("pop_g_c", 14),
        st.session_state.get("pop_g_center", 13),
        st.session_state.get("pop_g_d", 8),
    ]
    _pop_p = [
        st.session_state.get("pop_p_c", 35),
        st.session_state.get("pop_p_center", 40),
        st.session_state.get("pop_p_d", 55),
    ]
    _pop_s = [
        st.session_state.get("pop_s_c", 60),
        st.session_state.get("pop_s_center", 50),
        st.session_state.get("pop_s_d", 15),
    ]
    _pop_defs = [
        ("GovNukes per Electron", "#FFD700", "#333333", _pop_g),
        ("Providers per Electron", "#228B22", "white", _pop_p),
        ("SinSayers per Electron", "#8B0000", "white", _pop_s),
    ]
    _pop_cols = st.columns(3)
    for (title, _bc, _tc, vals), _cw in zip(_pop_defs, _pop_cols):
        _fig_pop = go.Figure()
        _fig_pop.add_trace(
            go.Bar(
                x=_labs3,
                y=vals,
                marker_color=_bc,
                text=[str(v) for v in vals],
                textposition="inside",
                textfont=dict(color=_tc, size=11),
                showlegend=False,
            )
        )
        _fig_pop.update_layout(
            title=dict(text=title, x=0.5, xanchor="center", font=dict(size=14)),
            height=240,
            showlegend=False,
            margin=dict(t=55, b=40, l=50, r=10),
            yaxis=dict(range=[1, max(vals) * 1.15]),
            plot_bgcolor="white",
        )
        with _cw:
            st.plotly_chart(_fig_pop, use_container_width=True)

# ====================== TABLES ======================
st.markdown('<div id="tables"></div>', unsafe_allow_html=True)
st.markdown("### Tables")
with st.expander("Per Capita Brains & Power", expanded=False):
    col_l, col_c, col_r = st.columns(3)
    for col, (scen, label) in zip([col_l, col_c, col_r], SCENARIOS):
        with col:
            st.markdown(f"**{label}**")
            df = calculate_per_capita(scen)
            st.dataframe(
                df.style.format(
                    {"IQ": "{:,.0f}", "Power ($)": "${:,.0f}"}
                ).set_properties(**{"text-align": "right"}),
                use_container_width=True,
                hide_index=True,
            )

with st.expander("En Masse Brains & Power", expanded=False):
    col_l, col_c, col_r = st.columns(3)
    for col, (scen, label) in zip([col_l, col_c, col_r], SCENARIOS):
        with col:
            st.markdown(f"**{label}**")
            dfm = calculate_en_masse(scen)

            def safe_format(x):
                return f"{x:,.0f}" if isinstance(x, (int, float)) else x

            styled = dfm.style.format(
                {"Total IQ": safe_format, "Power (Billions)": "${:,.0f}"}
            )
            styled = styled.set_properties(**{"text-align": "right"})
            st.dataframe(styled, use_container_width=True, hide_index=True)

with st.expander("BrainPower by Class", expanded=False):
    col_l, col_c, col_r = st.columns(3)
    for col, (scen, label) in zip([col_l, col_c, col_r], SCENARIOS):
        with col:
            st.markdown(f"**{label}**")
            df_bp, total_bp = calculate_breakdown(scen)
            df_display = df_bp.rename(columns={"tBP": "BrainPower (T$)"})
            total_row = pd.DataFrame([{"Class": "Total", "BrainPower (T$)": total_bp}])
            df_display = pd.concat([df_display, total_row], ignore_index=True)
            st.dataframe(
                df_display.style.format({"BrainPower (T$)": "{:.1f}"}).set_properties(
                    **{"text-align": "right"}
                ),
                use_container_width=True,
                hide_index=True,
            )

footer = "© 2026 David Burkean • Sharing is caring • Commercial use by permission • All Rights Reserved"
st.markdown(
    f"<div style='text-align: center; color: #666; padding: 20px 0; font-size: 0.9em; border-top: 1px solid #ddd;'>{footer}</div>",
    unsafe_allow_html=True,
)


# ---------------- PDF EXPORT (Playwright) ----------------

if st.session_state.get("_generate_pdf_pending", False):
    # clear pending flag and run generation after figures exist
    st.session_state["_generate_pdf_pending"] = False
    with st.spinner("Rendering PDF — launching Playwright..."):
        try:
            figs = [
                ("Gross Total BrainPower", fig_main),
                ("Class Breakdown (Stacked)", fig_stacked),
                ("Electrons v Nucleons", fig_en),
                ("Total Applicable IQ", fig_iq),
                ("Power per Capita", fig_pw),
            ]
            frags = figs_to_html_fragments(figs)
            metadata = [
                st.session_state.get("universe_name", ""),
                f"Households: {st.session_state.get('households',0):,}",
            ]
            report_html = build_report_html(
                f"Burkeanomics Report — {st.session_state.get('universe_name','Universe')}",
                frags,
                metadata,
                footer_text=footer,
            )
            pdf_bytes = render_pdf_with_playwright(report_html)
            bname = normalize_pdf_filename(
                st.session_state.get("universe_name", "universe") or "universe"
            )
            st.session_state["_pdf_ready"] = True
            st.session_state["_pdf_bytes"] = pdf_bytes
            st.session_state["_pdf_filename"] = bname
            st.rerun()
        except Exception as e:
            err = str(e)
            # Fallback: if Playwright isn't installed, offer the HTML report for download
            if (
                "playwright" in err.lower()
                or "playwright is not installed" in err.lower()
            ):
                bname_html = normalize_pdf_filename(
                    st.session_state.get("universe_name", "universe") or "universe"
                ).replace(".pdf", ".html")
                st.session_state["_pdf_ready"] = True
                st.session_state["_pdf_bytes"] = report_html.encode("utf-8")
                st.session_state["_pdf_filename"] = bname_html
                st.session_state["_pdf_mime"] = "text/html"
                st.rerun()
            else:
                st.error(f"PDF generation failed: {e}")
