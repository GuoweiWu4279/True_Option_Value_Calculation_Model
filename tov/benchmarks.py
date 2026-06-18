"""
Accessors for the market-archetype benchmark data (data/benchmarks.json).

Keeps the JSON as the single source of truth and gives the app a small, typed surface to read it,
so no benchmark figure is ever hard-coded in the UI.
"""

from __future__ import annotations

import json
import os

_DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "data", "benchmarks.json")


def load() -> dict:
    with open(_DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def regimes() -> dict:
    """All archetypes except the _meta block, as {key: record}."""
    return {k: v for k, v in load().items() if not k.startswith("_")}


def labels() -> dict:
    """{key: human label} for populating a selectbox."""
    return {k: v.get("label", k) for k, v in regimes().items()}


def exit_outcomes(stage: str) -> dict:
    """Calibrated exit-distribution preset (p_fail, survivor_median_multiple, sigma, fail_ceiling)
    for a funding stage. Falls back to the Series A (calibrated) preset for unknown stages."""
    table = load().get("_exit_outcomes", {})
    return table.get(stage, table.get("Series A", {
        "p_fail": 0.45, "survivor_median_multiple": 1.5, "sigma": 1.30, "fail_ceiling": 0.30}))


def get(regime_key: str, stage: str) -> dict:
    """
    Flattened defaults for a (regime, stage) pair:
    liquidation_multiple, participating, participation_cap, dilution, investor_ownership_pct.
    """
    rec = regimes().get(regime_key, {})
    return {
        "label": rec.get("label", regime_key),
        "liquidation_multiple": rec.get("liquidation_multiple", 1.0),
        "participating": rec.get("participating", False),
        "participation_cap": rec.get("participation_cap"),
        "dilution": rec.get("dilution_per_round", {}).get(stage, 0.18),
        "investor_ownership_pct": rec.get("investor_ownership_pct", {}).get(stage, 0.40),
        "note": rec.get("note", ""),
    }
