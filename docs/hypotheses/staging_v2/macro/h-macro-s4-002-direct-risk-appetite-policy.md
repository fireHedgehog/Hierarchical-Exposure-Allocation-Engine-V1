# H-MACRO-S4-002 - Decision Policy - Long-Biased Risk Appetite

| Field | Value |
| --- | --- |
| Study ID | H-MACRO-S4-002 |
| Legacy ID | None |
| Status | Inconclusive - Phase A v1.1; macro families baseline-dominated |
| Dataset | Phase A: sealed current-vintage dataset `real-macro-0f184797-d738-4ecd-a615-83b0020c5753`; Phase B requires release-time PIT data or an approved lag convention |
| Input | Macro-financial state candidates built from the core 11 factors; the recent 13-factor set is an extension |
| Target | Net long-only exposure-policy utility on SPY, with QQQ, DIA, and long-history XL ETFs as robustness panels |
| Production use | None until a result is manually accepted and translated |
| Does not claim | That a negative state means short SPY, that confidence is `1-p`, or that a current-vintage backtest is deployable |

## Product question

Given the macro-financial information actually available at a decision time,
what long-biased exposure would best balance participation and capital
protection, and how stable is that choice?

The product has two separate outputs:

- **Risk appetite:** `-100` is the strongest defensive warning, `0` is neutral,
  and `+100` is the strongest supportive reading. It describes state, not a
  signed position.
- **Confidence:** `0-100` describes out-of-sample policy agreement and
  reliability. It is not statistical significance.

The action remains long-only. The research grid is
`0x, 0.25x, 0.5x, 0.75x, 1x, 1.25x, 1.5x`; `0x` means cash, never short SPY.
The currently running staging policy remains unchanged until this study is
accepted manually.

## Economic preference, stated before tuning

The loss function is deliberately asymmetric. Avoiding a genuine loss,
drawdown, or volatility shock rewards a defensive warning. A false warning
pays missed upside and turnover. A false supportive reading pays the extra
downside and drawdown it created. This is a product risk preference, not a
claim that one universal utility function is scientifically correct.

For policy path `p` and benchmark `b = 1x`:

```text
Delta utility(p, b)
  = net annualized return difference
  - lambda_dd * maximum-drawdown difference
  - lambda_down * downside-volatility difference
  - lambda_turn * annual-turnover difference
  - explicit transaction and financing costs
```

All terms and units must be printed separately beside the combined utility.
The combined score may rank policies; it may not hide a return, drawdown, or
cost failure.

For exposure below `1x`, idle capital uses a declared cash return. Exposure
above `1x` pays a declared financing rate plus spread. Phase A may use zero
cash return as a conservative sensitivity, but no result above `1x` qualifies
without a real financing series. The source and availability convention must
be frozen before the run.

## Two-pass experiment

### Phase A - engineering screen

Use current-vintage data only to learn whether the machinery, candidate
families, grids, and result tables behave sensibly. Phase A may reject ideas,
but it cannot promote a production policy because historical release timing is
not point-in-time honest.

### Phase B - frozen confirmation

Freeze the candidate families, grid, utility profiles, cost model, folds, and
selection rule before opening a true release-time-PIT holdout. A manually
approved publication-lag convention is acceptable as a separate study, but
must not be silently mixed with true PIT data.

## Candidate families and finite grid

The first screen compares a few interpretable families; it does not search
arbitrary formulas or one model per factor. The broad design space below is a
roadmap. The smaller Phase A v1 contract immediately after it is the frozen
first run.

| Axis | Initial grid |
| --- | --- |
| State family | Exact runtime score; cluster-equal de-duplicated score; sign-constrained regularized risk model |
| Factor set | Core 11 primary; all 13 recent-history extension |
| Normalization | Current lookback; one-half lookback; double lookback, capped by available history |
| Tail clipping | `2.0`, `2.5`, `3.0` z-score bands |
| Smoothing | None; 1-month; 3-month |
| Decision frequency | Monthly primary; release-triggered only after release timestamps exist |
| Outcome horizon | 3M; 6M; report separately before any combination |
| Exposure | `0x` through `1.5x` in `0.25x` steps |
| Transaction cost | `1`, `5`, `10` bps per one-way `1x` turnover |
| Financing spread | `0`, `50`, `100` bps above the frozen cash/financing proxy |
| Preference profile | Return-seeking; balanced; capital-preservation |

### Frozen Phase A v1 contract

The first run deliberately tests defense before leverage. The core history
starts in 2006, while the stored real SOFR series starts in 2018. Full-history
selection therefore uses only `0x-1x` and a conservative zero cash return. A
later `1.25x/1.5x` extension must use the real SOFR period and remains
descriptive until it has enough time folds.

