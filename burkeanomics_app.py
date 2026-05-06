import streamlit as st
import plotly.express as px
import pandas as pd

st.set_page_config(page_title="Burkeanomics Calculator", layout="wide", initial_sidebar_state="expanded")

st.title("🧠 Burkeanomics Calculator")
st.caption("Burkeanomics Calculator **d1.70** | All Settings Visible + Dynamic | Based on 302 charts")

# ====================== RESET ======================
st.sidebar.header("⚙️ Settings")
if st.sidebar.button("🔄 Reset Settings", help="Reset ALL settings to defaults"):
    for key in list(st.session_state.keys()):
        if key.startswith(("th_", "iq_", "b_", "p_", "pop_", "households", "energy", "base_iq", "top_execs", "ai_iq")):
            del st.session_state[key]
    st.rerun()

# ====================== SIDEBAR ======================
with st.sidebar.expander("**📉 Electron Throttling Factor**", expanded=False):
    col = st.columns(3)
    with col[0]:
        st.caption("**cCon Left**")
        st.slider(" ", 0.0, 1.0, 0.75, 0.01, key="th_ccon")
    with col[1]:
        st.caption("**Center**")
        st.slider(" ", 0.0, 1.0, 0.50, 0.01, key="th_center")
    with col[2]:
        st.caption("**dCon Right**")
        st.slider(" ", 0.0, 1.0, 0.25, 0.01, key="th_dcon")

with st.sidebar.expander("**🧠 Class IQ Multipliers**", expanded=False):
    col_iq = st.columns(3)
    with col_iq[0]:
        st.caption("**cCon Left**")
        st.number_input("Electrons", value=1.00, step=0.05, key="iq_e_c")
        st.number_input("GovNukes", value=1.00, step=0.05, key="iq_g_c")
        st.number_input("Providers", value=1.00, step=0.05, key="iq_p_c")
        st.number_input("SinSayers", value=1.00, step=0.05, key="iq_s_c")
    with col_iq[1]:
        st.caption("**Center**")
        st.number_input("Electrons", value=1.00, step=0.05, key="iq_e_center")
        st.number_input("GovNukes", value=1.00, step=0.05, key="iq_g_center")
        st.number_input("Providers", value=1.00, step=0.05, key="iq_p_center")
        st.number_input("SinSayers", value=1.00, step=0.05, key="iq_s_center")
    with col_iq[2]:
        st.caption("**dCon Right**")
        st.number_input("Electrons", value=1.00, step=0.05, key="iq_e_d")
        st.number_input("GovNukes", value=1.00, step=0.05, key="iq_g_d")
        st.number_input("Providers", value=1.00, step=0.05, key="iq_p_d")
        st.number_input("SinSayers", value=1.00, step=0.05, key="iq_s_d")

with st.sidebar.expander("**📊 Per Capita Scaling Factors**", expanded=False):
    st.subheader("Brains")
    c1, c2 = st.columns(2)
    with c1:
        st.caption("**cCon Left**")
        st.number_input("Electrons", value=1.0, step=0.05, key="b_e_c")
        st.number_input("GovNukes", value=1.0, step=0.05, key="b_g_c")
        st.number_input("Providers", value=0.8, step=0.05, key="b_p_c")
        st.number_input("SinSayers", value=1.0, step=0.05, key="b_s_c")
    with c2:
        st.caption("**dCon Right**")
        st.number_input("Electrons", value=1.0, step=0.05, key="b_e_d")
        st.number_input("GovNukes", value=1.0, step=0.05, key="b_g_d")
        st.number_input("Providers", value=1.5, step=0.05, key="b_p_d")
        st.number_input("SinSayers", value=1.0, step=0.05, key="b_s_d")
    st.subheader("Power")
    p1, p2 = st.columns(2)
    with p1:
        st.caption("**cCon Left**")
        st.number_input("Electrons", value=1.0, step=0.05, key="p_e_c")
        st.number_input("GovNukes", value=1.3, step=0.05, key="p_g_c")
        st.number_input("Providers", value=0.5, step=0.05, key="p_p_c")
        st.number_input("SinSayers", value=1.5, step=0.05, key="p_s_c")
    with p2:
        st.caption("**dCon Right**")
        st.number_input("Electrons", value=1.0, step=0.05, key="p_e_d")
        st.number_input("GovNukes", value=0.5, step=0.05, key="p_g_d")
        st.number_input("Providers", value=0.8, step=0.05, key="p_p_d")
        st.number_input("SinSayers", value=0.9, step=0.05, key="p_s_d")

