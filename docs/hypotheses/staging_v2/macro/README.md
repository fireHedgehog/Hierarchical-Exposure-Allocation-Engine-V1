# Macro Research - Staging V2

Macro state, predictive relationship, risk probability, and exposure policy are
different objects. None is an entry signal.

The Stage 2 symbol fetch does not improve FRED point-in-time history. The first
V2 audit below therefore tests the exact runtime transformation, but remains a
current-vintage diagnostic rather than a production probability calibration.

## Current studies

| Study | Role | Status | Production use |
| --- | --- | --- | --- |
| [Warsh Reaction Function](h-macro-s7-001-warsh-reaction-function.md) | S7 | Observing | None |
| H-MACRO-S2-001 - Exact Runtime Outcome Matrix | S2 | Completed; PIT-limited | Risk-context interpretation only |
| H-MACRO-S3-CV-001 - Numeric Environment Translation | S3 diagnostic | Accepted for staging | Percentage and environment position |
| [Direct Risk Appetite Policy](h-macro-s4-002-direct-risk-appetite-policy.md) | S4 | Design; grid not frozen | None |
| H-MACRO-S6-001 - Runtime Contribution Redundancy | S6 | Completed | Keep current weights pending better evidence |

## H-MACRO-S2-001 initial design

Hypothesis: the exact 13-factor clipped runtime score has a stable relationship
with later market paths. The loop tests one score definition against several
targets; it does not treat the score as a probability.

| Loop axis | Initial values |
| --- | --- |
| Input | Exact runtime score; no reconstructed legacy score |
| Target family | Forward return; return direction; realized volatility; maximum adverse excursion |
| Horizon | 3M; 6M; 12M |
| View | Continuous score; supportive/mixed/adverse buckets |
| Validation | Time-ordered development/test split; parameters frozen before results |

Run 2026-08-28 with
[`macro_v2_exact_runtime_audit.py`](../../../../backend/research_lab/macro_v2_exact_runtime_audit.py):
sealed dataset `real-macro-0f184797-d738-4ecd-a615-83b0020c5753`, 5,469 SPY
bars, 258 monthly-strided runtime anchors, development before 2022 and temporal
test from 2022. `p` is a 2,000-repetition moving-block permutation result; `q`
is Benjamini-Hochberg across all 12 rows.

| Target | Horizon | Dev N | Test N | Dev rank IC | Test rank IC | IC rank | Zone effect | block p | BH q | q rank | Sign stable | Verdict |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| Maximum adverse excursion | 6M | 202 | 50 | +0.347 | +0.534 | 1 | +6.7% | 0.0015 | 0.0180 | 2 | Yes | supported |
| Realized volatility | 6M | 202 | 50 | -0.184 | -0.515 | 2 | +6.8% | 0.0030 | 0.0180 | 1 | Yes | supported |
| Return direction | 6M | 202 | 50 | +0.260 | +0.509 | 3 | +43.8% | 0.0240 | 0.0480 | 6 | Yes | supported |
| Maximum adverse excursion | 12M | 202 | 44 | +0.329 | +0.509 | 4 | +6.7% | 0.0390 | 0.0668 | 7 | Yes | inconclusive |
| Realized volatility | 12M | 202 | 44 | -0.076 | -0.502 | 5 | +4.9% | 0.1234 | 0.1559 | 10 | Yes | inconclusive |
| Forward return | 12M | 202 | 44 | +0.201 | +0.492 | 6 | +13.7% | 0.1299 | 0.1559 | 9 | Yes | inconclusive |
| Maximum adverse excursion | 3M | 202 | 53 | +0.335 | +0.451 | 7 | +4.0% | 0.0080 | 0.0320 | 3 | Yes | supported |
| Return direction | 12M | 202 | 44 | +0.188 | +0.423 | 8 | +28.6% | 0.2534 | 0.2534 | 12 | Yes | inconclusive |
| Realized volatility | 3M | 202 | 53 | -0.210 | -0.417 | 9 | +6.5% | 0.0130 | 0.0390 | 4 | Yes | supported |
| Return direction | 3M | 202 | 53 | +0.199 | +0.364 | 10 | +35.3% | 0.0210 | 0.0480 | 5 | Yes | supported |
| Forward return | 3M | 202 | 53 | +0.203 | +0.267 | 11 | +4.0% | 0.1104 | 0.1559 | 8 | Yes | inconclusive |
| Forward return | 6M | 202 | 50 | +0.267 | +0.266 | 12 | +5.8% | 0.2029 | 0.2213 | 11 | Yes | inconclusive |