| Choice | Frozen value |
| --- | --- |
| Decision path | Non-overlapping 21-SPY-trading-day segments; state observed at each segment start |
| Outer tests | 2015-2018; 2019-2022; 2023-latest, each with expanding prior training |
| Inner selection | Three expanding two-year validation blocks inside each outer training period |
| Primary asset | SPY |
| Robustness | QQQ, DIA, XLB, XLE, XLF, XLI, XLK, XLP, XLU, XLV, XLY |
| State families | Exact three-cluster runtime; four-block activity/price/rates/stress score; VIX-only baseline |
| Deferred family | Sign-constrained regularized model; add only after the simple policy machinery passes |
| Factor set | Core 11 only; credit-spread/all-13 history is too short for the outer folds |
| Normalization | Runtime lookback multiplied by `0.5`, `1`, or `2` |
| Tail clipping | `2.0`, `2.5`, `3.0` z-score bands |
| Smoothing | 1 or 3 monthly anchors |
| Policy | Training-score terciles mapped monotonically to `0x, 0.25x, 0.5x, 0.75x, 1x`; supportive tercile must be `1x`; only the explicit benchmark may ignore state |
| Cash / financing | Zero cash return; no leverage in v1 |
| Explicit cost | 5 bps per one-way `1x` turnover; 1 and 10 bps sensitivities |
| Return-seeking utility | `lambda_dd=0.25`, `lambda_down=0.10`, `lambda_turn=0` |
| Balanced utility | `lambda_dd=0.75`, `lambda_down=0.25`, `lambda_turn=0.001` |
| Capital-preservation utility | `lambda_dd=1.50`, `lambda_down=0.50`, `lambda_turn=0.0025` |
| Selection | Highest mean inner-fold timing utility versus a static policy with the same test-fold mean exposure; simplest configuration wins within one standard error |

The penalty profiles are transparent preference scenarios, not estimates from
the return sample. The scale audit treats annualized return, drawdown magnitude,
and annualized downside volatility as decimal returns; turnover is annual
one-way multiplier turnover. Changing these values after seeing results creates
a new design revision.

The first v1 machinery run exposed a structural degeneracy before any result
was accepted: capital-preservation utility could select permanent `0x`, which
measures unconditional risk aversion rather than macro timing. V1.1 therefore
requires the supportive state to return to `1x` and decomposes every result
into (a) allocation utility versus `1x`, and (b) timing utility versus a static
policy with the same mean exposure. A macro warning has research value only if
timing utility is positive; lowering exposure by itself is not evidence.

## Validation and selection

1. Use nested rolling-origin evaluation. Inner folds choose a candidate; outer
   folds estimate performance. Purge or embargo overlapping 3M/6M outcomes.
2. Compare every candidate with `1x` buy-and-hold, the current staging policy,
   and a volatility-only long-biased policy.
3. Record every tried configuration and the total search count. Do not rerun a
   narrower grid after seeing a holdout without creating a new revision.
4. Prefer the simplest candidate within one standard error of the best inner-
   fold utility. Rank by economic utility, not raw p-value.
5. Report SPY as the primary decision. QQQ and DIA test broad-index transfer;
   XL ETFs diagnose where the policy helps or breaks. They do not get pooled
   into a larger sample that hides disagreement.
6. Repeat without leverage, without the three worst SPY months, and under the
   highest cost assumptions. A result that exists only with leverage or one
   crisis is fragile.
7. Estimate selection risk with block resampling and a backtest-overfitting
   diagnostic. These are warnings, not automatic pass/fail bureaucracy.

## Risk appetite and confidence translation

For each anchor, estimate the out-of-sample expected utility curve over the
long-only exposure grid. Let `D` be the expected-utility advantage of the best
supportive action (`>1x`) over the best defensive action (`<1x`). Scale `D`
only with training data into `[-100, +100]`; this becomes risk appetite.

Confidence is derived from blocked out-of-sample resamples: how often the same
side of `1x` remains preferred and how stable the selected exposure is across
nearby parameters and broad-index panels. Its exact calibration must be shown
in reliability bins. Until calibration is adequate, label it **policy
agreement**, not probability.

Confidence shrinks action toward the `1x` baseline:

```text
effective multiplier = 1 + confidence * (candidate multiplier - 1)
```

where confidence is expressed from `0` to `1`. Low confidence therefore means
“stay near baseline,” not “take the opposite trade.”

## Phase A v1.1 results

Run 2026-08-28 with
[`macro_s4_long_biased_policy.py`](../../../../backend/research_lab/macro_s4_long_biased_policy.py):
224 non-overlapping policy periods from 2007-12-03 through 2026-08-17,
54 state variants, 757 admissible policy specifications, and three expanding
outer tests. All results use the frozen sealed dataset and remain
current-vintage diagnostics.