with st.sidebar.expander("**🧠 Nucleon Brains**", expanded=False):
    st.caption("Top Execs & AI Enhanced IQ per Entity")
    st.markdown("**GovNukes**")
    gcols = st.columns(3)
    with gcols[0]:
        st.number_input("Top Execs per", 10, step=1, key="top_execs_g_c")
        st.number_input("AI Enhanced IQ per Exec", 150, step=5, key="ai_iq_g_c")
    with gcols[1]:
        st.number_input("Top Execs per", 10, step=1, key="top_execs_g_center")
        st.number_input("AI Enhanced IQ per Exec", 150, step=5, key="ai_iq_g_center")
    with gcols[2]:
        st.number_input("Top Execs per", 10, step=1, key="top_execs_g_d")
        st.number_input("AI Enhanced IQ per Exec", 175, step=5, key="ai_iq_g_d")
    
    st.markdown("**Providers**")
    pcols = st.columns(3)
    with pcols[0]:
        st.number_input("Top Execs per", 12, step=1, key="top_execs_p_c")
        st.number_input("AI Enhanced IQ per Exec", 150, step=5, key="ai_iq_p_c")
    with pcols[1]:
        st.number_input("Top Execs per", 10, step=1, key="top_execs_p_center")
        st.number_input("AI Enhanced IQ per Exec", 225, step=5, key="ai_iq_p_center")
    with pcols[2]:
        st.number_input("Top Execs per", 10, step=1, key="top_execs_p_d")
        st.number_input("AI Enhanced IQ per Exec", 394, step=5, key="ai_iq_p_d")
    
    st.markdown("**SinSayers**")
    scols = st.columns(3)
    with scols[0]:
        st.number_input("Top Execs per", 10, step=1, key="top_execs_s_c")
        st.number_input("AI Enhanced IQ per Exec", 150, step=5, key="ai_iq_s_c")
    with scols[1]:
        st.number_input("Top Execs per", 10, step=1, key="top_execs_s_center")
        st.number_input("AI Enhanced IQ per Exec", 150, step=5, key="ai_iq_s_center")
    with scols[2]:
        st.number_input("Top Execs per", 10, step=1, key="top_execs_s_d")
        st.number_input("AI Enhanced IQ per Exec", 175, step=5, key="ai_iq_s_d")

with st.sidebar.expander("**👥 Nucleons per Electron**", expanded=False):
    col_e = st.columns(3)
    with col_e[0]:
        st.caption("**cCon Left**")
        st.number_input("GovNukes", 14, step=1, key="pop_g_c")
        st.number_input("Providers", 50, step=1, key="pop_p_c")
        st.number_input("SinSayers", 60, step=1, key="pop_s_c")
    with col_e[1]:
        st.caption("**Center**")
        st.number_input("GovNukes", 13, step=1, key="pop_g_center")
        st.number_input("Providers", 40, step=1, key="pop_p_center")
        st.number_input("SinSayers", 50, step=1, key="pop_s_center")
    with col_e[2]:
        st.caption("**dCon Right**")
        st.number_input("GovNukes", 8, step=1, key="pop_g_d")
        st.number_input("Providers", 55, step=1, key="pop_p_d")
        st.number_input("SinSayers", 15, step=1, key="pop_s_d")

with st.sidebar.expander("**🌐 Constants**", expanded=True):
    households = st.number_input("California Households (Electrons)", 13970000, step=10000, key="households")
    energy = st.number_input("Per Capita Energy Spend ($)", 6378, step=10, key="energy")
    base_iq = st.number_input("Base IQ", 100, step=1, key="base_iq")

# ====================== CALCULATIONS ======================
def calculate_per_capita(scen: str):
    th = st.session_state.get("th_ccon" if "cCon" in scen else "th_center" if "Center" in scen else "th_dcon", 0.5)
    suffix = "c" if "cCon" in scen else "center" if "Center" in scen else "d"
    base = st.session_state.get("base_iq", 100)
    rows = []
    
    # Un-throttled Electrons
    e_un_iq = base
    e_power = round(st.session_state.get("energy", 6378) * st.session_state.get(f"p_e_{suffix if suffix != 'center' else 'center'}", 1.0))
    rows.append({"Class": "Electrons (unthrottled)", "IQ": e_un_iq, "Power ($)": e_power})
    
    # Throttled Electrons
    e_mult = st.session_state.get(f"iq_e_{suffix if suffix != 'center' else 'center'}", 1.0)
    e_th_iq = round(base * (1 - th) * e_mult)
    rows.append({"Class": "Electrons (throttled)", "IQ": e_th_iq, "Power ($)": e_power})
    
    # GovNukes
    g_top = st.session_state.get(f"top_execs_g_{suffix}", 10)
    g_ai = st.session_state.get(f"ai_iq_g_{suffix}", 150)
    g_iq = g_top * g_ai
    g_power_base = 233860000 if "dCon" not in scen else 127560000
    g_power = round(g_power_base * st.session_state.get(f"p_g_{suffix if suffix != 'center' else 'center'}", 1.0))
    rows.append({"Class": "GovNukes", "IQ": g_iq, "Power ($)": g_power})
    
    # Providers
    p_top = st.session_state.get(f"top_execs_p_{suffix}", 10)
    p_ai = st.session_state.get(f"ai_iq_p_{suffix}", 225)
    p_iq = p_top * p_ai
    p_power_base = 63780000 if "dCon" not in scen else 51024000
    p_power = round(p_power_base * st.session_state.get(f"p_p_{suffix if suffix != 'center' else 'center'}", 1.0))
    rows.append({"Class": "Providers", "IQ": p_iq, "Power ($)": p_power})
    
    # SinSayers
    s_top = st.session_state.get(f"top_execs_s_{suffix}", 10)
    s_ai = st.session_state.get(f"ai_iq_s_{suffix}", 150)
    s_iq = s_top * s_ai
    s_power_base = 31890000 if "dCon" not in scen else 28701000
    s_power = round(s_power_base * st.session_state.get(f"p_s_{suffix if suffix != 'center' else 'center'}", 1.0))
    rows.append({"Class": "SinSayers", "IQ": s_iq, "Power ($)": s_power})
    
    return pd.DataFrame(rows)

