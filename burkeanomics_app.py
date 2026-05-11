import streamlit as st
import plotly.express as px
import pandas as pd

st.set_page_config(page_title="Burkeanomics Simulator", layout="wide", initial_sidebar_state="expanded")

st.title("🧠 Burkeanomics Simulator")
_ver_col, _ref_col = st.columns([2, 3])
with _ver_col:
    st.markdown("<p style='font-size:14px; font-weight:600; color:#555; margin-top:8px;'>Burkeanomics Simulator d1.89</p>", unsafe_allow_html=True)
with _ref_col:
    with st.expander("References"):
        st.markdown(
            "• [Bcon 300 — Burkean Economics](https://www.bnation.us/econ-300-burkean-economics)  \n"
            "• [Bcon 301 — Particle Physics Model of Socionomic Systems](https://www.bnation.us/econ-301)  \n"
            "• [Bcon 302 — BrainPower Charts](https://www.bnation.us/302-bp-charts)"
        )

# ====================== DEFAULTS ======================
if "universe_name" not in st.session_state:
    st.session_state["universe_name"] = "Cal Energy Economy"

# ====================== RESET ======================
st.sidebar.header("⚙️ Parameters")
st.sidebar.checkbox("🌙 Dark Mode", key="dark_mode", value=False)
if st.sidebar.button("🔄 Reset Settings", help="Reset ALL settings to defaults"):
    for key in list(st.session_state.keys()):
        if key.startswith(("th_", "iq_", "b_", "p_", "pop_", "households", "energy", "base_iq", "top_execs", "ai_iq", "rpf_")):
            del st.session_state[key]
    st.rerun()

# ====================== SIDEBAR ======================

_ch = lambda t: st.markdown(f"<p style='text-align:center;font-size:0.8rem;font-weight:600;color:#888;margin:0 0 4px 0'>{t}</p>", unsafe_allow_html=True)

with st.sidebar.expander("**🌐 Constants**", expanded=False):
    st.caption("Anchors everything else derives from")
    households = st.number_input("California Households (Electrons)", 13970000, step=10000, key="households")
    energy = st.number_input("Per Capita Energy Spend ($)", 6378, step=10, key="energy")
    base_iq = st.number_input("Base IQ", 100, step=1, key="base_iq")
    st.caption("**Nucleon Relative Power Factors** — Center Power = Energy × RPF")
    rpf_cols = st.columns(3)
    with rpf_cols[0]:
        st.number_input("GovNukes", value=36667, step=100, key="rpf_g")
    with rpf_cols[1]:
        st.number_input("Providers", value=10000, step=100, key="rpf_p")
    with rpf_cols[2]:
        st.number_input("SinSayers", value=5000, step=100, key="rpf_s")

with st.sidebar.expander("**👥 Nucleons per Electron**", expanded=False):
    st.caption("Population structure per scenario")
    col_e = st.columns(3)
    with col_e[0]:
        _ch("cCon Left")
        st.number_input("GovNukes", 14, step=1, key="pop_g_c")
        st.number_input("Providers", 50, step=1, key="pop_p_c")
        st.number_input("SinSayers", 60, step=1, key="pop_s_c")
    with col_e[1]:
        _ch("Center")
        st.number_input("GovNukes", 13, step=1, key="pop_g_center")
        st.number_input("Providers", 40, step=1, key="pop_p_center")
        st.number_input("SinSayers", 50, step=1, key="pop_s_center")
    with col_e[2]:
        _ch("dCon Right")
        st.number_input("GovNukes", 8, step=1, key="pop_g_d")
        st.number_input("Providers", 55, step=1, key="pop_p_d")
        st.number_input("SinSayers", 15, step=1, key="pop_s_d")

