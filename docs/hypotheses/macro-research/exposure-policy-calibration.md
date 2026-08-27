# Exposure policy calibration (H-MACRO10)

Status: preregistered
Version: v0.1
Registered: 2026-08-27

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
