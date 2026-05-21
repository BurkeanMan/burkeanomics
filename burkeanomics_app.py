import streamlit as st
import streamlit.components.v1 as _components
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import json
import math
from calculations import calculate_per_capita, calculate_en_masse, calculate_breakdown
from export import (
    build_report_html,
    figs_to_html_fragments,
    normalize_pdf_filename,
    render_pdf_with_playwright,
)
from supabase_client import (
    is_logged_in, current_user,
    sign_in, sign_up, sign_out,
    list_universes, save_universe, load_universe, delete_universe,
)

# Apply any pending JSON import before widgets are instantiated
if "_import_pending" in st.session_state:
    _pending = st.session_state.pop("_import_pending")
    for _k, _v in _pending.items():
        st.session_state[_k] = _v

st.set_page_config(
    page_title="Burkeanomics Simulator", layout="wide", initial_sidebar_state="expanded"
)

# Force one silent rerun on first load so all React expander handlers are hydrated
# before the user tries to open sections via TOC links.
if "initialized" not in st.session_state:
    st.session_state["initialized"] = True
    st.rerun()

# Detect screen width via JS; sets ?sw=m (mobile) or ?sw=p (tablet/desktop) on first load.
_sw = st.query_params.get("sw", "p")
_is_mobile = _sw == "m"
_components.html(
    """<script>
(function() {
    // Mobile detection: set ?sw= query param and redirect once
    var w = window.parent.innerWidth;
    var target = w < 768 ? 'm' : 'p';
    var url = new URL(window.parent.location.href);
    if (url.searchParams.get('sw') !== target) {
        url.searchParams.set('sw', target);
        window.parent.location.replace(url.toString());
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
        var all = window.parent.document.querySelectorAll('details');
        for (var i = 0; i < all.length; i++) {
            var s = all[i].querySelector('summary');
            if (s && s.textContent.indexOf(label) >= 0) return all[i];
        }
        return null;
    }
    function scrollToAnchor(id) {
        var el = window.parent.document.getElementById(id);
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
    window.parent.addEventListener('hashchange', function() {
        setTimeout(function() { openExpander(window.parent.location.hash); }, 80);
    });
})();
</script>""",
    height=0,
)

st.title("🧠 Burkeanomics Simulator")
# layout: version | generate | download | references
_ver_col, _gen_col, _dl_col, _ref_col = st.columns([2, 1, 1, 3])
with _ver_col:
    st.markdown(
        "<p style='font-size:14px; font-weight:600; color:#555; margin-top:8px;'>Burkeanomics Simulator d2.43</p>",
        unsafe_allow_html=True,
    )
with _gen_col:
    if st.button(
        "Generate PDF",
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
    "rpf_", "te_factor_", "ai_factor_", "universe_name", "dark_mode",
)

# ====================== ACCOUNT SIDEBAR ======================
with st.sidebar.expander("🔐 Account", expanded=not is_logged_in()):
    if is_logged_in():
        st.caption(f"Signed in as **{current_user()['email']}**")
        if st.button("Sign Out", key="sb_signout"):
            sign_out()
            st.rerun()
    else:
        _auth_mode = st.radio("", ["Sign In", "Sign Up"], horizontal=True, key="sb_auth_mode", label_visibility="collapsed")
        _sb_email = st.text_input("Email", key="sb_email")
        _sb_pw = st.text_input("Password", type="password", key="sb_pw")
        if _auth_mode == "Sign In":
            if st.button("Sign In", key="sb_signin_btn"):
                try:
                    sign_in(_sb_email, _sb_pw)
                    st.rerun()
                except Exception as _e:
                    st.error(f"Sign in failed: {_e}")
        else:
            if st.button("Sign Up", key="sb_signup_btn"):
                try:
                    sign_up(_sb_email, _sb_pw)
                    st.success("Account created! Check your email to confirm.")
                except Exception as _e:
                    st.error(f"Sign up failed: {_e}")

# ====================== MY UNIVERSES SIDEBAR ======================
if is_logged_in():
    with st.sidebar.expander("💾 My Universes", expanded=False):
        _universes = list_universes()
        if _universes:
            _uni_map = {u["name"]: u["id"] for u in _universes}
            _sel_uni = st.selectbox("Saved universes", list(_uni_map.keys()), key="sb_uni_select")
            _lc, _dc = st.columns(2)
            with _lc:
                if st.button("Load", key="sb_uni_load", use_container_width=True):
                    _loaded = load_universe(_uni_map[_sel_uni])
                    if _loaded:
                        st.session_state["_import_pending"] = _loaded["params"]
                        st.rerun()
            with _dc:
                if st.button("Delete", key="sb_uni_delete", use_container_width=True):
                    delete_universe(_uni_map[_sel_uni])
                    st.rerun()
            st.markdown("---")
        _save_name = st.text_input(
            "Save current universe as",
            value=st.session_state.get("universe_name", ""),
            key="sb_uni_save_name",
        )
        if st.button("💾 Save", key="sb_uni_save", use_container_width=True):
            if _save_name.strip():
                _params = {k: v for k, v in st.session_state.items()
                           if k.startswith(_EXPORT_PREFIXES)}
                save_universe(_save_name.strip(), _params)
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
    energy = st.number_input(
        "Electron Power per Capita", value=6378, step=10, key="energy"
    )
    st.markdown(
        f"<p style='text-align:center;font-size:0.85em;color:#888;margin-top:-8px'>${energy:,.0f}</p>",
        unsafe_allow_html=True,
    )
    base_iq = st.number_input("Base IQ", value=100, step=1, key="base_iq")

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
_FOOTER = "© 2026 David Burkean • Sharing is caring • All Rights Reserved"
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
st.markdown(
    "<div style='display:flex;gap:6px;padding:2px 0 14px 0;font-size:14px;font-weight:600;'>"
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

footer = "© 2026 David Burkean • Sharing is caring • All Rights Reserved"
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
