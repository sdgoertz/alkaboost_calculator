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
    st.image(logo_path, width=420)
else:
    st.warning("👉 Save the IG Chemical Solutions logo as **logo.png** in the same folder as this script.")

st.markdown('<h1 class="main-header">IG Chemical Solutions</h1>', unsafe_allow_html=True)
st.markdown('<p class="tagline">A New Element in Chemistry • AlkaBoost™ CIP Additive Cost-Savings Calculator</p>', unsafe_allow_html=True)
st.caption("Built from the official TDS • Primary focus on caustic chemical spend • All other savings optional/unlocked")

# ====================== SESSION STATE ======================
if 'last_units_imperial' not in st.session_state:
    st.session_state.last_units_imperial = True
if 'annual_solution_volume' not in st.session_state:
    st.session_state.annual_solution_volume = 1825000.0   # realistic default ~5000 gal × 365 cycles
if 'water_cost_per_vol' not in st.session_state:
    st.session_state.water_cost_per_vol = 0.012

# ====================== SIDEBAR INPUTS ======================
with st.sidebar:
    st.header("📍 Customer Location & Units")
    location = st.text_input("Customer Location (type city, region, or country)",
                             value="United States",
                             help="Type any location (e.g. Mexico City, Puebla, Queretaro, Laredo TX, Veracruz). Auto-detects realistic NaOH market price.")

    units = st.radio("Units System", ["Imperial (lb, gal, °F, USD)", "Metric (kg, L, °C, USD)"], horizontal=True, key="units_radio")
    is_imperial = units.startswith("Imperial")

    # Auto-convert annual volume & water cost when units change
    current_is_imperial = is_imperial
    if st.session_state.last_units_imperial != current_is_imperial:
        conv = 3.78541
        if current_is_imperial:  # switched TO imperial
            st.session_state.annual_solution_volume /= conv
            st.session_state.water_cost_per_vol *= conv
        else:  # switched TO metric
            st.session_state.annual_solution_volume *= conv
            st.session_state.water_cost_per_vol /= conv
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

    st.subheader("Production Data")
    cycles_per_year = st.number_input("CIP cycles per year", value=365, min_value=1, step=1,
                                      help="Typical plants run 200–400 CIPs/year. 365 = once-per-day average.")

    annual_solution_volume = st.number_input(f"Annual cleaning solution volume (baseline, all CIPs) ({vol_unit}/year)",
                                             value=st.session_state.annual_solution_volume,
                                             min_value=10000.0, key="annual_vol_input",
                                             help="Total volume of cleaning solution circulated across ALL CIP cycles in a year (this replaces the old per-cycle volume).")

    fresh_makeup_pct = st.slider("Fresh solution makeup per CIP cycle (%)",
                                 min_value=10, max_value=100, value=100, step=5,
                                 help="100% = single-pass system (full fresh solution every cycle). Lower % = RECYCLED CIP systems (only makeup chemicals added).")

    st.subheader("Caustic Parameters")
    baseline_naoh_pct = st.number_input("Baseline NaOH concentration in use solution (%)",
                                        value=5.0, min_value=0.5, step=0.1,
                                        help="Typical set-point concentration before AlkaBoost™.")

    naoh_reduction_pct = st.slider("NaOH consumption reduction with AlkaBoost™ (%)",
                                   0, 50, 30, step=1,
                                   help="How much less caustic is needed while still achieving equal or better cleaning.")

    cycle_reduction_pct = st.slider("Reduction in CIP frequency (%)", 0, 50, 0, step=1,
                                    help="Fewer CIPs needed over time due to superior cleaning performance.")

    st.subheader("AlkaBoost™ & Pricing")
    your_price_to_dist = st.number_input(f"Your price to distributor per {mass_unit}",
                                         value=2.15, min_value=0.0, step=0.01,
                                         help="Your selling price to the distributor (any tier).")
    freight_per_lb = st.number_input("Estimated freight to distributor/customer site ($ per lb or kg)",
                                     value=0.15 if "mexico" in loc_lower else 0.0, step=0.01,
                                     help="Extra shipping cost for bulk truckload, Laredo, Florida ports, Veracruz, etc.")
    distributor_landed_cost = your_price_to_dist + freight_per_lb

    additive_price = st.number_input(f"Customer quoted AlkaBoost™ price per {mass_unit}",
                                     value=2.50, min_value=0.0, step=0.01,
                                     help="The price the end-customer actually pays (distributor adds their markup).")

    # ====================== ADVANCED OPERATING SAVINGS ======================
    with st.expander("🔬 Advanced: Include Additional Operating Savings (energy, water, labor, maintenance)"):
        include_other_savings = st.checkbox("✅ Add these to the Net Savings calculation", value=False, key="include_other")

        st.subheader("Operating Costs & Savings")
        naoh_price = st.number_input(f"NaOH price per {mass_unit} (auto-filled)",
                                     value=naoh_default, step=0.01,
                                     help="Customer's actual delivered price for 50% liquid caustic.")
        energy_cost_per_cycle = st.number_input("Baseline energy cost per CIP ($)", value=45.0, step=1.0,
                                                help="Steam / electricity to heat and maintain temperature.")
        energy_savings_pct = st.slider("Energy savings % (lower temp/shorter time)", 0, 40, 15, step=5)
        water_cost_per_vol = st.number_input(f"Water + wastewater cost per {vol_unit}",
                                             value=st.session_state.water_cost_per_vol, key="water_input",
                                             step=0.001)
        labor_cost_per_cycle = st.number_input("Labor + downtime cost per CIP ($)", value=120.0, step=5.0)
        maintenance_savings_per_year = st.number_input("Annual maintenance/equipment-life savings ($)", value=2500.0, step=100.0)
        other_chemical_savings_annual = st.number_input("Other chemical (acid/sanitizer) savings per year ($)", value=0.0, step=100.0)

