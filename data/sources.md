# Data provenance

Every constant in this model traces to a published source below. Tax figures are IRS 2025
inflation-adjusted amounts; market figures are venture-data medians. Last reviewed: 2026-06.

## Federal tax constants (tax year 2025) — `tov/tax.py`

| Constant | Value | Source |
|---|---|---|
| AMT exemption (single / MFJ) | $88,100 / $137,000 | IRS Rev. Proc. 2024-40; Tax Foundation 2025 brackets |
| AMT exemption phaseout start (single / MFJ) | $626,350 / $1,252,700 | Tax Foundation 2025 brackets |
| AMT 28% bracket threshold | $239,100 ($119,550 MFS) | Tax Foundation 2025 brackets |
| Ordinary brackets (single / MFJ) | 10–37% per schedule | IRS / Tax Foundation 2025 brackets |
| Standard deduction (single / MFJ) | $15,750 / $31,500 | IRS 2025 |
| LTCG 0% ceiling (single / MFJ) | $48,350 / $96,700 | IRS / NerdWallet 2025 |
| LTCG 20% floor (single / MFJ) | $533,400 / $600,050 | IRS 2025 LTCG thresholds |
| NIIT | 3.8% over $200k / $250k MAGI | IRC §1411 (not inflation-indexed) |

Sources:
- Tax Foundation, *2025 Tax Brackets and Federal Income Tax Rates* — https://taxfoundation.org/data/all/federal/2025-tax-brackets/
- IRS, *Federal income tax rates and brackets* — https://www.irs.gov/filing/federal-income-tax-rates-and-brackets
- NerdWallet, *2025 and 2026 Capital Gains Tax Rates* — https://www.nerdwallet.com/taxes/learn/capital-gains-tax-rates

## California tax constants (2025) — `tov/tax.py`

| Constant | Value | Source |
|---|---|---|
| CA income brackets (single) | 1%–12.3%, 9 brackets | FTB 2025 Tax Rate Schedules |
| CA income brackets (MFJ) | thresholds = 2× single | FTB 2025 Tax Rate Schedules |
| CA standard deduction (single / MFJ) | $5,540 / $11,080 | FTB 2025 |
| Mental Health / Behavioral Health Services Tax | +1% on taxable income > $1,000,000 | Prop 63 (2004) / Prop 1 (2024) |
| CA AMT rate | 7% (flat) | FTB Schedule P |
| CA AMT exemption (single / MFJ) | ≈ $95,600 / $127,400 (indexed) | FTB Schedule P (approx.) |
| CA AMT exemption phaseout start (single / MFJ) | ≈ $359,000 / $478,000 | FTB Schedule P (approx.) |
| CA capital gains | taxed as ordinary income (no preferential rate) | CA R&TC |

California **does not conform to QSBS/§1202** — it taxes the full gain. Sources:
- California FTB, *2025 Tax Rate Schedules* — https://www.ftb.ca.gov/forms/2025/2025-540-tax-rate-schedules.pdf
- NerdWallet, *California State Income Tax Rates & Brackets (2025-2026)* — https://www.nerdwallet.com/taxes/learn/california-state-tax
- ESO Fund, *Exercising Stock Options in California: tax guide* — https://www.esofund.com/blog/exercising-stock-options-in-california

## QSBS / §1202 (federal) — `tov/tax.py`

Legacy (stock acquired 2010–Jul 4 2025): 100% exclusion if held ≥5 years; per-issuer cap = greater of
$10M or 10× basis; $50M gross-asset test. OBBBA (acquired after Jul 4 2025): tiered 50% (≥3y) / 75%
(≥4y) / 100% (≥5y); cap raised to $15M; gross-asset test raised to $75M. Partially-excluded gain is
taxed at 28%. Sources:
- The Tax Adviser, *QSBS gets a makeover: Sec. 1202's new look* (Nov 2025) — https://www.thetaxadviser.com/issues/2025/nov/qsbs-gets-a-makeover-what-tax-pros-need-to-know-about-sec-1202s-new-look/
- RSM, *The OBBBA expands QSBS exclusions* — https://rsmus.com/insights/services/business-tax/obbba-tax-qsbs.html

## Exit-outcome calibration — `data/benchmarks.json` (`_exit_outcomes`), `tov/montecarlo.py`

The "Series A" exit-distribution preset (p_fail 0.45, survivor median 1.5×, σ 1.3) is fit so the
simulated distribution reproduces Correlation Ventures' published shape: **~65% of outcomes below 1×**
and **~4% above 10×**. Verified by `tests/test_montecarlo.py::test_series_a_preset_reproduces_venture_anchors`.
Stage adjustments reflect documented failure-rate decline at later stages. Sources:
- Correlation Ventures data, via BIP Ventures, *What is the Venture Capital Power Law* — https://www.bipventures.vc/news/explainer-what-is-the-venture-capital-power-law
- AngelList, *What AngelList Data Says About Power-Law Returns in VC* — https://www.angellist.com/blog/what-angellist-data-says-about-power-law-returns-in-venture-capital

## Market archetypes — `data/benchmarks.json`

**Dilution medians.** Per-round median primary dilution from Carta's *State of Private Markets*
(2024–2025): Series A ≈ 18% (down from ~21% a year earlier), Series B ≈ 13% (down from ~15%),
Series C ≈ 16%. The series-wide trend over 2023–2025 is *downward* (companies selling smaller slices).
- Carta, *State of Private Markets: 2025 in Review* — https://carta.com/data/state-of-private-markets-q4-2025/
- Carta, *State of Private Markets: Q1 2025* — https://carta.com/data/state-of-private-markets-q1-2025/

**Liquidation terms.** 1× non-participating preferred is the market standard for healthy priced
rounds. The `structured_downround` archetype (1.5–2× multiples, participating preferred with 2× caps,
pay-to-play) models the documented rise of investor-protective "structured" terms in the 2022–2024
down market — it is an explicit **risk scenario, not a median**.
- Fenwick & West, *Venture Beacon* quarterly VC market trend reports — https://www.fenwick.com/insights
- Cooley, *Venture Financing Report* (terms / pay-to-play prevalence) — https://www.cooley.com

**Investor as-converted ownership** (`investor_ownership_pct`) is an order-of-magnitude estimate of
cumulative preferred ownership by stage on a typical post-A/B/C cap table; it drives the
conversion/participation math in Simple mode. Override it with real figures via Advanced mode.

## What is NOT sourced (and why)

The **exit-value distribution** (`tov/montecarlo.py` defaults: failure probability, survivor median
multiple, dispersion) is a deliberately sober *judgement*, not a measured benchmark — venture outcome
distributions are heavy-tailed and dataset-dependent. These are user-facing sliders precisely so the
assumption is explicit and owned by the user, not smuggled in as fact.