with st.sidebar.expander("**🧬 Per Capita Nucleon Brains**", expanded=False):
    st.caption("Intelligence inputs per entity")
    st.markdown("**GovNukes**")
    gcols = st.columns(3)
    with gcols[0]:
        st.number_input("Top Execs", 10, step=1, key="top_execs_g_c")
        st.number_input("AI Enhanced IQ", 150, step=5, key="ai_iq_g_c")
    with gcols[1]:
        st.number_input("Top Execs", 10, step=1, key="top_execs_g_center")
        st.number_input("AI Enhanced IQ", 150, step=5, key="ai_iq_g_center")
    with gcols[2]:
        st.number_input("Top Execs", 10, step=1, key="top_execs_g_d")
        st.number_input("AI Enhanced IQ", 175, step=5, key="ai_iq_g_d")

    st.markdown("**Providers**")
    pcols = st.columns(3)
    with pcols[0]:
        st.number_input("Top Execs", 12, step=1, key="top_execs_p_c")
        st.number_input("AI Enhanced IQ", 150, step=5, key="ai_iq_p_c")
    with pcols[1]:
        st.number_input("Top Execs", 10, step=1, key="top_execs_p_center")
        st.number_input("AI Enhanced IQ", 225, step=5, key="ai_iq_p_center")
    with pcols[2]:
        st.number_input("Top Execs", 10, step=1, key="top_execs_p_d")
        st.number_input("AI Enhanced IQ", 394, step=5, key="ai_iq_p_d")

    st.markdown("**SinSayers**")
    scols = st.columns(3)
    with scols[0]:
        st.number_input("Top Execs", 10, step=1, key="top_execs_s_c")
        st.number_input("AI Enhanced IQ", 150, step=5, key="ai_iq_s_c")
    with scols[1]:
        st.number_input("Top Execs", 10, step=1, key="top_execs_s_center")
        st.number_input("AI Enhanced IQ", 150, step=5, key="ai_iq_s_center")
    with scols[2]:
        st.number_input("Top Execs", 10, step=1, key="top_execs_s_d")
        st.number_input("AI Enhanced IQ", 175, step=5, key="ai_iq_s_d")

with st.sidebar.expander("**📊 Per Capita Scaling**", expanded=False):
    st.caption("Multipliers applied to those inputs")
    st.markdown("<p style='text-align:center;font-weight:600;margin:4px 0'>Brains — IQ multiplier per class</p>", unsafe_allow_html=True)
    bq1, bq2, bq3 = st.columns(3)
    with bq1:
        _ch("cCon Left")
        st.number_input("Electrons", value=1.00, step=0.05, key="iq_e_c")
        st.number_input("GovNukes", value=1.00, step=0.05, key="iq_g_c")
        st.number_input("Providers", value=1.00, step=0.05, key="iq_p_c")
        st.number_input("SinSayers", value=1.00, step=0.05, key="iq_s_c")
    with bq2:
        _ch("Center")
        st.number_input("Electrons", value=1.00, step=0.05, key="iq_e_center")
        st.number_input("GovNukes", value=1.00, step=0.05, key="iq_g_center")
        st.number_input("Providers", value=1.00, step=0.05, key="iq_p_center")
        st.number_input("SinSayers", value=1.00, step=0.05, key="iq_s_center")
    with bq3:
        _ch("dCon Right")
        st.number_input("Electrons", value=1.00, step=0.05, key="iq_e_d")
        st.number_input("GovNukes", value=1.00, step=0.05, key="iq_g_d")
        st.number_input("Providers", value=1.00, step=0.05, key="iq_p_d")
        st.number_input("SinSayers", value=1.00, step=0.05, key="iq_s_d")

    st.markdown("<hr style='margin:12px 0 6px 0;border:none;border-top:1px solid #ddd;'><p style='text-align:center;font-weight:600;margin:0 0 4px 0'>Power — $ multiplier per class</p>", unsafe_allow_html=True)
    pw1, pw2, pw3 = st.columns(3)
    with pw1:
        _ch("cCon Left")
        st.number_input("Electrons", value=1.0, step=0.05, key="p_e_c")
        st.number_input("GovNukes", value=1.3, step=0.05, key="p_g_c")
        st.number_input("Providers", value=0.5, step=0.05, key="p_p_c")
        st.number_input("SinSayers", value=1.5, step=0.05, key="p_s_c")
    with pw2:
        _ch("Center")
        st.number_input("Electrons", value=1.0, step=0.05, key="p_e_center")
        st.number_input("GovNukes", value=1.0, step=0.05, key="p_g_center")
        st.number_input("Providers", value=1.0, step=0.05, key="p_p_center")
        st.number_input("SinSayers", value=1.0, step=0.05, key="p_s_center")
    with pw3:
        _ch("dCon Right")
        st.number_input("Electrons", value=1.0, step=0.05, key="p_e_d")
        st.number_input("GovNukes", value=0.55, step=0.05, key="p_g_d")
        st.number_input("Providers", value=0.8, step=0.05, key="p_p_d")
        st.number_input("SinSayers", value=0.9, step=0.05, key="p_s_d")

