"""
Monte Carlo over exit outcomes — the layer that turns a payoff *diagram* into an option *value*.

An option's value is not the payoff at one exit you typed in; it is the expectation of the payoff
over the distribution of exits that could actually happen, most of which are failure. This module
models that distribution and integrates the (correct) waterfall payoff against it.

Exit model (a mixture, because venture outcomes are bimodal — mostly zero, occasionally huge):
    with probability p_fail   : exit ~ Uniform(0, fail_ceiling * V0)   (the company dies / fire-sale)
    otherwise (survives)      : exit = V0 * LogNormal(median = survivor_median_multiple, sigma)

V0 is the current post-money valuation (known, or reverse-solved). The lognormal right tail captures
the power-law-ish reality that a few survivors return many multiples. Defaults are calibrated to be
sober, not promotional, and every parameter is user-overridable and surfaced in the UI.

Performance: the option payoff is a deterministic, monotonic, piecewise-linear function of exit
value, so we evaluate the waterfall on a grid ONCE and map all samples by interpolation.
"""

from __future__ import annotations

import numpy as np

from .waterfall import CapTable, option_payoff


def payoff_curve(cap: CapTable, option_shares: float, strike: float,
                 v_max: float, n_points: int = 1500):
    """Sample the net pre-tax option payoff across [0, v_max]. Returns (xs, ys) arrays."""
    xs = np.linspace(0.0, max(v_max, 1.0), n_points)
    ys = np.array([option_payoff(cap, float(v), option_shares, strike)["net_pretax"] for v in xs])
    return xs, ys


def simulate_exit_values(v0: float, n: int, p_fail: float, fail_ceiling: float,
                         survivor_median_multiple: float, sigma: float, seed: int = 12345):
    """
    Draw `n` exit valuations from the mixture model.

    p_fail            probability the company fails / fire-sales (exit well below the last round)
    fail_ceiling      failure exits land in Uniform(0, fail_ceiling * v0)  (e.g. 0.3 = up to 30% of V0)
    survivor_median   median exit multiple for survivors (e.g. 2.0 = 2x the current valuation)
    sigma             lognormal shape; larger = fatter tail of big outcomes
    """
    rng = np.random.default_rng(seed)
    u = rng.random(n)
    failed = u < p_fail
    fail_vals = rng.uniform(0.0, max(1e-9, fail_ceiling) * v0, size=n)
    mu = np.log(max(1e-9, survivor_median_multiple))
    surv_vals = rng.lognormal(mean=mu, sigma=sigma, size=n) * v0
    return np.where(failed, fail_vals, surv_vals).clip(min=0.0)


def simulate(cap: CapTable, option_shares: float, strike: float, v0: float,
             n: int = 50_000, p_fail: float = 0.55, fail_ceiling: float = 0.25,
             survivor_median_multiple: float = 2.5, sigma: float = 1.1,
             v_max_mult: float = 30.0, seed: int = 12345,
             tax_fn=None) -> dict:
    """
    Run the simulation and return the distribution of (optionally after-tax) option outcomes.

    tax_fn: optional callable(pre_tax_payoff: float) -> after_tax_payoff. If given, stats are
            computed on the after-tax payoff (so the headline expected value is take-home).

    Returns a dict of statistics plus the raw payoff samples (for histogramming in the UI).
    """
    v_max = max(v0 * v_max_mult, cap.total_preference * 4, 1.0)
    xs, ys = payoff_curve(cap, option_shares, strike, v_max)

    exits = simulate_exit_values(v0, n, p_fail, fail_ceiling, survivor_median_multiple, sigma, seed)
    payoffs = np.interp(exits, xs, ys)          # net PRE-tax payoff per simulated exit
    if tax_fn is not None:
        payoffs = np.array([tax_fn(float(p)) for p in payoffs])

    payoffs = payoffs.clip(min=0.0)
    zero_mask = payoffs <= 1.0                   # within $1 of nothing

    return {
        "n": int(n),
        "expected_value": float(payoffs.mean()),
        "prob_zero": float(zero_mask.mean()),            # P(your options are worth ~nothing)
        "p10": float(np.percentile(payoffs, 10)),
        "p50": float(np.percentile(payoffs, 50)),
        "p90": float(np.percentile(payoffs, 90)),
        "p99": float(np.percentile(payoffs, 99)),
        "max": float(payoffs.max()),
        "cvar_10": _cvar(payoffs, 0.10),                 # mean of the worst 10% of outcomes
        "exits": exits,
        "payoffs": payoffs,
        "v_max": v_max,
    }


def _cvar(payoffs: np.ndarray, q: float) -> float:
    """Conditional Value at Risk: the mean payoff in the worst `q` quantile of outcomes."""
    cutoff = np.percentile(payoffs, q * 100)
    tail = payoffs[payoffs <= cutoff]
    return float(tail.mean()) if tail.size else float(payoffs.min())
