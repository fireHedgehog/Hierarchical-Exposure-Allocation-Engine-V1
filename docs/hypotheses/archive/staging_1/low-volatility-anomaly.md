# Low-volatility anomaly (H-LOWVOL01)

Status: concluded-rejected (raw-return version, on this universe/window; see Observation log)
Version: v0.1
Registered: 2026-08-26

Not wired into any pipeline stage. Candidate addition to
`cross_sectional_momentum`'s ranking, orthogonal to its existing momentum
horizons: ranks by trailing realized-volatility stability, not by trend
strength.

## Thesis

Lower trailing realized-volatility assets earn better risk-adjusted (and
sometimes even raw) forward returns than a naive risk-return tradeoff would
predict — a real, replicated anomaly, not the textbook expectation that
higher risk should earn higher return. Ranking the staging universe by
inverse trailing volatility should show a real, positive relationship with
forward returns.

This would be falsified by a real test showing no significant relationship
(or the textbook-expected positive one — higher vol, higher forward return)
between trailing realized volatility and forward return across this
staging universe.

## Prior

Ang, Hodrick, Xing & Zhang (2006), "The Cross-Section of Volatility and
Expected Returns," *Journal of Finance*. Frazzini & Pedersen (2014),
"Betting Against Beta," *Journal of Financial Economics* — a genuine,
widely replicated anomaly across markets and time periods, distinct from
and largely uncorrelated with momentum (a stability signal, not a trend
signal) — a real candidate for adding an independent bet to the ensemble,
not a restatement of momentum in different clothing.

## What would count as a real checkpoint

A continuous, statistically testable claim, same shape as time-series
momentum: real trailing realized volatility (e.g. a rolling 63-day
annualized standard deviation of returns), inverted and ranked
cross-sectionally, tested for real IC against forward return via
`pearson_significance`/`rank_information_coefficient`, pooled across every
tradable staging symbol's real price history. Computed via
`backend/research_lab/low_volatility_anomaly.py` (read-only against the
sealed dataset, never the production DB).

## Promotion criteria

Real, significant IC (loose bar acceptable, per Grinold & Kahn — see
time-series-momentum.md for the same reasoning). Once this and at least
one other independent cross-sectional candidate both have real evidence,
both become eligible for a real weighted-combination experiment alongside
the existing momentum horizons — checked for redundancy first
(`effective_number_of_bets`/pairwise correlation, already real
infrastructure) to confirm it's an independent bet, not 0.9x momentum
in different clothing.

## Observation log

| Date | Checkpoint | Reading | Note |
| --- | --- | --- | --- |
| 2026-08-26 | Real IC test, 63-day trailing realized vol (inverted) vs. 21-day forward return, `research_lab/low_volatility_anomaly.py` against dataset `real-macro-d9a319bd-09e0-443b-93b3-2e6ec70f4170`, stride=5 | **Rejected as stated, for raw return.** r=-0.19 (adjusted p<0.0001, n=10,115); Rank IC=-0.15 (raw p<0.0001). The calmest third of the sample had a mean 21-day forward return of only +0.62%, vs. +2.73% for the most volatile third — the opposite of the predicted direction. | Real, not softened. Notable: this is the *same direction of surprise* as time-series-momentum.md's rejection, not an unrelated fluke — both are consistent with one underlying story about this specific window (2016-2026): a high-realized-vol reading is usually a recent drawdown/selloff, and if sharp drawdowns get bought aggressively in a dominant secular bull market, that alone produces both "down periods reverse up" (time-series momentum) and "volatile periods rebound hard" (this one) as two faces of the same regime characteristic, not two independent anomalies. Real scope caveat, not glossed over: this only tested raw forward return; the academic claim (Ang et al.; Frazzini & Pedersen) is more precisely stated in risk-adjusted (Sharpe/CAPM-alpha) terms — a volatile asset can have a higher raw return and still a worse risk-adjusted one. This result does not test that more precise claim; a real risk-adjusted follow-up would need to divide the forward return by its own realized vol before comparing buckets, not compared here. |
