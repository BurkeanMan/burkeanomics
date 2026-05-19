import streamlit as st
import pandas as pd


def calculate_per_capita(scen: str):
    th = (
        st.session_state.get(
            (
                "th_ccon"
                if "cCon" in scen
                else "th_center" if "Center" in scen else "th_dcon"
            ),
            50,
        )
        / 100
    )
    suffix = "c" if "cCon" in scen else "center" if "Center" in scen else "d"
    base = st.session_state.get("base_iq", 100)
    energy = st.session_state.get("energy", 6378)
    rows = []

    # Electrons — power always equals Per Capita Electron Power
    rows.append({"Class": "Electrons (unthrottled)", "IQ": base, "Power ($)": energy})
    rows.append(
        {
            "Class": "Electrons (throttled)",
            "IQ": round(base * (1 - th)),
            "Power ($)": energy,
        }
    )

    def _nuc_iq(cls, default_te, default_ai):
        te_c = st.session_state.get(f"top_execs_{cls}_center", default_te)
        ai_c = st.session_state.get(f"ai_iq_{cls}_center", default_ai)
        if suffix == "center":
            return round(te_c * ai_c)
        return round(
            te_c
            * st.session_state.get(f"te_factor_{cls}_{suffix}", 1.0)
            * ai_c
            * st.session_state.get(f"ai_factor_{cls}_{suffix}", 1.0)
        )

    # GovNukes
    g_iq = _nuc_iq("g", 10, 150)
    g_power = round(
        energy
        * st.session_state.get("rpf_g", 36667)
        * st.session_state.get(f"p_g_{suffix}", 1.0)
    )
    rows.append({"Class": "GovNukes", "IQ": g_iq, "Power ($)": g_power})

    # Providers
    p_iq = _nuc_iq("p", 10, 225)
    p_power = round(
        energy
        * st.session_state.get("rpf_p", 10000)
        * st.session_state.get(f"p_p_{suffix}", 1.0)
    )
    rows.append({"Class": "Providers", "IQ": p_iq, "Power ($)": p_power})

    # SinSayers
    s_iq = _nuc_iq("s", 10, 150)
    s_power = round(
        energy
        * st.session_state.get("rpf_s", 5000)
        * st.session_state.get(f"p_s_{suffix}", 1.0)
    )
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
        rows.append(
            {
                "Class": cls,
                "Total IQ": total_iq,
                "Power (Billions)": round(total_power / 1e9),
            }
        )
    return pd.DataFrame(rows)


def calculate_breakdown(scen: str):
    suffix = "c" if "cCon" in scen else "center" if "Center" in scen else "d"
    per = calculate_per_capita(scen).set_index("Class")
    hh = st.session_state.get("households", 13970000)
    pop_g = st.session_state.get(f"pop_g_{suffix}", 13)
    pop_p = st.session_state.get(f"pop_p_{suffix}", 40)
    pop_s = st.session_state.get(f"pop_s_{suffix}", 50)

    def tbp(pop, cls):
        return round(pop * per.loc[cls, "IQ"] * per.loc[cls, "Power ($)"] / 1e12, 1)

    data = [
        {"Class": "Electrons", "tBP": tbp(hh, "Electrons (throttled)")},
        {"Class": "GovNukes", "tBP": tbp(pop_g, "GovNukes")},
        {"Class": "Providers", "tBP": tbp(pop_p, "Providers")},
        {"Class": "SinSayers", "tBP": tbp(pop_s, "SinSayers")},
    ]
    df = pd.DataFrame(data)
    return df, round(df["tBP"].sum(), 1)
