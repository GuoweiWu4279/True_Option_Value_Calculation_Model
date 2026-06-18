# Archive — historical, do not use

These files are the **original MVP**, kept for history. They are superseded and should not be imported
or treated as current.

- `calculation_engine_legacy.py` — the first waterfall engine. It silently ignored participation and
  the non-participating conversion option, collapsed all investors into one class, and double-counted
  preferred in the common denominator. Replaced by the `tov/` package (validated against golden tests).
- `benchmarks_legacy.json` — the first benchmark file (market-regime keyed, terms unsourced). Replaced
  by `data/benchmarks.json` (year/regime archetypes) + `data/sources.md` (provenance).

Replaced 2026-06 during the ground-up rebuild. See `../README.md`.
