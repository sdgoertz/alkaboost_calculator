import streamlit as st
import pandas as pd
import io
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import os

st.set_page_config(page_title="AlkaBoost™ CIP Savings Calculator", layout="wide", page_icon="🧪")

# ====================== BRANDING ======================
st.markdown("""
    <style>
    .main-header {font-size: 42px; font-weight: bold; color: #1E3A8A;}
    .tagline {font-size: 18px; color: #0F172A; font-style: italic;}
    .metric-positive {color: #16a34a !important;}
    .metric-negative {color: #dc2626 !important;}
    </style>
""", unsafe_allow_html=True)

logo_path = "logo.png"
if os.path.exists(logo_path):
    st.image(logo_path, width=210)
else:
    st.warning("👉 Save the IG Chemical Solutions logo as **logo.png** in the same folder as this script.")

st.markdown('<h1 class="main-header">AlkaBoost™ CIP Additive Cost-Savings Calculator</h1>', unsafe_allow_html=True)
st.caption("IG Chemical Solutions — igchemicalsolutions.com")

# ====================== SESSION STATE ======================
if 'last_units_imperial' not in st.session_state:
    st.session_state.last_units_imperial = True
if 'annual_naoh_baseline' not in st.session_state:
    st.session_state.annual_naoh_baseline = 76000.0   # ~5000 gal × 365 cycles × 5% NaOH × 8.34 lb/gal
if 'water_cost_per_vol' not in st.session_state:
    st.session_state.water_cost_per_vol = 0.012

# ====================== SIDEBAR INPUTS ======================
with st.sidebar:
    st.header("📍 Customer Location & Units")
    location = st.text_input("Customer Location",
                             value="United States",
                             help="Type any location (e.g. Mexico City, Puebla, Queretaro, Laredo TX, Veracruz). Auto-detects realistic NaOH market price.")

    units = st.radio("Units System", ["Imperial (lb, gal, °F, USD)", "Metric (kg, L, °C, USD)"], horizontal=True, key="units_radio")
    is_imperial = units.startswith("Imperial")

    # Auto-convert NaOH baseline & water cost when units change
    current_is_imperial = is_imperial
    if st.session_state.last_units_imperial != current_is_imperial:
        mass_conv = 2.20462  # lb ↔ kg
        vol_conv = 3.78541   # gal ↔ L
        if current_is_imperial:  # switched TO imperial
            st.session_state.annual_naoh_baseline *= mass_conv
            st.session_state.water_cost_per_vol *= vol_conv
        else:  # switched TO metric
            st.session_state.annual_naoh_baseline /= mass_conv
            st.session_state.water_cost_per_vol /= vol_conv
        st.session_state.last_units_imperial = current_is_imperial
        st.rerun()

    density_factor = 8.34 if is_imperial else 1.0
    vol_unit = "gal" if is_imperial else "L"
    mass_unit = "lb" if is_imperial else "kg"

    # NaOH price auto-detect
    loc_lower = location.lower()
    if any(word in loc_lower for word in ["mexico", "puebla", "queretaro", "merida", "villa hermosa", "cancun", "veracruz", "laredo"]):
        naoh_default = 0.72
    elif any(word in loc_lower for word in ["united states", "usa", "us", "texas", "florida"]):
        naoh_default = 0.60
    else:
        naoh_default = 0.65

    # ── CIP Parameters ──────────────────────────────────────
    st.subheader("CIP Parameters")
    cycles_per_year = st.number_input("CIP Cycles Per Year", value=365, min_value=1, step=1,
                                      help="Typical plants run 200–400 CIPs/year. 365 = once-per-day average.")

    annual_naoh_baseline = st.number_input(f"Annual NaOH Usage — Baseline ({mass_unit}/Year)",
                                           value=st.session_state.annual_naoh_baseline,
                                           min_value=100.0, key="annual_naoh_input",
                                           help="Total pounds (or kg) of NaOH your facility uses across all CIP cycles in a year at your current process. This is your baseline before AlkaBoost™.")

    fresh_makeup_pct = st.slider("Fresh Solution Makeup Per CIP Cycle (%)",
                                 min_value=10, max_value=100, value=100, step=5,
                                 help="100% = single-pass system (full fresh solution every cycle). Lower % = recycled CIP systems (only makeup chemicals added each cycle).")

    baseline_naoh_pct = st.number_input("NaOH Concentration (%)",
                                        value=5.0, min_value=0.5, step=0.1,
                                        help="Your current NaOH set-point concentration in the use solution (e.g. 3–5%). Used to estimate solution volume for water savings calculations.")

    # ── AlkaBoost Effects ────────────────────────────────────
    st.subheader("AlkaBoost™ Effects")
    naoh_reduction_pct = st.slider("NaOH Consumption Reduction With AlkaBoost™ (%)",
                                   0, 50, 30, step=1,
                                   help="How much less caustic is needed while still achieving equal or better cleaning.")

    cycle_reduction_pct = st.slider("Reduction In CIP Frequency (%)", 0, 50, 0, step=1,
                                    help="Fewer CIPs needed over time due to superior cleaning performance.")

    # ── AlkaBoost™ & Pricing ─────────────────────────────────
    st.subheader("AlkaBoost™ & Pricing")
    your_price_to_dist = st.number_input(f"Your Price To Distributor Per {mass_unit}",
                                         value=2.15, min_value=0.0, step=0.01,
                                         help="Your selling price to the distributor (any tier).")
    freight_per_lb = st.number_input(f"Estimated Freight Per {mass_unit} To Customer Site ($)",
                                     value=0.15 if "mexico" in loc_lower else 0.0, step=0.01,
                                     help="Extra shipping cost for bulk truckload, Laredo, Florida ports, Veracruz, etc.")
    distributor_landed_cost = your_price_to_dist + freight_per_lb

    additive_price = st.number_input(f"Customer Quoted AlkaBoost™ Price Per {mass_unit}",
                                     value=2.50, min_value=0.0, step=0.01,
                                     help="The price the end-customer actually pays (distributor adds their markup).")

    # ── Advanced Operating Savings ───────────────────────────
    with st.expander("🔬 Advanced: Include Additional Operating Savings (Energy, Water, Labor, Maintenance)"):
        include_other_savings = st.checkbox("✅ Add These To The Net Savings Calculation", value=False, key="include_other")

        naoh_price = st.number_input(f"NaOH Price Per {mass_unit} (Auto-Filled)",
                                     value=naoh_default, step=0.01,
                                     help="Customer's actual delivered price for 50% liquid caustic.")
        energy_cost_per_cycle = st.number_input("Baseline Energy Cost Per CIP ($)", value=45.0, step=1.0,
                                                help="Steam / electricity to heat and maintain temperature.")
        energy_savings_pct = st.slider("Energy Savings % (Lower Temp/Shorter Time)", 0, 40, 15, step=5)
        water_cost_per_vol = st.number_input(f"Water + Wastewater Cost Per {vol_unit}",
                                             value=st.session_state.water_cost_per_vol, key="water_input",
                                             step=0.001)
        labor_cost_per_cycle = st.number_input("Labor + Downtime Cost Per CIP ($)", value=120.0, step=5.0)
        maintenance_savings_per_year = st.number_input("Annual Maintenance/Equipment-Life Savings ($)", value=2500.0, step=100.0)
        other_chemical_savings_annual = st.number_input("Other Chemical (Acid/Sanitizer) Savings Per Year ($)", value=0.0, step=100.0)

