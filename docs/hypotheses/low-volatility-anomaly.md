# Low-volatility anomaly (H-LOWVOL01)

Status: preregistered
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
