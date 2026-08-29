# H-XSEC-S2-002 - Predictive Relationship - Price/Volume Factor Screen

| Field | Value |
| --- | --- |
| Study ID | H-XSEC-S2-002 |
| Legacy ID | None |
| Status | Confirmed discovery relationship; run 2026-08-29 |
| Dataset | Stage 2 adjusted OHLCV library through 2026-08-27 ET |
| Universe | Current 775-name Stage 2 roster; 503 names also receive an 11-sector-neutral view |
| Input | Simple trailing price, volatility, market-residual, and liquidity characteristics |
| Target | Forward 5/10/21/42/63-session return rank and top-minus-bottom quintile spread |
| Production use | None |
| Does not claim | Historical PIT investability, causality, or a ready trading strategy |

## Question

> At the same month-end, do stocks with a higher observable characteristic
> rank earn higher subsequent returns than stocks with a lower rank?

This is the ordinary cross-sectional question. It does not require a gap,
calendar-quarter onset, sector diffusion, earnings label, or narrative about
why a stock moved.

## Why this is the reset

Large cross-sectional research libraries normally compute many firm
characteristics, sort stocks at a common rebalance date, and compare future
returns across characteristic ranks. Chen and Zimmermann reproduce hundreds of
published predictors and explicitly report characteristic monotonicity and
long-short portfolio evidence ([Federal Reserve paper and data](https://www.federalreserve.gov/econres/feds/open-source-cross-sectional-asset-pricing.htm),
[open implementation](https://github.com/OpenSourceAP/CrossSection)). Nagel's
[cross-sectional survey](https://www.nber.org/papers/w18554) identifies past
returns and trading volume as the natural directly observable technical
predictors. Gu, Kelly, and Xiu find momentum, liquidity, and volatility among
the dominant predictor families even in nonlinear models
([NBER](https://www.nber.org/papers/w25398)).

We use that simple spine. The current database lacks fundamentals, so this run
tests the price/volume subset instead of inventing proxies for value, quality,
or earnings.

## Frozen matrix

Every signal is signed so a higher value means a higher predicted return.
Definitions use only information available at the formation close.

| Factor | Definition | Literature-shaped expectation |
| --- | --- | --- |
| `reversal_5d` | negative trailing 5-session return | Recent losers rebound |
| `momentum_1m` | trailing 21-session return | Very short continuation or reversal is measured, not assumed |
| `momentum_3_1` | return from session -63 to -21 | Intermediate winners continue |
| `momentum_6_1` | return from session -126 to -21 | Intermediate winners continue |
| `momentum_12_1` | return from session -252 to -21 | Classic 12-1 momentum; matches the open-source implementation |
| `high_52w` | adjusted close / maximum adjusted high over 252 sessions | Near-high names continue |
| `trend_consistency_3m` | positive-return fraction over 63 sessions | Persistent rather than one-day strength continues |
| `vol_scaled_momentum_6_1` | 6-1 return / trailing 126-session volatility | Strength per unit of recent noise |
| `residual_momentum_6_1` | cumulative market-residual return from -126 to -21 | Stock-specific strength continues |
| `low_total_vol_3m` | negative volatility of 63-session daily returns | Tests the simple low-total-volatility relation |
| `low_beta_1y` | negative 252-session SPY beta | Tests the low-beta relation |
| `low_idio_vol_1y` | negative volatility of 252-session SPY residuals | Tests the low-idiosyncratic-volatility relation documented by [Ang et al.](https://www.nber.org/papers/w10852) |
| `max_effect_1m` | negative maximum daily return over 21 sessions | Avoid lottery-like recent winners |
| `low_dollar_volume_1m` | negative log median dollar volume over 21 sessions | Separates a simple capacity/liquidity axis from Amihud price impact |
| `amihud_illiquidity_1m` | mean absolute return / dollar volume over 21 sessions | Small liquidity premium that large capital may not capture |

The first five return factors and `high_52w` are the simplest priority. The
remaining factors test whether volatility, residual strength, or a small-
capacity liquidity effect adds a different axis. This is one screen, not 15
papers.

## Sampling and tests

1. Form the cross-section at the final SPY trading session of each month.
2. Require 252 sessions of history, positive prices, and nonzero recent dollar
   volume. This removes broken rows, not difficult but real securities.
3. Broad view: rank every eligible Stage 2 name together.
4. Sector-neutral view: rank factor and outcome within each of the 11 Select
   Sector cohorts, then combine those within-sector ranks.
5. Compute a Spearman Rank IC per formation month for each factor and forward
   horizon. Report mean IC, monthly hit rate, and the two-sided p-value for the
   time-series mean IC. Longer overlapping horizons use a small Newey-West
   correction.
6. Report equal-weight top-quintile minus bottom-quintile forward return at the
   same dates. P-values alone never define usefulness.
7. Apply Benjamini-Hochberg q-values across the frozen factor x horizon family.
   Raw p remains visible.
8. Show development (through 2018), validation (2019 through 2023H1), and
   holdout (2023H2 onward) direction for candidates. No threshold is tuned from
   holdout.

The roster is today's roster viewed through historical prices. That label is
sufficient for this disposable discovery screen; it is not a reason to stop.

## Results - 2026-08-29

The run used 246 month-end formations from November 2005 through April 2026.
Average usable cross-sections were about 565 names broad and 449-453 names in
the sector-neutral view. Each cell is `mean monthly Rank IC / HAC p / BH q /
top-minus-bottom quintile spread`.

### Broad

| Factor | 5d | 10d | 21d | 42d | 63d |
| --- | --- | --- | --- | --- | --- |
| `reversal_5d` | +.016 / .0788 / .4471 / +.16% | +.020 / .0163 / .2032 / +.43% | +.014 / .0838 / .4471 / +.35% | +.010 / .1912 / .7101 / +.37% | +.007 / .2957 / .8215 / +.35% |
| `momentum_1m` | +.008 / .4015 / .9410 / +.16% | -.000 / .9988 / .9988 / +.17% | -.006 / .5215 / .9897 / +.06% | -.011 / .1988 / .7101 / +.10% | -.008 / .3256 / .8669 / +.10% |
| `momentum_3_1` | -.004 / .7023 / .9897 / -.17% | +.005 / .6617 / .9897 / +.03% | -.005 / .6045 / .9897 / -.09% | -.008 / .4471 / .9897 / -.01% | -.005 / .6554 / .9897 / +.08% |
| `momentum_6_1` | -.008 / .5354 / .9897 / -.31% | -.001 / .9360 / .9897 / -.06% | -.002 / .8793 / .9897 / -.02% | -.006 / .5686 / .9897 / +.04% | -.004 / .7510 / .9897 / +.16% |
| `momentum_12_1` | -.004 / .7425 / .9897 / -.29% | +.001 / .9342 / .9897 / -.10% | +.005 / .6650 / .9897 / -.01% | +.000 / .9879 / .9945 / -.00% | -.003 / .8553 / .9897 / -.04% |
| `high_52w` | -.002 / .9157 / .9897 / -.38% | -.001 / .9669 / .9915 / -.49% | -.001 / .9386 / .9897 / -.73% | -.005 / .7358 / .9897 / -1.49% | -.004 / .8121 / .9897 / -2.05% |
| `trend_consistency_3m` | -.000 / .9715 / .9915 / -.11% | +.003 / .7398 / .9897 / -.14% | -.001 / .9336 / .9897 / -.33% | -.006 / .5445 / .9897 / -.66% | -.006 / .5843 / .9897 / -.95% |
| `vol_scaled_momentum_6_1` | -.006 / .6330 / .9897 / -.28% | -.002 / .8780 / .9897 / -.07% | -.004 / .6603 / .9897 / -.10% | -.007 / .4711 / .9897 / -.08% | -.005 / .6237 / .9897 / -.02% |
| `residual_momentum_6_1` | -.007 / .5605 / .9897 / -.26% | -.000 / .9717 / .9915 / +.03% | -.003 / .7310 / .9897 / +.12% | -.006 / .5323 / .9897 / +.34% | -.005 / .6230 / .9897 / +.56% |
| `low_total_vol_3m` | -.005 / .7646 / .9897 / -.38% | +.001 / .9436 / .9897 / -.64% | +.002 / .8773 / .9897 / -1.08% | -.008 / .6776 / .9897 / -2.48% | -.009 / .6841 / .9897 / -3.67% |
| `low_beta_1y` | -.021 / .2367 / .7336 / -.43% | -.020 / .2397 / .7336 / -.67% | -.013 / .4196 / .9684 / -.87% | -.024 / .2068 / .7213 / -1.90% | -.029 / .1957 / .7101 / -2.79% |
| `low_idio_vol_1y` | -.005 / .7116 / .9897 / -.40% | -.002 / .8798 / .9897 / -.73% | -.000 / .9868 / .9945 / -1.06% | -.008 / .6090 / .9897 / -2.39% | -.010 / .5988 / .9897 / -3.60% |
| `max_effect_1m` | -.003 / .8468 / .9897 / -.33% | +.006 / .6338 / .9897 / -.49% | +.007 / .5895 / .9897 / -.77% | +.002 / .8756 / .9897 / -1.72% | +.003 / .8513 / .9897 / -2.65% |
| `low_dollar_volume_1m` | -.009 / .2667 / .7808 / +.15% | -.013 / .0868 / .4471 / +.14% | +.004 / .6229 / .9897 / +.61% | +.014 / .0919 / .4471 / +1.44% | +.020 / .0416 / .3634 / +2.31% |
| `amihud_illiquidity_1m` | -.007 / .4813 / .9897 / +.17% | -.011 / .2370 / .7336 / +.26% | +.005 / .5517 / .9897 / +.79% | +.018 / .0954 / .4471 / +1.86% | +.023 / .0531 / .3792 / +2.90% |

### Sector-neutral

| Factor | 5d | 10d | 21d | 42d | 63d |
| --- | --- | --- | --- | --- | --- |
| `reversal_5d` | +.019 / .0109 / .1983 / +.07% | +.025 / .0006 / .0138 / +.32% | +.015 / .0250 / .2682 / +.27% | +.011 / .0643 / .4383 / +.36% | +.011 / .0949 / .4471 / +.27% |
| `momentum_1m` | +.004 / .6548 / .9897 / +.20% | -.008 / .3429 / .8867 / +.12% | -.008 / .3294 / .8669 / +.11% | -.009 / .2184 / .7281 / +.10% | -.008 / .2759 / .7808 / +.12% |
| `momentum_3_1` | +.003 / .7678 / .9897 / -.12% | +.008 / .3783 / .9157 / +.05% | -.001 / .9312 / .9897 / +.01% | -.004 / .7031 / .9897 / -.02% | -.002 / .8056 / .9897 / +.14% |
| `momentum_6_1` | -.001 / .9197 / .9897 / -.18% | +.002 / .8868 / .9897 / -.08% | -.001 / .9374 / .9897 / -.03% | -.005 / .6370 / .9897 / -.09% | -.005 / .6552 / .9897 / -.02% |
| `momentum_12_1` | -.002 / .8948 / .9897 / -.16% | +.003 / .7990 / .9897 / -.09% | +.006 / .5531 / .9897 / +.06% | +.007 / .5885 / .9897 / +.03% | +.005 / .7223 / .9897 / +.10% |
| `high_52w` | -.013 / .3038 / .8285 / -.27% | -.018 / .1436 / .5823 / -.47% | -.017 / .1479 / .5837 / -.69% | -.021 / .1037 / .4678 / -1.38% | -.024 / .1060 / .4678 / -1.89% |
| `trend_consistency_3m` | -.007 / .3524 / .8958 / -.11% | -.006 / .3898 / .9282 / -.11% | -.006 / .3785 / .9157 / -.13% | -.009 / .2715 / .7808 / -.28% | -.011 / .2241 / .7308 / -.48% |
| `vol_scaled_momentum_6_1` | +.001 / .9609 / .9915 / -.13% | +.002 / .8400 / .9897 / -.02% | -.003 / .7170 / .9897 / -.01% | -.007 / .5279 / .9897 / -.04% | -.007 / .5192 / .9897 / -.03% |
| `residual_momentum_6_1` | +.002 / .8815 / .9897 / -.11% | +.004 / .7286 / .9897 / +.01% | +.001 / .9227 / .9897 / +.05% | -.002 / .8570 / .9897 / +.08% | -.001 / .8917 / .9897 / +.23% |
| `low_total_vol_3m` | -.017 / .2144 / .7281 / -.30% | -.019 / .1422 / .5823 / -.54% | -.022 / .0734 / .4471 / -.94% | -.035 / .0149 / .2032 / -2.05% | -.041 / .0177 / .2046 / -2.93% |
| `low_beta_1y` | -.020 / .1756 / .6755 / -.29% | -.025 / .0829 / .4471 / -.52% | -.023 / .0803 / .4471 / -.88% | -.034 / .0340 / .3310 / -1.82% | -.040 / .0353 / .3310 / -2.62% |
| `low_idio_vol_1y` | -.017 / .1407 / .5823 / -.34% | -.020 / .0747 / .4471 / -.60% | -.021 / .0511 / .3792 / -1.01% | -.032 / .0123 / .1983 / -2.10% | -.038 / .0132 / .1983 / -3.09% |
| `max_effect_1m` | -.009 / .3616 / .9041 / -.26% | -.005 / .5897 / .9897 / -.40% | -.010 / .2597 / .7791 / -.69% | -.020 / .0453 / .3634 / -1.56% | -.024 / .0460 / .3634 / -2.18% |
| `low_dollar_volume_1m` | -.001 / .9327 / .9897 / +.09% | -.001 / .8618 / .9897 / +.13% | +.026 / <.0001 / .0005 / +.55% | +.043 / <.0001 / <.0001 / +1.22% | +.053 / <.0001 / <.0001 / +1.77% |
| `amihud_illiquidity_1m` | +.003 / .6976 / .9897 / +.15% | +.003 / .6337 / .9897 / +.27% | +.030 / <.0001 / .0003 / +.77% | +.050 / <.0001 / <.0001 / +1.71% | +.061 / <.0001 / <.0001 / +2.52% |

## Reading

The confirmed discovery relationship is sector-neutral Amihud illiquidity at
42 and 63 sessions. Its full-sample IC/spread is `+.050/+1.71%` at 42 sessions
and `+.061/+2.52%` at 63 sessions. Both remain positive in validation and the
recent holdout:

| Factor / horizon | Development IC / spread | Validation IC / spread | Holdout IC / spread | Reading |
| --- | --- | --- | --- | --- |
| Amihud 42d | +.061 / +2.02% | +.042 / +1.26% | +.012 / +1.07% | Confirmed, decaying |
| Amihud 63d | +.075 / +2.90% | +.051 / +1.89% | +.018 / +1.81% | Confirmed, decaying |
| Low dollar volume 42d | +.057 / +1.69% | +.036 / +.71% | -.008 / +.01% | Historical capacity proxy; IC did not survive |
| Low dollar volume 63d | +.070 / +2.44% | +.043 / +1.05% | -.004 / +.05% | Historical capacity proxy; IC did not survive |
| Reversal 10d | +.040 / +.53% | +.014 / +.24% | -.029 / -.49% | Full-sample relationship decayed and reversed |

The low-dollar-volume comparator was added after the first provisional Amihud
reading, so it is diagnosis rather than independent confirmation. It matters:
simple low volume loses its IC and nearly all spread in holdout while Amihud
remains positive. Recent price movement relative to available volume therefore
contains more information than low trading capacity alone in this sample.

Classic 3-1, 6-1, and 12-1 momentum, 52-week-high proximity, residual momentum,
and trend consistency show no useful IC here. Low volatility, low beta, and the
MAX signal lean in the opposite direction over longer horizons, but none
survives the frozen multiple-test family. They are not current candidates.

This result nominates one factor definition, not a strategy. The next practical
test is a sector-neutral long-only ranking using Amihud, with measured turnover,
the `$1m` liquidity floor, position-capacity limits, and explicit costs. No
production translation is authorized before that implementation test.