# ====================== CALCULATIONS ======================
# NaOH baseline is now a direct input (lbs or kg/year)
naoh_baseline_annual = annual_naoh_baseline
naoh_baseline_per_cycle = naoh_baseline_annual / cycles_per_year if cycles_per_year > 0 else 0

naoh_with_per_cycle = naoh_baseline_per_cycle * (1 - naoh_reduction_pct / 100)
additive_per_cycle = naoh_with_per_cycle * 0.10

cycles_with = cycles_per_year * (1 - cycle_reduction_pct / 100)

naoh_with_annual = naoh_with_per_cycle * cycles_with
additive_annual = additive_per_cycle * cycles_with

# Derive solution volume per cycle for water savings (from NaOH input + concentration)
chemical_volume_factor = fresh_makeup_pct / 100.0
solution_volume_per_cycle = (
    naoh_baseline_per_cycle / ((baseline_naoh_pct / 100) * density_factor * chemical_volume_factor)
    if (baseline_naoh_pct > 0 and density_factor > 0 and chemical_volume_factor > 0)
    else 0
)

# NaOH price: use from advanced expander if open, otherwise use auto-detected default
_naoh_price = naoh_price if st.session_state.get("include_other", False) else naoh_default

baseline_chemical_cost = naoh_baseline_annual * _naoh_price
with_chemical_cost = naoh_with_annual * _naoh_price + additive_annual * additive_price

chemical_savings = baseline_chemical_cost - (naoh_with_annual * _naoh_price)
net_chemical_savings = chemical_savings - additive_annual * additive_price

# Other savings (only if unlocked)
if st.session_state.get("include_other", False):
    total_water_savings_annual = (
        solution_volume_per_cycle * water_cost_per_vol * cycles_per_year * (cycle_reduction_pct / 100)
    )
    energy_savings_annual = energy_cost_per_cycle * cycles_per_year * (energy_savings_pct / 100)
    labor_savings_annual = labor_cost_per_cycle * cycles_per_year * (cycle_reduction_pct / 100)
    total_other_savings = (energy_savings_annual + total_water_savings_annual +
                           labor_savings_annual + maintenance_savings_per_year + other_chemical_savings_annual)
else:
    total_other_savings = 0.0

gross_savings = chemical_savings + total_other_savings
net_savings = gross_savings - additive_annual * additive_price

break_even_price = gross_savings / additive_annual if additive_annual > 0 else 0.0

# ====================== DISPLAY ======================
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Baseline Annual NaOH Cost", f"${baseline_chemical_cost:,.0f}")

