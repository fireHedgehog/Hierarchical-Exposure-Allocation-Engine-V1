# Conjunctive XLU trigger (H-SECT09)

Status: concluded-inconclusive — the IC is real and significant at both windows, but substantially driven by a 3-observation extreme bucket; not trustworthy standing alone yet. See Observation log.
Version: v0.2
Registered: 2026-08-27
Concluded: 2026-08-27

The genuinely different-mechanism idea from this folder's restart-here
table (user's own, inspired by `XLU` surviving every check in
H-SECT01-05): not a linear/continuous relationship (every H-SECT02-05/
07/08 test used one), but whether `XLU`'s edge is materially stronger
specifically when *multiple* macro conditions align simultaneously.
Deliberately narrow — only `XLU` (the one sleeve with real, beta-
adjusted, OOS-replicated evidence), only the 3 clusters already used in
production (`compute_regime_v3`'s `CLUSTERS`), not a fresh sweep across
raw indicators. A 12-sleeve × 20-indicator combinatorial search was
explicitly named and rejected as data-mining risk before this was
scoped.

## Thesis

`XLU`'s forward beta-adjusted relative return (same measure H-SECT05
validated) is materially larger when more of the 3 real macro clusters
(`growth_inflation`, `rate_level`, `market_stress`) simultaneously read
"stressed," not just a smooth function of the aggregate composite score
H-SECT02/05 already tested. If true, the number of *aligned* clusters
carries information beyond the composite's own single number.

Falsified by: `alignment_count` (0-3 clusters stressed) shows no real
IC with `XLU`'s forward beta-adjusted return, or the effect is no
stronger than what the aggregate composite score (already tested)
predicts on its own.

## Method

At each monthly-strided date, real per-cluster mean contribution
(z-score, `[-1, 1]`, same computation `compute_regime_v3` already does
internally, historically recomputed point-in-time like H-SECT02's
composite series). `alignment_count` = count of the 3 clusters with
mean contribution ≤ `STRESSED_TERCILE_CUTOFF` (-0.33, the same cutoff
already used everywhere else, not a new threshold). `XLU`'s forward
relative return, beta-adjusted (252-day trailing beta to `SPY`, same
method as H-SECT05), over the same 63/126-day windows. IC between
`alignment_count` and the beta-adjusted forward return — 2 tests, no
correction needed at this scale (below the point where multiple-
comparisons risk is meaningful). Descriptive mean return by
`alignment_count` bucket (0/1/2/3) reported alongside, for the direct
"does simultaneous alignment matter" reading.

## What would count as a real checkpoint

One real run of `research_lab/conjunctive_xlu_trigger.py` against the
sealed dataset.

## Promotion criteria

A confirmed result here would be interesting context (does `XLU`'s
already-real macro sensitivity concentrate in aligned-stress episodes)
but does not itself justify new production code — same non-negotiable
every paper in this arc has carried, and H-SECT04 already showed a
real sleeve-level correlation doesn't automatically survive becoming
an allocation rule.

## Observation log

| Date | Checkpoint | Reading |
| --- | --- | --- |
| 2026-08-27 | Real run, `research_lab/conjunctive_xlu_trigger.py`, full 2004-2026 sample. IC(alignment_count, `XLU` beta-adjusted forward return), both windows. | **Real, significant, but fragile.** 63d: r=+0.145, p=0.023. 126d: r=+0.134, p=0.037. |

| alignment_count | n (63d) | Mean beta-adj return (63d) | n (126d) | Mean beta-adj return (126d) |
| --- | --- | --- | --- | --- |
| 0 (no cluster stressed) | 109 | -0.39% | 109 | +0.05% |
| 1 | 105 | +1.25% | 105 | +2.25% |
| 2 | 28 | +1.33% | 25 | +1.95% |
| 3 (all 3 clusters stressed) | **3** | **+5.49%** | **3** | **+7.27%** |

**Honest caveat, not glossed over:** `alignment_count=3` has only 3 real
observations — its large mean return is likely a high-leverage outlier
in the correlation, not a reliable estimate. The correlation's
significance should not be trusted as standing independent of that thin
bucket. The more robust sub-pattern, on much larger real samples, is
simpler: any cluster alignment (count ≥ 1, n=105-133 depending on
window) beats no alignment (count=0, n=109) — real, but that's closer
to "does `XLU` do better in any stress at all" (already known from
H-SECT02/05) than a genuine "conjunctive, multiple-conditions-required"
effect. The specific 2-of-3 or 3-of-3 conjunctive story this paper set
out to test is not established with confidence at this sample size.
