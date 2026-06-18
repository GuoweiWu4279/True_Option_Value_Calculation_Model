"""
True Option Value — a startup-equity reality-check engine.

What it answers: not "what could my equity be worth" (the optimistic number on your offer letter) but
"across the realistic distribution of exits, what is it worth in expectation, how likely is zero, and
could the tax bill exceed the payout?"

Every control on this page feeds a number that is actually computed. The math lives in the `tov`
package and is covered by a golden-test suite (tests/run_all.py). See README.md for assumptions.

Run:  streamlit run app.py
"""

import json
import os

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from tov import benchmarks, reverse, tax
from tov import montecarlo as mc
from tov.waterfall import PreferredRound, CapTable, distribute, option_payoff, breakeven_valuation

st.set_page_config(page_title="True Option Value", page_icon="📊", layout="wide")

st.markdown("""
<style>
    html, body, [class*="css"] { font-family: 'Inter','Helvetica Neue',Helvetica,Arial,sans-serif; }
    h1 { font-size: 2.4rem !important; font-weight: 700; }
    div[data-testid="stMetricValue"] { font-size: 24px !important; font-weight: 600; }
    div[data-testid="stMetricLabel"] { font-size: 13px !important; color: #9E9E9E; }
    .box { padding: 18px 20px; border-radius: 8px; margin: 6px 0; }
    .box-bad  { background: rgba(255,75,75,0.10);  border-left: 5px solid #ff4b4b; }
    .box-warn { background: rgba(255,193,7,0.10);   border-left: 5px solid #ffc107; }
    .box-good { background: rgba(0,204,150,0.10);    border-left: 5px solid #00cc96; }
    .box-t { font-size: 18px; font-weight: 700; margin-bottom: 6px; }
    .box-p { font-size: 15px; line-height: 1.5; margin: 0; }
</style>
""", unsafe_allow_html=True)


def money(x):
    return f"${x:,.0f}"


def compact(x):
    if x >= 1e6:
        return f"${x/1e6:.1f}M"
    if x >= 1e3:
        return f"${x/1e3:.0f}K"
    return f"${x:.0f}"


# ============================== SIDEBAR: INPUTS ==============================
st.sidebar.title("🔧 Your situation")

with st.sidebar.expander("1 · Your option grant", expanded=True):
    my_shares = st.number_input("Number of options", min_value=0, value=50_000, step=1_000)
    strike = st.number_input("Strike price ($/share)", min_value=0.0, value=1.00, step=0.05)
    option_type = st.radio("Option type", ["ISO", "NSO"], horizontal=True,
                           help="ISOs can trigger AMT if you exercise and hold. NSOs are taxed as "
                                "ordinary income on the spread at exercise.")
    fmv_now = st.number_input("Current 409A / share price ($)", min_value=0.0, value=4.00, step=0.25,
                              help="Fair market value per share today — used for the AMT bargain "
                                   "element if you exercise ISOs and hold.")

with st.sidebar.expander("2 · Company & cap table", expanded=True):
    regime_labels = benchmarks.labels()
    regime_key = st.selectbox("Market regime (fills term defaults)",
                              options=list(regime_labels.keys()),
                              format_func=lambda k: regime_labels[k])
    stage = st.selectbox("Latest round raised", ["Series A", "Series B", "Series C"])
    bench = benchmarks.get(regime_key, stage)
    st.caption(bench["note"])

    total_raised = st.number_input("Total capital raised ($)", min_value=0, value=40_000_000,
                                   step=1_000_000, format="%d")
    post_money = st.number_input("Last post-money valuation ($)", min_value=1, value=150_000_000,
                                 step=5_000_000, format="%d",
                                 help="From the last round announcement. Anchors the exit model.")

    # Fully-diluted shares: reverse-solve from price if available, else direct input.
    share_src = st.radio("Fully-diluted shares from…", ["Enter directly", "Derive from price/share"],
                         horizontal=False)
    if share_src == "Derive from price/share":
        pps = st.number_input("Last round price per share ($)", min_value=0.01, value=15.00, step=0.5)
        fd_shares = reverse.fd_shares_from_post_money(post_money, pps) or 10_000_000
        st.caption(f"Implied fully-diluted shares: {fd_shares:,.0f}")
    else:
        fd_shares = st.number_input("Current fully-diluted shares", min_value=1, value=10_000_000,
                                    step=100_000)

    advanced = st.toggle("Advanced: model the preference stack round-by-round", value=False)

