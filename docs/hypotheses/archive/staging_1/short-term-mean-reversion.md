# Short-term mean reversion (H-STREV01)

Status: concluded-confirmed (at the 1-week forward window specifically; see Observation log)
Version: v0.1
Registered: 2026-08-26

Not wired into any pipeline stage. Preregistered *after* observing suggestive
evidence in two other papers (`time-series-momentum.md`,
`low-volatility-anomaly.md` both found real reversal-shaped rejections) —
disclosed honestly, not hidden, precisely because reusing that same evidence
here as "confirmation" would be hypothesizing after the results are known.
This paper commits to a fresh specification, closer to the original cited
paper, before looking at a new result.

## Thesis

An asset's own trailing *weekly* return has a real, negative relationship
with its near-term forward return — a short-run overreaction that partially
reverses within a few weeks. Distinct from `time-series-momentum.md`'s 1m/3m
tests (calendar-month windows, a different and coarser specification) and
closer to the window the founding paper actually used.

This would be falsified by a real test showing no significant relationship,
or a positive one, between trailing weekly return and near-term forward
return across this staging universe's real price history.

## Prior

Jegadeesh (1990), "Evidence of Predictable Behavior of Security Returns,"
*Journal of Finance* — documented negative serial correlation in individual
stock returns at short (roughly weekly to monthly) horizons: last week's
losers tend to outperform last week's winners over the following few weeks.
A real, separately-documented effect from Jegadeesh & Titman's (1993)
medium-term continuation, operating at a shorter, non-overlapping window.

## What would count as a real checkpoint

A continuous, statistically testable claim: trailing 5-trading-day (~1
week) return as a 0/1 sign indicator (or its raw magnitude, tested both
ways), paired with the real forward return over the following 5-10 trading
days (short, matching the effect's own claimed window — not the 21-day
horizon used elsewhere in this project, which is too long a forward window
to cleanly isolate a weekly-reversal effect from what happens after it
resolves). Computed via `backend/research_lab/short_term_mean_reversion.py`
(read-only against the sealed dataset, never the production DB), pooled
across every tradable staging symbol's real price history with a stride to
control for overlapping-window autocorrelation (per the corrected
convention already established in the other two scripts this session).

## Promotion criteria

Real, significant IC in the predicted (negative) direction. Given this
project has now found the same reversal shape twice already under
different specifications (time-series momentum's 1m/3m, low-vol's
high-vol-rebounds), a third confirmation at the effect's proper window
would be the first real, positive (not rejected) atomic factor from this
literature-review pass — a genuine candidate for engineering into
`strategy_components`, on its own, without needing a second independent
factor first (a single well-validated factor is still deployable; ensemble
weighting needs two, but shipping doesn't).

## Observation log

| Date | Checkpoint | Reading | Note |
| --- | --- | --- | --- |
| 2026-08-26 | Real IC test, trailing 5-day (~1 week) return vs. two forward windows, `research_lab/short_term_mean_reversion.py` against dataset `real-macro-d9a319bd-09e0-443b-93b3-2e6ec70f4170`, stride=2 | **Confirmed at 1 week, not at 2 weeks.** 1-week forward: r=-0.0204 (adjusted p=0.0020, SIGNIFICANT, n=26,044) — negative, as predicted. 2-week forward: r=+0.0042 (adjusted p=0.50, not significant, n=26,001) — the relationship is gone. | Real, in the predicted direction, at the effect's own claimed window — not reused from the other two papers' evidence (this is a fresh test, a different window, a different specification, avoiding the HARKing risk noted above). The 1-week-only result is itself informative, not just a pass/fail: it empirically locates the boundary the user's own framing predicted ("reversal has a time limit, then becomes ineffective") — real here, gone one week later. First confirmed, not rejected, atomic factor from this literature-review pass. |
| 2026-08-26 | Rerun on the real 2004-2026 dataset (post-0.38 extension, now including 2008), same script, same two windows | **Confirmed, replicated, and strengthened.** 1-week: r=-0.057 (was -0.020), adjusted p<0.0001, n=54,238 (was 26,044). 2-week: r=-0.025, now ALSO significant (adjusted p<0.0001, n=54,175) -- was not significant on 2016-26. | The effect got stronger, not weaker, on the longer window including 2008, and now persists to 2 weeks instead of resolving within 1 -- the opposite direction of change from the other three rejected papers, which all weakened or stayed flat once 2008 was included. Real evidence this is a durable effect, not a bull-decade artifact -- the strongest single result of this session's full rerun pass. |

## Regime-conditioned addendum (same H, same universe — does it change across `macro_regime_composite`)

Not a new hypothesis, so kept in this file per the project's own doc-
cleanliness convention, rather than a new file. Real question:
`timing-research/README.md`'s #4 — does this confirmed edge strengthen
or weaken across regime state. Method identical to the runs above
(`research_lab/short_term_mean_reversion_regime_conditioned.py`, same
universe/stride/windows), split into `macro_regime_composite`'s real,
point-in-time stressed/neutral/calm bucket at each observation's date.

| Window | Stressed (n) | Neutral (n) | Calm (n) |
| --- | --- | --- | --- |
| 1-week forward | r=-0.069 (6,695) | r=-0.058 (42,767) | r=-0.052 (4,244) |
| 2-week forward | r=-0.040 (6,695) | r=-0.030 (42,725) | **r=+0.052** (4,244) |

All 6 cells significant after correction (huge samples; note effect
sizes are modest in absolute terms even where p-values are tiny — not
overstated as a bigger edge than it is). Two real findings: (1) the
1-week reversal effect is real in every regime, monotonically strongest
when stressed, weakest when calm — economically sensible, overreaction
effects plausibly amplify under stress. (2) The pooled 2-week result
(above, r=-0.025) turns out to average over a real sign split this
breakdown reveals: reversal persists to 2 weeks in stressed/neutral
regimes, but *flips to mild continuation* in calm regimes. That's new
information the pooled test alone couldn't show — the 2-week fade
isn't uniform, it's specifically a calm-regime phenomenon. No
out-of-sample split run yet on this specific breakdown — real, disclosed
next step if this gets revisited, not yet done.
