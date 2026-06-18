"""
Reverse solvers — turn the fragments an employee actually has into the inputs the model needs.

The whole project thesis is that employees rarely know the full cap table. But they usually know a
*few* numbers from their offer letter or the last round announcement. These helpers back out the
fully-diluted share count and ownership from those scraps, with the algebra made explicit.
"""

from __future__ import annotations

from typing import Optional


def fd_shares_from_post_money(post_money_valuation: float, price_per_share: float) -> Optional[float]:
    """
    Fully-diluted shares = post-money valuation / price per share of the last round.

    Both numbers are commonly disclosed when a round is announced.
    """
    if price_per_share <= 0:
        return None
    return post_money_valuation / price_per_share


def fd_shares_from_ownership(my_shares: float, my_ownership_pct: float) -> Optional[float]:
    """If your offer letter quotes a current ownership %, invert it to the total share count."""
    if my_ownership_pct <= 0:
        return None
    return my_shares / (my_ownership_pct / 100.0)


def ownership_pct(my_shares: float, fd_shares: float) -> float:
    if fd_shares <= 0:
        return 0.0
    return my_shares / fd_shares * 100.0


def dilute(fd_shares: float, dilution_pct_per_round: float, rounds: int) -> float:
    """
    Project fully-diluted shares forward through `rounds` future raises, each selling
    `dilution_pct_per_round` of the company. Your share count is fixed; the denominator grows.
    """
    factor = 1.0
    for _ in range(max(0, rounds)):
        factor *= (1.0 - dilution_pct_per_round)
    if factor <= 0:
        return float("inf")
    return fd_shares / factor


def naive_paper_value(my_shares: float, strike: float, price_per_share: float) -> float:
    """
    What a naive '% x exit' calculator (or your offer letter's 'potential value') tells you:
    shares x (last preferred price - strike). The whole point of this tool is to show how far
    the waterfall-adjusted reality can fall below this number.
    """
    return max(0.0, my_shares * (price_per_share - strike))
