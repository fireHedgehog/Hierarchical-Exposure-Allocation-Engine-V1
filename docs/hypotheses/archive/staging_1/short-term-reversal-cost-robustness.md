# Short-term reversal: transaction-cost / turnover robustness (H-STREV02)

Status: invalidated by calendar-alignment and turnover bugs; historical output retained below only as context
Version: v0.1
Registered: 2026-08-26

> **Correction, 2026-08-30:** the script used the same integer row index
> across securities with different listing dates, so formation and exit dates
> were not shared. It also counted a complete replacement as 200% turnover
> while applying a round-trip cost rate. The +444.2% curve and its cost
> thresholds have no evidence status. H-XSEC-S2-004 later found a much smaller,
> correctly aligned liquid-stock reversal relationship; it did not rerun this
> trading/cost claim.

Not wired into any pipeline stage. Direct follow-up to `short-term-mean-
reversion.md` (H-STREV01, confirmed, strengthened on 2004-2026): that paper
tested gross IC only. Real quant practice (and this project's own Milestone
4 "trading reality" category, never populated with real data before now)
treats gross statistical significance and net-of-cost tradability as
separate questions — a real, significant IC can still be economically
worthless if turnover and realistic costs eat it, which the literature
explicitly documents for short-horizon reversal specifically (net returns
here are known to be sensitive to transaction costs and often strongest in
harder-to-scale, less liquid names).

## Thesis

A real, tradable long-only strategy built directly on H-STREV01's signal
(rank the tradable universe by trailing 5-day return each week, buy the
biggest losers, hold one week) retains a real, positive net-of-cost edge
at realistic transaction-cost assumptions for this specific staging
universe — not at every conceivable cost level, but at levels plausible
for the actual instruments involved (major sector ETFs, broad index
ETFs, and two mega-cap stocks — already a liquid universe, not one that
needs a separate large-cap/liquid-universe filter the way a broader
individual-equity universe would).

This would be falsified by the net edge disappearing (Sharpe near zero or
negative, or gross-to-net degradation exceeding what realistic turnover
and cost assumptions can explain as "still tradable") at cost levels
plausible for this universe.

## What would count as a real checkpoint

A real walk-forward comparison, not another IC test: weekly rebalance
(5-trading-day cadence, matching the signal's own confirmed window),
rank the tradable universe by trailing 5-day return, buy the bottom N
(biggest recent losers) equal-weighted, hold to the next rebalance,
chain into a real equity curve — gross, and net at several real,
disclosed round-trip cost assumptions (5bps, 10bps, 25bps, 50bps),
scaled by actually-measured turnover each period, not an assumed
constant. Computed via
`backend/research_lab/short_term_reversal_cost_robustness.py`
(read-only against the sealed dataset, imports nothing from repository/
pipeline internals, never writes anywhere).

## Promotion criteria

A real, positive net Sharpe surviving at least the lower end of the
disclosed cost range. If the edge survives: real candidate for
`strategy_components`, registered honestly (`research_status=confirmed`,
paired with whatever the net-cost result actually supports for
`trading_ready`). If gross survives but net does not at any plausible
cost level: still worth registering as a real, demonstrated research
factor with `trading_ready=false` — a pipeline running an honestly
labeled, cost-unvalidated factor is more honest than a synthetic
placeholder kept only so a page isn't empty (this project's own
developer's letter: pipeline runnable is not the same standard as
trading ready).

## Observation log

| Date | Checkpoint | Reading | Note |
| --- | --- | --- | --- |
| 2026-08-26 | Real weekly walk-forward, buy the biggest trailing-5-day losers (top 5 of the tradable universe), `research_lab/short_term_reversal_cost_robustness.py` against dataset `real-macro-d9f2cc46-a52b-4d9e-a3ef-b8bdef437e63`, 410 real rebalance periods | **Gross: real and strong.** Total return +444.2%, Sharpe 1.15, max drawdown -34.3%. **Net of real, measured turnover (mean 148.7% per period — this strategy rotates holdings almost completely most weeks) at four disclosed cost levels**: 5bps -> Sharpe 0.96; 10bps -> Sharpe 0.77; 25bps -> Sharpe 0.21 (barely positive); 50bps -> Sharpe -0.73 (edge fully destroyed). | Real, cost-sensitive, not a clean yes/no. The edge survives at cost levels genuinely plausible for this specific universe (major, highly liquid sector/index ETFs plus two mega-caps typically trade at single-digit-bps round-trip spreads in practice) but breaks down well before 50bps. Turnover is real and high by construction -- ranking by "who crashed most this week" naturally reshuffles the book close to completely, unlike momentum-style rankings with more persistence. Caveat disclosed, not glossed over: the walk-forward spine is constrained by the shortest symbol's real history (XLC, listed 2018), so this actually covers ~2018-2026, not the full 2004-2026 window the dataset otherwise supports -- same limitation the existing cross-sectional backtest already has. Confirmed as real and tradable *at this universe's realistic cost levels*, not universally -- exactly the honest, cost-sensitive category this paper was preregistered to test for, not a pass/fail simplification. |
