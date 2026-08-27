# Asset selection research

Scope: does *which* asset/sector/theme to hold carry real, mineable
signal — separate from *how much* total risk to carry (macro regime)
and *when* to act (timing, its own folder now). Same lifecycle and
rules as the parent [`docs/hypotheses/README.md`](../README.md); own
index for the same reason `macro-research/` got one.

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
| 1 | Relative expected return — E[R_section − R_market \| state] | Which section's excess return is real, not just its absolute return |
| 2 | Relative risk efficiency — return per unit of vol/drawdown | The strongest-momentum section isn't automatically the best use of budget if it's also the most volatile/crowded |
| 3 | State sensitivity — exposure mapping to specific macro drivers (real yield, USD, oil, credit spreads), not a static GICS label | Connects directly to the macro layer's own factor clusters |
| 4 | Theme leadership — which cluster currently carries the market's marginal capital flow | Matches this project's own thematic-beta trading style (see [`thematic-beta-selection-process.md`](../thematic-beta-selection-process.md)) |
| 5 | Breadth / diffusion — is leadership concentrated in a few names or spreading | Distinguishes healthy leadership from late-stage narrow crowding |
| 6 | Crowding / convexity — has the strongest section become a negative-convexity trade (upside needs continued inflow, a miss is a big downside) | A different axis from momentum itself |
| 7 | Cross-section persistence — real duration distribution of leadership (median weeks in top-decile relative strength before it fades) | The actual testable version of "does leadership persist" |

**Recommended first question, if this gets picked up:** does section
leadership persist, and does macro regime materially change that
persistence — the one question that would connect this folder to
`macro-research/` for the first time with real evidence, not just a
parked cross-reference.

## Restart-here: open questions, none started yet

| Question | Note |
| --- | --- |
| Section leadership persistence, regime-conditional (#7 above, connected to macro state) | **Designed:** [`section-leadership-persistence.md`](section-leadership-persistence.md) (H-SECT01), preregistered 2026-08-27. Universe already confirmed real in `data/desk.db` (9 sector ETFs, 2004-2026) — no fetch needed. Not run yet. |
| Sector/industry relative strength vs. real forward return (#1) | Not started |
| Cross-asset momentum ranking — equities vs. gold vs. bonds vs. commodities (#1, broader universe) | Not started |
| Relative risk efficiency (#2) | Not started |
| State sensitivity / exposure mapping to macro drivers (#3) | Not started; natural pairing with macro-research's existing factor clusters |
| Theme leadership / marginal-flow detection (#4) | Not started; no data source identified yet for "capital flow," may need a proxy |
| Breadth / diffusion (#5) | Not started |
| Crowding / convexity (#6) | Not started; likely needs an options-market or short-interest proxy, may hit the same "free data only" ceiling macro research did |
| Regime-conditional cross-sectional performance — does `cross_sectional_momentum`'s edge change across `macro_regime_composite` states | Same as #7/recommended start; also listed in [macro-research](../macro-research/README.md)'s gap table |

## Index

| Paper | Status | Covers |
| --- | --- | --- |
| [Section leadership persistence](section-leadership-persistence.md) (H-SECT01) | preregistered | Does sector leadership (top-tercile trailing-3-month return, 9-sector universe) persist longer than a real permutation-null predicts, and does that duration depend on the macro regime active at entry. Design only — not run yet. |
