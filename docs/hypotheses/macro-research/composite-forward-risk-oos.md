# Composite forward risk — out-of-sample split

Status: observing
Version: v0.1
Registered: 2026-08-27

Out-of-sample split of `composite-forward-risk.md` (H-MACRO09), requested
directly. Chronological split at **2019-01-01** (disclosed before running,
not chosen after seeing either half) — not random, since shuffling a time
series would leak future information through the trailing-window z-scores.
No parameters refit on either half; nothing in this composite was ever
fitted, so this is a real replication check, not overfitting protection in
the classic sense. `research_lab/composite_forward_risk_oos.py`.

- **In-sample**: 2004–2018 (includes 2008).
- **Out-of-sample**: 2019–2026 (includes the 2020 COVID crash and the 2022
  hiking cycle — a real, eventful holdout, not a quiet stretch where a null
  result would be uninformative either way).

## Results

| Window | Sample | IC (r) | P(≥10% dd) stressed | P(≥10% dd) calm | Diff | p |
| --- | --- | --- | --- | --- | --- | --- |
| 3mo | In-sample | +0.310, p<0.0001 | 23.6% (13/55) | 3.6% (2/55) | +20.0pp | 0.0041 |
| 3mo | **Out-of-sample** | +0.244, p=0.021 | 31.0% (9/29) | 6.9% (2/29) | +24.1pp | 0.0411 |
| 6mo | In-sample | +0.331, p<0.0001 | 29.1% (16/55) | 7.3% (4/55) | +21.8pp | 0.0055 |
| 6mo | **Out-of-sample** | +0.311, p=0.0035 | 46.4% (13/28) | 3.6% (1/28) | +42.9pp | 0.0004 |

## Reading this

**Replicates cleanly.** Both windows stay significant out-of-sample despite
a much smaller n (28-29 per tercile vs. 55), and the 6-month effect is
*stronger* out-of-sample (+42.9pp vs. +21.8pp in-sample) — the opposite of
what overfitting to the in-sample period would produce. A real, encouraging
result for a first pass with zero fitted parameters.

## Promotion criteria

Still not claimed — one split, one composite design, no threshold
sensitivity check, Liquidity/Guidance/policy-operations still excluded.
But this is the strongest piece of evidence in the macro-research folder so
far. `macro_regime_composite` stays frozen regardless.

## Observation log

| Date | Checkpoint | Reading |
| --- | --- | --- |
| 2026-08-27 | Chronological split at 2019-01-01, both forward windows | See Results table above — replicates out-of-sample, strengthens at 6mo. |