with st.sidebar.expander("3 · Future dilution", expanded=False):
    future_rounds = st.slider("Future rounds before exit", 0, 4, 1,
                              help="Each future raise issues new shares and dilutes you.")
    dilution_each = st.slider("Dilution per future round (%)", 0, 40,
                              int(bench["dilution"] * 100), 1) / 100.0
    diluted_fd = reverse.dilute(fd_shares, dilution_each, future_rounds)
    cur_own = reverse.ownership_pct(my_shares, fd_shares)
    dil_own = reverse.ownership_pct(my_shares, diluted_fd)
    st.caption(f"Your stake: {cur_own:.4f}% ➝ {dil_own:.4f}% after {future_rounds} round(s)")

with st.sidebar.expander("4 · Taxes (federal + state estimate)", expanded=False):
    status = st.radio("Filing status", ["single", "mfj"], horizontal=True,
                      format_func=lambda s: "Single" if s == "single" else "Married (joint)")
    state = st.radio("State", ["CA", "none"], horizontal=True,
                     format_func=lambda s: "California" if s == "CA" else "No state tax",
                     help="California adds a 7% AMT, taxes gains as ordinary income (no LTCG break), "
                          "and does NOT recognize QSBS.")
    ordinary_income = st.number_input("Your other ordinary income ($)", min_value=0,
                                      value=180_000, step=10_000)
    if option_type == "ISO":
        exit_strategy = st.radio(
            "Exercise / sale strategy",
            ["Sell at exit (disqualifying → ordinary)", "Exercise early & hold (AMT now → LTCG later)"],
        )
        iso_hold = exit_strategy.startswith("Exercise early")
    else:
        st.caption("NSOs: the spread at exercise is ordinary income.")
        iso_hold = False
    treatment = "ltcg" if (option_type == "ISO" and iso_hold) else "ordinary"

    qsbs = None
    if treatment == "ltcg":
        if st.checkbox("Shares may qualify for QSBS (§1202)", value=False,
                       help="Federal exclusion on Qualified Small Business Stock held >5 years "
                            "(company <$75M gross assets at issuance). California does NOT conform."):
            era = st.radio("When were the shares acquired?",
                           ["pre_jul2025", "post_jul2025"],
                           format_func=lambda e: "Before Jul 5, 2025 (legacy)" if e == "pre_jul2025"
                           else "After Jul 4, 2025 (OBBBA tiers)")
            yrs = st.slider("Years you'll have held at sale", 0, 7, 5)
            qsbs = {"eligible": True, "era": era, "years": yrs, "basis": my_shares * strike}

