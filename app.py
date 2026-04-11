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
_DEFAULTS_IMPERIAL = {
    'annual_naoh_baseline': 76000.0,   # lb/year
    'water_cost_per_vol':   0.012,     # $/gal
    'price_your_dist':      1.85,      # $/lb
    'price_additive':       2.50,      # $/lb
    'price_freight':        0.15,      # $/lb
}
for k, v in _DEFAULTS_IMPERIAL.items():
    if k not in st.session_state:
        st.session_state[k] = v
if 'last_units_imperial' not in st.session_state:
    st.session_state.last_units_imperial = True

# ====================== SIDEBAR ======================
with st.sidebar:
    st.header("📍 Customer Location & Units")
    location = st.text_input("Customer Location",
                             value="United States",
                             help="Type any location (e.g. Puebla, Queretaro, Laredo TX, Veracruz). Auto-detects NaOH market price.")

    units = st.radio("Units System", ["Imperial (lb, gal, °F, USD)", "Metric (kg, L, °C, USD)"],
                     horizontal=True, key="units_radio")
    is_imperial = units.startswith("Imperial")

    # ── Unit conversion: update ALL convertible widget values on switch ──────
    if st.session_state.last_units_imperial != is_imperial:
        MASS  = 2.20462   # lb ↔ kg
        VOL   = 3.78541   # gal ↔ L
        if is_imperial:   # metric → imperial
            st.session_state.annual_naoh_baseline  *= MASS
            st.session_state.water_cost_per_vol    *= VOL
            st.session_state.price_your_dist       /= MASS   # $/kg → $/lb
            st.session_state.price_additive        /= MASS
            st.session_state.price_freight         /= MASS
        else:             # imperial → metric
            st.session_state.annual_naoh_baseline  /= MASS
            st.session_state.water_cost_per_vol    /= VOL
            st.session_state.price_your_dist       *= MASS   # $/lb → $/kg
            st.session_state.price_additive        *= MASS
            st.session_state.price_freight         *= MASS
        # Push converted values into widget keys so inputs display new numbers
        st.session_state["annual_naoh_input"]   = st.session_state.annual_naoh_baseline
        st.session_state["water_input"]         = st.session_state.water_cost_per_vol
        st.session_state["price_your_dist_w"]   = st.session_state.price_your_dist
        st.session_state["price_additive_w"]    = st.session_state.price_additive
        st.session_state["price_freight_w"]     = st.session_state.price_freight
        st.session_state.last_units_imperial    = is_imperial
        st.rerun()

    density_factor = 8.34 if is_imperial else 1.0
    vol_unit  = "gal" if is_imperial else "L"
    mass_unit = "lb"  if is_imperial else "kg"

    # NaOH price auto-detect from location
    loc_lower = location.lower()
    if any(w in loc_lower for w in ["mexico", "puebla", "queretaro", "merida", "villa hermosa",
                                     "cancun", "veracruz", "laredo"]):
        naoh_default = 0.72 if is_imperial else 0.72 * 2.20462
    elif any(w in loc_lower for w in ["united states", "usa", "us", "texas", "florida"]):
        naoh_default = 0.60 if is_imperial else 0.60 * 2.20462
    else:
        naoh_default = 0.65 if is_imperial else 0.65 * 2.20462

    # ── CIP Parameters ──────────────────────────────────────────────────────
    st.subheader("CIP Parameters")

    cycles_per_year = st.number_input("CIP Cycles Per Year", value=365, min_value=1, step=1,
                                      help="Typical plants run 200–400 CIPs/year. 365 = once-per-day average.")

    annual_naoh_baseline = st.number_input(
        f"Annual NaOH Usage — Baseline ({mass_unit}/Year)",
        value=st.session_state.annual_naoh_baseline,
        min_value=100.0, key="annual_naoh_input",
        help="Total lbs (or kg) of NaOH used across all CIP cycles in a year at your current process, "
             "before AlkaBoost™. Check your annual caustic purchase records for this number.")

    baseline_naoh_pct = st.number_input("NaOH Concentration (%)", value=5.0, min_value=0.5, step=0.1,
                                        help="Your current NaOH concentration in the use solution (e.g. 3–5%). "
                                             "Used to estimate solution volume for water savings in Advanced mode.")

    # ── AlkaBoost™ Effects ───────────────────────────────────────────────────
    st.subheader("AlkaBoost™ Effects")

    naoh_reduction_pct = st.slider("NaOH Consumption Reduction With AlkaBoost™ (%)", 0, 50, 30, step=1,
                                   help="How much less caustic is needed while achieving equal or better cleaning. "
                                        "Typical field result: 25–35%.")

    cycle_reduction_pct = st.slider("Reduction In CIP Frequency (%)", 0, 50, 0, step=1,
                                    help="Fewer CIPs needed over time due to superior cleaning performance.")

    # ── AlkaBoost™ & Pricing ─────────────────────────────────────────────────
    st.subheader("AlkaBoost™ & Pricing")

    your_price_to_dist = st.number_input(
        f"Your Price To Distributor Per {mass_unit}",
        value=st.session_state.price_your_dist,
        min_value=0.0, step=0.01, key="price_your_dist_w",
        help="Your selling price to the distributor.")

    freight_per_lb = st.number_input(
        f"Estimated Freight Per {mass_unit} To Customer Site ($)",
        value=st.session_state.price_freight,
        min_value=0.0, step=0.01, key="price_freight_w",
        help="Shipping cost per lb/kg to the customer's site. Default $0.15 covers most domestic shipments.")

    distributor_landed_cost = your_price_to_dist + freight_per_lb

    additive_price = st.number_input(
        f"Customer Quoted AlkaBoost™ Price Per {mass_unit}",
        value=st.session_state.price_additive,
        min_value=0.0, step=0.01, key="price_additive_w",
        help="The price the end-customer actually pays (after distributor markup).")

    # ── Advanced: Additional Operating Savings ──────────────────────────────
    with st.expander("🔬 Advanced: Include Additional Operating Savings (Energy, Water, Labor, Maintenance)"):
        include_other_savings = st.checkbox("✅ Add These To The Net Savings Calculation",
                                            value=False, key="include_other")

        fresh_makeup_pct = st.slider(
            "Fresh Solution Makeup Per CIP Cycle (%)", min_value=10, max_value=100, value=100, step=5,
            help="100% = single-pass (full fresh solution every cycle). "
                 "Set lower for RECYCLED CIP systems — only the makeup fraction is re-dosed each cycle. "
                 "This scales the estimated solution volume used for water savings below.")

        naoh_price = st.number_input(f"NaOH Price Per {mass_unit} (Auto-Filled)",
                                     value=naoh_default, step=0.01,
                                     help="Customer's actual delivered price for 50% liquid caustic.")
        energy_cost_per_cycle = st.number_input("Baseline Energy Cost Per CIP ($)", value=45.0, step=1.0,
                                                help="Steam / electricity cost to heat and run the CIP.")
        energy_savings_pct = st.slider("Energy Savings % (Lower Temp/Shorter Time)", 0, 40, 15, step=5)
        water_cost_per_vol = st.number_input(f"Water + Wastewater Cost Per {vol_unit}",
                                             value=st.session_state.water_cost_per_vol,
                                             key="water_input", step=0.001)
        labor_cost_per_cycle = st.number_input("Labor + Downtime Cost Per CIP ($)", value=120.0, step=5.0)
        maintenance_savings_per_year = st.number_input("Annual Maintenance/Equipment-Life Savings ($)",
                                                       value=2500.0, step=100.0)
        other_chemical_savings_annual = st.number_input("Other Chemical (Acid/Sanitizer) Savings Per Year ($)",
                                                        value=0.0, step=100.0)

