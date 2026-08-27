# Macro composite methodology (design v1)

Status: design — not a hypothesis, no observation log. A proposal to review
and correct before any code, per direct instruction.

Not wired into any pipeline stage. Not the same document as the frontend
Methodology page's existing macro card, which still describes the frozen
`macro_regime_composite` naive-v2 — this stays a separate research design
until validated, then that page gets updated, in that order, not before.

## The real problem this answers

"Today" is a slice through several factors at different points in their own
release cycle — one printed yesterday, another 3 weeks ago with a new print
due in 1 week. A composite has to produce one number today regardless. Two
separable questions, answered separately:

1. **When does a factor's raw value change?** (staleness policy)
2. **Given today's known value — fresh or 3-weeks-old — how do we score it?**
   (normalization / "compare with what")

## 1. Staleness: hold flat between real releases, never fabricate

Already the real, existing behavior of `macro_regime_composite`'s own code
(`_score_yoy_surprise_factor`/`_score_level_surprise_factor` in
`scoring_v2.py` both always read `ordered[-1]`, the single latest real
observation) — made explicit here as policy, not a new mechanism:

- A factor's raw value updates only on its own real release date. Between
  releases, its value — and therefore its score — stays exactly flat. Not
  interpolated, not decayed toward neutral, not guessed.
- `SERIES_METADATA` already tags every series' real `frequency`
  (daily/weekly/monthly/quarterly) — this is the same information a
  staleness-aware display already needs, reused, not duplicated.
- A factor 3 weeks stale with a print due in 1 week is not "acting up or
  down" — it is contributing today exactly what it contributed on its own
  last real release date. That is the honest answer, not a gap to paper
  over.

## 2. Normalization: one real mechanism, two speeds

**Proposed real upgrade, not a new invention:** the existing surprise
mechanism divides by a **hand-picked `scale` constant** (e.g. NFCI's
`scale=0.1`) — a real, disclosed naive-v2 simplification, not a true
z-score. The concrete "flexi norm" fix: divide by the factor's own
**trailing standard deviation** instead of a hand-picked number —

```
z = (latest_value - trailing_mean) / trailing_stdev
```

— a real, standard, adaptive normalization: automatically wider for a
naturally volatile series (VIX), narrower for a naturally stable one
(core PCE), with no hand-picked constant per factor. Same mechanism for
every factor; only what counts as "latest" and the trailing window differ:

| Factor shape | "Latest value" | Trailing window compares against |
| --- | --- | --- |
| Release-driven, YoY-shaped (CPI, PCE, PPI, payrolls) | Latest YoY reading | Trailing YoY history — the existing `_score_yoy_surprise_factor` shape, kept |
| Release-driven, level-shaped (GDP) | Latest level | Trailing level history |
| Continuous/daily (VIX, yields, spreads, breakevens) | Today's level | Trailing daily-level history (e.g. 2-year rolling) — answers "compare with yesterday?" no: a z-score against recent history is more informative than a 1-day delta, which only says *direction*, not *how unusual* |

One real design choice to confirm, not assumed: **rolling vs. expanding**
trailing window. A rolling window (e.g. 2 years) adapts to regime changes
(2004-level VIX "normal" shouldn't anchor a 2026 reading); an expanding
window is more stable but slower to adapt. Recommend rolling, disclosed as
naive/hand-picked like every other first-pass parameter in this project.

## 3. Aggregation: weighted sum, weights from the real cluster structure

`composite = Σ (weight_i × z_i)`, sum not product (matches the existing
composite's own shape, most interpretable, avoids sign/zero pathologies a
product would introduce).

**Weights come from H-MACRO08's real finding, not equal-weighting the raw
list:** ~4 independent clusters (inflation/growth, rate level, market
stress, policy operations), several with 4-6 highly-correlated raw members.
Equal-weighting all 17-26 raw indicators would let the inflation/growth
cluster (6 correlated members) outvote market stress (2 members) 3-to-1 by
construction, not because it is more informative. Proposed: weight
**clusters** equally, then split each cluster's weight equally (or
representative-indicator-only) across its own members — naive, disclosed,
not fit; a real improvement over both "equal-weight everything" and the
current hand-picked 8-factor weights, without claiming more rigor than a
first pass actually has.

## 4. Validation before any code — exactly what was asked for

A face-validity backtest, not a statistical test: pick several real,
well-known historical dates and check whether the proposed methodology's
output matches known reality. Cheap, `research_lab` only, no schema or
pipeline changes:

| Date | Known reality | What the composite should say |
| --- | --- | --- |
| 2008-10 (Lehman aftermath) | Real risk-off | Strongly risk-off |
| 2020-03 (COVID crash) | Real risk-off | Strongly risk-off |
| 2021-11 (market top, pre-hiking) | Real risk-on, late-cycle | Risk-on, plausibly with stress cluster already diverging |
| 2022-10 (hiking-cycle trough) | Real risk-off | Risk-off |
| 2024-Q4 / most recent (disclosed as-of, not cherry-picked after seeing the result) | — | Whatever the real data says — the actual test |

Dates chosen for real, well-known, undisputed outcomes — not selected
after seeing what the script produces (the same discipline as every
falsification-first paper in this folder).

## Sequencing — the "long way to go," made explicit

1. **This document** — review, correct before anything else.
2. **Face-validity backtest** (`research_lab`, no schema/pipeline changes).
3. Only if that holds up: a **new hypothesis paper** with the real backtest
   numbers (not this design doc) — the actual evidence gate.
4. Only after that: `schema.sql` registration (new `strategy_versions` row,
   `macro_regime_composite` naive-v3, matching the naive-v1→v2 promotion
   pattern already used everywhere else in this project) and `fetch_data`/
   `regime_filter` wiring so it computes on every real pipeline run, not
   just in `research_lab`.
5. Only after that: the frontend Methodology page's macro card gets
   rewritten to describe what's actually live — not before, and not this
   document standing in for that page.

`macro_regime_composite` stays frozen at naive-v2 through steps 1-3,
unchanged from the existing rule.
