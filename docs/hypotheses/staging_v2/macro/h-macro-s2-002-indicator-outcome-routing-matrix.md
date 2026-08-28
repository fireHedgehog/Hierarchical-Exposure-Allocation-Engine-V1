# H-MACRO-S2-002 - Predictive Relationship - Indicator-Outcome Routing Matrix

| Field | Value |
| --- | --- |
| Study ID | H-MACRO-S2-002 |
| Legacy ID | H-MACRO01 through H-MACRO07 supplied fragments of this matrix |
| Status | Completed; PIT-limited |
| Dataset | `real-macro-0f184797-d738-4ecd-a615-83b0020c5753` |
| Input | Every stored FRED input, combined only where three policy-rate series form one continuous target-rate history |
| Target | Future equity path, equity leadership, duration/inflation pricing, credit/USD, policy/liquidity, gold, and volatility outcomes |
| Production use | None |
| Does not claim | One best macro indicator, a calibrated risk probability, or an exposure policy |

## Question

Which future dimension, if any, does each macro-financial indicator inform out
of sample? VIX remains both a valid fast input and a volatility target, but it
cannot erase slower macro inputs by winning a single exposure-utility contest.

## Frozen experiment

One loop evaluates the full indicator-outcome matrix. Results remain routed by
outcome family; there is no global winner and no aggregate score in this study.

| Axis | Frozen values |
| --- | --- |
| Input lanes | Fundamental: activity, inflation, employment, fiscal; Policy/rates: policy rate, nominal and real yields, breakevens, administered rates; Transmission: NFCI, VIX, HY/IG spreads, USD; Liquidity: WALCL and Treasury General Account |
| Input views | `state`: economically meaningful level or YoY state; `impulse`: roughly three-month change in that state |
| View selection | Select state versus impulse on development data for each indicator-target cell; evaluate that frozen choice on the temporal test only |
| Anchors | Every 21 SPY trading days; last observation dated on or before the anchor |
| Validation | Development before 2022-01-01; temporal test from 2022-01-01; moving-block permutation sized to the forward horizon |
| Multiplicity | Benjamini-Hochberg within each target-horizon family, never across unrelated economic questions |
| Minimum evidence | Confirmatory: at least 36 development and 24 test anchors. A shorter route with at least 24 total anchors gets a clearly labeled two-thirds/one-third exploratory split, no `p/q`, and cannot be supported |
| Honest limitation | FRED history is current-vintage and keyed to observation date, not true historical release availability |

The three raw Fed target series are not treated as three economic indicators:
`DFEDTAR` supplies the pre-2008 target and the midpoint of `DFEDTARL` and
`DFEDTARU` supplies the later target range. All three stored series are thereby
used once without manufacturing duplicate votes.

## Target routes

| Family | Outcome | Horizons | Product meaning |
| --- | --- | --- | --- |
| Equity path | SPY forward return, maximum adverse excursion, realized volatility | 1M, 3M, 6M | Direction, damage, and turbulence are different outcomes |
| Equity leadership | QQQ-DIA, IWM-SPY, cyclical-defensive ETF return spread | 3M, 6M | Macro may rotate leadership without forecasting the market level |
| Duration and inflation | TLT return, 10Y nominal-yield change, 10Y breakeven change | 3M, 6M | Discount-rate and inflation-pricing transmission |
| Credit and USD | HY OAS change, broad-dollar change | 1M, 3M | Funding stress and international tightening; HY is recent-window only |
| Policy and liquidity | Fed target-rate change, WALCL percentage change, TGA normalized change | 3M, 6M | Central-bank and Treasury response rather than asset return |
| Diversifier | GLD return | 3M, 6M | Inflation/fiscal/stress expression outside US equity |
| Volatility | VIX level change | 1M, 3M | Fast risk transmission and mean reversion |

`cyclical-defensive` is the equal-weight return of XLY/XLI/XLF/XLB/XLE minus
the equal-weight return of XLP/XLU/XLV. XLC and XLRE are omitted from that long-
history route because their stored histories begin later.

## Interpretation contract

Each tested cell reports selected view, development/test rank IC, block `p`,
within-route `q`, sample window, sign stability, and whether the predictor is
the target's own series. Self-series persistence or mean reversion is useful,
but it is labeled separately from cross-series leading information.

The compact result has two tables:

1. one row per input: its strongest stable cross-series route, if any;
2. one row per target-horizon: its strongest stable inputs from distinct lanes.

A cell is `supported` only when the selected view has the same non-zero sign in
development and test, absolute test rank IC is at least `0.15`, and within-route
`q <= 0.10`. Otherwise it is `inconclusive`; unavailable coverage remains
`insufficient`. These labels organize evidence and do not authorize S3 or S4.

## Run 2026-08-29

[`macro_s2_indicator_outcome_matrix.py`](../../../../backend/research_lab/macro_s2_indicator_outcome_matrix.py)
ran 24 economic indicators built from all 26 stored FRED series against 35
target-horizon routes: 840 cells, 21-trading-day anchors, 1,000 block
permutations per eligible cell. The fixed split supplied 202 development and 55
test anchors at most. There were 55 supported cells, 638 inconclusive cells,
and 147 recent-window exploratory cells. The 55 are correlated routes and
horizons, not 55 independent discoveries.

### Input routing

