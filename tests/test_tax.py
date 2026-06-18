"""
Golden tests for the 2025 federal tax estimators. Each expected number is hand-computed in the
comments from the published 2025 brackets (see data/sources.md).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tov import tax

APPROX = 2.0


def _close(a, b, tol=APPROX):
    return abs(a - b) <= tol


def test_regular_income_tax_single():
    # $150k single. Taxable 134.25k. 1192.5 + 4386 + 12072.5 + 7416 = 25067.
    assert _close(tax.regular_income_tax(150_000, "single"), 25_067)


def test_iso_amt_trap_single():
    # $150k ordinary + $200k bargain element, single.
    # TMT(350k) = 239100*.26 + (261900-239100)*.28 = 68,550; regular = 25,067 -> AMT 43,483.
    r = tax.iso_amt_on_exercise(150_000, "single", 200_000)
    assert _close(r["amt_due"], 43_483, 5), r
    assert 0.20 < r["effective_rate"] < 0.24, r   # ~21.7% of the bargain element


def test_iso_amt_zero_when_no_bargain():
    r = tax.iso_amt_on_exercise(150_000, "single", 0)
    assert _close(r["amt_due"], 0.0)


def test_ltcg_no_niit():
    # $100k ordinary + $50k LT gain, single. Stacks 100k->150k, all in 15% band. No NIIT (end<200k+).
    assert _close(tax.ltcg_tax(50_000, 100_000, "single"), 7_500)


def test_ltcg_with_niit():
    # $250k ordinary + $100k gain, single. All 15% = 15,000. NIIT on (350k-250k)=100k * 3.8% = 3,800.
    assert _close(tax.ltcg_tax(100_000, 250_000, "single"), 18_800)


def test_ordinary_on_spread_spans_brackets():
    # $100k ordinary + $50k NSO spread, single. reg(150k)-reg(100k) = 25,067 - 13,449 = 11,618.
    assert _close(tax.ordinary_on_spread(50_000, 100_000, "single"), 11_618)


def test_net_proceeds_treatments_differ():
    # On a $100k gain the ordinary path should net less than the LTCG path for a mid earner.
    ord_net = tax.net_proceeds_after_exit_tax(100_000, 200_000, "single", "ordinary")["net"]
    ltcg_net = tax.net_proceeds_after_exit_tax(100_000, 200_000, "single", "ltcg")["net"]
    assert ltcg_net > ord_net, (ord_net, ltcg_net)


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
    print(f"\n{passed}/{len(fns)} tax golden tests passed")
    sys.exit(0 if passed == len(fns) else 1)
