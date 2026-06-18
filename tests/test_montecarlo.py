"""
Tests for the Monte Carlo value layer.

The headline test pins the simulator against a CLOSED-FORM expectation: with no preferred stock and
a zero strike, the option payoff is linear in the exit value (payoff = f * V), so E[payoff] = f * E[V]
and E[V] is known analytically from the mixture parameters. If the integrator drifts, this fails.
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tov.waterfall import CapTable
from tov import montecarlo as mc


def test_expected_value_matches_closed_form():
    # Pure common, zero strike -> payoff(V) = f * V, f = option_shares / common_shares.
    common = 10_000_000
    option_shares = 100_000
    f = option_shares / common
    cap = CapTable([], common_shares=common)

    v0 = 100_000_000
    p_fail, fail_ceiling, median_mult, sigma = 0.5, 0.2, 2.0, 0.6
    res = mc.simulate(cap, option_shares, strike=0.0, v0=v0,
                      n=80_000, p_fail=p_fail, fail_ceiling=fail_ceiling,
                      survivor_median_multiple=median_mult, sigma=sigma,
                      v_max_mult=60.0, seed=7)

    e_v_fail = fail_ceiling * v0 / 2.0
    e_v_surv = v0 * median_mult * math.exp(sigma ** 2 / 2.0)
    e_v = p_fail * e_v_fail + (1 - p_fail) * e_v_surv
    expected = f * e_v

    rel_err = abs(res["expected_value"] - expected) / expected
    assert rel_err < 0.03, (res["expected_value"], expected, rel_err)


def test_prob_zero_tracks_failure_when_common_wiped():
    # Big preference relative to V0: in every failure draw common is wiped, so prob_zero >= p_fail.
    from tov.waterfall import PreferredRound
    cap = CapTable([PreferredRound("Pref", 80_000_000, 1.0, as_converted_shares=8_000_000)],
                   common_shares=2_000_000)
    res = mc.simulate(cap, 50_000, strike=0.10, v0=100_000_000,
                      n=40_000, p_fail=0.6, fail_ceiling=0.3,
                      survivor_median_multiple=1.2, sigma=0.5, seed=11)
    assert res["prob_zero"] >= 0.60, res["prob_zero"]


def test_distribution_ordering_and_bounds():
    cap = CapTable([], common_shares=10_000_000)
    res = mc.simulate(cap, 100_000, 0.0, 50_000_000, n=20_000, seed=3)
    assert 0.0 <= res["prob_zero"] <= 1.0
    assert res["p10"] <= res["p50"] <= res["p90"] <= res["p99"] <= res["max"] + 1
    assert res["cvar_10"] <= res["p50"] + 1
    assert res["expected_value"] <= res["max"] + 1


def test_tax_fn_reduces_expected_value():
    cap = CapTable([], common_shares=10_000_000)
    base = mc.simulate(cap, 100_000, 0.0, 50_000_000, n=20_000, seed=5)
    taxed = mc.simulate(cap, 100_000, 0.0, 50_000_000, n=20_000, seed=5,
                        tax_fn=lambda p: p * 0.7)   # flat 30% haircut
    assert taxed["expected_value"] < base["expected_value"]
    assert abs(taxed["expected_value"] - 0.7 * base["expected_value"]) < base["expected_value"] * 0.01


def test_series_a_preset_reproduces_venture_anchors():
    # The calibrated 'Series A' exit preset must reproduce Correlation Ventures' published shape:
    # ~65% of outcomes below 1x the last valuation, ~4% above 10x. This is what makes the expected
    # value defensible rather than invented.
    from tov import benchmarks
    p = benchmarks.exit_outcomes("Series A")
    v0 = 100_000_000
    exits = mc.simulate_exit_values(v0, n=200_000, p_fail=p["p_fail"],
                                    fail_ceiling=p["fail_ceiling"],
                                    survivor_median_multiple=p["survivor_median_multiple"],
                                    sigma=p["sigma"], seed=42)
    below_1x = (exits < v0).mean()
    above_10x = (exits > 10 * v0).mean()
    assert 0.62 <= below_1x <= 0.68, below_1x        # target ~0.65
    assert 0.025 <= above_10x <= 0.055, above_10x    # target ~0.04


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
    print(f"\n{passed}/{len(fns)} monte carlo tests passed")
    sys.exit(0 if passed == len(fns) else 1)
