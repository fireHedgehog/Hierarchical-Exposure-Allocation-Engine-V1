# MAX effect / lottery-demand anomaly (H-MAX01)

Status: concluded-rejected (on this universe/window; see Observation log)
Version: v0.1
Registered: 2026-08-26

Not wired into any pipeline stage. Chosen deliberately as an orthogonal
candidate to everything tested so far this session: not about trend
direction (time-series-momentum.md, short-term-mean-reversion.md) and not
about total variance (low-volatility-anomaly.md), but about tail/skewness
behavior specifically — a genuinely different mechanism, not another
flavor of the same axis.

## Thesis

An asset's recent single-day maximum return (a lottery-like payoff) has a
real, negative relationship with its near-term forward return — investors
overpay for lottery-like upside exposure, and that overpayment mean-reverts
away. Ranking the staging universe by trailing maximum daily return should
show a real, negative relationship with subsequent forward return.

This would be falsified by a real test showing no significant relationship,
or a positive one, between trailing maximum daily return and forward
return across this staging universe.

## Prior

Bali, Cakici & Whitelaw (2011), "Maxing Out: Stocks as Lotteries and the
Cross-Section of Expected Returns," *Journal of Financial Economics* — a
real, replicated anomaly distinct from both momentum and low-volatility:
it isolates extreme single-day upside specifically, not the trend or the
overall variance of returns.

## What would count as a real checkpoint

A continuous, statistically testable claim, same shape as the other
price/vol papers this session: trailing maximum daily return over a
lookback window (e.g. 21 trading days, matching this project's own
standard monthly convention), tested for real IC against forward return
via `pearson_significance`/`rank_information_coefficient`, pooled across
every tradable staging symbol's real price history. Computed via
`backend/research_lab/max_effect.py` (read-only against the sealed
dataset, never the production DB).

## Promotion criteria

Real, significant IC in the predicted (negative) direction. If confirmed,
checked for real independence — not just difference in name — against
`short-term-mean-reversion.md`'s already-confirmed factor and the existing
production momentum blend, via `effective_number_of_bets`/pairwise
correlation (already-built infrastructure, 0.15): a high recent single-day
max return and a recent overall negative trailing return are not
obviously the same thing, but they are not obviously independent either,
and that has to be checked, not assumed, before either counts as a
separate bet.

## Observation log

| Date | Checkpoint | Reading | Note |
| --- | --- | --- | --- |
| 2026-08-26 | Real IC test, trailing 21-day max single-day return (inverted) vs. 21-day forward return, `research_lab/max_effect.py` against dataset `real-macro-d9a319bd-09e0-443b-93b3-2e6ec70f4170`, stride=5 | **Rejected, opposite direction.** r=-0.18 (adjusted p<0.0001, n=10,283); Rank IC=-0.13. The calmest-max third had a mean 21-day forward return of only +0.58%, vs. +2.41% for the third with the most extreme recent single-day max — the opposite of the predicted lottery-premium-reverts direction. | Real, not softened. This is the third rejection this session with the *same* directional signature: `low-volatility-anomaly.md` (calm underperforms, volatile outperforms) and this one (calm max underperforms, extreme max outperforms) both point the same way as `time-series-momentum.md`'s own-asset reversal finding — extreme/volatile/down periods in this window keep getting followed by stronger recoveries, not weaker ones. Three independent specifications landing on the same regime signature is stronger evidence for "this window has a dominant dip-buying/recovery character" than any one of them alone, though still not proof — a real, honest pattern worth naming plainly rather than treating as three unrelated surprises. Not promoted: rejected results don't reach the orthogonality-check step. |