# ====================== CALCULATIONS ======================
naoh_baseline_annual    = annual_naoh_baseline
naoh_baseline_per_cycle = naoh_baseline_annual / cycles_per_year if cycles_per_year > 0 else 0

naoh_with_per_cycle  = naoh_baseline_per_cycle * (1 - naoh_reduction_pct / 100)
additive_per_cycle   = naoh_with_per_cycle * 0.10

cycles_with      = cycles_per_year * (1 - cycle_reduction_pct / 100)
naoh_with_annual = naoh_with_per_cycle * cycles_with
additive_annual  = additive_per_cycle * cycles_with

# Derive solution volume per cycle for water savings
_chem_vol_factor = fresh_makeup_pct / 100.0
solution_volume_per_cycle = (
    naoh_baseline_per_cycle / ((baseline_naoh_pct / 100) * density_factor * _chem_vol_factor)
    if baseline_naoh_pct > 0 and density_factor > 0 and _chem_vol_factor > 0 else 0
)

_naoh_price = naoh_price if st.session_state.get("include_other", False) else naoh_default

baseline_chemical_cost = naoh_baseline_annual * _naoh_price
with_chemical_cost     = naoh_with_annual * _naoh_price + additive_annual * additive_price

chemical_savings    = baseline_chemical_cost - (naoh_with_annual * _naoh_price)
net_chemical_savings = chemical_savings - additive_annual * additive_price