with st.sidebar.expander("5 · Exit outlook (drives the distribution)", expanded=False):
    dist_mode = st.radio("Distribution", ["Calibrated to stage (data-anchored)", "Manual"],
                         help="Calibrated presets reproduce Correlation Ventures' published venture "
                              "outcome shape (~65% exit below 1×, ~4% above 10×).")
    if dist_mode.startswith("Calibrated"):
        eo = benchmarks.exit_outcomes(stage)
        p_fail = eo["p_fail"]
        median_mult = eo["survivor_median_multiple"]
        sigma = eo["sigma"]
        fail_ceiling = eo["fail_ceiling"]
        st.caption(f"**{stage}** preset → P(fail)={p_fail:.0%}, median survivor {median_mult:.1f}×, σ={sigma:.1f}. "
                   "Calibrated to published venture outcomes; failure rate falls at later stages.")
    else:
        preset = st.select_slider("Outlook", ["Bleak", "Conservative", "Base", "Optimistic"],
                                  value="Conservative")
        presets = {
            "Bleak":        dict(p_fail=0.75, median=1.0, sigma=0.9),
            "Conservative": dict(p_fail=0.60, median=1.8, sigma=1.0),
            "Base":         dict(p_fail=0.45, median=2.8, sigma=1.1),
            "Optimistic":   dict(p_fail=0.30, median=4.0, sigma=1.2),
        }
        pr = presets[preset]
        p_fail = st.slider("P(failure / fire-sale)", 0.0, 0.95, pr["p_fail"], 0.05)
        median_mult = st.slider("Median survivor exit (× current valuation)", 0.5, 10.0, pr["median"], 0.1)
        sigma = st.slider("Upside dispersion (σ)", 0.3, 2.0, pr["sigma"], 0.1)
        fail_ceiling = 0.25
        st.caption("Most startups exit below their last valuation; a few return many multiples. "
                   "Tune these to your own conviction.")


# ============================== BUILD THE CAP TABLE ==============================
if advanced:
    st.sidebar.markdown("---")
    st.sidebar.markdown("**Preference stack** (senior = paid first)")
    n_rounds = st.sidebar.number_input("How many preferred rounds?", 1, 4, 2)
    rounds = []
    remaining_pref_shares = max(0.0, diluted_fd * bench["investor_ownership_pct"])
    for i in range(int(n_rounds)):
        with st.sidebar.expander(f"Round {i+1}", expanded=(i == 0)):
            nm = st.text_input("Name", value=["Series A", "Series B", "Series C", "Series D"][i],
                               key=f"nm{i}")
            inv = st.number_input("Invested ($)", min_value=0,
                                  value=int(total_raised / n_rounds), step=1_000_000, key=f"inv{i}")
            mult = st.number_input("Liquidation multiple (×)", 0.0, 5.0,
                                   float(bench["liquidation_multiple"]), 0.5, key=f"mult{i}")
            sen = st.number_input("Seniority (0 = most senior)", 0, 9, i, key=f"sen{i}")
            part = st.checkbox("Participating?", value=bench["participating"], key=f"part{i}")
            capm = st.number_input("Participation cap (× invested, 0 = none)", 0.0, 5.0,
                                   float(bench["participation_cap"] or 0.0), 0.5, key=f"cap{i}")
            shr = st.number_input("As-converted shares", min_value=0,
                                  value=int(remaining_pref_shares / n_rounds), step=100_000,
                                  key=f"shr{i}")
            rounds.append(PreferredRound(nm, inv, mult, int(sen), part,
                                         (capm if capm > 0 else None), shr))
    pref_shares_total = sum(r.as_converted_shares for r in rounds)
    common_shares = max(1.0, diluted_fd - pref_shares_total)
    cap = CapTable(rounds, common_shares)
else:
    io = bench["investor_ownership_pct"]
    pref_shares_total = diluted_fd * io
    common_shares = max(1.0, diluted_fd - pref_shares_total)
    cap = CapTable([PreferredRound(
        "Aggregate investors", total_raised, bench["liquidation_multiple"], 0,
        bench["participating"], bench["participation_cap"], pref_shares_total)], common_shares)


# ============================== DERIVED QUANTITIES ==============================
overhang = cap.total_preference
breakeven = breakeven_valuation(cap, my_shares, strike)
naive_value = reverse.naive_paper_value(my_shares, strike, post_money / fd_shares)
bargain = max(0.0, (fmv_now - strike)) * my_shares
amt = tax.combined_amt_on_iso_exercise(ordinary_income, status, bargain, state) \
    if treatment == "ltcg" else None


def after_tax(pre_tax_payoff):
    return tax.combined_exit_tax(pre_tax_payoff, ordinary_income, status, treatment,
                                 state=state, qsbs=qsbs)["net"]