| Input | Lane | Supported cells | Strongest supported cross-series route | View | Dev IC / test IC | q |
| --- | --- | ---: | --- | --- | ---: | ---: |
| INDPRO | Fundamental | 0 | None | — | — | — |
| CPIAUCSL | Fundamental | 1 | QQQ-DIA return spread 3M | Impulse | -0.166 / -0.441 | 0.073 |
| PPIACO | Fundamental | 1 | SPY adverse excursion 1M | State | -0.148 / -0.443 | 0.010 |
| PCEPILFE | Fundamental | 1 | SPY adverse excursion 1M | State | -0.131 / -0.310 | 0.045 |
| PAYEMS | Fundamental | 2 | Fed target change 6M | State | +0.430 / +0.811 | 0.052 |
| GDPC1 | Fundamental | 1 | SPY adverse excursion 1M | Impulse | +0.247 / +0.319 | 0.045 |
| MTSDS133FMS | Fundamental | 1 | 10Y breakeven change 3M | State | -0.246 / -0.478 | 0.042 |
| ICSA | Fundamental | 1 | Fed target change 3M | State | -0.301 / -0.529 | 0.037 |
| NFCI | Transmission | 1 | SPY realized volatility 1M | State | +0.484 / +0.251 | 0.100 |
| VIXCLS | Transmission | 3 | SPY realized volatility 1M | State | +0.666 / +0.681 | 0.005 |
| BAMLH0A0HYM2 | Transmission | 0 | Exploratory only: 2023+ history | — | — | — |
| BAMLC0A0CM | Transmission | 0 | Exploratory only: 2023+ history | — | — | — |
| DTWEXBGS | Transmission | 2 | Fed target change 3M | State | +0.139 / +0.470 | 0.074 |
| DGS10 | Policy/rates | 4 | TLT return 6M | State | +0.310 / +0.767 | 0.021 |
| DGS30 | Policy/rates | 6 | TLT return 6M | State | +0.323 / +0.667 | 0.084 |
| DFII10 | Policy/rates | 7 | 10Y nominal-yield change 6M | State | -0.270 / -0.744 | 0.010 |
| DFII30 | Policy/rates | 5 | TLT return 6M | State | +0.495 / +0.638 | 0.089 |
| T10YIE | Policy/rates | 4 | SPY adverse excursion 6M | State | -0.093 / -0.558 | 0.031 |
| T5YIE | Policy/rates | 5 | 10Y breakeven change 6M | State | -0.395 / -0.599 | 0.010 |
| SOFR | Policy/rates | 2 | Fed target change 3M | Impulse | +0.551 / +0.617 | 0.005 |
| IORB | Policy/rates | 0 | Exploratory only: 2021+ history | — | — | — |
| FED_TARGET | Policy/rates | 0 | None cross-series | — | — | — |
| WALCL | Liquidity | 2 | SPY realized volatility 1M | State | +0.292 / +0.484 | 0.005 |
| WTREGEN | Liquidity | 0 | None | — | — | — |

### Routed outcomes

Only routes with at least one supported cross-series input are expanded here.
The table shows at most one leader per input lane, preventing a cluster of
closely related yields from occupying every visible slot.

| Target route | Supported cross-series cells | Distinct-lane leaders, test IC (`q`) |
| --- | ---: | --- |
| SPY adverse excursion 1M | 8 | T5YIE -0.529 (0.010); PPIACO -0.443 (0.010); WALCL -0.344 (0.045) |
| SPY adverse excursion 3M | 2 | T5YIE -0.573 (0.021) |
| SPY adverse excursion 6M | 2 | T5YIE -0.562 (0.049) |
| SPY realized volatility 1M | 3 | VIXCLS +0.681 (0.005); WALCL +0.484 (0.005) |
| SPY realized volatility 3M | 2 | VIXCLS +0.543 (0.042) |
| QQQ-DIA return spread 3M | 1 | CPIAUCSL impulse -0.441 (0.073) |
| Cyclical-defensive spread 3M | 1 | T10YIE -0.503 (0.042) |
| TLT return 3M | 4 | DGS10 +0.667 (0.007) |
| TLT return 6M | 4 | DGS10 +0.767 (0.021) |
| 10Y nominal-yield change 3M | 3 | DFII10 -0.642 (0.021) |
| 10Y nominal-yield change 6M | 2 | DFII10 -0.744 (0.010) |
| 10Y breakeven change 3M | 3 | MTSDS133FMS -0.478 (0.042); T5YIE -0.476 (0.042) |
| 10Y breakeven change 6M | 1 | T5YIE -0.599 (0.010) |
| Fed target change 3M | 8 | PAYEMS +0.779 (0.005); SOFR impulse +0.617 (0.005); DTWEXBGS +0.470 (0.074) |
| Fed target change 6M | 1 | PAYEMS +0.811 (0.052) |
| GLD return 6M | 4 | DGS10 +0.692 (0.052) |

No cross-series input was supported for SPY return magnitude at 1M, 3M, or 6M;
SPY realized volatility at 6M; IWM-SPY at 3M/6M; HY OAS; broad USD; WALCL;
TGA share; 1M VIX change; or the remaining leadership, gold, and volatility
horizons. Null routes remain part of the result rather than omitted trials.

Self-series relationships were kept outside the cross-series leaders. DGS10 and
T10YIE showed stable mean reversion at 3M/6M; the Fed target's own impulse showed
3M persistence; VIX level showed 3M mean reversion. HY OAS showed similar recent-
window behavior, but only 21/11 and 20/10 exploratory development/test anchors.

## Conclusion

The useful abstraction is a routed macro map, not one return predictor and not
one direct exposure score. Macro fundamentals contributed mainly to damage,
leadership, inflation-pricing, and policy-response routes. Rates contributed to
duration, breakeven, gold, and drawdown routes. VIX remained the strongest fast
volatility input without becoming the whole macro model.

This result rejects direct return-magnitude forecasting as the organizing
question. It supports retaining multiple state dimensions for later S3 design,
but does not yet specify how to combine them, estimate a risk probability, or
set exposure. Current-vintage/release-date leakage and the single 2022-2026 test
regime remain the next scientific constraints.
