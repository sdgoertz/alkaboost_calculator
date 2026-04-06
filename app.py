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
    </style>
""", unsafe_allow_html=True)

# LOGO - save as "logo.png" in the same folder as this script for full branding
logo_path = "logo.png"
if os.path.exists(logo_path):
    st.image(logo_path, width=420)
else:
    st.warning("👉 Please save the IG Chemical Solutions logo as **logo.png** in the same folder as this script for full branding.")

st.markdown('<h1 class="main-header">IG Chemical Solutions</h1>', unsafe_allow_html=True)
st.markdown('<p class="tagline">A New Element in Chemistry • AlkaBoost™ CIP Additive Cost-Savings Calculator</p>', unsafe_allow_html=True)
st.caption("Built from the official TDS • Comprehensive operating-cost model • Works for any industry (edible oil, sugar, chicken processing, canning, etc.)")

# ====================== SIDEBAR INPUTS ======================
with st.sidebar:
    st.header("📍 Location & Units")
    location = st.selectbox("Customer Location (auto-fills NaOH market price)",
                            ["United States (Domestic)", "Mexico", "Other / Custom"])
    units = st.radio("Units System", ["Imperial (lb, gal, °F, USD)", "Metric (kg, L, °C, USD)"], horizontal=True)

    is_imperial = units.startswith("Imperial")
    density_factor = 8.34 if is_imperial else 1.0          # lb/gal or kg/L for dilute solutions
    vol_unit = "gal" if is_imperial else "L"
    mass_unit = "lb" if is_imperial else "kg"
    temp_unit = "°F" if is_imperial else "°C"

    # NaOH price auto-fill based on location (April 2026 market averages for 50% liquid caustic delivered)
    if location == "United States (Domestic)":
        naoh_default = 0.60
    elif location == "Mexico":
        naoh_default = 0.72   # slight premium for logistics/import
    else:
        naoh_default = 0.65
    st.caption("💡 Auto-filled NaOH price reflects current market averages (override below with your customer's actual contract price)")

    st.subheader("Production Data")
    cycles_per_year = st.number_input("CIP cycles per year", value=730, min_value=1, step=1)
    solution_volume = st.number_input(f"Cleaning solution volume per CIP ({vol_unit})", value=5000.0, min_value=100.0)

    st.subheader("Caustic & Cycle Parameters")
    baseline_naoh_pct = st.number_input("Baseline NaOH concentration (%)", value=5.0, min_value=0.5, step=0.1)
    naoh_reduction_factor = st.slider("NaOH reduction with AlkaBoost™ (your 30% rule of thumb)", 0.5, 1.0, 0.70, step=0.01)
    cycle_reduction_pct = st.slider("Reduction in CIP frequency (%)", 0, 50, 0, step=1)
    water_reduction_per_cycle_pct = st.slider("Additional water/rinse reduction per CIP (%)", 0, 30, 0, step=1)

    st.subheader("AlkaBoost™ Pricing (Distributor View)")
    packaging = st.selectbox("Your packaging to distributor",
                             ["55-gal drums", "275/330 gal totes", "Bulk (>20K lbs)", "Custom"])
    your_prices = {"55-gal drums": 2.15, "275/330 gal totes": 1.85, "Bulk (>20K lbs)": 1.65, "Custom": 0.0}
    your_price_to_dist = your_prices[packaging] if packaging != "Custom" else st.number_input("Your custom price to distributor ($/lb or $/kg)", value=2.15, step=0.01)
    freight_per_lb = st.number_input("Estimated freight to distributor/customer site ($ per lb or kg)", value=0.15 if location == "Mexico" else 0.0, step=0.01)
    distributor_landed_cost = your_price_to_dist + freight_per_lb

    st.subheader("Customer-Facing Additive Price")
    additive_price = st.number_input(f"Customer quoted AlkaBoost™ price per {mass_unit}", value=2.50, min_value=0.0, step=0.01)

    st.subheader("Costs & Other Savings")
    naoh_price = st.number_input(f"NaOH price per {mass_unit} (auto-filled above)", value=naoh_default, step=0.01)
    energy_cost_per_cycle = st.number_input("Baseline energy cost per CIP ($)", value=45.0, step=1.0)
    energy_savings_pct = st.slider("Energy savings % (lower temp/shorter time)", 0, 40, 15, step=5)
    water_cost_per_vol = st.number_input(f"Water + wastewater cost per {vol_unit}", value=0.012 if is_imperial else 0.0032, step=0.001)
    labor_cost_per_cycle = st.number_input("Labor + downtime cost per CIP ($)", value=120.0, step=5.0)
    maintenance_savings_per_year = st.number_input("Annual maintenance/equipment-life savings ($)", value=2500.0, step=100.0)
    other_chemical_savings_annual = st.number_input("Other chemical (acid/sanitizer) savings per year ($)", value=0.0, step=100.0)

# ====================== CALCULATIONS ======================
naoh_baseline_per_cycle = solution_volume * (baseline_naoh_pct / 100) * density_factor
naoh_with_per_cycle = solution_volume * (baseline_naoh_pct * naoh_reduction_factor / 100) * density_factor
additive_per_cycle = naoh_with_per_cycle * 0.10                     # 10% of NaOH weight per TDS

cycles_with = cycles_per_year * (1 - cycle_reduction_pct / 100)

naoh_baseline_annual = naoh_baseline_per_cycle * cycles_per_year
naoh_with_annual = naoh_with_per_cycle * cycles_with
additive_annual = additive_per_cycle * cycles_with

baseline_chemical_cost = naoh_baseline_annual * naoh_price
with_chemical_cost = naoh_with_annual * naoh_price + additive_annual * additive_price

# Water savings (frequency reduction + per-cycle reduction)
total_water_savings_annual = (
    solution_volume * water_cost_per_vol * cycles_per_year * (cycle_reduction_pct / 100) +
    solution_volume * water_cost_per_vol * cycles_with * (water_reduction_per_cycle_pct / 100)
)

energy_savings_annual = energy_cost_per_cycle * cycles_per_year * (energy_savings_pct / 100)
labor_savings_annual = labor_cost_per_cycle * cycles_per_year * (cycle_reduction_pct / 100)
total_other_savings = energy_savings_annual + total_water_savings_annual + labor_savings_annual + maintenance_savings_per_year + other_chemical_savings_annual

gross_savings = (baseline_chemical_cost - (naoh_with_annual * naoh_price)) + total_other_savings
additive_total_cost = additive_annual * additive_price
net_savings = gross_savings - additive_total_cost

if additive_annual > 0:
    break_even_price = gross_savings / additive_annual
else:
    break_even_price = 0

# ====================== DISPLAY ======================
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Baseline Annual NaOH Cost", f"${baseline_chemical_cost:,.0f}")
with col2:
    st.metric("With AlkaBoost™ Chemical Cost", f"${with_chemical_cost:,.0f}", delta=f"-${gross_savings:,.0f}")
with col3:
    st.metric("Net Annual Savings to Customer", f"${net_savings:,.0f}", delta_color="normal")
with col4:
    st.metric("Customer Break-Even Additive Price", f"${break_even_price:.2f}")

st.divider()

st.subheader("📊 Full Summary Table")
df_summary = pd.DataFrame({
    "Metric": [
        f"NaOH used per year (baseline) ({mass_unit})",
        f"NaOH used per year (with AlkaBoost™) ({mass_unit})",
        f"AlkaBoost™ used per year ({mass_unit})",
        "Gross caustic + operating savings",
        "Customer additive cost",
        "Net savings to customer",
        f"Customer break-even price per {mass_unit}",
        "Distributor landed cost per lb/kg (your price + freight)",
        "Distributor margin room at customer break-even"
    ],
    "Value": [
        f"{naoh_baseline_annual:,.0f}",
        f"{naoh_with_annual:,.0f}",
        f"{additive_annual:,.0f}",
        f"${gross_savings:,.0f}",
        f"${additive_total_cost:,.0f}",
        f"${net_savings:,.0f}",
        f"${break_even_price:.2f}",
        f"${distributor_landed_cost:.2f}",
        f"${max(0, break_even_price - distributor_landed_cost):.2f}"
    ]
})
st.dataframe(df_summary, use_container_width=True, hide_index=True)

st.info("**Dosing per TDS:** AlkaBoost™ = 10 % by weight of the NaOH in the use solution. All savings are annualized and fully customizable.")

# ====================== DISTRIBUTOR MARGIN EXPANDER ======================
with st.expander("🔍 Distributor Margin Analysis (your tiered pricing + freight)"):
    st.write(f"Your price to distributor: **${your_price_to_dist:.2f}** per {mass_unit} ({packaging})")
    st.write(f"Freight to site: **${freight_per_lb:.2f}** per {mass_unit}")
    st.write(f"**Distributor landed cost:** ${distributor_landed_cost:.2f}")
    st.write(f"**Maximum customer price they can charge while still delivering positive ROI:** ${break_even_price:.2f}")
    st.success(f"**Distributor has ${max(0, break_even_price - distributor_landed_cost):.2f} per {mass_unit} of margin room** (before their own operating costs)")

# ====================== DOWNLOADS ======================
csv = df_summary.to_csv(index=False).encode()
st.download_button("📥 Download results as CSV", csv, "AlkaBoost_Savings_Report.csv", "text/csv")


def create_pdf_report():
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    c.setFont("Helvetica-Bold", 20)
    c.drawString(50, height - 50, "IG Chemical Solutions – AlkaBoost™ CIP Savings Report")
    c.setFont("Helvetica", 12)
    c.drawString(50, height - 80, f"Location: {location} • Units: {units} • Generated: {pd.Timestamp.now().strftime('%Y-%m-%d')}")

    y = height - 130
    for i, row in df_summary.iterrows():
        c.drawString(50, y, f"{row['Metric']}: {row['Value']}")
        y -= 22
        if y < 100:
            c.showPage()
            y = height - 50

    c.setFont("Helvetica-Oblique", 10)
    c.drawString(50, 50, "Powered by the official AlkaBoost™ TDS • Comprehensive model includes chemicals, energy, water, labor, maintenance & freight")
    c.save()
    buffer.seek(0)
    return buffer


pdf_bytes = create_pdf_report()
st.download_button("📄 Save as Professional PDF Report",
                   data=pdf_bytes,
                   file_name="AlkaBoost_CIP_Savings_Report.pdf",
                   mime="application/pdf")

st.caption("✅ Fully branded • Handles US or Mexico freight • Auto NaOH pricing • Unlimited industries • Ready for your Mexico distributor")
