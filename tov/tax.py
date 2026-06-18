"""
Federal tax estimators (tax year 2025) for equity compensation.

Scope and honesty: this is a SIMPLIFIED FEDERAL estimate. It exists to surface the order of
magnitude of the two outcomes that actually wreck employees — the AMT cash bill at ISO exercise,
and the ordinary-vs-capital-gains split at sale. It is NOT a tax return.

Explicitly excluded (documented in README): state income tax (California adds a large, separate AMT
of its own), itemized deductions / SALT, the AMT credit carryforward and its recovery, ISO $100k
vesting limit, 83(b) elections, QSBS (Section 1202) exclusion, payroll/Medicare on NSO spread,
and any interaction with other preference items. All constants are 2025 IRS inflation-adjusted
figures (see data/sources.md).
"""

from __future__ import annotations

# --- 2025 ordinary income brackets (applied to taxable income AFTER the standard deduction) ---
# Each entry is (lower_bound, marginal_rate).
ORDINARY_2025 = {
    "single": [(0, .10), (11_925, .12), (48_475, .22), (103_350, .24),
               (197_300, .32), (250_525, .35), (626_350, .37)],
    "mfj":    [(0, .10), (23_850, .12), (96_950, .22), (206_700, .24),
               (394_600, .32), (501_050, .35), (751_600, .37)],
}
STD_DEDUCTION_2025 = {"single": 15_750, "mfj": 31_500}

# --- 2025 AMT ---
AMT_EXEMPTION_2025 = {"single": 88_100, "mfj": 137_000}
AMT_PHASEOUT_START_2025 = {"single": 626_350, "mfj": 1_252_700}
AMT_PHASEOUT_RATE = 0.25            # exemption shrinks $0.25 per $1 of AMTI over the threshold
AMT_28_THRESHOLD_2025 = 239_100    # AMT base above this is taxed 28%, below 26%

# --- 2025 long-term capital gains + NIIT ---
LTCG_0_TOP_2025 = {"single": 48_350, "mfj": 96_700}
LTCG_20_START_2025 = {"single": 533_400, "mfj": 600_050}
NIIT_THRESHOLD = {"single": 200_000, "mfj": 250_000}
NIIT_RATE = 0.038


def _norm(status: str) -> str:
    s = status.lower().strip()
    if s in ("single", "s"):
        return "single"
    if s in ("mfj", "married", "married filing jointly", "joint"):
        return "mfj"
    raise ValueError(f"unsupported filing status: {status!r} (use 'single' or 'mfj')")


def _progressive(amount: float, brackets) -> float:
    """Tax on `amount` through a (lower_bound, rate) bracket schedule."""
    amount = max(0.0, amount)
    tax = 0.0
    for i, (lo, rate) in enumerate(brackets):
        hi = brackets[i + 1][0] if i + 1 < len(brackets) else float("inf")
        if amount > lo:
            tax += (min(amount, hi) - lo) * rate
        else:
            break
    return tax


def regular_income_tax(ordinary_income: float, status: str) -> float:
    """Rough regular federal income tax: standard deduction, single/MFJ schedule, no credits."""
    status = _norm(status)
    taxable = max(0.0, ordinary_income - STD_DEDUCTION_2025[status])
    return _progressive(taxable, ORDINARY_2025[status])


def tentative_minimum_tax(amt_base: float, status: str) -> float:
    """
    Tentative minimum tax on an AMT base (AMTI before the exemption).

    AMT disallows the standard deduction, so callers pass *gross* ordinary income (plus preferences)
    as the base — a documented, slightly conservative simplification.
    """
    status = _norm(status)
    exemption = AMT_EXEMPTION_2025[status]
    over = max(0.0, amt_base - AMT_PHASEOUT_START_2025[status])
    exemption = max(0.0, exemption - AMT_PHASEOUT_RATE * over)
    base = max(0.0, amt_base - exemption)
    if base <= AMT_28_THRESHOLD_2025:
        return base * 0.26
    return AMT_28_THRESHOLD_2025 * 0.26 + (base - AMT_28_THRESHOLD_2025) * 0.28


def iso_amt_on_exercise(ordinary_income: float, status: str, bargain_element: float) -> dict:
    """
    Estimated AMT cash bill from exercising ISOs and HOLDING past year-end (the classic trap).

    bargain_element = (FMV_at_exercise - strike) * shares  -> an AMT preference item.

    AMT owed = max(0, TMT - regular_tax). We report the INCREMENTAL AMT caused by the ISO, i.e. the
    extra tax you would not owe but for the exercise.
    """
    status = _norm(status)
    bargain_element = max(0.0, bargain_element)
    reg = regular_income_tax(ordinary_income, status)
    tmt_without = tentative_minimum_tax(ordinary_income, status)
    tmt_with = tentative_minimum_tax(ordinary_income + bargain_element, status)
    amt_without = max(0.0, tmt_without - reg)
    amt_with = max(0.0, tmt_with - reg)
    incremental = max(0.0, amt_with - amt_without)
    return {
        "bargain_element": bargain_element,
        "regular_tax": reg,
        "tentative_min_tax": tmt_with,
        "amt_due": incremental,                 # extra cash out of pocket at exercise
        "effective_rate": incremental / bargain_element if bargain_element > 0 else 0.0,
    }