if st.session_state.get("include_other", False):
    water_savings_annual  = solution_volume_per_cycle * water_cost_per_vol * cycles_per_year * (cycle_reduction_pct / 100)
    energy_savings_annual = energy_cost_per_cycle * cycles_per_year * (energy_savings_pct / 100)
    labor_savings_annual  = labor_cost_per_cycle  * cycles_per_year * (cycle_reduction_pct / 100)
    total_other_savings   = (energy_savings_annual + water_savings_annual + labor_savings_annual
                             + maintenance_savings_per_year + other_chemical_savings_annual)
else:
    total_other_savings = 0.0

net_savings     = chemical_savings + total_other_savings - additive_annual * additive_price
break_even_price = (chemical_savings + total_other_savings) / additive_annual if additive_annual > 0 else 0.0

# Derived insight metrics
naoh_cost_reduction_pct = (chemical_savings / baseline_chemical_cost * 100) if baseline_chemical_cost > 0 else 0
additive_total_cost     = additive_annual * additive_price
payback_months          = (additive_total_cost / (net_savings / 12)) if net_savings > 0 else float('inf')

# ====================== DISPLAY ======================
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Baseline Annual NaOH Cost", f"${baseline_chemical_cost:,.0f}")
with col2:
    delta_chem = net_chemical_savings
    st.metric("New Annual Chemical Cost (NaOH + AlkaBoost™)",
              f"${with_chemical_cost:,.0f}",
              delta=f"-${delta_chem:,.0f}" if delta_chem >= 0 else f"${abs(delta_chem):,.0f}",
              delta_color="inverse")
with col3:
    color = "#16a34a" if net_savings >= 0 else "#dc2626"
    st.markdown(f"<h3 style='color:{color};'>Net Annual Savings<br>${net_savings:,.0f}</h3>",
                unsafe_allow_html=True)

# ROI insight strip
r1, r2, r3 = st.columns(3)
with r1:
    st.metric("Caustic Cost Reduction", f"{naoh_cost_reduction_pct:.1f}%",
              help="Percentage reduction in annual NaOH spend after switching to AlkaBoost™.")
with r2:
    pb = f"{payback_months:.1f} months" if payback_months != float('inf') else "N/A"
    st.metric("Estimated Payback Period", pb,
              help="How long until AlkaBoost™ additive costs are fully offset by savings.")
with r3:
    roi_pct = (net_savings / additive_total_cost * 100) if additive_total_cost > 0 else 0
    st.metric("Return On Investment", f"{roi_pct:.0f}%",
              help="Net savings as a percentage of the annual AlkaBoost™ spend.")

st.divider()

# ── Summary Table ────────────────────────────────────────────────────────────
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

st.info("**Dosing Per TDS:** AlkaBoost™ = 10% by weight of the NaOH in the use solution. "
        "Recycled CIP systems supported — set Fresh Solution Makeup % in Advanced.")

# ── Distributor Margin ───────────────────────────────────────────────────────
with st.expander("🔍 Distributor Margin Analysis"):
    st.write(f"Your Price To Distributor: **${your_price_to_dist:.2f}** per {mass_unit}")
    st.write(f"Freight: **${freight_per_lb:.2f}** per {mass_unit}")
    st.write(f"**Distributor Landed Cost:** ${distributor_landed_cost:.2f}")
    if additive_annual > 0:
        margin_room = max(0, break_even_price - distributor_landed_cost)
        st.success(f"**Distributor Has ${margin_room:.2f} Per {mass_unit} Of Margin Room**")
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
    c.drawString(50, height - 85,
                 f"Location: {location}  |  Units: {units}  |  Generated: {pd.Timestamp.now().strftime('%Y-%m-%d')}")

    y = height - 130
    for _, row in df_summary.iterrows():
        c.drawString(50, y, f"{row['Metric']}: {row['Value']}")
        y -= 24
        if y < 120:
            c.showPage()
            y = height - 50

    if os.path.exists(logo_path):
        try:
            c.drawImage(logo_path, 50, 28, width=160, height=50, preserveAspectRatio=True)
        except Exception:
            pass
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(50, 18, "Results are estimates. Dosing per manufacturer recommendation (AlkaBoost TDS). "
                         "Consult your distributor for site-specific analysis.")
    c.save()
    buffer.seek(0)
    return buffer


pdf_bytes = create_pdf_report()
st.download_button("📄 Save Report (PDF)", data=pdf_bytes,
                   file_name="AlkaBoost_CIP_Savings_Report.pdf", mime="application/pdf")

st.divider()
st.caption(
    "Disclaimer: Figures and calculations in this tool are based on general industry assumptions, "
    "the most recently available market data, and manufacturer-recommended dosing rates per the "
    "AlkaBoost™ Technical Data Sheet (TDS). Results are estimates only and may vary based on your "
    "specific process conditions, product concentrations, and supplier pricing. "
    "Consult your IG Chemical Solutions distributor for a more accurate, site-specific analysis."
)
