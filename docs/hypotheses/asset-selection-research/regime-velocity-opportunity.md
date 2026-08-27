# Regime velocity vs. cross-sectional opportunity (H-SECT08)

Status: concluded-rejected — clean, no OOS check needed (a null full-sample result doesn't need out-of-sample validation the way a confirmed one does)
Version: v0.2
Registered: 2026-08-27
Concluded: 2026-08-27

User's own explicit correction: not a re-run of the sector-tilt idea
(H-SECT04, rejected) with velocity swapped in for level — a higher-
level question first, same shape as H-SECT07: does regime *direction*
(not just level) change the cross-sectional opportunity set. Today's
composite reading of 49 reached from 30 vs. reached from 65 may not be
the same market state, even though the static tercile bucket
(`macro_regime_composite`'s only current output) reads identical.

## Thesis

A macro regime that's actively deteriorating or improving (real
velocity/acceleration in the composite score, or freshly transitioned
between terciles) predicts more cross-sectional opportunity (real
forward spread — same outcome H-SECT07 used) than a regime that's been
stably at the same level for a while. Direction is parked, same as
H-SECT07 — this asks whether the *rate of change* itself carries
information the static level doesn't, not which sleeve benefits.

Falsified by: none of the 3 velocity-family variables clear
Benjamini-Hochberg correction meaningfully above chance.

## Method

3 real state variables, computed from the same point-in-time composite
series H-SECT02/07 already build, at each monthly-strided date:

| Variable | Definition |
| --- | --- |
| `velocity` | Composite score at *t* minus composite score at *t*−63 trading days (real trailing 3-month change) |
| `acceleration` | `velocity` at *t* minus `velocity` at *t*−63 (change in the rate of change) |
| `days_since_transition` | Real trading days since the composite last crossed a tercile boundary (stressed/neutral/calm) |

**Outcome**: the same forward `top3_minus_bottom3` spread H-SECT07
used (63/126-day windows), for direct comparability — 3 variables × 2
windows = 6 tests, Benjamini-Hochberg corrected. Deliberately narrower
than H-SECT07's 10 (fewer variables, same discipline against
combinatorial sprawl).

## What would count as a real checkpoint

One real run of `research_lab/regime_velocity_opportunity.py` against
the sealed dataset.

## Promotion criteria

Same shape as H-SECT07 — this is a gate question, not a tradable
signal on its own. Given H-SECT07's own OOS result was ambiguous, a
confirmed result here would need its own OOS check before being
trusted, not accepted on a full-sample read alone.

## Observation log

| Date | Checkpoint | Reading |
| --- | --- | --- |
| 2026-08-27 | Real run, `research_lab/regime_velocity_opportunity.py`, full 2004-2026 sample. 6 tests (3 velocity-family variables × 2 windows), Benjamini-Hochberg corrected. | **Clean rejection — 0 of 6 significant**, all correlations trivially small (r=+0.01 to +0.07, no coherent sign pattern). Regime velocity, acceleration, and time-since-transition carry no real information about forward cross-sectional opportunity in this universe, at this specification. |

**Reading this:** unlike H-SECT07 (a real full-sample pattern that didn't survive OOS), this is a clean null even before splitting — no promising signal to lose. Static regime *level* (H-SECT02/05's `XLU` finding, and the composite's own validated drawdown-probability use) still carries real information; regime *direction* over a 3-month window, tested this way, does not add anything on top of it for the cross-sectional opportunity question. Doesn't rule out a different specification (e.g. a shorter or longer velocity window) but no reason from this result to try one — a real null, not a design failure to iterate on.