def ltcg_tax(gain: float, ordinary_income: float, status: str) -> float:
    """Long-term capital gains tax on `gain`, stacked on top of ordinary income, plus NIIT."""
    status = _norm(status)
    gain = max(0.0, gain)
    start = ordinary_income                     # LTCG stacks above ordinary income
    end = ordinary_income + gain
    zero_top = LTCG_0_TOP_2025[status]
    twenty_start = LTCG_20_START_2025[status]

    def overlap(a, b, lo, hi):
        return max(0.0, min(b, hi) - max(a, lo))

    in_0 = overlap(start, end, 0, zero_top)
    in_15 = overlap(start, end, zero_top, twenty_start)
    in_20 = overlap(start, end, twenty_start, float("inf"))
    tax = in_15 * 0.15 + in_20 * 0.20

    niit_base = max(0.0, end - max(start, NIIT_THRESHOLD[status]))
    tax += niit_base * NIIT_RATE
    return tax


def ordinary_on_spread(spread: float, ordinary_income: float, status: str) -> float:
    """Incremental ordinary tax on an equity spread (NSO exercise, or ISO disqualifying disposition)."""
    status = _norm(status)
    spread = max(0.0, spread)
    return (regular_income_tax(ordinary_income + spread, status)
            - regular_income_tax(ordinary_income, status))


def net_proceeds_after_exit_tax(gross_gain: float, ordinary_income: float, status: str,
                                treatment: str) -> dict:
    """
    Net of tax on the gain realised at exit.

    treatment: 'ltcg'      ISO qualifying disposition -> long-term capital gains (+ NIIT)
               'ordinary'  NSO, or ISO disqualifying disposition -> ordinary income
    """
    if treatment == "ltcg":
        tax = ltcg_tax(gross_gain, ordinary_income, status)
    elif treatment == "ordinary":
        tax = ordinary_on_spread(gross_gain, ordinary_income, status)
    else:
        raise ValueError("treatment must be 'ltcg' or 'ordinary'")
    return {"gross_gain": gross_gain, "tax": tax, "net": max(0.0, gross_gain - tax)}


# =====================================================================================
# California (2025) — the state that matters most for the target user (Bay Area).
# CA has NO preferential capital-gains rate (gains are ordinary), its own 7% AMT (ISO bargain
# element is a CA preference too), and it does NOT conform to federal QSBS (§1202) — California
# taxes the full gain even when it is 100% excluded federally. Constants per data/sources.md;
# AMT exemption/phaseout are inflation-indexed and used here as documented approximations.
# =====================================================================================

# CA MFJ brackets are exactly 2x the single thresholds.
_CA_SINGLE = [(0, .01), (11_079, .02), (26_264, .04), (41_452, .06), (57_542, .08),
              (72_724, .093), (371_479, .103), (445_771, .113), (742_953, .123)]
_CA_MFJ = [(0, .01), (22_158, .02), (52_528, .04), (82_904, .06), (115_084, .08),
           (145_448, .093), (742_958, .103), (891_542, .113), (1_485_906, .123)]
CA_BRACKETS_2025 = {"single": _CA_SINGLE, "mfj": _CA_MFJ}
CA_STD_DEDUCTION_2025 = {"single": 5_540, "mfj": 11_080}
CA_MHST_THRESHOLD = 1_000_000          # +1% "millionaire" surtax on taxable income over $1M
CA_MHST_RATE = 0.01
CA_AMT_RATE = 0.07
CA_AMT_EXEMPTION_2025 = {"single": 95_600, "mfj": 127_400}
CA_AMT_PHASEOUT_START_2025 = {"single": 359_000, "mfj": 478_000}


def ca_income_tax(income: float, status: str) -> float:
    """California regular tax (ordinary rates; capital gains are taxed identically). Includes MHST."""
    status = _norm(status)
    taxable = max(0.0, income - CA_STD_DEDUCTION_2025[status])
    tax = _progressive(taxable, CA_BRACKETS_2025[status])
    if taxable > CA_MHST_THRESHOLD:
        tax += (taxable - CA_MHST_THRESHOLD) * CA_MHST_RATE
    return tax