sim = mc.simulate(cap, my_shares, strike, v0=float(post_money),
                  p_fail=p_fail, survivor_median_multiple=median_mult, sigma=sigma,
                  fail_ceiling=fail_ceiling, tax_fn=after_tax, n=40_000)
amt_cost = amt["total"] if amt else 0.0
ev_net_of_amt = max(0.0, sim["expected_value"] - amt_cost)


# ============================== MAIN: HEADER ==============================
st.title("📊 True Option Value")
st.markdown("#### What your startup equity is *actually* worth — after preferences, dilution, and tax")

m1, m2, m3, m4 = st.columns(4)
m1.metric("💸 Liquidation overhang", money(overhang),
          help="Investors are paid this much before common sees a dollar.")
m2.metric("⚖️ Breakeven exit", money(breakeven) if breakeven else "Never",
          help="The company must sell for at least this for your options to clear their strike.")
m3.metric("📉 Your diluted stake", f"{dil_own:.4f}%")
m4.metric("🧾 'Offer letter' value", money(naive_value),
          help="The naive number: your shares × last share price. Compare it to the expected value below.")

st.markdown("---")

# ============================== SECTION: THE VALUE (headline) ==============================
st.subheader("🎯 The number that matters: expected value, not the brochure value")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Expected value (after-tax)", money(sim["expected_value"]),
          help="Probability-weighted take-home across all simulated exits. This is the 'option value'.")
c2.metric("P(worth ~nothing)", f"{sim['prob_zero']*100:.0f}%",
          help="Share of simulated exits where your options net essentially zero.")
c3.metric("Median outcome (P50)", money(sim["p50"]))
c4.metric("Upside (P90)", money(sim["p90"]))

naive_vs_ev = (sim["expected_value"] / naive_value) if naive_value > 0 else 0
if naive_value > 0:
    st.markdown(
        f"""<div class="box box-warn"><div class="box-t">Reality discount</div>
        <p class="box-p">Your offer letter implies <b>{money(naive_value)}</b>. After the waterfall,
        dilution, a <b>{sim['prob_zero']*100:.0f}%</b> chance of zero, and tax, the probability-weighted
        value is <b>{money(sim['expected_value'])}</b> — about <b>{naive_vs_ev*100:.0f}%</b> of the
        headline. Worst-case decile (CVaR&nbsp;10%): <b>{money(sim['cvar_10'])}</b>.</p></div>""",
        unsafe_allow_html=True)

# Outcome-probability buckets — far more legible than a raw histogram of a heavy-tailed payoff.
payoffs = sim["payoffs"]
hi = max(float(np.percentile(payoffs, 95)), 1.0)
cuts = np.linspace(0, hi, 6)[1:]            # five upper edges from hi/5 .. P95
labels = ["$0 (worthless)"]
probs = [float((payoffs <= 1.0).mean())]
colors = ["#ff4b4b"]
lo = 1.0
for c in cuts:
    probs.append(float(((payoffs > lo) & (payoffs <= c)).mean()))
    labels.append(f"≤ {compact(c)}")
    colors.append("#00cc96")
    lo = c
probs.append(float((payoffs > hi).mean()))
labels.append(f"> {compact(hi)}")
colors.append("#00e6a8")

fig_hist = go.Figure(go.Bar(
    x=[p * 100 for p in probs], y=labels, orientation="h",
    marker_color=colors,
    text=[f"{p*100:.0f}%" for p in probs], textposition="outside",
    cliponaxis=False,
))
fig_hist.update_layout(
    template="plotly_dark", height=320, bargap=0.25,
    xaxis_title="Probability of this take-home outcome (%)",
    yaxis=dict(autorange="reversed"),
    margin=dict(l=10, r=30, t=20, b=30),
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
)
st.plotly_chart(fig_hist, width="stretch")
st.caption(f"Read it as: **{sim['prob_zero']*100:.0f}%** of simulated exits leave you with essentially "
           f"nothing; the green bars are the chance of each upside band. Expected (probability-weighted) "
           f"take-home: **\\${sim['expected_value']:,.0f}**.")

st.markdown("---")

