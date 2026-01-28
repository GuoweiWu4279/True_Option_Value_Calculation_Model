import streamlit as st
import pandas as pd
import json
import plotly.graph_objects as go
from calculation_engine import calculate_payout, ShareClass, UserEquity

# --- 1. Global Configuration & CSS Styling (UI Polish) ---
st.set_page_config(
    page_title="Equity Reality Check",
    page_icon="💸",
    layout="wide"
)

# Inject custom CSS to adjust font sizes, spacing, and UI elements
st.markdown("""
<style>
    /* Increase main title size and weight */
    h1 {
        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
        font-weight: 700;
        color: #FFFFFF;
    }
    /* Optimize the display style of Metrics */
    div[data-testid="stMetricValue"] {
        font-size: 28px;
        font-weight: bold;
    }
    /* Adjust Sidebar padding (Streamlit default spacing optimization) */
    .css-1d391kg {
        padding-top: 1rem;
    }
    /* Add a distinct background box for the status messages */
    .highlight-box {
        padding: 15px;
        border-radius: 10px;
        background-color: #1E1E1E;
        border: 1px solid #333;
        margin-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. Load Data ---
@st.cache_data
def load_benchmarks():
    try:
        with open('benchmarks.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

benchmarks = load_benchmarks()

# --- 3. Sidebar Configuration ---
st.sidebar.title("🔧 Configuration")

with st.sidebar.expander("1. Your Offer Details", expanded=True):
    my_shares = st.number_input("Number of Options", min_value=0, value=10000, step=100)
    strike_price = st.number_input("Strike Price ($)", min_value=0.0, value=0.5, step=0.01)

with st.sidebar.expander("2. Company & Dilution", expanded=True):
    current_total_shares = st.number_input("Current Fully Diluted Shares", min_value=1, value=10000000)
    
    dilution_pct = st.slider(
        "Est. Future Dilution (%)", 
        0, 80, 20, 5,
        help="Anticipated dilution from future fundraising rounds."
    )
    
    diluted_total_shares = current_total_shares / (1 - (dilution_pct / 100))
    current_ownership = (my_shares / current_total_shares) * 100
    diluted_ownership = (my_shares / diluted_total_shares) * 100
    
    st.caption(f"Ownership Impact: {current_ownership:.3f}% ➝ {diluted_ownership:.3f}%")

with st.sidebar.expander("3. Liquidation Terms", expanded=True):
    scenario = st.selectbox(
        "Market Environment",
        options=list(benchmarks.keys()) if benchmarks else ["Market Standard", "Distressed"]
    )
    round_stage = st.selectbox("Latest Round", ["Series A", "Series B", "Series C"])
    
    # Auto-fill logic based on selected scenario
    defaults = benchmarks.get(scenario, {}).get(round_stage, {})
    total_raised = st.number_input("Total Capital Raised ($)", min_value=0, value=20000000, step=1000000, format="%d")
    
    # The 'key' argument forces a refresh of the input value when the scenario changes
    liq_multiple = st.number_input(
        "Liquidation Multiple", 
        min_value=0.0, 
        value=float(defaults.get("liquidation_multiple", 1.0)), 
        step=0.1,
        key=f"liq_mult_{scenario}_{round_stage}" 
    )
    
    is_participating = st.checkbox(
        "Participating Preferred?", 
        value=defaults.get("participation", False),
        key=f"part_{scenario}_{round_stage}"
    )

# --- 4. Core Logic Calculation ---

investor_stack = [
    ShareClass("Aggregate Investors", total_raised, liq_multiple, is_participating)
]
user_equity_obj = UserEquity(my_shares, strike_price)

# Calculate Breakeven Point
pref_total = total_raised * liq_multiple
breakeven_val = pref_total + (strike_price * diluted_total_shares)

# --- 5. Main Dashboard Interface ---

st.title("💸 Equity Reality Check")
st.markdown("### The true value of your stock options")
st.markdown("Use this tool to verify if your options are worth anything under different exit scenarios.")

# Top Key Metrics Bar
col1, col2, col3 = st.columns(3)
col1.metric("💸 Liquidation Preference", f"${pref_total:,.0f}", help="Money investors take FIRST before you get anything.")
col2.metric("⚖️ Breakeven Valuation", f"${breakeven_val:,.0f}", help="Company MUST sell for at least this amount for you to profit.")
col3.metric("📉 Your Diluted Stake", f"{diluted_ownership:.4f}%")

st.divider()

# --- 6. Interactive Slider (Comparison Fix) ---

# [CRITICAL FIX]: No longer using dynamic values for the slider.
# We use st.session_state to remember the user's last slider position.
# If the user hasn't dragged it yet, default to a fixed initial value (e.g., 3x Capital Raised).
if 'slider_val' not in st.session_state:
    st.session_state.slider_val = int(total_raised * 3)

def update_slider():
    st.session_state.slider_val = st.session_state.slider_key

max_sim_value = max(int(total_raised * 10), int(breakeven_val * 2))

st.markdown("#### 🏗️ Simulate Exit Valuation")
exit_val = st.slider(
    "Drag to simulate: How much is the company sold for?", 
    min_value=0, 
    max_value=max_sim_value, 
    value=st.session_state.slider_val, # Use Session State to keep position fixed
    step=1000000,
    format="$%d",
    key="slider_key",
    on_change=update_slider
)

# Real-time Calculation
result = calculate_payout(exit_val, investor_stack, diluted_total_shares, user_equity_obj)

# Result Display Area (Enhanced color contrast)
c1, c2 = st.columns([2, 1])

with c1:
    if result == 0:
        st.markdown(
            f"""
            <div style="padding: 20px; background-color: rgba(255, 75, 75, 0.1); border-left: 5px solid #ff4b4b; border-radius: 5px;">
                <h3 style="color: #ff4b4b; margin:0;">🛑 UNDERWATER ($0)</h3>
                <p style="margin:0;">At a <b>${exit_val:,.0f}</b> exit, liquidation preferences eat up all the cash. You get nothing.</p>
            </div>
            """, unsafe_allow_html=True
        )
    else:
        st.markdown(
            f"""
            <div style="padding: 20px; background-color: rgba(0, 204, 150, 0.1); border-left: 5px solid #00cc96; border-radius: 5px;">
                <h3 style="color: #00cc96; margin:0;">✅ PROFITABLE</h3>
                <p style="margin:0;">If the company sells for <b>${exit_val:,.0f}</b>, you are in the money.</p>
            </div>
            """, unsafe_allow_html=True
        )

with c2:
    # Large Net Profit Metric
    st.metric("💰 Your Net Profit (Pre-tax)", f"${result:,.0f}")

# --- 7. Chart Visualization Area ---
st.subheader("📊 Profitability Zones")

x_values = list(range(0, max_sim_value, int(max_sim_value / 100)))
y_values = []
for val in x_values:
    y_values.append(calculate_payout(val, investor_stack, diluted_total_shares, user_equity_obj))

fig = go.Figure()
fig.add_trace(go.Scatter(
    x=x_values, y=y_values,
    mode='lines',
    name='Net Profit',
    line=dict(color='white', width=2),
    fill='tozeroy',
    fillgradient=dict(
        type='horizontal',
        colorscale=[[0, 'rgba(255,0,0,0.2)'], [breakeven_val/max_sim_value, 'rgba(255,0,0,0.2)'], [breakeven_val/max_sim_value, 'rgba(0,204,150,0.4)'], [1, 'rgba(0,204,150,0.6)']]
    )
))
fig.add_vline(x=breakeven_val, line_dash="dash", line_color="yellow", annotation_text="Breakeven")
fig.add_vline(x=exit_val, line_dash="dot", line_color="white", annotation_text="Current")
fig.update_layout(
    xaxis_title="Exit Valuation ($)", 
    yaxis_title="Your Net Profit ($)", 
    template="plotly_dark", 
    height=400,
    margin=dict(l=20, r=20, t=40, b=20)
)
st.plotly_chart(fig, use_container_width=True)

# --- 8. Educational Mechanics & Methodology ---
st.markdown("---")
with st.expander("📚 Knowledge Base: Mechanics, Dilution & Data Sources"):
    st.markdown("""
    ### 1. The "Waterfall" Logic (Liquidation Preference)
    Startup exits are not a simple pie-splitting contest. They follow a strict "Payment Waterfall":
    * **Tier 1 - Investors (The Hurdle):** Investors with "Preferred Stock" get paid first. A **1x Liquidation Preference** means they must get their original investment back before Common Stock sees a dime. A **2x Preference** means they take double their money first.
    * **Tier 2 - Common Stock (You):** Employees and Founders split whatever cash is *remaining*. If the exit value is lower than the investor payout (the "Overhang"), your shares are mathematically worth $0.

    ### 2. The Dilution Trajectory (Why your slice shrinks)
    The ownership % you see in your Offer Letter is **not** what you will have at the exit.
    * **Future Rounds:** A company typically goes through Series A, B, C, D, etc. Each new round issues new shares, diluting existing shareholders by typically **15-25% per round**[cite: 142].
    * **The Option Pool Shuffle:** Investors often require the company to expand the employee option pool *before* they invest. This dilution usually hits existing shareholders (you) the hardest.
    * *How this tool handles it:* The "Est. Future Dilution" slider allows you to factor in these future rounds to see your *real* ownership at exit.

    ### 3. Data Sources
    The baseline scenarios ("Market Standard" vs. "Distressed") are derived from aggregated venture capital market reports, specifically:
    * **Fenwick & West** Silicon Valley Venture Capital Surveys[cite: 124].
    * **Carta** State of Private Markets Reports[cite: 138].
    * *Note:* "Distressed" scenarios simulate the rise of structured terms (higher multiples) seen in down-markets.
    """)

# --- 9. Legal Disclaimer (Strict & Professional) ---
st.markdown("---")
st.warning("""
**⚠️ LEGAL DISCLAIMER: FOR EDUCATIONAL PURPOSES ONLY**

This application is a simulation tool designed solely for informational purposes to illustrate financial concepts. **It does not constitute legal, tax, financial, or investment advice.**

* **No Fiduciary Relationship:** The creators of this tool are not Registered Investment Advisors (RIA), tax professionals, or attorneys.
* **Estimation Only:** Private market valuations, term sheets, and tax implications (such as AMT) are complex and opaque. Actual financial outcomes will vary significantly based on your company's specific contract terms and prevailing market conditions.
* **Independent Verification Required:** You should consult with qualified professionals (CPA, Tax Attorney, or Financial Advisor) before making any decisions regarding your stock options, including exercising options or secondary sales.
* **Liability:** The creators assume no liability for any financial losses, damages, or adverse tax consequences resulting from the use of this tool.
""")