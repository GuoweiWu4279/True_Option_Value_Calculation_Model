"""
Golden tests for California tax, the combined federal+CA AMT, and the QSBS (§1202) exclusion.
Hand-computed from the 2025 CA rate schedule and the OBBBA QSBS rules (see data/sources.md).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tov import tax

APPROX = 3.0


def _close(a, b, tol=APPROX):
    return abs(a - b) <= tol


def test_ca_income_tax_single():
    # $180k single. Taxable 174,460. Sum of CA brackets = 12,663.42.
    assert _close(tax.ca_income_tax(180_000, "single"), 12_663, 5)


def test_ca_amt_on_iso_exercise():
    # $180k + $150k bargain, single. CA TMT(330k)=16,408; CA reg=12,663 -> incremental CA AMT 3,745.
    assert _close(tax.ca_amt_on_iso_exercise(180_000, "single", 150_000), 3_745, 5)


def test_combined_amt_adds_state():
    c = tax.combined_amt_on_iso_exercise(180_000, "single", 150_000, state="CA")
    assert _close(c["federal"], 30_683, 5)
    assert _close(c["state"], 3_745, 5)
    assert _close(c["total"], 34_428, 8)
    # No-state case drops CA.
    c0 = tax.combined_amt_on_iso_exercise(180_000, "single", 150_000, state="none")
    assert c0["state"] == 0.0


def test_qsbs_full_exclusion_zeros_federal():
    # 5-year hold, post-OBBBA, gain under the $15M cap -> 100% federal exclusion.
    q = {"eligible": True, "era": "post_jul2025", "years": 5, "basis": 50_000}
    assert _close(tax.federal_gain_tax(5_000_000, 180_000, "single", q), 0.0, 1)


def test_qsbs_partial_tier_28pct():
    # 3-year hold, post-OBBBA -> 50% excluded; $2.5M included at 28% + 3.8% NIIT = 795,000.
    q = {"eligible": True, "era": "post_jul2025", "years": 3, "basis": 50_000}
    assert _close(tax.federal_gain_tax(5_000_000, 180_000, "single", q), 795_000, 50)


def test_california_does_not_conform_to_qsbs():
    # Even with 100% federal QSBS exclusion, California taxes the full $5M gain as ordinary income.
    q = {"eligible": True, "era": "post_jul2025", "years": 5, "basis": 50_000}
    r = tax.combined_exit_tax(5_000_000, 180_000, "single", "ltcg", state="CA", qsbs=q)
    assert _close(r["federal"], 0.0, 1), r
    assert r["state"] > 500_000, r          # CA still takes its cut — the conformity trap
    assert r["total"] == r["state"]


def test_combined_exit_tax_ltcg_vs_ordinary():
    # In CA, LTCG saves only the FEDERAL preference; the state portion is ordinary either way.
    ltcg = tax.combined_exit_tax(200_000, 180_000, "single", "ltcg", state="CA")
    ordn = tax.combined_exit_tax(200_000, 180_000, "single", "ordinary", state="CA")
    assert ltcg["total"] < ordn["total"]
    assert ltcg["state"] == ordn["state"]   # CA identical; only federal differs


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
    print(f"\n{passed}/{len(fns)} CA-tax / QSBS tests passed")
    sys.exit(0 if passed == len(fns) else 1)
