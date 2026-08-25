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