| Utility profile | Selected family by outer fold | Mean OOS timing U | Allocation U vs 1x | Mean CAGR | Worst max DD | Annual turnover | Worst timing fold | Verdict |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Return-seeking | static / VIX / VIX | -0.0041 | -0.0164 | 11.70% | 27.60% | 1.42 | -0.0100 | rejected |
| Balanced | static / VIX / VIX | +0.0066 | +0.0091 | 12.45% | 27.60% | 1.14 | +0.0000 | baseline-only; inconclusive |
| Capital-preservation | static / VIX / VIX | +0.0305 | +0.0539 | 10.97% | 24.47% | 1.48 | +0.0000 | preference-specific VIX defense |

Balanced family isolation is the decisive comparison. Each row is allowed to
select only that state family or static `1x`.

| Allowed state family | Mean OOS timing U | Allocation U vs 1x | Worst timing fold | Positive timing folds | Verdict |
| --- | ---: | ---: | ---: | ---: | --- |
| Exact three-cluster runtime | -0.0144 | -0.0124 | -0.0490 | 1/3 | baseline-dominated |
| Four-block activity/price/rates/stress | -0.0211 | -0.0105 | -0.0451 | 0/3 | baseline-dominated |
| VIX-only | +0.0026 | -0.0009 | +0.0000 | 1/3 | weak and selection-unstable |

The globally selected balanced VIX policy reduced SPY average outer-fold
maximum drawdown by 3.77 percentage points and remained positive at 1 and 10
bps costs. It failed on QQQ (`-0.0254` timing utility), XLK (`-0.0258`), and
XLY (`-0.0240`); DIA and seven of nine long-history XL sectors were positive.
That is useful risk-engineering evidence, but not broad confirmation.

| Balanced exposure band | N | Mean exposure | 6M adverse-event rate | 1M policy win rate | Confidence |
| --- | ---: | ---: | ---: | ---: | --- |
| Defensive below 0.5x | 0 | n/a | n/a | n/a | not calibrated |
| Cautious 0.5-0.75x | 20 | 0.50x | 35.0% | 20.0% | not calibrated |
| Baseline 1x | 114 | 1.00x | 20.2% | 100.0% by equality | not calibrated |

## Interpretation and stopping decision

Phase A v1.1 does not support translating the current 11-factor macro score
into exposure. The simple VIX baseline was chosen whenever any dynamic policy
survived, while both macro families had negative mean timing utility. Balanced
and capital-preservation benefits are therefore evidence for a fast market-risk
overlay and a stated loss preference, not evidence that slow macro inputs time
equity exposure.

The result also changes when the allowed family set changes under the
one-standard-error rule. That candidate-set dependence is a selection-stability
warning. Do not tune v1.1 further on the same outcomes. A new revision must
either test a preregistered slow-macro-plus-fast-VIX architecture against
VIX-only, add the deferred sign-constrained risk model, or wait for honest PIT
history. The current production/staging algorithm remains untouched.

## Decision rules

A candidate is **confirmed** only if it improves SPY out-of-sample balanced or
capital-preservation utility, does not worsen maximum drawdown under the
capital-preservation profile, keeps the same policy direction in at least two
of three outer folds, and remains directionally useful without leverage and at
high costs. Cross-asset disagreement is reported, not averaged away.

A candidate is **preference-specific** if it works for only one declared
utility profile. It is **inconclusive** if nearby parameters reverse the
action, and **rejected** if `1x` or volatility-only dominates. None of these
statuses changes application code automatically.

Before production translation, a human must approve the factor set, state
mapping, confidence label, maximum exposure, and any factor retirement. The UI
contract -- number, confidence, bar, color, and contribution table -- remains
available even when every research candidate fails.

## Focused literature anchors

These sources constrain design choices; this file is not a paper library.

- Merton, R. C. (1981). *On market timing and investment performance. I: An
  equilibrium theory of value for market forecasts*. The Journal of Business,
  54(3), 363-406. https://doi.org/10.1086/296137
- Moreira, A., & Muir, T. (2017). *Volatility-managed portfolios*. The Journal
  of Finance, 72(4), 1611-1644. https://doi.org/10.1111/jofi.12513
- Bailey, D. H., Borwein, J. M., Lopez de Prado, M., & Zhu, Q. J. (2017). *The
  probability of backtest overfitting*. Journal of Computational Finance,
  20(4), 39-69. https://doi.org/10.21314/JCF.2016.322
- Frazzini, A., Israel, R., & Moskowitz, T. J. (2012). *Trading costs of asset
  pricing anomalies* (Fama-Miller Working Paper).
  https://doi.org/10.2139/ssrn.2294498

The pre-run literature task is narrow: verify utility scaling, volatility-only
baseline construction, financing/cash conventions, and selection-bias
diagnostics. Any new source must change a declared design choice or stay out of
the document.