with st.sidebar.expander("**🏷️ Metadata**", expanded=False):
    st.text_input("Universe Name", placeholder="e.g. Cal Energy Economy", key="universe_name")

# ====================== CALCULATIONS ======================
def calculate_per_capita(scen: str):
    th = st.session_state.get("th_ccon" if "cCon" in scen else "th_center" if "Center" in scen else "th_dcon", 50) / 100
    suffix = "c" if "cCon" in scen else "center" if "Center" in scen else "d"
    base = st.session_state.get("base_iq", 100)
    energy = st.session_state.get("energy", 6378)
    rows = []

    # Electrons
    e_power = round(energy * st.session_state.get(f"p_e_{suffix}", 1.0))
    rows.append({"Class": "Electrons (unthrottled)", "IQ": base, "Power ($)": e_power})
    e_th_iq = round(base * (1 - th) * st.session_state.get(f"iq_e_{suffix}", 1.0))
    rows.append({"Class": "Electrons (throttled)", "IQ": e_th_iq, "Power ($)": e_power})

    # GovNukes — power anchored at energy × RPF, scaled per scenario
    g_iq = round(st.session_state.get(f"top_execs_g_{suffix}", 10) * st.session_state.get(f"ai_iq_g_{suffix}", 150) * st.session_state.get(f"iq_g_{suffix}", 1.0))
    g_power = round(energy * st.session_state.get("rpf_g", 36667) * st.session_state.get(f"p_g_{suffix}", 1.0))
    rows.append({"Class": "GovNukes", "IQ": g_iq, "Power ($)": g_power})

    # Providers
    p_iq = round(st.session_state.get(f"top_execs_p_{suffix}", 10) * st.session_state.get(f"ai_iq_p_{suffix}", 225) * st.session_state.get(f"iq_p_{suffix}", 1.0))
    p_power = round(energy * st.session_state.get("rpf_p", 10000) * st.session_state.get(f"p_p_{suffix}", 1.0))
    rows.append({"Class": "Providers", "IQ": p_iq, "Power ($)": p_power})

    # SinSayers
    s_iq = round(st.session_state.get(f"top_execs_s_{suffix}", 10) * st.session_state.get(f"ai_iq_s_{suffix}", 150) * st.session_state.get(f"iq_s_{suffix}", 1.0))
    s_power = round(energy * st.session_state.get("rpf_s", 5000) * st.session_state.get(f"p_s_{suffix}", 1.0))
    rows.append({"Class": "SinSayers", "IQ": s_iq, "Power ($)": s_power})

    return pd.DataFrame(rows)

