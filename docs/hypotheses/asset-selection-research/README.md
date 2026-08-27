# Asset selection research

Scope: does *which* asset/sector/theme to hold carry real, mineable
signal — separate from *when* to enter (single-name timing, tested
elsewhere) and from the single-name cross-sectional ranking already
live in production. Same lifecycle and rules as the parent
[`docs/hypotheses/README.md`](../README.md); own index for the same
reason `macro-research/` got one — this can grow into many papers, and
knowledge should distill into tables, not one flat file.

## Relation to what's already tested

Existing top-level papers already tested single-symbol technical
factors, mostly IC vs. real forward return within one universe:

- Time-series momentum — rejected
- Short-term mean reversion — confirmed
- Low-volatility anomaly — rejected (raw return)
- MAX effect / lottery demand — rejected
- Vol-scaled cross-sectional momentum — inconclusive
- Dow Theory risk-state — confirmed

`cross_sectional_momentum` (12-1) is the one graduated result from that
line of work, live in production. This folder is the layer above those:
which *dimension* to rank (sector vs. sector, asset class vs. asset
class, theme vs. theme, fundamental characteristic), not which signal
to use for ranking within one universe.

## Candidate framework

Two layers, kept separate on purpose (parallel to macro's 3-layer
split, lighter because there's no policy-response layer here):

1. **Selection dimension** — what's being ranked: sector/industry,
   asset class (equities vs. gold vs. bonds vs. commodities), theme,
   or a fundamental characteristic (quality, value, low-vol).
2. **Real forward outcome** — relative return, risk-adjusted return, or
   drawdown, always benchmarked against an equal-weight/unconditional
   baseline. Same non-negotiable this project applies everywhere else:
   a raw rate alone proves nothing without that baseline.

## Restart-here: open questions, none started yet

| Question | Note |
| --- | --- |
| Sector/industry relative strength vs. real forward return | Not started |
| Cross-asset momentum ranking (equities vs. gold vs. bonds vs. commodities) | Not started |
| Fundamental/non-collinear factor tilts (quality, value, low-vol) beyond what's already rejected at single-name level | Not started |
| Regime-conditional cross-sectional performance — does `cross_sectional_momentum`'s edge change across `macro_regime_composite` states | Parked in [macro-research](../macro-research/README.md)'s gap table too — connects the two folders |

## Index

| Paper | Status | Covers |
| --- | --- | --- |
| _none yet_ | — | — |
