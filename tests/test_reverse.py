"""Tests for the reverse solvers (offer-letter fragments -> model inputs)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tov import reverse


def _close(a, b, tol=1e-6):
    return abs(a - b) <= tol


def test_fd_shares_from_post_money():
    # $200M post-money at $20.00/share -> 10M fully diluted shares.
    assert _close(reverse.fd_shares_from_post_money(200_000_000, 20.0), 10_000_000)


def test_fd_shares_from_ownership():
    # 100k shares at 0.5% ownership -> 20M fully diluted shares.
    assert _close(reverse.fd_shares_from_ownership(100_000, 0.5), 20_000_000)


def test_ownership_roundtrip():
    fd = reverse.fd_shares_from_ownership(100_000, 0.5)
    assert _close(reverse.ownership_pct(100_000, fd), 0.5)


def test_dilution_compounds():
    # 10M shares, three 20% rounds -> 10M / 0.8^3 = 19.53125M.
    assert _close(reverse.dilute(10_000_000, 0.20, 3), 10_000_000 / (0.8 ** 3), 1e-3)


def test_naive_paper_value():
    assert _close(reverse.naive_paper_value(100_000, 0.50, 20.0), 1_950_000)


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
    print(f"\n{passed}/{len(fns)} reverse-solver tests passed")
    sys.exit(0 if passed == len(fns) else 1)