def calculate_en_masse(scen: str):
    df_per = calculate_per_capita(scen)
    suffix = "c" if "cCon" in scen else "center" if "Center" in scen else "d"
    hh = st.session_state.get("households", 13970000)
    pop_g = st.session_state.get(f"pop_g_{suffix}", 13)
    pop_p = st.session_state.get(f"pop_p_{suffix}", 40)
    pop_s = st.session_state.get(f"pop_s_{suffix}", 50)
    pop_map = {
        "Electrons (unthrottled)": hh,
        "Electrons (throttled)": hh,
        "GovNukes": pop_g,
        "Providers": pop_p,
        "SinSayers": pop_s,
    }
    rows = []
    for _, r in df_per.iterrows():
        cls = r["Class"]
        population = pop_map.get(cls, hh)
        if "unthrottled" in cls:
            total_iq = st.session_state.get("base_iq", 100) * population
        else:
            total_iq = r["IQ"] * population
        total_power = r["Power ($)"] * population
        rows.append({"Class": cls, "Total IQ": total_iq, "Power (Billions)": round(total_power / 1e9)})
    return pd.DataFrame(rows)

def calculate_breakdown(scen: str):
    suffix = "c" if "cCon" in scen else "center" if "Center" in scen else "d"
    per = calculate_per_capita(scen).set_index("Class")
    hh    = st.session_state.get("households", 13970000)
    pop_g = st.session_state.get(f"pop_g_{suffix}", 13)
    pop_p = st.session_state.get(f"pop_p_{suffix}", 40)
    pop_s = st.session_state.get(f"pop_s_{suffix}", 50)
    def tbp(pop, cls):
        return round(pop * per.loc[cls, "IQ"] * per.loc[cls, "Power ($)"] / 1e12, 1)
    data = [
        {"Class": "Electrons", "tBP": tbp(hh,    "Electrons (throttled)")},
        {"Class": "GovNukes",  "tBP": tbp(pop_g, "GovNukes")},
        {"Class": "Providers", "tBP": tbp(pop_p, "Providers")},
        {"Class": "SinSayers", "tBP": tbp(pop_s, "SinSayers")},
    ]
    df = pd.DataFrame(data)
    return df, round(df["tBP"].sum(), 1)

# ====================== DASH ======================
SCENARIOS = [("cCon (Left)", "Left"), ("Center", "Center"), ("dCon (Right)", "Right")]

# ====================== CHARTS ======================
_FOOTER = "© 2026 David Burkean • All Rights Reserved • Credited Sharing Encouraged"
_FOOTER_ANNOTATION = dict(
    text=_FOOTER, xref="paper", yref="paper", x=0.5, y=-0.28,
    showarrow=False, font=dict(size=10, color="#666"), align="center"
)

_universe = st.session_state.get("universe_name", "").strip()
st.header(f"Health & Wealth of the {_universe}" if _universe else "Health & Wealth of the [Universe]")
st.markdown("<style>section[data-testid='stMain'] details summary p { font-weight:600; font-size:0.95rem; } section[data-testid='stSidebar'] div[data-testid='stNumberInput'] label { text-align:center; display:block; width:100%; }</style>", unsafe_allow_html=True)

with st.expander("Electron Throttles", expanded=True):
    st.markdown("<style>div.stSlider > label { display:block; text-align:center; width:100%; }</style>", unsafe_allow_html=True)
    _et_l, _et_c, _et_r = st.columns(3)
    with _et_l:
        st.slider("Left · cCon", 0, 100, 75, 1, format="%d%%", key="th_ccon")
    with _et_c:
        st.slider("Center", 0, 100, 50, 1, format="%d%%", key="th_center")
    with _et_r:
        st.slider("Right · dCon", 0, 100, 25, 1, format="%d%%", key="th_dcon")

compare_df = pd.DataFrame([
    {"Scenario": label, "Total tBP (Trillions Smart $)": calculate_breakdown(scen)[1]}
    for scen, label in SCENARIOS
])
_totals = compare_df["Total tBP (Trillions Smart $)"]
_lv, _cv, _rv = list(_totals)
_pct_lc = round((_cv - _lv) / _lv * 100)
_pct_cr = round((_rv - _cv) / _cv * 100)
_pct_lr = round((_rv - _lv) / _lv * 100)
_ac = "#cc2200"

