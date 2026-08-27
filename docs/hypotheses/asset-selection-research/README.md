# Asset selection research

Scope: does *which* asset/sector/theme to hold carry real, mineable
signal — separate from *how much* total risk to carry (macro regime)
and *when* to act (timing, its own folder now). Same lifecycle and
rules as the parent [`docs/hypotheses/README.md`](../README.md); own
index for the same reason `macro-research/` got one.

## Real universe (corrected framing, 2026-08-27)

This project doesn't have individual-stock cross-sectional data at any
real scale — the real, tradeable universe is 13 assets, all with
identical real history 2004-12-01 to 2026-08-26 (checked directly
against `data/desk.db`, anchored on `GLD`'s own listing, same anchor
the rest of this project already uses for its "2004+" dataset window):
`GLD`, `SPY`, `QQQ`, `DIA`, and the 9 sector SPDR ETFs (`XLB` `XLE`
`XLF` `XLI` `XLK` `XLP` `XLU` `XLV` `XLY`).

That's a small *sleeve/asset-class allocation* universe, not a broad
cross-sectional stock universe — a real, structural limit on what's
testable here, not a data-quality gap to fix. What fits: leadership/
relative-strength questions (small cross-section, but real), regime-
conditioned relative return, defensive rotation, duration/rate
sensitivity, inflation/dollar sensitivity, sector breadth/diffusion.
What doesn't fit without individual-stock data: the classic factor zoo
(value, quality, profitability, size, earnings revision — all need
stock- or industry-level fundamentals), decile-level stock-picking
momentum (13 assets isn't enough cross-section for deciles), or
theme/industry granularity finer than GICS sectors (AI hardware vs.
software vs. cybersecurity needs individual names). This folder is
positioned as the middle validation layer this size of universe is
actually good for — proving whether `macro state → relative sleeve
preference` is a real chain at all, before ever deciding whether it's
worth extending down to individual stocks.

## Relation to what's already tested

Existing top-level papers already tested single-symbol technical
factors, mostly IC vs. real forward return within one universe — not
sector/asset-class comparisons:

- Time-series momentum — rejected
- Short-term mean reversion — confirmed
- Low-volatility anomaly — rejected (raw return)
- MAX effect / lottery demand — rejected
- Vol-scaled cross-sectional momentum — inconclusive

`cross_sectional_momentum` (12-1) is the one graduated result from that
line of work, live in production — it ranks *within* one universe. This
folder is the layer above: which *dimension* to rank across (sector,
asset class, theme, fundamental characteristic), not which signal to
rank with inside one universe.

## The question, compressed

Not "will semiconductors go up" — **conditional on the current macro
and market state, is this exposure a better use of the risk budget than
the available alternatives.** Three questions nest together:

- Macro regime: how much risk should I own? (own folder)
- Asset selection: where should that risk be expressed? (this folder)
- Timing: when should I change the position? (own folder)

## Candidate framework — 7 sub-questions, not started

Each needs its own real-vs-baseline test, same non-negotiable this
project applies everywhere: a raw rate alone proves nothing.

| # | Question | Note |
| --- | --- | --- |
| 1 | Relative expected return — E[R_section − R_market \| state] | **Answered, confirmed** (H-SECT02): 11 of 24 sleeve/window tests significant after correction, all economically coherent (defensives + gold up in stress, growth/cyclicals up when calm) |
| 2 | Relative risk efficiency — return per unit of vol/drawdown | Not started |
| 3 | State sensitivity — exposure mapping to specific macro drivers (real yield, USD, oil, credit spreads), not a static GICS label | Partially answered by H-SECT02 (regime composite, not individual drivers yet) — decomposing which specific driver (real yield vs. credit vs. inflation) is doing the work is real follow-up work |
| 4 | Theme leadership — which cluster currently carries the market's marginal capital flow | Matches this project's own thematic-beta trading style (see [`thematic-beta-selection-process.md`](../thematic-beta-selection-process.md)) |
| 5 | Breadth / diffusion — is leadership concentrated in a few names or spreading | Distinguishes healthy leadership from late-stage narrow crowding |
| 6 | Crowding / convexity — has the strongest section become a negative-convexity trade (upside needs continued inflow, a miss is a big downside) | A different axis from momentum itself |
| 7 | Cross-section persistence — real duration distribution of leadership (median weeks in top-decile relative strength before it fades) | **Answered, rejected** (H-SECT01): at a quarterly, non-overlapping horizon, leadership persistence is indistinguishable from chance |

**Next recommended question:** an out-of-sample split of H-SECT02
(same shape as H-MACRO09's own OOS follow-up), before it's promotion-
ready. If that holds, the natural next step is the allocation-level
test H-SECT02's own paper scoped but didn't design: does a regime-
tilted sleeve allocation actually beat equal-weight/static on real
OOS Sharpe/drawdown/turnover — the test that would justify wiring any
of this into the allocation engine, vs. leaving it as sleeve-tilt
context for manual use.

## Restart-here: open questions, none started yet

| Question | Note |
| --- | --- |
| Section leadership persistence, regime-conditional (#7 above, connected to macro state) | **Run, rejected:** [`section-leadership-persistence.md`](section-leadership-persistence.md) (H-SECT01). At a quarterly, non-overlapping horizon, real persistence is indistinguishable from chance (33.3% vs. 33.3%, p=0.52) — a daily overlapping-window test had appeared to confirm it, but that was a mechanical confound, caught before write-up. |
| Regime-conditioned sleeve relative return (#1/#3) | **Run, confirmed:** [`regime-conditioned-sleeve-return.md`](regime-conditioned-sleeve-return.md) (H-SECT02). 11/24 tests significant, economically coherent. No OOS split yet. |
| H-SECT02 out-of-sample split | Not started; recommended next step before promotion |
| Regime-tilted sleeve allocation vs. equal-weight/static, real OOS Sharpe/drawdown/turnover | Not started; the actual allocation-level test, contingent on H-SECT02's OOS split holding |
| Which specific macro driver (real yield, credit, inflation) drives each sleeve's sensitivity | Not started; H-SECT02 used the composite, not individual factors |
| Relative risk efficiency (#2) | Not started |
| Theme leadership / marginal-flow detection (#4) | Not started; no data source identified yet for "capital flow," may need a proxy |
| Breadth / diffusion (#5) | Not started |
| Crowding / convexity (#6) | Not started; likely needs an options-market or short-interest proxy, may hit the same "free data only" ceiling macro research did |
| Regime-conditional cross-sectional performance — does `cross_sectional_momentum`'s edge change across `macro_regime_composite` states | Same as #7/recommended start; also listed in [macro-research](../macro-research/README.md)'s gap table |

## Index

| Paper | Status | Covers |
| --- | --- | --- |
| [Section leadership persistence](section-leadership-persistence.md) (H-SECT01) | concluded-rejected | Real quarterly-horizon test: P(leader next quarter \| leader this quarter) = 33.3%, exactly chance (p=0.52). A same-session daily-overlapping-window test had appeared to confirm persistence (p=0.001) — turned out to be a mechanical rolling-window artifact, not a real effect; caught and superseded before promotion. |
| [Regime-conditioned sleeve relative return](regime-conditioned-sleeve-return.md) (H-SECT02) | concluded-confirmed (in-sample) | Different mechanism than H-SECT01: macro state, not trend, predicting relative return. 11 of 24 sleeve/window tests significant after correction (~1.2 expected by chance) — defensives + gold outperform SPY when stressed, growth/cyclicals outperform when calm. No OOS split yet. |