# ============================== SECTION: PAYOFF DIAGRAM ==============================
st.subheader("📈 Payoff vs. exit valuation — and the gap from what you were told")

# Focus the x-axis on where the curve actually bends (breakeven + the conversion kink), not the
# Monte Carlo's far tail — otherwise the interesting shape is compressed into an invisible sliver.
chart_max = max(post_money * 2.0, (breakeven or 0) * 2.5, overhang * 2.5, 1.0)
xs, ys = mc.payoff_curve(cap, my_shares, strike, chart_max, n_points=400)
naive_line = np.maximum(0.0, dil_own / 100.0 * xs - my_shares * strike)

fig = go.Figure()
fig.add_trace(go.Scatter(x=xs, y=naive_line, mode="lines", name="'Offer letter' (naive % × exit)",
                         line=dict(color="#888", width=1.5, dash="dot")))
fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", name="True payoff (after waterfall)",
                         line=dict(color="#00cc96", width=2.5), fill="tozeroy",
                         fillcolor="rgba(0,204,150,0.12)"))
if breakeven:
    fig.add_vline(x=breakeven, line_dash="dash", line_color="#ffc107",
                  annotation_text="Breakeven")
fig.add_vline(x=post_money, line_dash="dot", line_color="white", annotation_text="Last valuation")
fig.update_layout(template="plotly_dark", height=420, xaxis_title="Exit valuation ($)",
                  yaxis_title="Your net payoff ($)", margin=dict(l=20, r=20, t=30, b=20),
                  paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                  legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0))
st.plotly_chart(fig, width="stretch")
st.caption("The dotted grey line is the linear story your offer letter tells. The solid line is the "
           "waterfall reality: flat at zero until the overhang clears, then bending as preferred "
           "converts. The space between them is the information asymmetry this tool exists to close.")

# ============================== SECTION: AMT TRAP ==============================
if treatment == "ltcg":
    st.markdown("---")
    st.subheader("🧨 The AMT trap")
    eff = (amt_cost / bargain * 100) if bargain > 0 else 0
    a1, a2, a3 = st.columns(3)
    a1.metric("Bargain element", money(bargain), help="(409A − strike) × shares, taxed under AMT.")
    a2.metric("Est. AMT due at exercise", money(amt_cost),
              help=f"~{eff:.0f}% of the bargain element. Federal {money(amt['federal'])}"
                   + (f" + California {money(amt['state'])}." if state == "CA" else "."))
    a3.metric("Expected value net of AMT", money(ev_net_of_amt))
    if state == "CA" and amt["state"] > 0:
        st.caption(f"Breakdown: federal AMT **\\${amt['federal']:,.0f}** + California AMT "
                   f"**\\${amt['state']:,.0f}** = **\\${amt_cost:,.0f}**, all due the year you exercise.")
    if amt_cost > sim["p10"] and amt_cost > 0:
        st.markdown(
            f"""<div class="box box-bad"><div class="box-t">🛑 AMT exceeds your downside</div>
            <p class="box-p">You would owe the IRS{' and California' if state == 'CA' else ''}
            <b>{money(amt_cost)}</b> the year you exercise — more than the <b>{money(sim['p10'])}</b>
            your equity is worth in the bottom 10% of outcomes. If the company underperforms, you can
            pay more tax than the stock ever returns. This is exactly how employees end up underwater
            on a 'winning' offer.</p></div>""",
            unsafe_allow_html=True)
    else:
        st.markdown(
            f"""<div class="box box-warn"><div class="box-t">⚠️ Real cash, paid before any exit</div>
            <p class="box-p">Exercising and holding triggers an estimated <b>{money(amt_cost)}</b> AMT
            bill in the exercise year — out of pocket, long before any liquidity. Make sure you can
            carry it.</p></div>""",
            unsafe_allow_html=True)

    if qsbs:
        no_q = tax.combined_exit_tax(sim["p90"], ordinary_income, status, "ltcg", state=state, qsbs=None)
        with_q = tax.combined_exit_tax(sim["p90"], ordinary_income, status, "ltcg", state=state, qsbs=qsbs)
        fed_saved = no_q["federal"] - with_q["federal"]
        frac = tax.qsbs_excluded_fraction(qsbs["era"], qsbs["years"])
        st.markdown(
            f"""<div class="box box-good"><div class="box-t">🛡️ QSBS (§1202): {frac*100:.0f}% federal exclusion</div>
            <p class="box-p">On a P90 (${sim['p90']:,.0f}) outcome, the QSBS exclusion would save about
            <b>{money(fed_saved)}</b> in <b>federal</b> tax.
            {'But California does <b>not</b> conform — it still taxes the full gain as ordinary income, so your CA bill is unchanged.' if state == 'CA' else ''}
            Requires the company to be a qualified small business (&lt;$75M gross assets at issuance) and
            the holding period above.</p></div>""",
            unsafe_allow_html=True)