# Theme-aware colors — driven by sidebar toggle
_is_dark = st.session_state.get("dark_mode", False)
_val_color  = "white" if _is_dark else "black"    # bar total labels
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
_th_c   = st.session_state.get("th_ccon",   75) / 100
_th_ctr = st.session_state.get("th_center", 50) / 100
_th_d   = st.session_state.get("th_dcon",   25) / 100

def _case_hdr(th, is_dcon=False):
    pct = round(th * 100)
    code = f"D{pct}" if is_dcon else f"C{100 - pct}"
    qual = "Massive cCon" if th >= 0.76 else "Strong cCon" if th >= 0.6 else "Moderate cCon" if th >= 0.4 else "Minimal cCon"
    return f"<b>{code}: {pct}% cCon</b><br>{qual}"

_case_hdrs = [_case_hdr(_th_c), _case_hdr(_th_ctr), _case_hdr(_th_d, True)]
_tick_labels = ["Left<br>cCon", "Center", "Right<br>dCon"]
_xaxis_cfg = dict(title="", ticktext=_tick_labels, tickvals=["Left", "Center", "Right"])

fig_main = px.bar(compare_df, x="Scenario", y="Total tBP (Trillions Smart $)",
                  color="Scenario", color_discrete_map={"Left": "#1f77b4", "Center": "#888888", "Right": "#d62728"})
fig_main.update_traces(texttemplate="")   # labels via annotations for dark-mode safety
fig_main.update_layout(height=520, bargap=0.25, showlegend=False,
                       xaxis=_xaxis_cfg, yaxis=dict(range=[_y_min, _y_max]),
                       margin=dict(b=160, t=90))

# Bar value labels — no box, theme-aware color
for label_col, total in zip(["Left", "Center", "Right"], list(_totals)):
    fig_main.add_annotation(x=label_col, y=total, xref="x", yref="y",
        text=f"<b>S${total:.1f}T</b>", showarrow=False,
        yanchor="bottom", yshift=6, font=dict(size=15, color=_val_color))

# Case description headers above plot area
for (_, label), hdr in zip(SCENARIOS, _case_hdrs):
    fig_main.add_annotation(x=label, y=1.03, xref="x", yref="paper",
        text=hdr, showarrow=False, yanchor="bottom",
        font=dict(size=11, color=_desc_color), align="center")

# Growth arcs — cubic bezier (C) with control points close to endpoints → steep entry/exit
def _add_arc(fig, x0, y0, x1, y1, peak, cx_inset, pct_label, label_x, ac):
    fig.add_shape(type="path",
        path=f"M {x0},{y0} C {x0+cx_inset},{peak} {x1-cx_inset},{peak} {x1},{y1}",
        xref="x", yref="y", line=dict(color=ac, width=2))
    ax = (x1 - cx_inset) * 0.15 + x1 * 0.85
    ay = peak * 0.15 + y1 * 0.85
    fig.add_annotation(x=x1, y=y1, ax=ax, ay=ay,
        xref="x", yref="y", axref="x", ayref="y",
        text="", showarrow=True, arrowhead=2, arrowwidth=2, arrowcolor=ac)
    fig.add_annotation(x=label_x, y=peak, xref="x", yref="y",
        text=f"<b>+{pct_label}%</b>", showarrow=False,
        font=dict(color=ac, size=13), yanchor="top", yshift=-10)

_add_arc(fig_main, 0, _lv_y, 1, _cv_y, _peak_lc, 0.12, _pct_lc, 0.5, _ac)
_add_arc(fig_main, 1, _cv_y, 2, _rv_y, _peak_cr, 0.12, _pct_cr, 1.7, _ac)
_add_arc(fig_main, 0, _lv_y, 2, _rv_y, _peak_lr, 0.18, _pct_lr, 1.0, _ac)

fig_main.add_annotation(**_FOOTER_ANNOTATION)
with st.expander("Total BrainPower", expanded=True):
    st.plotly_chart(fig_main, use_container_width=True)

stack_data = []
for scen, label in SCENARIOS:
    df, _ = calculate_breakdown(scen)
    for _, row in df.iterrows():
        stack_data.append({"Scenario": label, "Class": row["Class"], "tBP": row["tBP"], "Label": row["Class"]})
