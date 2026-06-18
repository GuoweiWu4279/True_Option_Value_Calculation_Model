"""
Liquidation-waterfall distribution engine.

This is the analytical core. Given a cap table and an exit (equity) value, it computes how the
proceeds flow through the preference stack down to common — handling the three mechanisms a naive
"% x exit" calculator silently ignores:

  1. Seniority / stacking      Senior rounds are paid before junior rounds; same rank is pari passu.
  2. Conversion option         Non-participating preferred takes max(preference, as-converted value).
                               At high exits it *converts to common* and forgoes its preference.
  3. Participation (+ caps)    Participating preferred takes its preference AND shares the residual,
                               up to an optional cap (a multiple of invested); beyond the cap it
                               converts to common if that is worth more.

Mechanisms 2 and 3 are interdependent (one holder's choice changes the residual everyone else
shares), so the solver iterates to the equilibrium set of conversion decisions via best-response
dynamics. For the monotone payoff structures here this converges in a handful of steps.

All values are in dollars / share counts. The engine is deterministic and side-effect free.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

_EPS = 1e-6


@dataclass
class PreferredRound:
    """One preferred financing round (or an aggregated block of investors)."""

    name: str
    invested: float                       # capital invested in this round ($)
    multiple: float = 1.0                 # liquidation-preference multiple (1.0x, 1.5x, 2.0x, ...)
    seniority: int = 0                    # LOWER = more senior (paid first). Equal = pari passu.
    participating: bool = False           # participating preferred ("double dip")?
    participation_cap: Optional[float] = None  # cap as a MULTIPLE of invested (e.g. 2.0). None = uncapped.
    as_converted_shares: float = 0.0      # common-equivalent shares if this round converts

    @property
    def preference(self) -> float:
        return self.invested * self.multiple

    @property
    def cap_total(self) -> Optional[float]:
        if self.participation_cap is None:
            return None
        return self.participation_cap * self.invested


@dataclass
class CapTable:
    """The full ownership picture at exit."""

    rounds: list                          # list[PreferredRound]
    common_shares: float                  # all common + option pool (INCLUDES the user's option shares)

    @property
    def fully_diluted_shares(self) -> float:
        return self.common_shares + sum(r.as_converted_shares for r in self.rounds)

    @property
    def total_preference(self) -> float:
        """The full liquidation overhang if every round takes its preference."""
        return sum(r.preference for r in self.rounds)


def _distribute_given_decisions(cap: CapTable, exit_value: float, convert: dict):
    """
    Distribute `exit_value` given a fixed set of conversion decisions.

    `convert[name]` True  -> that round converts to common (forgoes preference, shares pro rata).
                    False -> that round takes its preference (and participates if participating).

    Returns (payouts, common_price_per_share) where payouts maps round name -> $ and
    '__common__' -> total $ to the common pool.
    """
    rounds = cap.rounds
    payouts = {r.name: 0.0 for r in rounds}

    # --- Step 1: pay liquidation preferences (non-converting rounds), most senior first ---
    remaining = exit_value
    pref_takers = [r for r in rounds if not convert[r.name]]
    for rank in sorted({r.seniority for r in pref_takers}):
        group = [r for r in pref_takers if r.seniority == rank]
        demand = sum(r.preference for r in group)
        pay = min(remaining, demand)
        for r in group:
            frac = (r.preference / demand) if demand > 0 else 0.0
            payouts[r.name] += pay * frac
        remaining -= pay
        if remaining <= _EPS:
            remaining = 0.0
            break
    residual = max(0.0, remaining)

    # --- Step 2: distribute the residual to the common pool ---
    # Pool members: common + converted rounds (as common) + participating non-converted rounds.
    # Participation caps are settled by an inner loop: once a participating round would exceed its
    # cap, it is locked at the cap and removed from the pool, and the freed cash is redistributed.
    excluded_capped: set = set()
    locked: dict = {}                     # name -> participation $ locked at the cap (beyond preference)
    residual_pool = residual
    common_payout = 0.0
    common_price = 0.0

    def build_members():
        members = {"__common__": cap.common_shares}
        for r in rounds:
            if convert[r.name]:
                members[r.name] = r.as_converted_shares
            elif r.participating and r.name not in excluded_capped:
                members[r.name] = r.as_converted_shares
        return members

    for _ in range(len(rounds) + 2):
        members = build_members()
        total_shares = sum(members.values())
        price = (residual_pool / total_shares) if total_shares > 0 else 0.0

        # Does any participating, non-converted, not-yet-capped round breach its cap?
        newly_capped = None
        for r in rounds:
            if convert[r.name] or not r.participating or r.name in excluded_capped:
                continue
            if r.cap_total is None:
                continue
            total_take = payouts[r.name] + price * r.as_converted_shares   # preference + participation
            if total_take > r.cap_total + _EPS:
                newly_capped = r
                locked[r.name] = max(0.0, r.cap_total - payouts[r.name])
                break

        if newly_capped is None:
            # Settle: assign the per-share price to every pool member.
            for key, sh in members.items():
                if key == "__common__":
                    common_payout = price * sh
                else:
                    payouts[key] += price * sh        # participation / conversion proceeds
            common_price = price
            for nm, amt in locked.items():
                payouts[nm] += amt                    # locked participation for capped rounds
            break

        excluded_capped.add(newly_capped.name)
        residual_pool = max(0.0, residual_pool - locked[newly_capped.name])

    payouts["__common__"] = common_payout
    return payouts, common_price


def distribute(cap: CapTable, exit_value: float):
    """
    Compute the full waterfall at `exit_value`.

    Returns (payouts, common_price_per_share, convert_decisions):
        payouts            dict: round name -> $, and '__common__' -> $ to common pool
        common_price       $ per common share
        convert_decisions  dict: round name -> bool (True if it converted to common)
    """
    exit_value = max(0.0, float(exit_value))
    rounds = cap.rounds
    convert = {r.name: False for r in rounds}   # start: everyone takes their preference

    # Best-response dynamics: repeatedly flip the single decision that most improves that round's
    # own payout, until no unilateral flip helps (a Nash equilibrium of the conversion game).
    for _ in range(500):
        payouts, _ = _distribute_given_decisions(cap, exit_value, convert)
        best_gain, best_name = _EPS, None
        for r in rounds:
            trial = dict(convert)
            trial[r.name] = not trial[r.name]
            tp, _ = _distribute_given_decisions(cap, exit_value, trial)
            gain = tp[r.name] - payouts[r.name]
            if gain > best_gain:
                best_gain, best_name = gain, r.name
        if best_name is None:
            break
        convert[best_name] = not convert[best_name]

    payouts, common_price = _distribute_given_decisions(cap, exit_value, convert)
    return payouts, common_price, convert


def option_payoff(cap: CapTable, exit_value: float, option_shares: float, strike: float) -> dict:
    """
    Net pre-tax payoff to an option holder whose shares are part of `cap.common_shares`.

    A rational holder exercises only if in the money, so the payoff is floored at 0.
    Returns a dict with gross / exercise_cost / net_pretax / common_price.
    """
    _, common_price, _ = distribute(cap, exit_value)
    gross = option_shares * common_price
    exercise_cost = option_shares * strike
    net_pretax = max(0.0, gross - exercise_cost)
    return {
        "common_price": common_price,
        "gross": gross,
        "exercise_cost": exercise_cost,
        "net_pretax": net_pretax,
        "in_the_money": gross > exercise_cost + _EPS,
    }


def breakeven_valuation(cap: CapTable, option_shares: float, strike: float,
                        v_hi: Optional[float] = None) -> Optional[float]:
    """
    Smallest exit value at which the option's net pre-tax payoff turns positive.

    Solved by binary search on the (monotonic, piecewise-linear) payoff curve. Returns None if the
    option is never in the money below `v_hi`.
    """
    if strike <= 0:
        # Any positive common price clears a zero strike; breakeven is where common first sees cash.
        v_hi = v_hi or max(1.0, cap.total_preference * 4 + 1.0)
    if v_hi is None:
        v_hi = max(cap.total_preference * 10, strike * cap.fully_diluted_shares * 4, 1.0)

    def net(v):
        return option_payoff(cap, v, option_shares, strike)["gross"] - option_shares * strike

    if net(v_hi) <= 0:
        return None
    lo, hi = 0.0, v_hi
    for _ in range(60):
        mid = (lo + hi) / 2
        if net(mid) > 0:
            hi = mid
        else:
            lo = mid
    return hi