with col2:
    delta_chem = net_chemical_savings
    # Cost went DOWN = down arrow (green); cost went UP = up arrow (red)
    st.metric("New Annual Chemical Cost (NaOH + AlkaBoost™)",
              f"${with_chemical_cost:,.0f}",
              delta=f"-${delta_chem:,.0f}" if delta_chem >= 0 else f"${abs(delta_chem):,.0f}",
              delta_color="inverse")

with col3:
    if net_savings >= 0:
        st.markdown(f"<h3 style='color:#16a34a;'>Net Annual Savings<br>${net_savings:,.0f}</h3>", unsafe_allow_html=True)
    else:
        st.markdown(f"<h3 style='color:#dc2626;'>Net Annual Savings<br>${net_savings:,.0f}</h3>", unsafe_allow_html=True)

st.divider()

st.subheader("📊 Full Summary Table")
_metrics = [
    f"NaOH Used Per Year — Baseline ({mass_unit})",
    f"NaOH Used Per Year — With AlkaBoost™ ({mass_unit})",
    f"AlkaBoost™ Used Per Year ({mass_unit})",
    "Chemical Savings (NaOH Reduction Only)",
    "Net Chemical Savings (After Additive Cost)",
]
_values = [
    f"{naoh_baseline_annual:,.0f}",
    f"{naoh_with_annual:,.0f}",
    f"{additive_annual:,.0f}",
    f"${chemical_savings:,.0f}",
    f"${net_chemical_savings:,.0f}",
]
if st.session_state.get("include_other", False) and total_other_savings != 0:
    _metrics.append("Additional Operating Savings")
    _values.append(f"${total_other_savings:,.0f}")
_metrics += [
    "Net Annual Savings",
    f"Customer Break-Even Price Per {mass_unit}",
    f"Distributor Landed Cost Per {mass_unit} (Your Price + Freight)",
    "Distributor Margin Room At Customer Break-Even",
]
_values += [
    f"${net_savings:,.0f}",
    f"${break_even_price:.2f}",
    f"${distributor_landed_cost:.2f}",
    f"${max(0, break_even_price - distributor_landed_cost):.2f}",
]
df_summary = pd.DataFrame({"Metric": _metrics, "Value": _values})
st.dataframe(df_summary, use_container_width=True, hide_index=True)

st.info("**Dosing Per TDS:** AlkaBoost™ = 10% by weight of the NaOH in the use solution. Recycled CIP systems fully supported.")

# ====================== DISTRIBUTOR MARGIN ======================
with st.expander("🔍 Distributor Margin Analysis"):
    st.write(f"Your Price To Distributor: **${your_price_to_dist:.2f}** per {mass_unit}")
    st.write(f"Freight: **${freight_per_lb:.2f}** per {mass_unit}")
    st.write(f"**Distributor Landed Cost:** ${distributor_landed_cost:.2f}")
    if additive_annual > 0:
        st.success(f"**Distributor Has ${max(0, break_even_price - distributor_landed_cost):.2f} Per {mass_unit} Of Margin Room**")
    else:
        st.warning("No additive volume calculated.")

# ====================== DOWNLOADS ======================
csv = df_summary.to_csv(index=False).encode()
st.download_button("📥 Download (CSV)", csv, "AlkaBoost_Savings_Report.csv", "text/csv")


def create_pdf_report():
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    c.setFont("Helvetica-Bold", 22)
    c.drawString(50, height - 60, "AlkaBoost™ CIP Savings Report")
    c.setFont("Helvetica", 11)
    c.drawString(50, height - 85, f"Location: {location}  |  Units: {units}  |  Generated: {pd.Timestamp.now().strftime('%Y-%m-%d')}")

    y = height - 130
    for _, row in df_summary.iterrows():
        c.drawString(50, y, f"{row['Metric']}: {row['Value']}")
        y -= 24
        if y < 120:
            c.showPage()
            y = height - 50

    # Logo at the bottom of the last page
    if os.path.exists(logo_path):
        try:
            c.drawImage(logo_path, 50, 28, width=160, height=50, preserveAspectRatio=True)
        except Exception:
            pass
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(50, 18, "Results are estimates. Dosing per manufacturer recommendation (AlkaBoost TDS). Consult your distributor for site-specific analysis.")

    c.save()
    buffer.seek(0)
    return buffer


pdf_bytes = create_pdf_report()
st.download_button("📄 Save Report (PDF)",
                   data=pdf_bytes,
                   file_name="AlkaBoost_CIP_Savings_Report.pdf",
                   mime="application/pdf")

st.divider()
st.caption(
    "Disclaimer: Figures and calculations in this tool are based on general industry assumptions, "
    "the most recently available market data, and manufacturer-recommended dosing rates per the "
    "AlkaBoost™ Technical Data Sheet (TDS). Results are estimates only and may vary based on your "
    "specific process conditions, product concentrations, and supplier pricing. "
    "Consult your IG Chemical Solutions distributor for a more accurate, site-specific analysis."
)
