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
| 1 | Relative expected return — E[R_section − R_market \| state] | **Answered, confirmed but narrowed** (H-SECT02 → H-SECT05): raw test found 11/24 significant, but beta-adjustment (controlling for each sleeve's own beta to SPY) drops that to 3/24. Only `XLU` (both windows) and `XLY` (63d) are real independent of beta — `GLD`'s headline effect was almost entirely a beta artifact. |
| 2 | Relative risk efficiency — return per unit of vol/drawdown | Not started |
| 3 | State sensitivity — exposure mapping to specific macro drivers (real yield, USD, oil, credit spreads), not a static GICS label | **Answered, rejected** (H-SECT03): no single driver (real yield, credit, VIX, breakeven inflation) dominates any sleeve's sensitivity — a real null supporting the composite's own redundancy-aware design over any one raw factor |
| 4 | Theme leadership — which cluster currently carries the market's marginal capital flow | Matches this project's own thematic-beta trading style (see [`thematic-beta-selection-process.md`](../thematic-beta-selection-process.md)) |
| 5 | Breadth / diffusion — is leadership concentrated in a few names or spreading | Distinguishes healthy leadership from late-stage narrow crowding |
| 6 | Crowding / convexity — has the strongest section become a negative-convexity trade (upside needs continued inflow, a miss is a big downside) | A different axis from momentum itself |
| 7 | Cross-section persistence — real duration distribution of leadership (median weeks in top-decile relative strength before it fades) | **Answered, rejected** (H-SECT01): at a quarterly, non-overlapping horizon, leadership persistence is indistinguishable from chance |

**Where this arc landed:** H-SECT01 (rejected) → H-SECT02 (confirmed,
real regime-conditioned sleeve sensitivity) → H-SECT03 (rejected — no
single driver explains it, it's a genuine composite effect) → H-SECT04
(rejected — the real correlation doesn't translate into a meaningful
allocation edge once turned into an actual weighted portfolio rule) →
H-SECT05 (H-SECT02 narrowed — most of it was beta, not new information;
`XLU` is the one sleeve that survives every check run). H-SECT06 (gold
reaction function) reopens `GLD` specifically as a cold-start, ongoing
event log — not reversing H-SECT05's finding that gold's correlation
with the *existing* composite was mostly beta, but testing whether a
*different*, currently-unmodeled mechanism (fiscal dominance) is doing
something real instead. H-SECT07-09 asked a higher-level question —
park *direction*, test whether real opportunity/differentiation itself
is predictable: H-SECT07 (dispersion) found a real full-sample pattern
that didn't survive an OOS check; H-SECT08 (regime velocity) was a
clean, unambiguous null; H-SECT09 (conjunctive `XLU` trigger) found a
significant-but-fragile result driven by a 3-observation extreme
bucket. Net conclusion on the concluded papers:
`macro_regime_composite` stays scoped to gross exposure
(`risk_envelope_allocation`, already live); this specific sleeve-tilt
idea is a real, tested, documented dead end, not an unexplored one.
Remaining open questions (#2, #4, #5, #6) are lower-priority — none
connect as directly to what's already been validated. #5 (breadth) is
specifically **not researchable** with this project's data: it needs
individual-stock membership within each sector, which this project
deliberately doesn't have (ETF-level only, a real, disclosed scope
decision, not a gap to close).

## Restart-here: every known gap, in one place

| Question | Status |
| --- | --- |
| Section leadership persistence (#7) | **Rejected.** [H-SECT01](section-leadership-persistence.md): quarterly persistence = exactly chance (33.3%, p=0.52). |
| Regime-conditioned sleeve relative return (#1/#3) | **Confirmed, then narrowed.** [H-SECT02](regime-conditioned-sleeve-return.md): 11/24 significant raw. [H-SECT05](beta-adjusted-regime-sensitivity.md) controlled for beta: only 3/24 survive (`XLU` both windows, `XLY` 63d real; `GLD`'s headline effect was almost entirely beta). |
| Which driver explains it (#3, decomposed) | **Rejected (real null).** [H-SECT03](sleeve-driver-decomposition.md): no single driver (real yield/credit/VIX/breakeven) dominates — genuinely a composite effect. |
| Regime-tilted allocation vs. equal-weight, real OOS Sharpe/drawdown/turnover | **Rejected.** [H-SECT04](regime-tilted-allocation-backtest.md): Sharpe improvement +0.008 OOS — real in sign, economically trivial, doesn't clear its own turnover cost. This line of work is concluded, not parked. |
| Is the regime-sleeve correlation just beta? | **Answered.** [H-SECT05](beta-adjusted-regime-sensitivity.md): mostly yes, for `GLD`/`DIA`/`XLP`/`QQQ`. `XLU` and `XLY` (63d) are real beyond beta. |
| Relative risk efficiency (#2) | Not started; lower priority now that #1/#3's allocation-level payoff (H-SECT04) came back negative |
| Theme leadership / marginal-flow detection (#4) | Not started; no data source identified yet for "capital flow," may need a proxy |
| Breadth / diffusion (#5) | **Not researchable with this project's data** — needs individual-stock membership within each sector; this project deliberately works at the ETF/sleeve level only. Not a gap to close. |
| Sleeve dispersion / opportunity-set | **Run, inconclusive.** [H-SECT07](sleeve-dispersion-opportunity.md): 6/10 significant full-sample, but 0/10 out-of-sample (same sign, plausibly underpowered, not reversed). Real but unconfirmed — don't build on it as a settled gate yet. |
| Regime velocity (worsening vs. stably-stressed) — does it change cross-sectional dispersion/opportunity | **Rejected, cleanly.** [H-SECT08](regime-velocity-opportunity.md): 0/6 significant, all r trivially small. No OOS check needed — a null full-sample result doesn't need it the way a confirmed one does. |
| Conjunctive `XLU` trigger (multiple clusters aligned) | **Run, inconclusive.** [H-SECT09](conjunctive-xlu-trigger.md): IC significant both windows (p=0.02-0.04), but driven substantially by a 3-observation extreme bucket (all 3 clusters stressed). The more robust sub-pattern (any alignment beats none, n=105+) is closer to "already known from H-SECT02/05" than a real conjunctive effect. |
| Gold's own reaction function — fiscal-dominance/debasement hedge vs. Fed-dovish | **Observing.** [`gold-reaction-function.md`](gold-reaction-function.md) (H-SECT06), cold-start event log, same shape as `warsh-reaction-function.md`. 1 real checkpoint (2026-08-27). |
| Conjunctive/constraint-based sector triggers | Not started; user's own idea, inspired by `XLU` being the one sleeve that survived every check (H-SECT05). Instead of one continuous composite IC (what H-SECT02/03/05 all tested), test whether a sleeve only shows a strong, reliable directional bias when *several* specific conditions align simultaneously (e.g. real yield rising AND credit spreads widening AND USD strong) — a genuinely different design (rule/AND-based, not linear correlation), not yet tried anywhere in this folder |
| Crowding / convexity (#6) | Not started; likely needs an options-market or short-interest proxy, may hit the same "free data only" ceiling macro research did |
| Regime-conditional cross-sectional performance for `cross_sectional_momentum` itself (not sleeve-level) | Still open; different from H-SECT01/02, which tested sleeves, not the production momentum strategy — also listed in [macro-research](../macro-research/README.md)'s gap table |

## Index

| Paper | Status | Covers |
| --- | --- | --- |
| [Section leadership persistence](section-leadership-persistence.md) (H-SECT01) | concluded-rejected | Real quarterly-horizon test: P(leader next quarter \| leader this quarter) = 33.3%, exactly chance (p=0.52). A same-session daily-overlapping-window test had appeared to confirm persistence (p=0.001) — turned out to be a mechanical rolling-window artifact, not a real effect; caught and superseded before promotion. |
| [Regime-conditioned sleeve relative return](regime-conditioned-sleeve-return.md) (H-SECT02) | concluded-confirmed, narrowed by H-SECT05 | Different mechanism than H-SECT01: macro state, not trend, predicting relative return. 11 of 24 sleeve/window tests significant after correction (~1.2 expected by chance) — but see H-SECT05, most of this doesn't survive beta-adjustment. |
| [Sleeve driver decomposition](sleeve-driver-decomposition.md) (H-SECT03) | concluded-rejected | Which single real driver (yield/credit/vol/inflation) explains each sleeve's H-SECT02 sensitivity — none does. 1 of 48 tests significant, below the ~2.4 chance baseline. A real null supporting the composite's own design over any one raw factor. |
| [Regime-tilted allocation backtest](regime-tilted-allocation-backtest.md) (H-SECT04) | concluded-rejected | Does tilting the 12-sleeve book by regime beat equal-weight on real OOS Sharpe/drawdown/turnover — no. OOS Sharpe improvement +0.008, economically trivial, doesn't clear its own turnover cost. Closes the loop: real correlation (H-SECT02) doesn't survive becoming an actual allocation rule. |
| [Beta-adjusted regime sensitivity](beta-adjusted-regime-sensitivity.md) (H-SECT05) | concluded-confirmed (partial) | Does H-SECT02 survive controlling for each sleeve's own beta to SPY? Mostly no — 11/24 raw drops to 3/24 beta-adjusted. `GLD`'s headline effect was almost entirely a beta artifact. `XLU` (both windows) is the one finding that survives every check in this arc: raw, OOS, and beta-adjusted. |
| [Gold reaction function](gold-reaction-function.md) (H-SECT06) | observing | Cold-start event log (same shape as `warsh-reaction-function.md`): is `GLD` decoupling from the real-yield/Fed-dovish mechanic toward fiscal-dominance/currency-debasement pricing? Motivated by H-SECT02/03/05's own findings (GLD's composite correlation was never explained by a single driver, and weakened out-of-sample). 1 real checkpoint so far. |
| [Sleeve dispersion / opportunity-set](sleeve-dispersion-opportunity.md) (H-SECT07) | concluded-inconclusive | Does currently-observable cross-sectional dispersion predict forward opportunity (bigger realized spread)? 6/10 significant full-sample (r=0.18-0.34, `dispersion`/`top3_minus_bottom3`/`leadership_gap`) — but 0/10 out-of-sample. Same sign throughout, plausibly underpowered rather than reversed, but doesn't clear this arc's usual bar. Real, not yet confirmed. |
| [Regime velocity vs. opportunity](regime-velocity-opportunity.md) (H-SECT08) | concluded-rejected | Does regime *direction* (velocity/acceleration/days-since-transition), not just level, predict cross-sectional opportunity? No — 0/6 significant, trivially small correlations. A clean null, no ambiguity. |
| [Conjunctive XLU trigger](conjunctive-xlu-trigger.md) (H-SECT09) | concluded-inconclusive | Is `XLU`'s edge stronger when multiple macro clusters simultaneously stress, beyond the aggregate composite already tested? IC significant both windows but driven substantially by a 3-observation extreme bucket — fragile, not confidently established at this sample size. |
| [Theme relative strength vs. broad index](theme-relative-strength.md) (H-SECT10) | concluded-rejected | Does `SMH`/`IGV`'s relative strength against `QQQ`/`SPY`/`DIA` specifically (not the other sleeves) persist at short "a few weeks" windows? No — 0/24 significant, well-powered (n=259-545/cell), no near-misses. 23/24 raw correlations negative (a real but non-significant hint of reversal, not persistence). |
