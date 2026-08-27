# Composite face-validity backtest

Status: observing (design validation, not a strategy hypothesis)
Version: v0.1
Registered: 2026-08-27

Tests `composite-methodology-v1.md`'s proposed design (z-score per
indicator, hold-flat staleness, 3-cluster average — policy-operations
cluster excluded, ambiguous sign) against known historical outcomes.
`research_lab/composite_face_validity_backtest.py`, point-in-time correct
(only data available as-of each date).

## Results

| Date | Known reality | Composite | Verdict |
| --- | --- | --- | --- |
| 2008-10-15 (Lehman aftermath) | Risk-off | -1.45 | ✅ Match |
| 2020-03-23 (COVID trough) | Risk-off | -1.82 | ✅ Match |
| 2021-11-15 (late-cycle top) | Risk-on | -1.02 | ❌ **Miss** |
| 2022-10-14 (hiking trough) | Risk-off | -1.22 | ✅ Match |
| 2026-08-25 (current) | Not pre-judged | -0.01 | Neutral |

## The miss, read honestly

2021-11-15: equities were near all-time highs (naive "risk-on" by price),
but the composite read risk-off — driven by real, unusually high inflation
surprises (CPIAUCSL/PCEPILFE/PPIACO all >2 std devs above trailing
expectation — the real start of the 2021-22 inflation surge) and a
tightening NFCI reading, even while VIX itself stayed calm (+0.72, correctly
reading no near-term stress).

**This is a real, substantive finding, not a clean fail**: it raises the
actual design question directly, not resolved here — is this composite
meant to be a *coincident* read of what markets are doing today, or a
*leading* macro-conditions read that can validly diverge from price for a
while before price catches up? The real 2022 crash that followed is
consistent with the composite having been early, not wrong. Which framing
is intended changes how this result should be scored — a real, open
decision, not a bug to patch.

## What this validates and doesn't

- Staleness/z-score/clustering mechanics ran correctly end to end, real
  data, point-in-time correct, no fabricated values.
- 3 of 4 unambiguous crisis dates matched.
- The one disagreement is informative about a real design choice
  (coincident vs. leading), not evidence of a coding error.
- Not validated: the policy-operations cluster (excluded), Liquidity,
  Guidance, and whether -0.15/+0.15 are the right neutral-band thresholds
  (hand-picked, not fit).

## Next

Resolve the coincident-vs-leading question before anything moves toward
`schema.sql`. `macro_regime_composite` stays frozen.
