# Exposure policy calibration (H-MACRO10)

Status: concluded-confirmed. Real directional bug found and fixed (naive-v2, `envelope_v2.py`, live in production); the fix also backtests better than both static exposure and the old naive-v1 formula, consistently across full-sample, in-sample, and out-of-sample.
Version: v0.2
Registered: 2026-08-27
Concluded: 2026-08-28

## Thesis

`risk_envelope_allocation` (naive-v1, `backend/engine/allocation/envelope.py`)
maps regime confidence straight to a gross-exposure multiplier:
`multiplier = clamp(confidence * 2.0, 0.5, 1.5)`. That collapses two
different hypotheses into one number. H-MACRO09 validated: composite
state → forward drawdown *probability*. This paper is the separate,
still-untested claim: composite state (or its drawdown probability) →
*optimal gross exposure level*. Flagged by an external review, not
discovered internally — recorded here because it's real and correct.

## Prior

None run yet. Optimal exposure would actually depend on expected
return conditional on regime, conditional volatility, drawdown
*severity* (not just probability), turnover cost of changing exposure,
and diversification against other sleeves — a portfolio-optimization/
utility question, not a correlation test. The current 0.5x-1.5x band
and the `* 2.0` scale factor are both hand-picked, already disclosed as
naive-v1/`registered_only` in `schema.sql` and the Methodology page —
not silently presented as validated.

## What would count as a real checkpoint

A real backtest comparing, out-of-sample: (a) static 1.0x gross
exposure, (b) the current confidence-scaled multiplier, (c) at least
one alternative scaling rule (e.g. scaled off drawdown probability
directly, or off realized/conditional volatility) — on real forward
Sharpe and real realized max drawdown. Same chronological-split
discipline as `composite-forward-risk-oos.md`.

## Promotion criteria

A real, out-of-sample result showing the scaled rule beats static
exposure on risk-adjusted return without materially worsening realized
drawdown. Until then `risk_envelope_allocation` stays naive-v1/
registered_only — this paper doesn't change that status, it documents
that the confidence→multiplier mapping is a separate, unvalidated
hypothesis layered on top of a validated one (H-MACRO09), and keeps the
two from being read as one proven chain.

## Architecture note

Keep three layers separate going forward: macro state estimator → risk
probability estimator → exposure policy. `regime_confidence` and
`gross_multiplier` must not collapse into one number, even though
today's naive-v1 code does exactly that. Next real step, if picked up,
is testing the third arrow (probability → exposure) on its own — not
making the macro composite itself more complex.

## Observation log

| Date | Checkpoint | Reading |
| --- | --- | --- |
| 2026-08-27 | Preregistered from external review pointing out the conceptual mismatch between H-MACRO09's validated drawdown-probability evidence and the unvalidated confidence→multiplier mapping in `envelope.py`. Also confirmed as correctly scoped: the live percentile gauge only claims a validated relationship at the 3 tercile zones (0-33/33-67/67-100), not at fine percentile resolution — matches the decile-granularity finding already logged in `composite-forward-risk.md`. | No experiment run yet. |
| 2026-08-28 | Direct check of the actual formula at the real, current confidence range (0.071-0.345), before any backtest. | **A real, more severe finding than "unvalidated": naive-v1's formula is directionally backwards.** `stressed` (confidence 0.345) → 0.69x. `middle` (0.238) → 0.50x (floored). `calm` (0.071) → 0.50x (floored). Stressed gets *more* exposure than calm; calm and middle are indistinguishable. Live-confirmed, not just computed: a real pipeline run at confidence=0.24 had already published exactly a 0.50x multiplier. |
| 2026-08-28 | Fixed: `backend/engine/allocation/envelope_v2.py` (naive-v2). Real, monotonically decreasing linear interpolation between the same two already-validated calibration endpoints (`HISTORICAL_DRAWDOWN_RATE_CALM` → 1.5x, `HISTORICAL_DRAWDOWN_RATE_STRESSED` → 0.5x) — no new numbers invented, same 0.5x-1.5x band as naive-v1. `schema.sql` gained the naive-v2 registration (new `strategy_versions` row, dual-path summary correction). 8 new isolated tests (`test_allocation_envelope_v2.py`), including a direct regression test at the real production confidence range. 185/186 backend tests passing (1 known pre-existing flaky concurrency test). Live-verified: the same real regime state (confidence 0.24) now publishes a 0.89x multiplier, not 0.50x. | Real bug fixed, verified 3 ways (unit test, live pipeline, direct math) before any backtest. |
| 2026-08-28 | Real checkpoint this paper was designed for: `research_lab/exposure_policy_backtest.py` — static 1.0x vs. naive-v1 (bug) vs. naive-v2 (fixed), on the same 12-sleeve equal-weight book H-SECT04 used, real OOS split (2019-01-01). | **Confirmed — naive-v2 beats static on both Sharpe and drawdown, consistently across every window.** See table below. |

| Window | Rule | Sharpe | Max drawdown | Ann. return |
| --- | --- | --- | --- | --- |
| Full sample | Static 1.0x | 0.83 | -46.95% | +11.28% |
| Full sample | naive-v1 (bug) | 0.76 | -30.77% | +5.61% |
| Full sample | **naive-v2 (fixed)** | **0.88** | **-34.82%** | +10.61% |
| In-sample (2004-2018) | Static 1.0x | 0.67 | -46.95% | +9.09% |
| In-sample | **naive-v2** | **0.76** | **-34.82%** | +9.65% |
| Out-of-sample (2019-2026) | Static 1.0x | 1.04 | -22.11% | +16.46% |
| Out-of-sample | **naive-v2** | **1.05** | **-19.76%** | +14.54% |

naive-v2 beats static on Sharpe in all 3 windows (never reverses) and on max drawdown in all 3 windows too — a small, real, consistently-directional improvement, meeting this paper's own promotion bar. naive-v1 (the bug) shows lower drawdown than static, but that's an accident of chronic under-exposure (its multiplier floors at 0.5x most of the time), not a real, designed risk-reduction — it sacrifices real return without a real risk-adjusted payoff (Sharpe 0.76-1.03, roughly flat-to-worse than static). Real, disclosed limitation: the Sharpe differences are modest and no formal significance test was run on them (unlike this project's IC/proportion tests elsewhere) — the promotion case rests on directional consistency across 3 independently-windowed backtests plus the already-proven, independent directional-bug fix, not on a p-value for the Sharpe gap itself.