def calculate_en_masse(scen: str):
    df_per = calculate_per_capita(scen)
    hh = st.session_state.get("households", 13970000)
    rows = []
    for _, r in df_per.iterrows():
        if "unthrottled" in r["Class"]:
            total_iq = st.session_state.get("base_iq", 100) * hh
        else:
            total_iq = r["IQ"] * hh   # throttled uses throttled IQ
        total_power = r["Power ($)"] * hh
        rows.append({"Class": r["Class"], "Total IQ": total_iq, "Power (Billions)": round(total_power / 1e9)})
    return pd.DataFrame(rows)

def calculate_breakdown(scen: str):
    th = st.session_state.get("th_ccon" if "cCon" in scen else "th_center" if "Center" in scen else "th_dcon", 0.5)
    suffix = "c" if "cCon" in scen else "center" if "Center" in scen else "d"
    data = []
    base_iq_val = st.session_state.get("base_iq", 100)
    
    electron_iq_multiplier = st.session_state.get(f"iq_e_{suffix if suffix != 'center' else 'center'}", 1.0)
    electron_effective_iq = base_iq_val * (1 - th) * electron_iq_multiplier
    electron_brains_scale = st.session_state.get(f"b_e_{suffix if suffix != 'center' else 'center'}", 1.0)
    electron_power_scale = st.session_state.get(f"p_e_{suffix if suffix != 'center' else 'center'}", 1.0)
    tbp_electrons = st.session_state.get("households", 13970000) * electron_effective_iq * st.session_state.get("energy", 6378) * electron_brains_scale * electron_power_scale / 1e12
    data.append({"Class": "Electrons", "tBP": round(tbp_electrons, 1)})
    
    govnuke_population_per_electron = st.session_state.get(f"pop_g_{suffix}", 13)
    govnuke_iq_multiplier = st.session_state.get(f"iq_g_{suffix if suffix != 'center' else 'center'}", 1.0)
    govnuke_effective_iq = base_iq_val * govnuke_iq_multiplier
    govnuke_brains_scale = st.session_state.get(f"b_g_{suffix if suffix != 'center' else 'center'}", 1.0)
    govnuke_power_scale = st.session_state.get(f"p_g_{suffix if suffix != 'center' else 'center'}", 1.0)
    govnuke_base = 4428571429 if "cCon" in scen else 3307692308 if "Center" in scen else 2125000000
    tbp_g = govnuke_population_per_electron * govnuke_effective_iq * govnuke_base * govnuke_brains_scale * govnuke_power_scale / 1e12
    data.append({"Class": "GovNukes", "tBP": round(tbp_g, 1)})
    
    provider_population_per_electron = st.session_state.get(f"pop_p_{suffix}", 40)
    provider_iq_multiplier = st.session_state.get(f"iq_p_{suffix if suffix != 'center' else 'center'}", 1.0)
    provider_effective_iq = base_iq_val * provider_iq_multiplier
    provider_brains_scale = st.session_state.get(f"b_p_{suffix if suffix != 'center' else 'center'}", 1.0)
    provider_power_scale = st.session_state.get(f"p_p_{suffix if suffix != 'center' else 'center'}", 1.0)
    provider_base = 580000000 if "cCon" in scen else 1425000000 if "Center" in scen else 2000000000
    tbp_p = provider_population_per_electron * provider_effective_iq * provider_base * provider_brains_scale * provider_power_scale / 1e12
    data.append({"Class": "Providers", "tBP": round(tbp_p, 1)})
    
    sinsayer_population_per_electron = st.session_state.get(f"pop_s_{suffix}", 50)
    sinsayer_iq_multiplier = st.session_state.get(f"iq_s_{suffix if suffix != 'center' else 'center'}", 1.0)
    sinsayer_effective_iq = base_iq_val * sinsayer_iq_multiplier
    sinsayer_brains_scale = st.session_state.get(f"b_s_{suffix if suffix != 'center' else 'center'}", 1.0)
    sinsayer_power_scale = st.session_state.get(f"p_s_{suffix if suffix != 'center' else 'center'}", 1.0)
    sinsayer_base = 716666667 if "cCon" in scen else 480000000 if "Center" in scen else 533333333
    tbp_s = sinsayer_population_per_electron * sinsayer_effective_iq * sinsayer_base * sinsayer_brains_scale * sinsayer_power_scale / 1e12
    data.append({"Class": "SinSayers", "tBP": round(tbp_s, 1)})
    
    df = pd.DataFrame(data)
    return df, round(df["tBP"].sum(), 1)

