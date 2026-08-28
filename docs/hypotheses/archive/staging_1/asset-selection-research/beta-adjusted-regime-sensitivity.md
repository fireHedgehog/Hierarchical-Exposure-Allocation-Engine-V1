# Beta-adjusted regime sensitivity (H-SECT05)

Status: concluded-confirmed (partially — a real, narrower core survives; several of H-SECT02's headline results were substantially beta, not new information)
Version: v0.2
Registered: 2026-08-27
Concluded: 2026-08-27

A real hole in H-SECT02, caught before it was treated as settled: that
paper correlated the composite against raw `R_sleeve − R_SPY`, never
controlling for each sleeve's own beta to `SPY`. `XLU`/`XLP` are
well-known low-beta sleeves, and H-MACRO09 already showed the composite
predicts *when SPY is likely to fall*. A low-beta sleeve relatively
outperforming exactly when the composite is stressed could be purely
mechanical — low beta cushions a falling market, the composite predicts
falling markets — not new, sleeve-specific macro information. This
paper tests whether H-SECT02's finding survives removing that effect.

## Thesis

After adjusting for each sleeve's own trailing beta to `SPY`, at least
some of H-SECT02's 11 significant sleeve/window results remain real —
i.e. the composite predicts more than what beta alone would explain.

Falsified by: beta-adjustment removes the significant relationship for
most or all of the 11 — meaning H-SECT02 was substantially rediscovering
beta, not finding independent sleeve-level macro sensitivity.

## Method

Real trailing beta per sleeve, 252-trading-day daily-return window
(disclosed, standard 1-year convention, not tuned), point-in-time
correct — beta at anchor date *t* uses only the 252 real daily returns
ending at or before *t*, no lookahead. `alpha_return = R_sleeve − β ×
R_SPY` over the same forward windows (63/126 trading days) H-SECT02
used, same 21-day stride. Same 12 sleeves, same Benjamini-Hochberg
correction across the resulting 24 tests. Directly comparable to
H-SECT02's own 24-row table — same sleeves, same windows, only the
dependent variable changes (beta-adjusted alpha instead of raw
relative return).

## What would count as a real checkpoint

One real run of `research_lab/beta_adjusted_regime_sensitivity.py`,
producing the same 24-test panel, compared row-by-row against
H-SECT02's original results.

## Promotion criteria

Not a new production surface either way — this recalibrates how much
weight H-SECT02's finding deserves as *context*, since H-SECT04 already
closed the door on an automated allocation rule regardless of outcome
here. A result where the defensive-rotation core (`XLU`/`XLP`) survives
beta-adjustment would strengthen confidence in that specific piece of
context; a result where it doesn't would mean H-SECT02's summary should
be corrected, not just left standing.

## Observation log

| Date | Checkpoint | Reading |
| --- | --- | --- |
| 2026-08-27 | Real run, `research_lab/beta_adjusted_regime_sensitivity.py`, same dataset/sleeves/windows as H-SECT02. 24 tests, real 252-day trailing beta per sleeve, Benjamini-Hochberg corrected. | **The concern was real: 11/24 raw significant drops to 3/24 beta-adjusted** — still above the ~1.2 chance floor, so a real, narrower core survives, but most of H-SECT02's headline effect was beta, not new sleeve-specific macro information. |

| Sleeve | Window | Raw r (H-SECT02) | Beta-adj r | Beta-adj adj_p | Verdict |
| --- | --- | --- | --- | --- | --- |
| XLU | 126d | -0.285 | -0.213 | 0.0211 | **Survives — real, independent of beta** |
| XLU | 63d | -0.225 | -0.190 | 0.0306 | **Survives — real, independent of beta** |
| XLY | 63d | +0.215 | +0.184 | 0.0306 | **Survives — real, independent of beta** |
| XLP | 126d/63d | -0.254/-0.199 | -0.160/-0.147 | 0.0604/0.0667 | Weakens to a near-miss, same sign — real but substantially smaller than reported |
| DIA | both | -0.208/-0.184 | -0.135/-0.139 | 0.078/0.072 | Weakens to non-significant, same sign |
| QQQ | 63d | +0.170 | +0.160 | 0.0604 | Weakens to a near-miss |
| **GLD** | both | **-0.204/-0.111** | **-0.017/+0.025** | 0.91/0.84 | **Collapses to ~zero — H-SECT02's single largest effect was almost entirely a beta artifact, not real gold-specific stress-hedge information from this test** |

**Correction to H-SECT02, recorded here rather than silently edited into that paper's own log:** the defensive-rotation core (`XLU`, both windows) is the one finding in this whole arc that survives every check run so far — raw significance, OOS replication (H-SECT02's own OOS split), and now beta-adjustment. `XLY` (63d only) is a second, smaller real finding. Everything else in H-SECT02's "confirmed" list — most notably `GLD`'s headline +7.64%/-5.43% stressed-vs-calm swing — should be read as substantially or entirely a beta effect, not new information about that specific sleeve's macro sensitivity. This does not change H-SECT04's conclusion (already rejected on its own terms) but explains part of *why* the tilt found so little edge: two of its four tilted sleeves (`XLP`, and `QQQ`'s calm-side counterweight) turn out to carry weaker real signal than H-SECT02 reported.
