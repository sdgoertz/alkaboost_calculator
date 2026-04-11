import streamlit as st
import pandas as pd
import io
import urllib.parse
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import os

st.set_page_config(page_title="AlkaBoost™ CIP Savings Calculator", layout="wide", page_icon="🧪")

# ====================== BRANDING ======================
st.markdown("""
    <style>
    .main-header {font-size: 42px; font-weight: bold; color: #1E3A8A;}
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
_DEFAULTS_IMP = {
    'annual_naoh_baseline': 76000,   # lb/year  (int — no decimals)
    'water_cost_per_vol':   0.012,   # $/gal
    'price_your_dist':      1.85,    # $/lb
    'price_additive':       2.50,    # $/lb
    'price_freight':        0.15,    # $/lb
}
for k, v in _DEFAULTS_IMP.items():
    if k not in st.session_state:
        st.session_state[k] = v
for k in ('last_units_imperial', 'last_preset'):
    if 'last_units_imperial' not in st.session_state:
        st.session_state.last_units_imperial = True
    if 'last_preset' not in st.session_state:
        st.session_state.last_preset = "Custom / Enter Your Own"

# Industry preset library (all values in Imperial)
_PRESETS = {
    "Edible Oil Processing":  {'naoh': 76000,  'cycles': 260, 'conc': 5.0},
    "Dairy / Beverage":       {'naoh': 45000,  'cycles': 365, 'conc': 3.5},
    "Poultry Processing":     {'naoh': 95000,  'cycles': 365, 'conc': 5.0},
    "Sugar / Sweetener":      {'naoh': 55000,  'cycles': 200, 'conc': 4.0},
    "Canning / Fruit & Veg":  {'naoh': 40000,  'cycles': 130, 'conc': 3.0},
    "Brewery":                {'naoh': 25000,  'cycles': 300, 'conc': 2.5},
}

# ====================== SIDEBAR ======================
with st.sidebar:
    st.header("📍 Customer Location & Units")
    location = st.text_input("Customer Location", value="United States",
                             help="Affects the auto-filled NaOH market price (visible in the Advanced section). "
                                  "Pricing is based on static general market estimates for 50% liquid caustic delivered — "
                                  "no live data is pulled. Always override with the customer's actual contract price "
                                  "for accurate results. Currently recognized regions: United States and Mexico.")

    units = st.radio("Units System", ["Imperial (lb, gal, °F, USD)", "Metric (kg, L, °C, USD)"],
                     horizontal=True, key="units_radio")
    is_imperial = units.startswith("Imperial")

    # ── Unit conversion: update ALL widget values on switch ──────────────────
    if st.session_state.last_units_imperial != is_imperial:
        MASS = 2.20462
        VOL  = 3.78541
        if is_imperial:   # metric → imperial
            st.session_state.annual_naoh_baseline  = int(round(st.session_state.annual_naoh_baseline * MASS))
            st.session_state.water_cost_per_vol   *= VOL
            st.session_state.price_your_dist      /= MASS
            st.session_state.price_additive       /= MASS
            st.session_state.price_freight        /= MASS
        else:             # imperial → metric
            st.session_state.annual_naoh_baseline  = int(round(st.session_state.annual_naoh_baseline / MASS))
            st.session_state.water_cost_per_vol   /= VOL
            st.session_state.price_your_dist      *= MASS
            st.session_state.price_additive       *= MASS
            st.session_state.price_freight        *= MASS
        # Push into widget keys so displayed numbers update
        st.session_state["w_naoh"]     = st.session_state.annual_naoh_baseline
        st.session_state["w_water"]    = st.session_state.water_cost_per_vol
        st.session_state["w_dist"]     = st.session_state.price_your_dist
        st.session_state["w_additive"] = st.session_state.price_additive
        st.session_state["w_freight"]  = st.session_state.price_freight
        st.session_state.last_units_imperial = is_imperial
        st.rerun()

    density_factor = 8.34 if is_imperial else 1.0
    vol_unit  = "gal" if is_imperial else "L"
    mass_unit = "lb"  if is_imperial else "kg"

    # NaOH price auto-detect
    loc_lower = location.lower()
    _naoh_per_kg = (0.72 if any(w in loc_lower for w in
                    ["mexico","puebla","queretaro","merida","villa hermosa","cancun","veracruz","laredo"])
                    else 0.60 if any(w in loc_lower for w in
                    ["united states","usa","us","texas","florida"])
                    else 0.65)
    naoh_default = _naoh_per_kg if is_imperial else _naoh_per_kg * 2.20462

    # ── Industry Preset ──────────────────────────────────────────────────────
    st.subheader("Industry Preset")
    preset = st.selectbox("Quick-Fill By Industry",
                          ["Custom / Enter Your Own"] + list(_PRESETS.keys()),
                          key="industry_preset",
                          help="Select your industry to auto-fill typical NaOH usage, cycle frequency, and concentration. You can still adjust any value manually.")

    if preset != "Custom / Enter Your Own" and preset != st.session_state.last_preset:
        p = _PRESETS[preset]
        naoh_val = p['naoh'] if is_imperial else int(round(p['naoh'] / 2.20462))
        st.session_state.annual_naoh_baseline = naoh_val
        st.session_state["w_naoh"]     = naoh_val
        st.session_state["w_cycles"]   = p['cycles']
        st.session_state["w_conc"]     = p['conc']
        st.session_state.last_preset   = preset
        st.rerun()
    elif preset == "Custom / Enter Your Own":
        st.session_state.last_preset = "Custom / Enter Your Own"

    # ── Simple: Chemical Cost & Pricing ─────────────────────────────────────
    with st.expander("💡 Simple: Chemical Cost & Pricing", expanded=True):
        st.subheader("CIP Parameters")

        cycles_per_year = st.number_input(
            "CIP Cycles Per Year", min_value=1, step=1,
            value=st.session_state.get("w_cycles", 260), key="w_cycles",
            help="260 = once per working day (M–F). 365 = daily including weekends. "
                 "130 = every other working day. Adjust to match your plant's actual schedule.")

        annual_naoh_baseline = st.number_input(
            f"Annual NaOH Usage — Baseline ({mass_unit}/Year)",
            value=st.session_state.annual_naoh_baseline,
            min_value=100, step=1, key="w_naoh",
            help="Total lbs (or kg) of NaOH purchased/consumed across all CIP cycles in a year "
                 "before AlkaBoost™. Check your annual caustic purchase records.")

        st.subheader("AlkaBoost™ Effects")

        naoh_reduction_pct = st.slider(
            "NaOH Consumption Reduction With AlkaBoost™ (%)", 0, 50, 30, step=1,
            help="How much less caustic is needed while achieving equal or better cleaning. "
                 "25–35% is a conservative field estimate; some customers have reported reductions of up to 50%.")

        cycle_reduction_pct = st.slider(
            "Reduction In CIP Frequency (%)", 0, 50, 0, step=1,
            help="Fewer CIPs needed over time due to superior cleaning performance.")

        st.subheader("AlkaBoost™ & Pricing")

        your_price_to_dist = st.number_input(
            f"Your Price To Distributor Per {mass_unit}",
            value=st.session_state.price_your_dist,
            min_value=0.0, step=0.01, key="w_dist",
            help="Your selling price to the distributor.")

        freight_per_lb = st.number_input(
            f"Estimated Inbound Freight Per {mass_unit} (Manufacturer → Distributor)",
            value=st.session_state.price_freight,
            min_value=0.0, step=0.01, key="w_freight",
            help="Freight cost per lb/kg from the IG Chemical Solutions manufacturing facility "
                 "to the distributor's warehouse. Used to calculate the distributor's landed cost. "
                 "Freight from the distributor to the end-user is a separate negotiation between "
                 "the distributor and their customer.")

        distributor_landed_cost = your_price_to_dist + freight_per_lb

        additive_price = st.number_input(
            f"Customer Quoted AlkaBoost™ Price Per {mass_unit}",
            value=st.session_state.price_additive,
            min_value=0.0, step=0.01, key="w_additive",
            help="The price the end-customer actually pays (after distributor markup).")

        # ── Quick Summary (inline, chemical savings only) ────────────────────
        st.markdown("---")
        st.caption("📊 Quick Summary — Chemical Savings Only")
        _cycles_with_s = cycles_per_year * (1 - cycle_reduction_pct / 100)
        _naoh_pc_s     = annual_naoh_baseline / cycles_per_year if cycles_per_year > 0 else 0
        _naoh_with_s   = _naoh_pc_s * (1 - naoh_reduction_pct / 100) * _cycles_with_s
        _additive_s    = _naoh_pc_s * (1 - naoh_reduction_pct / 100) * 0.10 * _cycles_with_s
        _chem_sav_s    = (annual_naoh_baseline - _naoh_with_s) * naoh_default
        _add_cost_s    = _additive_s * additive_price
        _net_chem_s    = _chem_sav_s - _add_cost_s
        _bep_s         = _chem_sav_s / _additive_s if _additive_s > 0 else 0
        st.write(f"Chemical Savings: **${_chem_sav_s:,.0f}**")
        st.write(f"Additive Annual Cost: **${_add_cost_s:,.0f}**")
        st.write(f"Net Chemical Savings: **${_net_chem_s:,.0f}**")
        st.write(f"Customer Break-Even: **${_bep_s:.2f}** / {mass_unit}")

    # ── Advanced: Additional Operating Savings ───────────────────────────────
    with st.expander("🔬 Advanced: Include Additional Operating Savings (Energy, Water, Labor, Maintenance)"):
        include_other_savings = st.checkbox(
            "✅ Add These To The Net Savings Calculation", value=False, key="include_other")

        baseline_naoh_pct = st.number_input(
            "NaOH Concentration (%)", min_value=0.5, step=0.1,
            value=st.session_state.get("w_conc", 5.0), key="w_conc",
            help="Your current NaOH set-point in the use solution (e.g. 3–5%). "
                 "Used to derive solution volume for water savings calculations.")

        fresh_makeup_pct = st.slider(
            "Fresh Solution Makeup Per CIP Cycle (%)", min_value=10, max_value=100, value=100, step=5,
            help="100% = single-pass system (all-fresh solution every cycle). "
                 "Lower % = recycled CIP systems. This scales the estimated water volume used, "
                 "affecting water savings calculations below. Must set Water/Rinse Reduction > 0 "
                 "or Cycle Frequency Reduction > 0 to see an effect on results.")

        water_reduction_per_cycle_pct = st.slider(
            "Water / Rinse Volume Reduction Per CIP (%)", 0, 30, 0, step=1,
            help="Water saved per cycle from improved wetting, reduced foam, or shorter rinse. "
                 "This is separate from saving cycles entirely. "
                 "Changing Fresh Solution Makeup % above will scale this figure "
                 "proportionally for recycled systems.")

        naoh_price = st.number_input(
            f"NaOH Price Per {mass_unit} (Auto-Filled)", value=naoh_default, step=0.01,
            help="Customer's actual delivered price for 50% liquid caustic.")
        energy_cost_per_cycle = st.number_input(
            "Baseline Energy Cost Per CIP ($)", value=45.0, step=1.0,
            help="Steam / electricity cost to heat and run the CIP.")
        energy_savings_pct = st.slider(
            "Energy Savings % (Lower Temp/Shorter Time)", 0, 40, 15, step=5,
            help="AlkaBoost™ improves cleaning efficacy at lower temperatures and shorter contact times, "
                 "reducing steam and electricity costs. 10–20% is a typical conservative estimate.")
        water_cost_per_vol = st.number_input(
            f"Water + Wastewater Cost Per {vol_unit}",
            value=st.session_state.water_cost_per_vol, key="w_water", step=0.001,
            help="Combined cost of water supply and wastewater treatment per gallon (or liter). "
                 "Check your utility bill — many plants underestimate wastewater surcharges. "
                 "US average is roughly $0.01–$0.02/gal combined.")
        labor_cost_per_cycle = st.number_input(
            "Labor + Downtime Cost Per CIP ($)", value=120.0, step=5.0,
            help="Fully-loaded cost of labor, lost production time, and line downtime for one CIP cycle. "
                 "Include operator time, QA verification, and any scheduled production delays.")
        maintenance_savings_per_year = st.number_input(
            "Annual Maintenance/Equipment-Life Savings ($)", value=2500.0, step=100.0,
            help="Lower caustic concentrations and better surfactancy reduce scale buildup, corrosion, "
                 "and wear on pumps, valves, and heat exchangers. Estimate based on reduced descaling "
                 "frequency or extended equipment service intervals.")
        other_chemical_savings_annual = st.number_input(
            "Other Chemical (Acid/Sanitizer) Savings Per Year ($)", value=0.0, step=100.0,
            help="Savings from reducing acid or sanitizer use. AlkaBoost™'s improved cleaning performance "
                 "can reduce the need for acid CIP steps — and some users have eliminated the acid step "
                 "in their CIP process entirely.")

# ====================== CALCULATIONS ======================
naoh_baseline_annual    = annual_naoh_baseline
naoh_baseline_per_cycle = naoh_baseline_annual / cycles_per_year if cycles_per_year > 0 else 0

naoh_with_per_cycle = naoh_baseline_per_cycle * (1 - naoh_reduction_pct / 100)
additive_per_cycle  = naoh_with_per_cycle * 0.10

cycles_with      = cycles_per_year * (1 - cycle_reduction_pct / 100)
naoh_with_annual = naoh_with_per_cycle * cycles_with
additive_annual  = additive_per_cycle  * cycles_with

# Derive solution volume per cycle for water savings
_mkp = fresh_makeup_pct / 100.0
solution_volume_per_cycle = (
    naoh_baseline_per_cycle / ((baseline_naoh_pct / 100) * density_factor * _mkp)
    if baseline_naoh_pct > 0 and density_factor > 0 and _mkp > 0 else 0
)

_naoh_price = naoh_price if st.session_state.get("include_other", False) else naoh_default

baseline_chemical_cost = naoh_baseline_annual * _naoh_price
naoh_with_cost         = naoh_with_annual     * _naoh_price
additive_total_cost    = additive_annual      * additive_price
with_chemical_cost     = naoh_with_cost + additive_total_cost

chemical_savings     = baseline_chemical_cost - naoh_with_cost
net_chemical_savings = chemical_savings - additive_total_cost

if st.session_state.get("include_other", False):
    # Two components of water savings: fewer cycles + per-cycle reduction
    water_savings_freq  = (solution_volume_per_cycle * water_cost_per_vol
                           * cycles_per_year * (cycle_reduction_pct / 100))
    water_savings_cycle = (solution_volume_per_cycle * water_cost_per_vol
                           * cycles_with * (water_reduction_per_cycle_pct / 100))
    energy_savings_annual = energy_cost_per_cycle * cycles_per_year * (energy_savings_pct / 100)
    labor_savings_annual  = labor_cost_per_cycle  * cycles_per_year * (cycle_reduction_pct / 100)
    total_other_savings   = (energy_savings_annual + water_savings_freq + water_savings_cycle
                             + labor_savings_annual + maintenance_savings_per_year
                             + other_chemical_savings_annual)
else:
    total_other_savings = 0.0

net_savings               = chemical_savings + total_other_savings - additive_total_cost
break_even_price_chem     = chemical_savings / additive_annual if additive_annual > 0 else 0.0
break_even_price          = (chemical_savings + total_other_savings) / additive_annual if additive_annual > 0 else 0.0

naoh_cost_reduction_pct = (chemical_savings / baseline_chemical_cost * 100) if baseline_chemical_cost > 0 else 0
payback_months          = (additive_total_cost / (net_savings / 12)) if net_savings > 0 else float('inf')
roi_pct                 = (net_savings / additive_total_cost * 100) if additive_total_cost > 0 else 0
pb = f"{payback_months:.1f} months" if payback_months != float('inf') else "N/A"

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

st.divider()

# Summary table
st.subheader("📊 Full Summary Table")
_metrics = [
    f"NaOH Used Per Year — Baseline ({mass_unit})",
    f"NaOH Used Per Year — With AlkaBoost™ ({mass_unit})",
    f"AlkaBoost™ Used Per Year ({mass_unit})",
    "Chemical Savings (NaOH Reduction Only)",
]
_values = [
    f"{naoh_baseline_annual:,.0f}",
    f"{naoh_with_annual:,.0f}",
    f"{additive_annual:,.0f}",
    f"${chemical_savings:,.0f}",
]
if st.session_state.get("include_other", False):
    _metrics.append("Net Chemical Savings (After Additive Cost)")
    _values.append(f"${net_chemical_savings:,.0f}")
    if total_other_savings != 0:
        _metrics.append("Additional Operating Savings")
        _values.append(f"${total_other_savings:,.0f}")
_metrics.append("Net Annual Savings")
_values.append(f"${net_savings:,.0f}")
_metrics.append("Estimated Payback Period")
_values.append(pb)
_metrics.append("Return On Investment (%)")
_values.append(f"{roi_pct:.1f}%")

if st.session_state.get("include_other", False):
    _metrics.append(f"Customer Break-Even Price — Chemical Savings Only (Per {mass_unit})")
    _values.append(f"${break_even_price_chem:.2f}")
    _metrics.append(f"Customer Break-Even Price — Total All Savings (Per {mass_unit})")
    _values.append(f"${break_even_price:.2f}")
else:
    _metrics.append(f"Customer Break-Even Price Per {mass_unit}")
    _values.append(f"${break_even_price:.2f}")

_metrics += [
    f"Distributor Landed Cost Per {mass_unit} (Your Price + Freight)",
    "Distributor Margin Room At Customer Break-Even",
]
_values += [
    f"${distributor_landed_cost:.2f}",
    f"${max(0, break_even_price - distributor_landed_cost):.2f}",
]
df_summary = pd.DataFrame({"Metric": _metrics, "Value": _values})
st.dataframe(df_summary, use_container_width=True, hide_index=True,
             height=(len(df_summary) + 1) * 35 + 3)

st.info("**Dosing Per TDS:** AlkaBoost™ = 10% by weight of the NaOH in the use solution.")

# Distributor Margin
with st.expander("🔍 Distributor Margin Analysis"):
    st.write(f"Your Price To Distributor: **${your_price_to_dist:.2f}** per {mass_unit}")
    st.write(f"Freight: **${freight_per_lb:.2f}** per {mass_unit}")
    st.write(f"**Distributor Landed Cost:** ${distributor_landed_cost:.2f} per {mass_unit}")
    if st.session_state.get("include_other", False):
        st.write(f"**Customer Break-Even Price (Total All Savings):** ${break_even_price:.2f} per {mass_unit}")
    else:
        st.write(f"**Customer Break-Even Price (Chemical Savings):** ${break_even_price_chem:.2f} per {mass_unit}")
    if additive_annual > 0:
        margin_room = max(0, break_even_price - distributor_landed_cost)
        st.success(f"**Distributor has up to ${margin_room:.2f} per {mass_unit} of potential margin to negotiate**")
    else:
        st.warning("No additive volume calculated.")

# ====================== LEAD CAPTURE + DOWNLOADS ======================
st.divider()
st.subheader("📩 Save Your Results")
st.caption("Enter your info below to unlock the PDF report, CSV download, and email link.")

lc1, lc2 = st.columns(2)
with lc1:
    lead_name  = st.text_input("Your Name *",     placeholder="Jane Smith")
    lead_email = st.text_input("Email Address *", placeholder="jane@company.com")
with lc2:
    lead_company = st.text_input("Company / Facility Name *", placeholder="ABC Foods Inc.")
    lead_phone   = st.text_input("Phone Number *",  placeholder="(555) 123-4567")

lead_complete = all([lead_name.strip(), lead_company.strip(),
                     lead_email.strip(), lead_phone.strip()])

def create_pdf_report(l_name="", l_company="", l_email="", l_phone=""):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    _, height = letter

    c.setFont("Helvetica-Bold", 20)
    c.drawString(50, height - 55, "AlkaBoost™ CIP Savings Report")
    c.setFont("Helvetica", 10)
    c.drawString(50, height - 75,
                 f"Location: {location}  |  Units: {units}  |  Generated: {pd.Timestamp.now().strftime('%Y-%m-%d')}")
    if l_company or l_name:
        c.setFont("Helvetica-Bold", 10)
        c.drawString(50, height - 95, f"Prepared For: {l_name}  —  {l_company}")
    if l_email or l_phone:
        c.setFont("Helvetica", 10)
        c.drawString(50, height - 112, f"Contact: {l_email}  |  {l_phone}")

    y = height - 145
    for _, row in df_summary.iterrows():
        c.setFont("Helvetica", 10)
        c.drawString(50, y, f"{row['Metric']}: {row['Value']}")
        y -= 22
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

if not lead_complete:
    st.info("Complete all four fields above to unlock the Download, Save, and Email buttons.")
else:
    pdf_bytes = create_pdf_report(lead_name, lead_company, lead_email, lead_phone)
    csv_bytes = df_summary.to_csv(index=False).encode()

    bc1, bc2, bc3 = st.columns(3)
    with bc1:
        st.download_button("📥 Download (CSV)", csv_bytes,
                           "AlkaBoost_Savings_Report.csv", "text/csv")
    with bc2:
        st.download_button("📄 Save Report (PDF)", pdf_bytes,
                           "AlkaBoost_CIP_Savings_Report.pdf", "application/pdf")
    with bc3:
        st.download_button("📧 Email (PDF)", pdf_bytes,
                           "AlkaBoost_CIP_Savings_Report.pdf", "application/pdf")
        subj = urllib.parse.quote(f"AlkaBoost™ CIP Savings Report — {lead_company}")
        body = urllib.parse.quote(
            f"Dear {lead_name},\n\nPlease find attached your AlkaBoost™ CIP Savings Report.\n\n"
            f"Key Results:\n"
            f"  • Net Annual Savings: ${net_savings:,.0f}\n"
            f"  • Caustic Cost Reduction: {naoh_cost_reduction_pct:.1f}%\n"
            f"  • Estimated Payback: {pb}\n\n"
            f"Best regards,\nIG Chemical Solutions"
        )
        st.markdown(
            f'<small><a href="mailto:{lead_email}?subject={subj}&body={body}" target="_blank">'
            f'📬 Click to open email client (then attach PDF)</a></small>',
            unsafe_allow_html=True
        )

# ====================== DISCLAIMER ======================
st.divider()
st.caption(
    "Disclaimer: Figures and calculations in this tool are based on general industry assumptions, "
    "the most recently available market data, and manufacturer-recommended dosing rates per the "
    "AlkaBoost™ Technical Data Sheet (TDS). Results are estimates only and may vary based on your "
    "specific process conditions, product concentrations, and supplier pricing. "
    "Consult your IG Chemical Solutions distributor for a more accurate, site-specific analysis."
)