# ====================== CALCULATIONS ======================
solution_volume_per_cycle = annual_solution_volume / cycles_per_year if cycles_per_year > 0 else 0
chemical_volume_factor = fresh_makeup_pct / 100.0

naoh_baseline_per_cycle = solution_volume_per_cycle * (baseline_naoh_pct / 100) * density_factor * chemical_volume_factor
naoh_with_per_cycle = naoh_baseline_per_cycle * (1 - naoh_reduction_pct / 100)

additive_per_cycle = naoh_with_per_cycle * 0.10

cycles_with = cycles_per_year * (1 - cycle_reduction_pct / 100)

naoh_baseline_annual = naoh_baseline_per_cycle * cycles_per_year
naoh_with_annual = naoh_with_per_cycle * cycles_with
additive_annual = additive_per_cycle * cycles_with

# NaOH price needed for chemical cost — use naoh_default when advanced expander is closed
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
    st.metric("New Annual Chemical Cost (NaOH + AlkaBoost™)",
              f"${with_chemical_cost:,.0f}",
              delta=f"${delta_chem:,.0f}" if delta_chem >= 0 else f"-${abs(delta_chem):,.0f}",
              delta_color="normal" if delta_chem >= 0 else "inverse")

with col3:
    if net_savings >= 0:
        st.markdown(f"<h3 style='color:#16a34a;'>Net Annual Savings to Customer<br>${net_savings:,.0f}</h3>", unsafe_allow_html=True)
    else:
        st.markdown(f"<h3 style='color:#dc2626;'>Net Annual Savings to Customer<br>${net_savings:,.0f}</h3>", unsafe_allow_html=True)

st.divider()

st.subheader("📊 Full Summary Table")
df_summary = pd.DataFrame({
    "Metric": [
        f"NaOH used per year (baseline) ({mass_unit})",
        f"NaOH used per year (with AlkaBoost™) ({mass_unit})",
        f"AlkaBoost™ used per year ({mass_unit})",
        "Chemical savings (NaOH reduction only)",
        "Net chemical savings (after additive cost)",
        "Additional operating savings (if unlocked)",
        "Total gross savings",
        "Net annual savings to customer",
        f"Customer break-even price per {mass_unit}",
        "Distributor landed cost per lb/kg (your price + freight)",
        "Distributor margin room at customer break-even"
    ],
    "Value": [
        f"{naoh_baseline_annual:,.0f}",
        f"{naoh_with_annual:,.0f}",
        f"{additive_annual:,.0f}",
        f"${chemical_savings:,.0f}",
        f"${net_chemical_savings:,.0f}",
        f"${total_other_savings:,.0f}",
        f"${gross_savings:,.0f}",
        f"${net_savings:,.0f}",
        f"${break_even_price:.2f}",
        f"${distributor_landed_cost:.2f}",
        f"${max(0, break_even_price - distributor_landed_cost):.2f}"
    ]
})
st.dataframe(df_summary, use_container_width=True, hide_index=True)

st.info("**Dosing per TDS:** AlkaBoost™ = 10 % by weight of the NaOH in the use solution. Recycled CIP systems fully supported.")

# ====================== DISTRIBUTOR MARGIN ======================
with st.expander("🔍 Distributor Margin Analysis"):
    st.write(f"Your price to distributor: **${your_price_to_dist:.2f}** per {mass_unit}")
    st.write(f"Freight: **${freight_per_lb:.2f}** per {mass_unit}")
    st.write(f"**Distributor landed cost:** ${distributor_landed_cost:.2f}")
    if additive_annual > 0:
        st.success(f"**Distributor has ${max(0, break_even_price - distributor_landed_cost):.2f} per {mass_unit} of margin room**")
    else:
        st.warning("No additive volume calculated.")

# ====================== DOWNLOADS ======================
csv = df_summary.to_csv(index=False).encode()
st.download_button("📥 Download results as CSV", csv, "AlkaBoost_Savings_Report.csv", "text/csv")


def create_pdf_report():
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # Add logo if present
    if os.path.exists(logo_path):
        try:
            c.drawImage(logo_path, 50, height - 110, width=220, height=70, preserveAspectRatio=True)
        except Exception:
            pass

    c.setFont("Helvetica-Bold", 22)
    c.drawString(300, height - 70, "AlkaBoost™ CIP Savings Report")
    c.setFont("Helvetica", 11)
    c.drawString(300, height - 95, f"Location: {location} • Units: {units} • Generated: {pd.Timestamp.now().strftime('%Y-%m-%d')}")

    y = height - 160
    for _, row in df_summary.iterrows():
        c.drawString(50, y, f"{row['Metric']}: {row['Value']}")
        y -= 24
        if y < 80:
            c.showPage()
            y = height - 50

    c.setFont("Helvetica-Oblique", 9)
    c.drawString(50, 50, "IG Chemical Solutions • Official AlkaBoost™ TDS • Comprehensive model with recycled CIP support")
    c.save()
    buffer.seek(0)
    return buffer


pdf_bytes = create_pdf_report()
st.download_button("📄 Save as Professional PDF Report (with logo)",
                   data=pdf_bytes,
                   file_name="AlkaBoost_CIP_Savings_Report.pdf",
                   mime="application/pdf")

st.caption("✅ Annual caustic-solution volume input • Chemical-focused dashboard • Color-coded net savings • Other savings unlocked in expander • PDF includes logo")
