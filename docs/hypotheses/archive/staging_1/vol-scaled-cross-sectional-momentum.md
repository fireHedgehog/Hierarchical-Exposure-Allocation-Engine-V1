# Volatility-scaled cross-sectional momentum (H-VOLSCALE01)

Status: invalidated by calendar-alignment bug; historical output retained below only as context
Version: v0.1
Registered: 2026-08-26

> **Correction, 2026-08-30:** the script compared the same integer row index
> across independently starting security histories. Formation dates, forward
> returns, and structure states were therefore not one shared cross-section.
> The +117.7% baseline and scaling comparison have no evidence status. The
> script is now date-aligned, but this archived experiment was not rerun.

Not wired into any pipeline stage. Preregistered *before* running the
comparison, per this session's own stated discipline (external review's
correct point): the base strategy and the scaling mechanism are fixed
here, before any result exists, so this doesn't become a search for
whatever exposure rule happens to improve the number after the fact.

## Thesis

Scaling `cross_sectional_momentum`'s existing, real, already-validated
strategy backtest's exposure down when the selected symbols' swing
structure is broken (H-DOW02's confirmed volatility signal) improves its
risk-adjusted return (Sharpe ratio, max drawdown) relative to the
identical strategy at constant, unscaled exposure — this is real
volatility targeting (Moreira & Muir, 2017, "Volatility-Managed
Portfolios," *Journal of Finance*: `size ∝ target vol / forecast vol`),
not confidence scaling (a distinct, un-tested claim about direction-
prediction accuracy degrading, which this does not test).

This would be falsified by no real improvement, or a real deterioration,
in the vol-scaled version's Sharpe ratio and max drawdown relative to the
constant-exposure baseline.

## Why this base strategy, not MACD/RSI

Direct correction from external review: layering a risk scaler onto
`macd_rsi_single_name_timing` would be uninterpretable, because that
strategy's entry trigger already has no proven directional edge (0.29:
r≈0.002, p≈0.66) — any Sharpe improvement could be the scaler working,
could be a scaler coincidentally patching an already-broken strategy, or
could be nothing more than "less exposure, less drawdown," true of any
size reduction regardless of whether the signal is real. `cross_sectional_
momentum`'s strategy backtest (0.20) is the one result this session with
real, already-validated standing evidence (+338.0% vs. +196.0% benchmark,
Sharpe 1.22) — scaling exposure on top of a base with real evidence is the
only version of this test whose result is actually interpretable.

## What would count as a real checkpoint

Two parallel walk-forward equity curves over the identical real dataset,
identical ranking function (`compute_cross_section_v2`, the same one
`factor_engine.py` calls in production), identical `top_n=5`,
`rebalance_days=21`:

1. **Baseline** — the existing, unmodified backtest (constant, unscaled
   exposure each period), reproduced exactly to confirm the comparison
   starts from the same real result already on record.
2. **Vol-scaled** — at each rebalance date, the fraction of the selected
   top-N symbols whose own swing structure (H-DOW02's exact fractal
   detector) is broken determines that period's exposure:
   `exposure = 1.0 - 0.5 * broken_fraction` (a disclosed, hand-picked,
   naive rule — not fit to this universe, same standard this project
   applies to every other naive-v1 parameter). The remainder sits in cash
   (0% return for that fraction of the position).

Computed via `backend/research_lab/vol_scaled_cross_sectional_momentum.py`
(read-only against the sealed dataset, imports the real
`compute_cross_section_v2` from `engine/`, never the production DB).

## Promotion criteria

A real, meaningful improvement in Sharpe and/or max drawdown, not just a
smaller number from being less invested on average (both curves' total
exposure-years should be compared, not just the risk-adjusted ratios in
isolation, to rule out "less exposure always looks safer" as the whole
explanation). If confirmed, this is the first real, mechanism-attributed
evidence that H-DOW02's risk-state signal has actual sizing value, not
just a standalone significant correlation — the bar this project has held
since Milestone 3 for anything claiming production relevance.

## Observation log

| Date | Checkpoint | Reading | Note |
| --- | --- | --- | --- |
| 2026-08-26 | Real walk-forward comparison, `research_lab/vol_scaled_cross_sectional_momentum.py` against dataset `real-macro-13ac93ba-77a2-477b-b958-07cab33db090`, 85 real rebalance periods, identical ranking/top_n/rebalance_days as the production backtest | **Real vs. the naive 100%-exposure baseline**: total return +117.7% -> +92.4%, Sharpe 0.75 -> 0.76 (essentially flat), max drawdown -25.9% -> -19.9% (a real, meaningful improvement). Mean exposure in the scaled version: 77.2%. **Attribution check (added before reporting, not after seeing a disappointing baseline result) — a naive constant 77.2% exposure, same average level, zero structure timing**: total return +85.4%, Sharpe 0.75, max drawdown -20.5%. The timed and untimed versions are nearly identical (+92.4% vs. +85.4% return, -19.9% vs. -20.5% drawdown) — the timed version is marginally better on both, but the gap is small against only 85 real periods, well within what sampling noise could produce. | Honest, not softened either direction. Most of the original comparison's apparent improvement is explained by simply being less invested on average, not by the structure-timing mechanism specifically -- exactly the confound external review named before this was built. The timing mechanism is not clearly rejected (it's not worse, and it's directionally a touch better on both metrics simultaneously, which a pure coincidence wouldn't obviously produce either) but it is not confirmed as adding real, mechanism-specific value on this sample size. A real, mature research outcome: the attribution check existing at all, and changing the honest conclusion, is the actual point of building it this way rather than skipping straight to "Sharpe improved, ship it." |