# ============================== SECTION: KNOWLEDGE + ASSUMPTIONS ==============================
st.markdown("---")
with st.expander("📚 How this works — mechanics, the model, and what drives your number"):
    st.markdown("""
**The waterfall.** Exit proceeds are not split by ownership %. They flow top-down: senior preferred,
then junior preferred, then common (you). Each preferred round takes the *greater* of its liquidation
preference or its as-converted value, and *participating* preferred takes its preference **and** a
pro-rata slice of the rest (capped, sometimes). Common is the residual — and can be zero even in a
"successful" sale.

**The value, not the point.** Your equity isn't worth its payoff at one exit you picked — it's worth
the *expectation* over every exit that could happen, most of which are failure. We Monte-Carlo a
bimodal exit distribution (a mass of failures + a lognormal upside) through the waterfall to get the
expected value, the probability of zero, and the downside (CVaR).

**The tax.** ISOs can trigger AMT at exercise on the (409A − strike) spread — cash you owe before any
liquidity. NSOs and disqualifying ISO sales are ordinary income; qualifying ISO sales are long-term
capital gains, optionally with the **QSBS (§1202)** federal exclusion if held >5 years. **California**
adds its own 7% AMT, taxes gains as ordinary income (no LTCG break), and does **not** recognize QSBS —
so a Bay Area employee can owe large state tax even on a federally-excluded gain. Estimates are 2025.
""")

with st.expander("⚙️ Assumptions & limitations (read before trusting any number)"):
    st.markdown(r"""
- **Tax: federal + California, 2025.** Other states are "no state tax". Simplifications remain: no
  AMT-credit (MTC) recovery in later years, no ISO \$100k limit, no payroll tax on NSO spread, CA AMT
  exemption/phaseout use indexed approximations. QSBS assumes the company qualifies (&lt;\$75M gross assets).
- **Single aggregated round** in Simple mode (one blended preference); use **Advanced** to model true
  seniority and per-round terms.
- **Exit distribution.** "Calibrated" presets reproduce published venture outcomes (Correlation Ventures:
  ~65% below 1×, ~4% above 10×); "Manual" hands you the sliders. Either way it is a model, not a forecast.
- **Cap-table terms are archetypes** when you don't know the specifics — medians, not your company.
- The model assumes proceeds are all-cash at a single exit; it ignores escrow/earnouts, secondary
  sales, debt/venture-debt tranches, and management carve-outs (which only make common *worse*).
- Math is covered by a golden-test suite (`tests/run_all.py`); the *inputs* are still yours to get right (GIGO).
""")

st.warning("""
**⚠️ EDUCATIONAL TOOL — NOT FINANCIAL, TAX, OR LEGAL ADVICE.** This is a simulation to illustrate how
liquidation preferences, dilution, and AMT affect employee equity. It is not advice and creates no
advisory relationship. Private valuations, term sheets, and taxes are complex and company-specific —
consult a CPA or tax attorney before exercising options, selling shares, or making job decisions. The
authors assume no liability for decisions made using this tool.
""")
