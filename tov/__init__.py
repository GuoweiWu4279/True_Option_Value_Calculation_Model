"""
True Option Value (TOV) — a startup-equity reality-check engine.

Subpackages / modules:
    waterfall   Liquidation-waterfall distribution engine (the core).
    montecarlo  Exit-value distribution + simulation -> expected value, P(zero), CVaR.
    tax         Federal AMT / ordinary / LTCG estimators (2025) for ISO / NSO grants.
    reverse     Reverse solvers: derive fully-diluted shares / ownership from fragments.
    benchmarks  Year-based market archetypes (loaded from data/benchmarks.json).

Design principle: this package computes an *expected value* over a distribution of exit
outcomes, net of exercise cost and tax — not a single deterministic payoff point. See README.md
for the assumptions and limitations that bound every number it produces.
"""

from .waterfall import PreferredRound, CapTable, distribute, option_payoff, breakeven_valuation

__all__ = [
    "PreferredRound",
    "CapTable",
    "distribute",
    "option_payoff",
    "breakeven_valuation",
]