The exact runtime score has a stable relationship with 3M/6M adverse excursion,
realized volatility, and direction. Forward return magnitude does not survive
the corrected test. This supports a risk-context interpretation, not an entry
signal or return forecast.

## H-MACRO-S3-CV-001 numeric translation

Preserve both numeric product outputs without calling either a calibrated
release-time-PIT probability: the progress position is the current exact score's
empirical percentile; the percentage is the historical frequency of a 10% SPY
adverse excursion within six months, grouped by the runtime's existing zones.

Current exact-runtime reading on 2026-08-27: composite `+0.024`, mixed state,
`55.4/100` support position.

| Zone | Dev N / frequency | Test N / frequency | Full N / frequency |
| --- | ---: | ---: | ---: |
| Adverse | 21 / 23.8% | 10 / 60.0% | 31 / 35.5% |
| Mixed | 163 / 22.1% | 37 / 18.9% | 200 / 21.5% |
| Supportive | 18 / 5.6% | 3 / 0.0% | 21 / 4.8% |

Accepted staging UI pair: `55.4/100` environment position and `21.5%`
six-month adverse-frequency reference (`18.9%` in the held-out period). The
ordering is preserved in development, test, and full samples; the small adverse
and supportive test buckets remain visibly uncertain.

## H-MACRO-S4-002 direct risk appetite design

The independent [experiment document](h-macro-s4-002-direct-risk-appetite-policy.md)
holds the finite engineering grid, asymmetric long-only utility, literature
anchors, validation design, confidence translation, result-table shape, and
manual stopping rules. It is still a design: no grid has been frozen and no
result is implied.

## H-MACRO-S6-001 initial design

Diagnose the transformed contributions actually consumed by the runtime score,
not raw FRED series levels. Report pairwise correlation, cluster concentration,
and effective number of bets. This can justify keeping or questioning weights;
it cannot change them automatically.

| Contribution set | Window | N | Max abs correlation | Effective bets | Dominant cluster | Stability | Verdict |
| --- | --- | ---: | ---: | ---: | --- | --- | --- |
| Core 11 transformed contributions | 2006-10-02 to 2026-08-17 | 239 | 0.946 | 6.00 | rate level | dev 5.73 / test 5.85 | partly redundant |
| All 13 transformed contributions | 2023-10-10 to 2026-08-17 | 35 | 0.974 | 6.17 | rate level | insufficient split | concentrated |

Strongest pairs are 10Y/30Y yields (`+0.946` core, `+0.974` recent), nominal
and real yields (`+0.774` to `+0.920`), inflation/PPI (`+0.765`), and HY/IG
credit (`+0.715`, recent only). The stable core result is about six effective
bets rather than the roughly four inferred earlier from raw levels. That is not
evidence to replace the current cluster-equal weighting. The all-13 result has
only 35 common anchors and cannot establish stability.

## Honest limitation and translation decision

Historical FRED rows are current-vintage values aligned by observation date;
the dataset does not contain the true release timestamp for each historical
observation. This can leak information across an anchor date. The result is
useful for checking the exact runtime transformation, but is not honest enough
to claim a release-time-PIT probability.

- Keep the current 13-factor state score and cluster-equal weights.
- Preserve the percentage, 0-100 progress position, and 13-factor detail table.
- Use S3-CV's exact-runtime percentage and environment position in staging;
  manual translation was approved on 2026-08-28.
- Do not change the 0.5x-1.5x S4 policy from this run.
- Reopen S3 when true release-date PIT history exists, or when a separate,
  manually approved lag convention is preregistered.

## Manual gates

1. S2 and S6 are complete.
2. S3-CV supplies an honest current-vintage percentage; calibrated S3 remains
   blocked by release-time PIT.
3. The application retains its current 0.5x-1.5x staging policy band. S4-002
   may test 0x-1.5x, but cannot change the application without a separately
   accepted result and manual translation.
4. Later result changes still require a separate manual translation decision.
