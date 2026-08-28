# Composite forward risk (H-MACRO09)

Status: observing
Version: v0.1
Registered: 2026-08-27

Reframed per direct correction: not "does the composite match today's price
label" (a timing question) but "how likely is a real forward drawdown,
given today's reading" — a risk-context question, same reframe that turned
`dow-theory-trend-structure.md` (rejected) into `dow-theory-risk-state.md`
(confirmed). Same 3-cluster composite as `composite-face-validity-backtest.md`,
now tested pooled across real history instead of 5 hand-picked dates —
that paper's results still stand and aren't superseded, just extended.

## Method

`research_lab/composite_forward_risk.py`. Composite score at ~255 real,
monthly-strided dates (2004-2026), against SPY's own real forward max
drawdown at two windows (3mo, 6mo). Two real tests: continuous IC (Pearson),
and P(real ≥10% drawdown) comparing the bottom vs. top composite tercile
(Fisher's exact, `proportion_significance`) — the direct "how likely"
answer.

## Results

| Window | IC (r) | P(≥10% drawdown) — stressed tercile | P(≥10% drawdown) — calm tercile | Diff | p |
| --- | --- | --- | --- | --- | --- |
| 3 months | +0.284, p<0.0001 | 27.1% (23/85) | 4.7% (4/85) | +22.4pp | 0.0001 |
| 6 months | +0.323, p<0.0001 | 34.5% (29/84) | 7.1% (6/84) | +27.4pp | 0.0000 |

Both real, strong, and in the expected direction: a stressed reading is
roughly **5-7x more likely** to precede a real ≥10% drawdown than a calm
one, and the effect strengthens, not weakens, at 6 months.

## Reading this

This directly answers "how likely, how confident, how strong": a
composite reading in the bottom tercile isn't a prediction of *when*
price turns (the coincident-vs-leading tension in the face-validity
backtest stays genuinely open) — it's a real, quantified base-rate shift
in the odds of a real drawdown over the following 3-6 months. That's a
risk-context number, not a timing signal — consistent with how this is
meant to be used.

## Promotion criteria

Real, significant, first pass — not yet: no out-of-sample split, no test
of whether -10%/tercile are the best thresholds (both hand-picked,
disclosed), and this composite still excludes the policy-operations
cluster and all of Liquidity/Guidance. `macro_regime_composite` stays
frozen regardless.

## Observation log

| Date | Checkpoint | Reading |
| --- | --- | --- |
| 2026-08-27 | First real run, pooled 2004-2026, 3mo/6mo forward drawdown | See Results table above. |
| 2026-08-27 | Decile-granularity check: does the gradient hold finer than terciles? | **No, not reliably.** 10 buckets of ~25 samples each: P(≥10% drawdown) goes 40% → 28% → 40% → 24% → 36% → 16% → 20% → 8% → 0% → 7% from most-stressed to calmest decile — broadly monotonic overall, but genuinely non-monotonic within (decile 2 > decile 1; decile 4 > decile 3). Small per-bucket samples, real noise, not a design flaw. **Decision:** the live UI now shows a real, exact percentile-rank position (0-100, computed from the same real distribution) for intuitive gauge display, but only the 3 tercile zones (33/67 cutoffs) carry a further-tested predictive claim — fine position within a zone is honest positioning, not itself validated at that resolution. `backend/engine/regime/scoring_v3.py`'s `PERCENTILE_CHECKPOINTS`. |
| 2026-08-28 | Real robustness re-check, `research_lab/macro_significance_robustness_check.py`: the naive Pearson/Fisher significance tests used throughout this project assume independent observations, but `STRIDE_DAYS=21` sampling against 63/126-day forward windows leaves real overlap (see `docs/hypotheses/README.md`'s "Known methodology limitations"). Re-tested with a moving-block permutation (block size = ⌈forward_days/21⌉, 2,000 reps, shuffles contiguous blocks not individual points — respects the real autocorrelation instead of assuming independence). | **Holds.** 63d: r=-0.208, naive p=0.0008 → block-permutation p=0.0075 (still significant). 126d: r=-0.233, naive p=0.0002 → block-permutation p=0.0065 (still significant). The naive p-values were real but too optimistic (understating uncertainty by roughly 9-30x) — the corrected p-values are larger but the finding survives the more honest test. This project's foundational macro finding is real under either standard. |
