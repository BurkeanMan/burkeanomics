# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the app
streamlit run burkeanomics_app.py
```

## Architecture

This is a single-file Streamlit app (`burkeanomics_app.py`). All UI, state, and computation live in one file with no external modules.

**Conceptual model:** Three political scenarios ("cCon Left", "Center", "dCon Right") are compared across four social classes ("Electrons", "GovNukes", "Providers", "SinSayers"). Each scenario/class combination has configurable parameters controlling IQ multipliers, power scaling, population ratios, and throttling factors. All parameters are stored in `st.session_state` with prefixed keys (e.g. `th_ccon`, `iq_e_c`, `b_p_d`).

**Key suffix conventions used throughout the calculation functions:**
- Scenario suffix: `c` = cCon Left, `center` = Center, `d` = dCon Right
- Class prefix: `e` = Electrons, `g` = GovNukes, `p` = Providers, `s` = SinSayers

**Three calculation functions** each take a `scen` string and return a DataFrame:
- `calculate_per_capita(scen)` — IQ and energy spend per individual
- `calculate_en_masse(scen)` — per-capita values scaled by total California households
- `calculate_breakdown(scen)` — Total BrainPower (tBP) in trillions per class, using hardcoded base values per scenario

**Dashboard sections** (rendered in order):
1. Per Capita Brains & Power table (3-column layout, one per scenario)
2. En Masse Brains & Power table (same layout)
3. Grouped bar chart: total tBP per scenario
4. Stacked bar chart: tBP broken down by class per scenario