stack_df = pd.DataFrame(stack_data)
_y_max_stack = round(max(_totals) + 3)
fig_stacked = px.bar(stack_df, x="Scenario", y="tBP", color="Class", text="Label",
                     category_orders={"Class": ["SinSayers", "GovNukes", "Providers", "Electrons"]},
                     color_discrete_sequence=["#8B0000", "#FFD700", "#228B22", "#00008B"])
fig_stacked.update_traces(texttemplate="%{text}<br>S$%{y:.1f}T", textposition="inside",
                          textfont=dict(size=12, color="white", weight="bold"))
for trace in fig_stacked.data:
    if trace.name == "GovNukes":
        trace.textfont.color = "#8B0000"
    if trace.name in ["GovNukes", "Providers", "SinSayers"]:
        _nuke_bg = {"GovNukes": "#FFD700", "Providers": "#228B22", "SinSayers": "#8B0000"}
        trace.marker.pattern.shape = "x"
        trace.marker.pattern.bgcolor = _nuke_bg[trace.name]
        trace.marker.pattern.fgcolor = "rgba(0,0,0,0.12)" if trace.name == "GovNukes" else "rgba(255,255,255,0.32)"
        trace.marker.pattern.size = 8
fig_stacked.update_layout(height=520, barmode="stack", showlegend=False,
                          uniformtext=dict(minsize=8, mode="hide"),
                          xaxis=_xaxis_cfg, yaxis=dict(range=[0, _y_max_stack]),
                          margin=dict(b=160, t=90))
for _, (scen, label) in enumerate(SCENARIOS):
    _, total = calculate_breakdown(scen)
    fig_stacked.add_annotation(x=label, y=total, xref="x", yref="y",
        text=f"<b>S${total:.1f}T</b>", showarrow=False,
        yanchor="bottom", yshift=6, font=dict(size=15, color=_val_color), align="center")
for (_, label), hdr in zip(SCENARIOS, _case_hdrs):
    fig_stacked.add_annotation(x=label, y=1.03, xref="x", yref="paper",
        text=hdr, showarrow=False, yanchor="bottom",
        font=dict(size=11, color=_desc_color), align="center")
fig_stacked.add_annotation(**_FOOTER_ANNOTATION)
with st.expander("BrainPower by Class", expanded=True):
    st.plotly_chart(fig_stacked, use_container_width=True)

# ====================== TABLES ======================
with st.expander("Per Capita Brains & Power", expanded=False):
    col_l, col_c, col_r = st.columns(3)
    for col, (scen, label) in zip([col_l, col_c, col_r], SCENARIOS):
        with col:
            st.markdown(f"**{label}**")
            df = calculate_per_capita(scen)
            st.dataframe(
                df.style.format({"IQ": "{:,.0f}", "Power ($)": "${:,.0f}"})
                     .set_properties(**{"text-align": "right"}),
                use_container_width=True,
                hide_index=True
            )

with st.expander("En Masse Brains & Power", expanded=False):
    col_l, col_c, col_r = st.columns(3)
    for col, (scen, label) in zip([col_l, col_c, col_r], SCENARIOS):
        with col:
            st.markdown(f"**{label}**")
            dfm = calculate_en_masse(scen)
            def safe_format(x):
                return f"{x:,.0f}" if isinstance(x, (int, float)) else x
            styled = dfm.style.format({"Total IQ": safe_format, "Power (Billions)": "${:,.0f}"})
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
                df_display.style.format({"BrainPower (T$)": "{:.1f}"})
                    .set_properties(**{"text-align": "right"}),
                use_container_width=True,
                hide_index=True
            )

footer = "© 2026 David Burkean • All Rights Reserved • Credited Sharing Encouraged"
st.markdown(f"<div style='text-align: center; color: #666; padding: 20px 0; font-size: 0.9em; border-top: 1px solid #ddd;'>{footer}</div>", unsafe_allow_html=True)