# ====================== DASH ======================
st.subheader("Per Capita Brains & Power")
col_l, col_c, col_r = st.columns(3)
for col, scen in zip([col_l, col_c, col_r], ["cCon (Left)", "Center", "dCon (Right)"]):
    with col:
        st.markdown(f"**{scen}**")
        df = calculate_per_capita(scen)
        st.dataframe(
            df.style.format({"IQ": "{:,.0f}", "Power ($)": "${:,.0f}"})
                 .set_properties(**{"text-align": "right"}),
            use_container_width=True,
            hide_index=True
        )

st.subheader("En Masse Brains & Power")
col_l, col_c, col_r = st.columns(3)
for col, scen in zip([col_l, col_c, col_r], ["cCon (Left)", "Center", "dCon (Right)"]):
    with col:
        st.markdown(f"**{scen}**")
        dfm = calculate_en_masse(scen)
        def safe_format(x):
            return f"{x:,.0f}" if isinstance(x, (int, float)) else x
        styled = dfm.style.format({"Total IQ": safe_format, "Power (Billions)": "${:,.0f}"})
        styled = styled.set_properties(**{"text-align": "right"})
        st.dataframe(styled, use_container_width=True, hide_index=True)

# ====================== CHARTS ======================
st.subheader("Total BrainPower by Scenario: cCon • Center • dCon")
scenarios = ["cCon (Left)", "Center", "dCon (Right)"]
compare_df = pd.DataFrame([{"Scenario": s, "Total tBP (Trillions Smart $)": calculate_breakdown(s)[1]} for s in scenarios])

fig_main = px.bar(compare_df, x="Scenario", y="Total tBP (Trillions Smart $)",
                  color="Scenario", color_discrete_map={"cCon (Left)": "#1f77b4", "Center": "#87ceeb", "dCon (Right)": "#d62728"})
fig_main.update_traces(texttemplate="%{y:.1f}T", textposition="outside", textfont=dict(size=16, color="black", weight="bold"))
fig_main.add_hline(y=15, line_dash="dash", line_color="gold", annotation_text="15T X", annotation_position="top right")
fig_main.update_layout(height=520, bargap=0.25, showlegend=False, yaxis=dict(range=[15, 25]), margin=dict(b=160))
st.plotly_chart(fig_main, use_container_width=True)

stack_data = []
for scen in scenarios:
    df, _ = calculate_breakdown(scen)
    for _, row in df.iterrows():
        stack_data.append({"Scenario": scen, "Class": row["Class"], "tBP": row["tBP"]})
stack_df = pd.DataFrame(stack_data)
fig_stacked = px.bar(stack_df, x="Scenario", y="tBP", color="Class",
                     category_orders={"Class": ["SinSayers", "GovNukes", "Providers", "Electrons"]},
                     color_discrete_sequence=["#8B0000", "#FFD700", "#228B22", "#00008B"])
fig_stacked.update_traces(texttemplate="%{y:.1f}", textposition="inside", textfont=dict(size=13, color="white", weight="bold"))
fig_stacked.update_layout(height=520, barmode='stack', legend=dict(orientation="h", y=1.02, x=0.5, xanchor="center", title="Class"), margin=dict(b=160))
for i, scen in enumerate(scenarios):
    _, total = calculate_breakdown(scen)
    fig_stacked.add_annotation(x=i, y=total + 0.6, text=f"<b>{total:.1f}T</b>", showarrow=False,
                               font=dict(size=15, color="black", weight="bold"), align="center")
st.plotly_chart(fig_stacked, use_container_width=True)

footer = "© 2026 David Burkean • All Rights Reserved • Credited Sharing Encouraged"
st.markdown(f"<div style='text-align: center; color: #666; padding: 20px 0; font-size: 0.9em; border-top: 1px solid #ddd;'>{footer}</div>", unsafe_allow_html=True)