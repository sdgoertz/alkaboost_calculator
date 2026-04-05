import streamlit as st
import pandas as pd

st.set_page_config(page_title="AlkaBoost™ CIP Savings Calculator", layout="wide")
st.title("AlkaBoost™ CIP Additive Cost-Savings Calculator")
st.caption("Built from the official TDS • Emphasizes caustic reduction • Imperial ↔ Metric toggle")

# ====================== SIDEBAR INPUTS ======================
with st.sidebar:
    st.header("📋 Plant & Units")
    units = st.radio("Units System", ["Imperial (lb, gal, °F, USD)", "Metric (kg, L, °C, USD)"], horizontal=True)

    is_imperial = units.startswith("Imperial")
    density_factor = 8.34 if is_imperial else 1.0          # lb/gal or kg/L approx for dilute solutions
    vol_unit = "gal" if is_imperial else "L"
    mass_unit = "lb" if is_imperial else "kg"
    temp_unit = "°F" if is_imperial else "°C"

    st.subheader("Production Data")
    cycles_per_year = st.number_input("CIP cycles per year", value=365*2, min_value=1, step=1)
    solution_volume = st.number_input(f"Cleaning solution volume per CIP ({vol_unit})", value=5000.0, min_value=100.0)

    st.subheader("Caustic Parameters")
    baseline_naoh_pct = st.number_input("Baseline NaOH concentration in use solution (%)", value=5.0, min_value=0.5, step=0.1)
    naoh_reduction_factor = st.slider("NaOH reduction with AlkaBoost (your rule of thumb)", 0.5, 1.0, 0.70, step=0.01)
    new_naoh_pct = baseline_naoh_pct * naoh_reduction_factor

    st.subheader("Cycle Frequency Improvement")
    cycle_reduction_pct = st.slider("Reduction in CIP frequency due to better cleaning (%)", 0, 50, 0, step=1)

    st.subheader("Costs")
    naoh_price = st.number_input(f"Current NaOH price per {mass_unit}", value=0.65, min_value=0.0, step=0.01)
    additive_price = st.number_input(f"Proposed AlkaBoost price per {mass_unit} (leave blank to calculate fair price)", value=0.0, min_value=0.0, step=0.01)

    st.subheader("Other Savings (optional – set to 0 if unknown)")
    energy_cost_per_cycle = st.number_input("Baseline energy cost per CIP ($)", value=45.0, step=1.0)
    energy_savings_pct = st.slider("Energy savings % (lower temp/shorter time)", 0, 40, 15, step=5)
    water_cost_per_vol = st.number_input(f"Water + wastewater cost per {vol_unit}", value=0.012 if is_imperial else 0.0032, step=0.001)
    labor_cost_per_cycle = st.number_input("Labor + downtime cost per CIP ($)", value=120.0, step=5.0)
    maintenance_savings_per_year = st.number_input("Annual maintenance/equipment-life savings ($)", value=2500.0, step=100.0)

# ====================== CALCULATIONS ======================
# NaOH mass per cycle (baseline)
naoh_baseline_per_cycle = solution_volume * (baseline_naoh_pct / 100) * density_factor
naoh_with_per_cycle = solution_volume * (new_naoh_pct / 100) * density_factor

# Additive mass (10% of NaOH weight per TDS performance spec)
additive_per_cycle = naoh_with_per_cycle * 0.10

# Annual quantities
naoh_baseline_annual = naoh_baseline_per_cycle * cycles_per_year
naoh_with_annual = naoh_with_per_cycle * cycles_per_year * (1 - cycle_reduction_pct/100)
additive_annual = additive_per_cycle * cycles_per_year * (1 - cycle_reduction_pct/100)

# Costs
baseline_chemical_cost = naoh_baseline_annual * naoh_price
with_chemical_cost = naoh_with_annual * naoh_price + additive_annual * additive_price

# Other savings
energy_savings_annual = energy_cost_per_cycle * cycles_per_year * (energy_savings_pct / 100)
water_savings_annual = solution_volume * water_cost_per_vol * cycles_per_year * (cycle_reduction_pct / 100)
labor_savings_annual = labor_cost_per_cycle * cycles_per_year * (cycle_reduction_pct / 100)
total_other_savings = energy_savings_annual + water_savings_annual + labor_savings_annual + maintenance_savings_per_year

# Net results
gross_savings = (baseline_chemical_cost - (naoh_with_annual * naoh_price)) + total_other_savings
additive_total_cost = additive_annual * additive_price
net_savings = gross_savings - additive_total_cost

# Break-even & recommended price
if additive_annual > 0:
    break_even_price = gross_savings / additive_annual
    recommended_price = break_even_price * 0.55   # you keep ~55% of value created (customer keeps 45% – very fair)
else:
    break_even_price = 0
    recommended_price = 0

# ====================== DISPLAY ======================
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Baseline Annual NaOH Cost", f"${baseline_chemical_cost:,.0f}")
with col2:
    st.metric("With AlkaBoost NaOH + Additive Cost", f"${with_chemical_cost:,.0f}", delta=f"-${gross_savings:,.0f}")
with col3:
    st.metric("Net Annual Savings", f"${net_savings:,.0f}", delta_color="normal")

st.divider()

st.subheader("Key Outputs")
df_summary = pd.DataFrame({
    "Metric": [
        f"NaOH used per year baseline ({mass_unit})",
        f"NaOH used per year with AlkaBoost ({mass_unit})",
        f"AlkaBoost used per year ({mass_unit})",
        "Gross caustic + other savings",
        "Your additive cost at proposed price",
        "Net savings to customer",
        f"Break-even AlkaBoost price per {mass_unit}",
        f"Recommended fair price per {mass_unit} (55/45 split)"
    ],
    "Value": [
        f"{naoh_baseline_annual:,.0f}",
        f"{naoh_with_annual:,.0f}",
        f"{additive_annual:,.0f}",
        f"${gross_savings:,.0f}",
        f"${additive_total_cost:,.0f}",
        f"${net_savings:,.0f}",
        f"${break_even_price:.2f}",
        f"${recommended_price:.2f}"
    ]
})
st.table(df_summary)

st.info("**How the dosing works (from TDS):** AlkaBoost is added at 10 % by weight of the NaOH in the use solution (achieves the 0.3 % / 3 % performance spec). The calculator automatically uses this ratio.")

st.caption("You can change any input on the left and the numbers update live. Share this link with your Mexico distributor – they can use Metric instantly.")

# Optional download
csv = df_summary.to_csv(index=False).encode()
st.download_button("Download results as CSV", csv, "AlkaBoost_Savings_Report.csv", "text/csv")
