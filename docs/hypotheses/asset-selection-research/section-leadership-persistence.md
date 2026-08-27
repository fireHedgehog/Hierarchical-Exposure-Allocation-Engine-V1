# Section leadership persistence (H-SECT01)

Status: concluded-rejected (persistence, at the rigorous non-overlapping test); v2 addendum confirms the rejection holds within a real SPY trend regime too, not just pooled — see Observation log.
Version: v0.3
Registered: 2026-08-27
Concluded: 2026-08-27

Design-first, per direct instruction — every knob below is decided and
disclosed before any `research_lab/` code runs, same discipline as
`macro-research/composite-methodology-v1.md`. This is the "recommended
first question" from `asset-selection-research/README.md`'s framework
(#7, cross-section persistence, plus its regime-conditional extension).

## Universe (confirmed real, already in the database — no fetch needed)

The 9 sector-SPDR ETFs with full 2004-2026 real daily history: `XLB`,
`XLE`, `XLF`, `XLI`, `XLK`, `XLP`, `XLU`, `XLV`, `XLY`. Checked directly
against `data/desk.db` before writing this: all 9 have real bars from
2004-12-01 to 2026-08-26.

`XLC` (2018+) and `XLRE` (2015+) are excluded from the primary test — a
rotating universe size would bias rank/tercile comparisons across the
sample. Real, disclosed limitation, not a hidden one. A shorter-window
robustness check with all 11 is real follow-up work, not blocking.

## Thesis

Two separable claims, evaluated independently — not fused into one
pass/fail, same reason macro's layers stay separate:

1. **Persistence**: a sector that enters cross-sectional leadership
   (top tercile by trailing 3-month return, among the 9) stays there
   longer than pure rotation would predict.
2. **Regime interaction**: how long that leadership lasts depends on
   the macro regime (`macro_regime_composite`, stressed/neutral/calm)
   active when the leadership episode begins.

Falsified independently: (1) fails if real median episode duration
isn't meaningfully longer than a real permutation-null median; (2)
fails if duration doesn't differ meaningfully across regime buckets at
entry.

## Method

**Ranking.** Every real trading day, rank all 9 sectors by trailing
63-trading-day (~3 month) total return. Top 3 of 9 = "in leadership"
that day — an exact tercile cutoff, same convention already used for
the macro composite's terciles and the risk gauge's zones. No SPY
benchmark needed: ranking within the 9-sector set is already relative.

**Why daily, not a weekly/monthly stride.** Other papers in this
project use a stride (`short_term_mean_reversion.py`: 2,
`composite_forward_risk.py`: 21) to keep observations independent for
a correlation/IC significance test. This isn't that: extracting when a
state (in/out of leadership) starts and ends requires checking every
real day, the same way a regime-duration measurement would. No stride
to disclose here because none is appropriate — the target statistic is
different in kind, not just in cadence.

**Episode extraction.** A leadership episode = a maximal run of
consecutive trading days one sector stays in the top 3. Duration =
real trading days in that run. The final, still-open episode at the
end of the sample (2026-08-26) is right-censored and excluded from the
duration distribution — a naive, disclosed simplification, not full
survival analysis.

**Null baseline.** At each trading day, independently shuffle which 3
of the 9 sectors occupy the leadership slots (preserving "exactly 3
winners per day," breaking any real day-to-day persistence in *which*
sector wins). Repeat 1,000 times, extract the same episode-duration
statistic on each shuffled path, pool into a real null distribution.
Compare the real observed median duration against it — an empirical
one-sided p-value, not an assumed baseline rate. This is the same
"never credit a mechanism without a real baseline" discipline this
project already applies everywhere (H-GAPFILL01, H-CRASHREV01), adapted
to a duration question where a simple proportion baseline doesn't
apply.

**Regime interaction.** For every leadership-episode *start* event,
record `macro_regime_composite`'s tercile at that date, recomputed
historically the same way `composite-forward-risk.py` did for H-MACRO09
(point-in-time correct, not today's live value). Compare episode
duration across the 3 regime buckets with a Kruskal-Wallis test (real
non-normal duration data) plus descriptive medians per bucket. Known,
disclosed caveat: entry events aren't fully independent of each other
(a common regime shift can trigger several sectors' entries at once) —
naive first pass, not corrected for.

## What would count as a real checkpoint

One real run of `research_lab/section_leadership_persistence.py`
against the sealed 2004-2026 dataset, producing: the real vs. null
median-duration comparison (claim 1) and the regime-bucketed
Kruskal-Wallis result (claim 2). Both numbers in one pass — this isn't
a per-event checkpoint paper like Warsh's.

## Promotion criteria

Claim 1 alone, if confirmed, is quotable on its own (parallel to how
H-MACRO09 stood without needing the regime layer). If both confirm,
this becomes the first real evidence directly connecting the macro and
cross-sectional layers — grounds for a *future*, separately-designed
hypothesis about a regime-conditional sector tilt, not an automatic
engineering step from this paper alone (no schema/pipeline change is
implied by a confirmed result here).

## Observation log

| Date | Checkpoint | Reading |
| --- | --- | --- |
| 2026-08-27 | Real run, `research_lab/section_leadership_persistence.py`, dataset `real-macro-f7bd88ff-07eb-46d3-877f-701968666524`. 9 sectors, 5,468 real trading days (2004-2026), 1,480 real leadership episodes. | **Daily test (as designed): appeared to confirm.** Real median episode duration 3.0 trading days vs. permutation-null median 1.0 (1,000 reps) — empirical p=0.0010. But this test has a real confound not caught until after running it: a trailing-63-day window shares 62 of 63 days with the next day's window, so day-to-day rank stability is partly *mechanical*, not necessarily economic — the daily null breaks all cross-day correlation, which is a much weaker bar than genuine persistence needs to clear. |
| 2026-08-27 | Same run, added mid-session after noticing the confound: non-overlapping 63-day block test — independent windows only, no shared days between consecutive rankings. 86 real blocks. | **Rejected at the rigorous test.** P(sector stays a leader in the next independent quarter, given it led this quarter) = 85/255 = 33.3% — *exactly* the 33.3% (3-of-9) chance rate. Binomial test vs. chance: p=0.5235, not significant. Sector leadership at a quarterly, non-overlapping horizon is statistically indistinguishable from random rotation. This is the real result — the daily test's apparent confirmation was the mechanical artifact, not a false alarm caught cheaply thanks to running both. |
| 2026-08-27 | Regime interaction (Kruskal-Wallis across `macro_regime_composite` terciles at episode entry) | H=6.053, p=0.0485 — technically significant, but built on the daily-episode definition now known to be confound-dominated. Not promoted as a standalone finding: testing "does regime affect a mostly-mechanical duration statistic" isn't the same claim as "does regime affect real leadership persistence," and claim 1 (the thing regime would be conditioning) was rejected at the test that actually isolates it. Revisiting this properly would mean re-running the regime split on the block-level (quarterly) transition, not the daily episode list — real follow-up work, not done here. |

## v2 addendum: trend-conditioned re-test (same H, real market filter, kept in this file)

User's own direct methodological point: this project's experiments
have all tested pooled, unconditional relationships — but a real
market participant conditions on real, standard, *explainable* market
state (e.g. "is price above its own moving average," not an arbitrary
transform chosen after seeing results). That's the same legitimate
category as `macro_regime_composite` conditioning already used
elsewhere (e.g. this folder's own H-STREV addendum) — not overfitting,
as long as the filter is real, pre-specified, and disclosed before
running, which this is. Direct test of the classic claim: does
trend-following/leadership persistence get real in a genuine bull
trend, even though it was rejected pooled.

**Method** (`research_lab/section_leadership_persistence_trend_conditioned.py`):
same real, rigorous non-overlapping 63-day block test as the row
above — reused directly, not redesigned. Each block-to-block
transition split by a real, standard trend filter on `SPY` (5-day vs.
20-day moving average, price above both = bullish, below both =
bearish, otherwise mixed) as of the transition date, not a macro
factor this time — a genuinely different conditioning variable.

| Date | Checkpoint | Reading |
| --- | --- | --- |
| 2026-08-28 | Real run, same dataset, 86 real blocks split by real SPY trend regime at each transition. | **Rejected in every regime — the pooled null isn't hiding a real bull-market effect.** Bullish: 36/99 = 36.4% (vs. 33.3% chance), p=0.524. Bearish: 13/39 = 33.3%, p=1.000 (exactly chance). Mixed: 36/117 = 30.8%, p=0.624. All three real, disclosed sample sizes (39-117 transitions), none significant, none close. |

**Reading this honestly:** the user's methodological point was correct
and worth testing directly — a real, pre-specified market-state filter
is not "making the experiment dirty." But applying it here doesn't
rescue H-SECT01: sector leadership persistence stays exactly
chance-level whether the market is trending up, down, or sideways at
the moment of handoff. This strengthens, not just repeats, the
original rejection — it rules out "the pooled test just averaged away
a real bull-market effect" as an explanation for the null.
