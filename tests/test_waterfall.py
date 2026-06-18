"""
Golden tests for the waterfall engine.

Every case below is hand-computed from first principles (shown in the comments). These are the
cases the OLD engine got wrong: conversion of non-participating preferred, the participation
"double dip", participation caps, and stacked seniority. If the engine ever drifts, these fail.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tov.waterfall import PreferredRound, CapTable, distribute, option_payoff, breakeven_valuation

APPROX = 1.0  # dollar tolerance


def _close(a, b, tol=APPROX):
    return abs(a - b) <= tol


# Shared toy company: 5M preferred (as-converted) + 5M common = 10M fully diluted, $10M invested.
def _round(participating=False, multiple=1.0, cap=None, invested=10_000_000, shares=5_000_000):
    return PreferredRound("Pref", invested, multiple, 0, participating, cap, shares)


def test_nonparticipating_below_conversion_takes_preference():
    # Exit $15M. Pref = $10M. As-converted = 50% x 15 = $7.5M < $10M -> take preference.
    # Residual $5M to 5M common = $1.00/sh. Preferred $10M, common $5M.
    cap = CapTable([_round(participating=False)], common_shares=5_000_000)
    payouts, price, conv = distribute(cap, 15_000_000)
    assert _close(payouts["Pref"], 10_000_000), payouts
    assert _close(payouts["__common__"], 5_000_000), payouts
    assert _close(price, 1.00, 0.001)
    assert conv["Pref"] is False


def test_nonparticipating_above_conversion_converts():
    # Exit $30M. Take-pref would give common $20M; but preferred as-converted = 50% x 30 = $15M > $10M,
    # so it CONVERTS. $30M / 10M sh = $3.00/sh. Preferred $15M, common $15M (NOT $20M).
    cap = CapTable([_round(participating=False)], common_shares=5_000_000)
    payouts, price, conv = distribute(cap, 30_000_000)
    assert _close(payouts["Pref"], 15_000_000), payouts
    assert _close(payouts["__common__"], 15_000_000), payouts
    assert _close(price, 3.00, 0.001)
    assert conv["Pref"] is True


def test_conversion_threshold_is_continuous():
    # Crossover at V* = pref / ownership = 10 / 0.5 = $20M. Common = $10M either way.
    cap = CapTable([_round(participating=False)], common_shares=5_000_000)
    payouts, _, _ = distribute(cap, 20_000_000)
    assert _close(payouts["__common__"], 10_000_000), payouts


def test_participating_double_dip():
    # Exit $30M, 1x participating, no cap. Pref $10M off top; residual $20M shared 50/50 (10M sh).
    # Preferred $10M + $10M = $20M, common $10M. (vs $15M if non-participating -> the double dip.)
    cap = CapTable([_round(participating=True)], common_shares=5_000_000)
    payouts, price, _ = distribute(cap, 30_000_000)
    assert _close(payouts["Pref"], 20_000_000), payouts
    assert _close(payouts["__common__"], 10_000_000), payouts
    assert _close(price, 2.00, 0.001)


def test_participating_with_cap_then_converts():
    # Exit $50M, 1x participating, cap 2x = $20M. Uncapped take would be $10M + 50%x40 = $30M -> cap.
    # But as-converted = 50% x 50 = $25M > $20M cap, so it CONVERTS instead.
    # $50M / 10M = $5/sh. Preferred $25M, common $25M.
    cap = CapTable([_round(participating=True, cap=2.0)], common_shares=5_000_000)
    payouts, price, conv = distribute(cap, 50_000_000)
    assert _close(payouts["Pref"], 25_000_000), payouts
    assert _close(payouts["__common__"], 25_000_000), payouts
    assert conv["Pref"] is True


def test_participating_cap_binds_without_conversion():
    # Exit $36M, 1x participating, cap 2x = $20M. As-converted = 50% x 36 = $18M < $20M (won't convert).
    # Pref $10M; residual $26M; uncapped participation 50% x 26 = $13M -> total $23M > cap $20M.
    # Cap binds: preferred locked at $20M (participation $10M). Freed $3M -> common.
    # Common gets the rest: $36M - $20M = $16M.
    cap = CapTable([_round(participating=True, cap=2.0)], common_shares=5_000_000)
    payouts, _, conv = distribute(cap, 36_000_000)
    assert _close(payouts["Pref"], 20_000_000), payouts
    assert _close(payouts["__common__"], 16_000_000), payouts
    assert conv["Pref"] is False


def test_stacked_seniority_wipes_common():
    # Series B ($10M, senior, rank 0) + Series A ($5M, junior, rank 1), both 1x non-participating.
    # Exit $12M. B paid $10M first; A gets remaining $2M; common $0. (Order matters.)
    b = PreferredRound("Series B", 10_000_000, 1.0, seniority=0, as_converted_shares=10_000_000)
    a = PreferredRound("Series A", 5_000_000, 1.0, seniority=1, as_converted_shares=5_000_000)
    cap = CapTable([b, a], common_shares=5_000_000)
    payouts, _, _ = distribute(cap, 12_000_000)
    assert _close(payouts["Series B"], 10_000_000), payouts
    assert _close(payouts["Series A"], 2_000_000), payouts
    assert _close(payouts["__common__"], 0.0), payouts


def test_pari_passu_shares_pro_rata_when_short():
    # Two equally-senior rounds, $10M and $5M (both 1x). Exit $9M < $15M demand -> pro rata 2:1.
    r1 = PreferredRound("R1", 10_000_000, 1.0, seniority=0, as_converted_shares=10_000_000)
    r2 = PreferredRound("R2", 5_000_000, 1.0, seniority=0, as_converted_shares=5_000_000)
    cap = CapTable([r1, r2], common_shares=5_000_000)
    payouts, _, _ = distribute(cap, 9_000_000)
    assert _close(payouts["R1"], 6_000_000), payouts   # 9 * (10/15)
    assert _close(payouts["R2"], 3_000_000), payouts   # 9 * (5/15)
    assert _close(payouts["__common__"], 0.0), payouts


def test_option_payoff_and_breakeven():
    # 1x non-participating, $10M pref, FD 10M, common 5M. User owns 100k options, strike $0.50.
    cap = CapTable([_round(participating=False)], common_shares=5_000_000)
    # At $30M exit it converts -> $3.00/sh. Gross 100k x 3 = $300k; cost 100k x .5 = $50k; net $250k.
    r = option_payoff(cap, 30_000_000, 100_000, 0.50)
    assert _close(r["net_pretax"], 250_000), r
    # Breakeven: smallest exit where common price > strike $0.50.
    be = breakeven_valuation(cap, 100_000, 0.50)
    assert be is not None
    # Sanity: at breakeven the net is ~0, just above it is positive.
    assert option_payoff(cap, be * 1.01, 100_000, 0.50)["net_pretax"] > 0


def test_underwater_exit_pays_common_zero():
    cap = CapTable([_round(participating=False, invested=50_000_000, multiple=1.5)],
                   common_shares=5_000_000)
    payouts, _, _ = distribute(cap, 40_000_000)   # pref $75M > $40M exit
    assert _close(payouts["__common__"], 0.0), payouts


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS  {fn.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"FAIL  {fn.__name__}: {e}")
        except Exception as e:  # noqa
            print(f"ERROR {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{passed}/{len(fns)} waterfall golden tests passed")
    sys.exit(0 if passed == len(fns) else 1)
