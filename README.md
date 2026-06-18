# True Option Value Calculation Model (2025)

An interactive, web-based equity valuation model built in Python (Streamlit) that simulates complex
startup exit scenarios. Unlike traditional calculators that rely solely on percentage ownership, this
tool runs each exit through the full **liquidation waterfall** (preferences, seniority, conversion,
participation), over a **probability distribution** of outcomes, **net of dilution and federal + state
tax** — and reports the *expected value*, the *probability of zero*, and the *downside*, not a single
optimistic point.

The model bridges the gap between the theoretical offer-letter number and actual realized value,
serving as a dynamic tool for risk assessment under different market conditions. A full worked example
is in **[CASE_STUDY.md](CASE_STUDY.md)**.

###  Model Objective

* **Value, not a point estimate:** Compute the probability-weighted expected value of an option grant
  across a calibrated distribution of exits — most of which are failure — rather than its payoff at one
  hand-picked exit.
* **Visualize Risk Exposure:** Identify the "Zone of Zero" where common options are underwater due to
  investor liquidation preferences, even at a non-zero exit valuation.
* **Analyze Waterfall Logic:** Simulate the hierarchical distribution of proceeds — senior preferred,
  then junior preferred, then common — including the non-participating *conversion* decision and the
  participating "double dip" with caps.
* **Quantify the tax drag:** Model the AMT cash bill at ISO exercise (federal **and** California), the
  ordinary-vs-LTCG split at sale, and the QSBS (§1202) exclusion.
* **Assess Break-even Thresholds:** Calculate the precise exit valuation required for a positive net
  payout after strike, the preference hurdle, and dilution.

###  Key Takeaways

* **Structure over percentage:** "1% of the company" is meaningless without the terms; a liquidation
  preference is a hurdle that must clear before ownership % applies.
* **The mean flatters; the median tells the truth:** the expected value can sit near the offer-letter
  number purely on the strength of a thin upside tail, while the *median* outcome — what a typical,
  undiversified employee actually receives — is an order of magnitude lower.
* **The "Zone of Zero":** with high or participating preferences, employees can net **$0** even when the
  company sells for millions.
* **The AMT trap:** exercising ISOs and holding can create a cash tax bill *before any liquidity* —
  sometimes larger than the stock's eventual worth.
* **The California QSBS gap:** a 100% *federal* QSBS exclusion still leaves a large *state* bill, because
  California does not conform.

###  Model Structure

A modular, tested Python package (`tov/`) separated from the UI:

* **`tov/waterfall.py`** — the engine: `CapTable` / `PreferredRound` and a distribution solver handling
  seniority stacking, the non-participating conversion option, and participating preferred with caps,
  resolved via best-response equilibrium.
* **`tov/montecarlo.py`** — Monte Carlo over a bimodal exit distribution → expected value, P(zero),
  P10/P50/P90, and CVaR.
* **`tov/tax.py`** — 2025 federal + California estimators: AMT, ordinary income, LTCG, and QSBS §1202.
* **`tov/reverse.py`** — reverse solvers (offer-letter fragments → fully-diluted shares / ownership).
* **`data/`** — market archetypes and the calibrated exit-distribution presets, with **`sources.md`**
  documenting the provenance of every constant.
* **`app.py`** — the Streamlit UI; every control feeds a number that is actually computed.
* **Visualization (Plotly):** outcome-probability bands and the true-payoff-vs-offer-letter curve.

###  Key Assumptions (Base Methodology)

* **Waterfall hierarchy:** proceeds flow senior → junior preferred → common; non-participating preferred
  takes the greater of its preference or as-converted value.
* **Dilution:** a fully-diluted approach where future rounds are modeled as new-share issuance.
* **Market benchmarks:** default terms and dilution medians are drawn from Carta / Fenwick data; the
  exit distribution is calibrated to published venture outcomes (Correlation Ventures: ~65% below 1×,
  ~4% above 10×).
* **Taxation:** 2025 federal + California estimates (AMT, ordinary, LTCG, QSBS).

###  Model Scope & Limitations

* Federal + California only; other states are treated as no-state-tax. No AMT-credit (MTC) carryforward
  recovery, no ISO $100k limit, no payroll tax on the NSO spread.
* Simple mode blends the preference stack into one aggregated round; **Advanced mode** models true
  per-round seniority and terms.
* The exit distribution is a calibrated **model, not a forecast** of any one company.
* All-cash, single-exit assumption: ignores escrow/earnouts, secondary sales, venture debt, and
  management carve-outs (all of which only make common *worse*).
* **Educational and simulation purposes only** — not investment, tax, or legal advice.

###  Validation (why the numbers are trustworthy)

* The waterfall is checked against **hand-computed golden cases** — conversion crossover, the
  participation double-dip, caps (binding *and* converting), and stacked seniority.
* The Monte Carlo integrator is validated against a **closed-form expectation**.
* The calibrated distribution is asserted to **reproduce the published venture-outcome shape**.
* **34 golden tests** gate the whole engine. Run them first.

###  Run

```bash
pip install -r requirements.txt
python tests/run_all.py        # 34 golden tests — run this first
streamlit run app.py
```

###  Files

* `app.py` — Streamlit UI (inputs, charts, narrative).
* `tov/` — the tested calculation engine (waterfall, Monte Carlo, tax, reverse solvers).
* `data/benchmarks.json` + `data/sources.md` — market archetypes / calibrated presets + provenance.
* `tests/` — golden-test suite (`python tests/run_all.py`).
* `CASE_STUDY.md` — a full worked example with reproducible numbers.
* `archive/` — the original MVP engine, kept for history.
* `requirements.txt` — Python dependencies (Streamlit, NumPy, Plotly).

###  Author

Built by **Guowei (Gary) Wu** as a portfolio project demonstrating Python financial modeling, SaaS
equity analysis, and full-stack data application development.
