# Gold reaction function: fiscal dominance vs. Fed-dovish (H-SECT06)

Status: observing
Version: v0.1
Registered: 2026-08-27

Cold-start, event-log paper — same shape as `macro-research/warsh-
reaction-function.md`, not a backtest. `GLD`'s relationship to macro
drivers is hypothesized to have *structurally shifted*, not just be
noisy; that needs real checkpoints accumulated over time, the same way
Warsh's reaction function does, not one pooled 2004-2026 regression
(H-SECT02/03/05 already ran that regression and it's exactly what
motivates this paper — see Prior).

## Thesis

`GLD` is increasingly pricing fiscal-dominance / sovereign-credibility /
currency-debasement concerns, not purely the real-yield/Fed-dovish
mechanic textbooks describe (`real yield ↑ → GLD ↓`). If this holds,
gold should show real, repeated episodes of moving *with* rising yields
and a strong dollar, driven by deficit/debt-monetization news rather
than rate-cut expectations — and this project should stop implicitly
coding `GLD` as a "Fed-dovish asset" in any future design.

Falsified by: real episodes keep reverting to the textbook mechanic
(gold reliably falls when real yields rise, with no debasement-driven
exceptions), or a future formal re-test on a later window finds gold's
old real-yield relationship intact, not decoupled.

## Prior

Two real, already-computed pieces of in-repo evidence, not just today's
news, are consistent with this thesis:

1. **H-SECT03** (driver decomposition): `GLD`'s regime-composite
   sensitivity was never explained by any single tested driver (real
   yield, credit, VIX, breakeven inflation) — the composite doesn't
   include a fiscal/debasement dimension at all, so if that's actually
   what's moving gold, H-SECT03 would correctly find nothing.
2. **H-SECT02's OOS split**: `GLD`'s correlation with the existing
   composite was strong in-sample (2004-2018, 2008-driven) but weaker
   out-of-sample (2019-2026) — consistent with gold's *old* mechanic
   fading, not just noisier data. This paper is the real, named
   mechanism that OOS weakening could reflect.

## What would count as a real checkpoint

A real, dated market episode where gold's direction and the day's real
yield/USD/Fed-stance direction are recorded together, with the real
news source's own attribution — not this project's inference. Enough
checkpoints (same ~10-20 bar as H-W01) before this becomes a real,
testable classifier rather than a narrative. Once enough real dates
exist, the actual checkpoint is a formal re-test: does a fiscal/deficit
proxy (e.g. real 10Y-30Y term premium, TGA issuance pace, or a debt/GDP
trend) explain more of `GLD`'s post-2024 moves than `DFII10` alone did
in H-SECT03's window.

## Promotion criteria

None claimed yet — a cold start, same as H-W01. Real calibration needs
the same ~10-20 observation checkpoints before this graduates into an
actual quantitative re-test, let alone anything engineered.

## Observation log

| Date | Event | Gold move | Real yield / USD | Note |
| --- | --- | --- | --- | --- |
| 2026-08-27 | Reuters: "Gold drifts higher as eyes Fed Chair Warsh's comments" | Spot ~$4,630, ~+0.8% | USD firm; Fed-hike probability *rising* the same day | Textbook-inverted: gold up while real-yield-favorable conditions (higher hike odds, firm dollar) would predict down. Reuters attributes part of the move to currency-debasement/fiscal-deficit concerns and the Treasury expanding purchases of older long-dated bonds — a real, named alternative mechanism, not this project's own speculation. One day before Warsh's Jackson Hole keynote (`warsh-reaction-function.md`'s own next scheduled checkpoint, 2026-08-28) — both papers are watching the same real event from two angles (Fed reaction function vs. gold's own reaction function); worth cross-checking after the keynote lands. |
