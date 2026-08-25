# Time-series momentum (H-TSM01)

Status: concluded-rejected (on this universe/window; see Observation log)
Version: v0.1
Registered: 2026-08-26

Not wired into any pipeline stage. Candidate replacement/challenger for
`macd_rsi_single_name_timing`'s MACD-crossover entry trigger, which this
session's own real event-study (`run_timing_signal_significance_research`,
0.29) found has no real edge (r=+0.002, p=0.66) over this universe/decade.

## Thesis

An asset's own trailing return *sign* — not its return relative to peers,
and not a moving-average crossover derived from it — predicts the sign of
its own forward return. Go long when trailing 12-month return is positive,
flat otherwise. This is a distinct claim from cross-sectional momentum
(already real and built, `cross_sectional_momentum`): that ranks assets
against each other; this asks only about one asset's own trend, in
isolation.

This would be falsified by a real test showing no significant relationship
between an asset's own trailing-return sign and its own forward return,
across this staging universe's real price history.

## Prior

Moskowitz, Ooi & Pedersen (2012), "Time Series Momentum," *Journal of
Financial Economics* — documented positive, consistent time-series momentum
across equity indices, bonds, commodities, and currencies, 1985-2009+.
Hurst, Ooi & Pedersen extended the same finding back over roughly a century
of data across asset classes. One of the most replicated results in the
empirical asset-pricing literature — not a single-paper anomaly.

Directly motivated by this project's own finding: MACD's bullish crossover
is a noisy, lagging technical proxy for exactly this same underlying idea
(is the trend up or down). Time-series momentum tests the idea directly,
without the crossover mechanism's added noise.

## What would count as a real checkpoint

Unlike a qualitative, event-driven hypothesis (e.g. the Warsh reaction
function), this is a continuous, statistically testable claim — a
checkpoint here is a real computed IC/point-biserial test, not a
real-world event. Test: trailing-return sign (at 1m/3m/6m/12m lookbacks,
matching this project's existing momentum-horizon convention) as a 0/1
indicator, paired with the real forward return, pooled across every
tradable staging symbol's full real price history — the same
`pearson_significance` utility already used throughout this project's
real research. Computed via `backend/research_lab/time_series_momentum.py`
(read-only against the sealed dataset, never the production DB).

## Promotion criteria

Real, significant IC at at least one lookback horizon (a looser bar than
strict significance is acceptable per Grinold & Kahn's fundamental law —
a real, weak signal is still useful once weighted against others, not
useless until it clears an arbitrary strict cutoff alone). Once this and
at least one other independent timing candidate both have real evidence,
both become eligible for an engineered `strategy_components` entry and a
real weighted-combination experiment — a single candidate has nothing to
be weighted against.

## Observation log

| Date | Checkpoint | Reading | Note |
| --- | --- | --- | --- |
| 2026-08-26 | Real IC test, all 4 horizons (1m/3m/6m/12m), `research_lab/time_series_momentum.py` against dataset `real-macro-d9a319bd-09e0-443b-93b3-2e6ec70f4170`, stride=5 to control for overlapping-window autocorrelation | **Rejected as stated.** All 4 horizons significant after correction, but the sign is negative at every one -- the opposite of the predicted direction: 1m r=-0.042 (adj. p<0.0001, n=10,283), 3m r=-0.033 (adj. p=0.0009, n=10,115), 6m r=-0.035 (adj. p=0.0007, n=9,842), 12m r=-0.046 (adj. p<0.0001, n=9,317). Mean 21-day forward return after a trailing-negative period (+1.7% to +2.0%) consistently beat the mean forward return after a trailing-positive period (+1.1% to +1.3%), at every horizon tested. | Real, not an error -- rerun once already to rule out one (found: the first pass used no stride, overlapping 251-of-252-day windows on the 12m horizon, which understated the true p-values; corrected with stride=5, matching momentum_v2.py's own convention, and the result held). Plausible honest mechanism, not asserted as proven: this staging universe's window (2016-2026) contains one of the strongest sustained secular equity bull markets on record -- "buy the dip" being a persistently rewarded behavior would produce exactly this pattern (pullbacks recover strongly; strong run-ups have less room left to keep compounding at the same pace), without contradicting Moskowitz-Ooi-Pedersen's original cross-asset, multi-decade result, which was never tested on this specific universe/window. Notably different from cross_sectional_momentum's own real finding (0.26): that showed short-term reversal (1m/3m) but genuine 12-1 momentum -- this time-series (own-asset, not vs.-peers) version shows uniform mean-reversion across every horizon including 12m, a real, substantive distinction between "is this asset beating its peers" and "is this asset beating its own past," not the same question asked twice. |