def ca_tentative_min_tax(amt_base: float, status: str) -> float:
    status = _norm(status)
    ex = CA_AMT_EXEMPTION_2025[status]
    over = max(0.0, amt_base - CA_AMT_PHASEOUT_START_2025[status])
    ex = max(0.0, ex - AMT_PHASEOUT_RATE * over)
    return max(0.0, amt_base - ex) * CA_AMT_RATE


def ca_amt_on_iso_exercise(ordinary_income: float, status: str, bargain_element: float) -> float:
    """Incremental California AMT from exercising ISOs and holding (CA conforms on the preference)."""
    bargain_element = max(0.0, bargain_element)
    reg = ca_income_tax(ordinary_income, status)
    with_iso = max(0.0, ca_tentative_min_tax(ordinary_income + bargain_element, status) - reg)
    without = max(0.0, ca_tentative_min_tax(ordinary_income, status) - reg)
    return max(0.0, with_iso - without)


# --- QSBS / §1202 (federal only — California does not conform) ---

def qsbs_excluded_fraction(era: str, years_held: float) -> float:
    """
    Federal §1202 exclusion fraction.
    era 'post_jul2025' -> OBBBA tiers: 50% @3y, 75% @4y, 100% @5y.
    era 'pre_jul2025'  -> legacy (post-2010 acquisition): 100% @5y, else 0%.
    """
    if era == "post_jul2025":
        if years_held >= 5:
            return 1.0
        if years_held >= 4:
            return 0.75
        if years_held >= 3:
            return 0.50
        return 0.0
    return 1.0 if years_held >= 5 else 0.0


def federal_gain_tax(gain: float, ordinary_income: float, status: str, qsbs: dict = None) -> float:
    """
    Federal tax on a long-term gain, applying the §1202 QSBS exclusion if eligible.
    qsbs = {eligible, era, years, basis}. Per-issuer cap = max($15M post-OBBBA / $10M legacy, 10x basis).
    Partially-excluded QSBS (50%/75% tiers) is taxed at 28%; fully-excluded gain is untaxed.
    """
    gain = max(0.0, gain)
    if not qsbs or not qsbs.get("eligible"):
        return ltcg_tax(gain, ordinary_income, status)
    frac = qsbs_excluded_fraction(qsbs["era"], qsbs.get("years", 0))
    base_cap = 15_000_000 if qsbs["era"] == "post_jul2025" else 10_000_000
    cap = max(base_cap, 10.0 * qsbs.get("basis", 0.0))
    excluded = min(gain * frac, cap)
    taxable_gain = max(0.0, gain - excluded)
    if 0.0 < frac < 1.0:
        # §1 (h) 28% rate on the included portion of QSBS gain, plus NIIT.
        niit = max(0.0, taxable_gain) * NIIT_RATE if (ordinary_income + taxable_gain) > NIIT_THRESHOLD[_norm(status)] else 0.0
        return taxable_gain * 0.28 + niit
    return ltcg_tax(taxable_gain, ordinary_income, status)


def combined_amt_on_iso_exercise(ordinary_income: float, status: str, bargain_element: float,
                                 state: str = "CA") -> dict:
    """Federal + California incremental AMT from exercising and holding ISOs."""
    fed = iso_amt_on_exercise(ordinary_income, status, bargain_element)
    ca = ca_amt_on_iso_exercise(ordinary_income, status, bargain_element) if state == "CA" else 0.0
    return {"federal": fed["amt_due"], "state": ca, "total": fed["amt_due"] + ca,
            "bargain_element": fed["bargain_element"]}


def combined_exit_tax(gain: float, ordinary_income: float, status: str, treatment: str,
                      state: str = "CA", qsbs: dict = None) -> dict:
    """
    Federal + state tax on the gain realised at exit.

    treatment 'ltcg'     -> federal LTCG (with QSBS if eligible); CA taxes it as ordinary income.
    treatment 'ordinary' -> federal + CA ordinary income on the spread.
    Returns federal / state / total / net (take-home) and the effective rate.
    """
    gain = max(0.0, gain)
    if treatment == "ltcg":
        fed = federal_gain_tax(gain, ordinary_income, status, qsbs)
    elif treatment == "ordinary":
        fed = ordinary_on_spread(gain, ordinary_income, status)
    else:
        raise ValueError("treatment must be 'ltcg' or 'ordinary'")
    # California: no LTCG preference and no QSBS conformity -> always ordinary on the full gain.
    ca = (ca_income_tax(ordinary_income + gain, status) - ca_income_tax(ordinary_income, status)) \
        if state == "CA" else 0.0
    total = fed + ca
    return {"federal": fed, "state": ca, "total": total, "net": max(0.0, gain - total),
            "effective_rate": (total / gain) if gain > 0 else 0.0}
