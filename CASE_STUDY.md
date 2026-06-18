# Case study — "The $700K offer that's really worth $73K"

*A worked example showing why startup-equity offers are systematically mispriced, and how the True
Option Value engine quantifies the gap. Every number below is produced by the model in this repo and
is reproducible (`tests/run_all.py` validates the math; the scenario script is in the commit history).*

---

## The question

A candidate gets two offers. Big-tech: cash + liquid RSUs. Startup: lower cash + **50,000 stock
options**. The recruiter frames the options as "worth **$700,000**" — 50,000 shares × the last round
price of $15, minus the $1 strike.

Is that $700,000 real? The honest answer is a distribution, not a number — and its **median is an
order of magnitude lower** than the brochure. Here is the same offer under the model.

## The offer, precisely

| Input | Value |
|---|---|
| Options / strike / current 409A | 50,000 / \$1.00 / \$4.00 |
| Company | Series B, \$40M raised, \$150M post-money, 10M fully-diluted shares |
| Future dilution | one more round (~13%, Carta median) |
| Taxpayer | single, \$180K other income, **California** |
| Exit distribution | calibrated "Series B" preset (≈65% < 1×, ≈4% > 10× — Correlation Ventures) |

**Offer-letter value: \$700,000.**

## What the model says

| Scenario | Expected value (after-tax) | Median (P50) | P(≈ \$0) | Breakeven exit |
|---|--:|--:|--:|--:|
| **A.** Clean terms (1× non-participating), sell at exit | \$696,690 | **\$228,816** | 35% | \$46.9M |
| **B.** Structured terms (1.5× participating, 2× cap), sell at exit | \$585,965 | **\$73,099** | 45% | \$73.3M |

Two findings a naive calculator cannot produce:

1. **The mean flatters; the median tells the truth.** Even with *clean* terms, the expected value
   (\$697K) lands near the \$700K headline — but only because a thin 4% upside tail drags the average
   up. The **median employee gets \$228,816**, and **35% of the time the options are worth nothing**.
   For someone who holds *one* startup's equity and cannot diversify across a portfolio the way a VC
   can, the median and the probability of zero matter more than the mean. The brochure quotes neither.

2. **Terms are worth more than ownership.** Switching from clean 1× non-participating to a 1.5×
   participating-with-cap stack — the structure that returned in the 2022–24 down market — barely
   changes the headline ownership %, but it **lifts the breakeven from \$47M to \$73M, raises P(zero)
   from 35% to 45%, and collapses the median from \$229K to \$73,099.** Holding "1% of the company"
   means little until you know *which* 1%.

## The tax trap most employees never model

Suppose the candidate exercises the ISOs early to start the long-term capital-gains clock — common
advice. Under the model (clean terms, California):

| | Value |
|---|--:|
| AMT due **at exercise** (federal \$30,683 + California \$3,745) | **\$34,428** |
| Expected value if it works out (after-tax, LTCG) | \$879,085 |
| Worst-decile outcome (CVaR 10%) | **\$0** |

The \$34,428 is **cash owed the year you exercise — before any liquidity exists.** In the 35% of
outcomes where the company is worth nothing, and across the entire worst decile, you have **paid
\$34,428 in tax on a gain you never received.** This is the precise mechanism by which employees end
up *net negative* on a "winning" offer, and it is invisible on every offer letter.

## Where the rules actually help — and where California claws it back

If the shares qualify as QSBS (§1202) and are held five years, the model shows expected after-tax
value rising from **\$879K to \$1,185,898** — the federal exclusion removes federal tax on the gain.
But **California does not conform to QSBS**: it still taxes the full gain as ordinary income (up to
13.3%). A Bay Area employee who reads "100% federal exclusion" and assumes tax-free is wrong by a
six-figure state bill. The model makes that conformity gap explicit.

## Why this is trustworthy, not just plausible

A pretty calculator that is subtly wrong is worse than no calculator. This engine is built to be
*checkable*:

- **The waterfall is validated against hand-computed cases** — non-participating conversion, the
  participation double-dip, participation caps (binding and converting), and stacked seniority. These
  are exactly the cases a "% × exit" tool gets wrong.
- **The Monte-Carlo integrator is validated against a closed-form expectation** (the pure-common,
  zero-strike case where `E[payoff] = f · E[V]`).
- **The exit distribution is calibrated to published venture data** (Correlation Ventures' ~65% < 1×,
  ~4% > 10×) and a test asserts the simulation reproduces it.
- **Every tax and market constant is sourced** (`data/sources.md`), 2025 federal + California.
- **34 golden tests** gate the whole thing (`tests/run_all.py`).

## Honest limitations

Federal + California only; no AMT-credit recovery, QSBS assumes the company qualifies, single
aggregated preference in Simple mode, all-cash single-exit assumption (ignores escrow/earnouts,
secondary, venture debt, and management carve-outs — all of which only make common *worse*). The exit
distribution is a calibrated model, not a forecast of any one company. Inputs are still the user's to
get right.

## The takeaway

The offer letter's \$700,000 is not a lie, but it is the **single most optimistic point** on a
distribution whose **median is \$73K–\$229K** and whose **floor is a 35–45% chance of zero plus a tax
bill**. The product of this analysis is not a different number — it is the **distribution, the
breakeven, and the downside**, which is what a rational, undiversified employee needs to compare a
startup offer against a liquid one. It sells clarity, not optimism.
