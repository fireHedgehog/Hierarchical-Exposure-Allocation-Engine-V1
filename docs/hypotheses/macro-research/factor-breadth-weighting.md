# Factor breadth-weighting vs. cluster-equal-weighting (H-MACRO11)

Status: concluded-confirmed, real and substantial — but flagged, not
promotion-ready: the target tested here (forward SPY return) is not
the target the live composite is actually validated against (forward
drawdown probability, H-MACRO09). Real next step required before this
touches production; not done yet. See Observation log.
Version: v0.1
Registered: 2026-08-28
Concluded: 2026-08-28

Picks up an already-flagged, pre-scoped gap directly:
`macro-research/README.md`'s own restart-here table has carried
"Compare cluster-equal-weighting against IC-weighted alternatives"
since the naive-v3 promotion. Prompted by the same Fundamental-Law
question just applied to the sleeve layer (H-SECT04 v2) — applied here
to the macro composite itself.

## Thesis

`macro_regime_composite`'s naive-v3 design gives every real cluster
(growth/inflation, rate level, market stress) equal weight, then every
member within a cluster equal weight (H-MACRO08's redundancy-aware
fix, replacing v1/v2's hand-picked per-factor weights). That's a real
improvement over v1/v2, but it still isn't IC-weighted — a factor with
real, measured predictive power gets the same weight as one with none,
as long as they're in the same cluster. A real, walk-forward IC-
weighted combination of the same 13 factors should out-forecast the
cluster-equal design.

Falsified by: the IC-weighted alternative's real, out-of-sample IC
against forward SPY return doesn't beat the existing cluster-equal
composite's own OOS IC.

## Method

Real, point-in-time per-factor contributions (the same z-scores
`compute_regime_v3` already computes internally, extracted directly,
not re-derived) at every real historical anchor date. Real per-factor
IC (Pearson, contribution vs. forward 126-trading-day SPY return)
learned **in-sample only** (2004-2018), held fixed, applied unchanged
out-of-sample (2019-2026) — no lookahead. IC-weighted alternative
composite: `Σ(IC_i × contribution_i) / Σ|IC_i|`. Real effective
breadth via this project's own proven PCA machinery
(`effective_number_of_bets`, H-MACRO08's tool). Compared against the
existing cluster-equal composite's own real IC, same target, same
dates, both halves.

## What would count as a real checkpoint

One real run of `research_lab/macro_factor_breadth_test.py` against
the sealed dataset.

## Observation log

| Date | Checkpoint | Reading |
| --- | --- | --- |
| 2026-08-28 | Real run, `research_lab/macro_factor_breadth_test.py`. 256 real anchors, 11 of 13 factors had enough in-sample history for a real IC (`BAMLH0A0HYM2`/`BAMLC0A0CM` excluded — real data only from 2023, no in-sample coverage before the 2019 split, disclosed not guessed). | **Confirmed, and substantially larger than anything found at the sleeve layer.** |

| Metric | Value |
| --- | --- |
| Mean \|IC\| across 11 factors | 0.148 |
| Real effective breadth | 7.33 (vs. naive count 13; a different, continuous measure than H-MACRO08's "~4 clusters," not contradictory — this counts real independence among factors, not a categorical grouping) |
| Grinold-predicted IR | 0.402 |
| In-sample IC — cluster-equal (existing) | +0.258 |
| In-sample IC — IC-weighted (alternative) | +0.403 |
| **Out-of-sample IC — cluster-equal (existing)** | **+0.210** |
| **Out-of-sample IC — IC-weighted (alternative)** | **+0.400** |

The IC-weighted alternative nearly doubles the real, out-of-sample IC
(+0.400 vs. +0.210) — and the improvement is *larger* out-of-sample
than in-sample (+0.190 OOS vs. +0.145 in-sample), the same
strengthens-not-weakens-OOS pattern H-MACRO09 itself showed, a real
sign this isn't overfitting. A real, explainable mechanism, not a
fluke: cluster-equal-weighting forces near-zero or wrong-signed
factors (`rates_10y` IC=+0.020, `rates_30y` IC=-0.028, `volatility`
IC=-0.053 against *this* target) to the same weight as genuinely
predictive ones (`ppi` +0.260, `growth` +0.255, `inflation` +0.233) —
IC-weighting correctly down-weights the former.

**The real, disclosed reason this is not promotion-ready:** the target
tested here is forward SPY *return* — a continuous, symmetric measure
— not forward SPY *drawdown probability*, the actual, real,
out-of-sample-validated target the live composite's calibrated
`confidence` is built and tested against (H-MACRO09). `volatility` and
the rate factors scoring near-zero IC *here* does not mean they're
uninformative for drawdown probability specifically — a tail/asymmetric
target can have a very different real factor structure than a
continuous-return target. Re-weighting the live composite based on
*this* result alone would risk optimizing for the wrong thing.

## Promotion criteria

Real, substantial, and directionally confirmed — but a required next
step, not done here: re-run this exact method with the target swapped
to match H-MACRO09's own real target (P(real SPY drawdown ≥10% within
6 months)), same walk-forward discipline. Only if the IC-weighted
alternative also beats cluster-equal-weighting on *that* target, OOS,
does this become a real candidate for `scoring_v3.py` → `scoring_v4.py`
(a new version row, v3's code untouched, matching this project's own
established promotion pattern) — a real, live-production-facing change
that deserves that confirmation first, not promoted on this result
alone.
