# H-XSEC-S2-004 - Liquid Leadership and Reversal

| Field | Value |
| --- | --- |
| Study ID | H-XSEC-S2-004 |
| Status | Completed; four diagnostic candidates; no production authority |
| Type | Predictive relationship |
| Category | Cross-sectional |
| Dataset | Stage 2 dual-basis adjusted-OHLC/volume library |
| Primary universe | Dynamic top 100 by trailing 21-session median dollar volume |
| Production authority | None |

## Question

> Among the most liquid current-vintage US equities, do established winners
> continue to lead, and do the largest one-week losers separately rebound?

These are two tail relationships, not one monotone factor. Winner continuation
and loser reversal can coexist as a U-shaped return curve; one full-universe
Rank IC can cancel them and incorrectly read as “nothing.”

The momentum anchor is the classic prior-2-to-12-month construction used in
[Kenneth French's public factor definition](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/det_mom_factor.html)
and the winner-continuation evidence of
[Jegadeesh and Titman (1993)](https://onlinelibrary.wiley.com/doi/10.1111/j.1540-6261.1993.tb04702.x).
The separate weekly-loser loop follows the short-horizon reversal question in
[Lehmann (1990)](https://www.nber.org/papers/w2533) and French's separate
[short-term reversal definition](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/det_st_rev_factor.html).
Industry leadership is preserved in the primary rank because it can be part of
momentum rather than noise
([Moskowitz and Grinblatt, 1999](https://onlinelibrary.wiley.com/doi/10.1111/0022-1082.00146)).

## Non-negotiable time contract

| Item | Frozen rule |
| --- | --- |
| Calendar | Exact SPY trading-session spine; no per-symbol positional index |
| Formation | Last SPY session of each calendar week |
| Signal knowledge | Adjusted close through formation close `t` only |
| Entry | Each security's adjusted open on shared session `t+1` |
| Exit | Adjusted close on the same shared `t+h` date |
| Missing data | Null; never forward-filled and never replaced by that symbol's “latest” bar |
| Eligibility | Real bars at every signal endpoint, entry, and exit; at least 252 prior sessions |

The Stage 1 strategy backtest, volatility-scaled backtest, and cost-robustness
backtest used the same row number across independently starting price arrays.
Their strategy-level return and cost figures are invalidated by that calendar
bug and cannot serve as priors here. H-XSEC-S2-002's SPY-spine implementation
was aligned correctly, but its broad monotone IC was not this tail estimand.

## Frozen pools

At each formation, `ADV21` is the median of `raw close * volume` over the prior
21 sessions. Raw close must be at least $5.

| Pool | Definition | Authority |
| --- | --- | --- |
| Primary | Dynamic `ADV21` ranks 1-100 | The only candidate-producing pool |
| Breadth | Dynamic ranks 1-200 | Sensitivity only |
| Control | Dynamic ranks 201+ | Small/lower-liquidity control only; never investable evidence |
| Familiar-name sanity | Fixed MAG7 and dynamic two most-liquid names per sector | Code/intuition check only |

`Top 100` is a most-liquid large-stock proxy, not a historical market-cap
classification: the database has no point-in-time market cap. Current-vintage
survivorship remains a known limitation, not a reason to mix small stocks into
the primary result.

## Loop M - classic liquid-stock momentum

Six frozen rows, with no fitted weights:

| Signal | Definition at `t` |
| --- | --- |
| `momentum_1m` | `C[t] / C[t-21] - 1` |
| `momentum_3m` | `C[t] / C[t-63] - 1` |
| `momentum_6m` | `C[t] / C[t-126] - 1` |
| `momentum_12m` | `C[t] / C[t-252] - 1` |
| `classic_12_1` | `C[t-21] / C[t-252] - 1` |
| `multi_1_3_6_12` | Equal-weight mean of the four same-date percentile ranks |

The primary response is the top decile's equal-weight return minus the entire
Top-100 pool return over 63 sessions. The 5/21/126-session columns measure the
path and decay; they are not alternative choices. Top-minus-bottom is not a
primary metric because the loser tail may contain a different reversal effect.

## Loop R - liquid-stock one-week reversal

| Signal | Definition at `t` |
| --- | --- |
| `reversal_5d` | `-(C[t] / C[t-5] - 1)` |
| `sector_relative_reversal_5d` | Negative stock 5-day return minus its same-date sector-peer mean |

The primary response is the highest-score decile minus the Top-100 pool over
five sessions. The 10/21-session columns measure decay only. Sector-peer
returns use the same stocks, adjusted basis, entry, and exit dates; this avoids
mixing the library's dual-basis stock data with the older anchor dataset's
non-dual-basis ETF opens.

## Statistics and decision rule

Every observation is first reduced to one same-date cross-sectional result.
Report effect size before inference:

| Output | Reading |
| --- | --- |
| Tail excess | Long-only relationship that the product could eventually consume |
| Same-date Spearman IC | Monotonicity diagnostic, not the sole gate |
| Decile curve | Detects U-shapes and tail asymmetry |
| Sector-peer excess | Separates individual selection from sector leadership |
| Hit rate / membership turnover | Stability and implementation burden |
| Quarterly block interval | Preserves the weekly/overlapping-path dependence approximately |

The eight primary cells are six momentum signals at 63 sessions and two
reversal signals at five sessions. Their post-2019 one-sided quarter-block
p-values receive one Benjamini-Hochberg correction. A row is only a research
candidate when its Top-100 tail excess is positive in Development (through
2018), Validation (2019 through 2023-H1), and the already-seen recent historical
holdout (2023-H2 onward), and its post-2019 `q < .10`. The holdout is not
pristine because earlier work inspected these dates. Top-200, control, MAG7,
and sector sanity panels cannot rescue a failed primary row.

## Run audit

`backend/research_lab/liquid_leadership_and_reversal.py` ran after the design
above was frozen and an unchanged-calculation verification run returned the
same table. It read all 775 accepted receipts on 5,469 exact SPY
sessions from 2004-12-01 through 2026-08-27 ET and produced 1,056 weekly
formations. Mean/min/max eligible names were 556/388/740; the lower-liquidity
control averaged 356 names. All entries were next-session adjusted opens.

## Primary result table

The interval is the post-2019 two-sided 95% quarter-block interval; `p` is the
frozen one-sided positive-tail test and `q` corrects the eight rows together.

| Family | Signal | H | N | Full excess [post-2019 CI] | Dev | Validation | Recent | p / q | IC | Hit | Turnover | Verdict |
| --- | --- | ---: | ---: | --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | --- |
| M | `momentum_1m` | 63 | 1,056 | +0.64% [-0.22%, +3.64%] | +0.15% | +0.68% | +3.30% | .0480 / .0640 | -.011 | 51.0% | 46.6% | Diagnostic candidate |
| M | `momentum_3m` | 63 | 1,056 | +1.04% [-0.59%, +5.87%] | +0.33% | +0.99% | +4.68% | .0830 / .0830 | -.015 | 51.9% | 28.7% | Diagnostic candidate |
| M | `momentum_6m` | 63 | 1,056 | +1.48% [+1.70%, +8.13%] | -0.28% | +2.92% | +7.76% | .0045 / .0120 | -.009 | 54.4% | 22.1% | Fails Development sign |
| M | `momentum_12m` | 63 | 1,056 | +1.92% [+1.73%, +10.15%] | -0.10% | +1.97% | +11.68% | .0065 / .0130 | -.001 | 54.4% | 16.4% | Fails Development sign |
| M | `classic_12_1` | 63 | 1,056 | +2.01% [+1.78%, +9.98%] | -0.09% | +2.09% | +11.75% | .0040 / .0120 | +.001 | 52.5% | 16.9% | Fails Development sign |
| M | `multi_1_3_6_12` | 63 | 1,056 | +0.74% [-0.47%, +5.45%] | -0.10% | +0.86% | +4.94% | .0600 / .0685 | -.012 | 54.6% | 32.6% | Fails Development sign |
| R | `reversal_5d` | 5 | 1,056 | +0.14% [+0.02%, +0.52%] | +0.07% | +0.30% | +0.20% | .0245 / .0392 | +.019 | 51.8% | 85.3% | Diagnostic candidate |
| R | `sector_relative_reversal_5d` | 5 | 1,056 | +0.18% [+0.07%, +0.46%] | +0.13% | +0.30% | +0.21% | .0020 / .0120 | +.017 | 52.5% | 86.4% | Diagnostic candidate |

## Path and pool robustness

| Signal | 5d | 10d | 21d | 63d | 126d |
| --- | ---: | ---: | ---: | ---: | ---: |
| `momentum_1m` | -0.10% | n/a | -0.08% | +0.64% | +1.41% |
| `momentum_3m` | -0.08% | n/a | +0.33% | +1.04% | +2.47% |
| `momentum_6m` | -0.00% | n/a | +0.39% | +1.48% | +3.62% |
| `momentum_12m` | +0.07% | n/a | +0.64% | +1.92% | +4.21% |
| `classic_12_1` | +0.09% | n/a | +0.71% | +2.01% | +4.50% |
| `multi_1_3_6_12` | -0.10% | n/a | +0.11% | +0.74% | +2.07% |
| `reversal_5d` | +0.14% | +0.20% | +0.43% | n/a | n/a |
| `sector_relative_reversal_5d` | +0.18% | +0.25% | +0.46% | n/a | n/a |

| Signal | Top 100 | Top 200 | Rank 201+ control | Top-100 sector-peer excess |
| --- | ---: | ---: | ---: | ---: |
| `momentum_1m` | +0.64% | +0.43% | +0.25% | +1.16% |
| `momentum_3m` | +1.04% | +1.17% | +0.54% | +1.45% |
| `momentum_6m` | +1.48% | +1.54% | +0.55% | +1.94% |
| `momentum_12m` | +1.92% | +1.51% | +0.50% | +2.51% |
| `classic_12_1` | +2.01% | +1.52% | +0.48% | +2.43% |
| `multi_1_3_6_12` | +0.74% | +0.88% | +0.35% | +1.18% |
| `reversal_5d` | +0.14% | +0.15% | +0.10% | +0.12% |
| `sector_relative_reversal_5d` | +0.18% | +0.15% | +0.14% | +0.17% |

## Why the old IC looked empty

The primary-horizon Top-100 decile curves are not monotone. The middle ranks
are generally weak while both tails can be positive. Selected examples:

| Signal | D1 | D2 | D3 | D4 | D5 | D6 | D7 | D8 | D9 | D10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `momentum_3m` | +0.56% | +0.41% | +0.08% | -0.13% | -0.46% | -0.53% | -0.66% | -0.23% | -0.09% | +1.04% |
| `classic_12_1` | +0.26% | +0.20% | -0.06% | -0.38% | -0.31% | -0.43% | -0.36% | -0.51% | -0.41% | +2.01% |
| `reversal_5d` | -0.10% | -0.13% | -0.07% | -0.00% | -0.06% | +0.04% | +0.00% | +0.06% | +0.11% | +0.14% |
| `sector_relative_reversal_5d` | -0.05% | -0.12% | -0.04% | -0.06% | +0.01% | -0.00% | +0.03% | +0.01% | +0.06% | +0.18% |

This is the central result. Near-zero or negative mean Rank IC is compatible
with a useful winner tail when the loser tail also rebounds. The Top-100
effects are larger than the rank-201+ controls, so small/lower-liquidity names
do not create the result. The familiar-name sanity panel also saw the intended
direction (`classic_12_1`: MAG7 +1.92%, dynamic sector leaders +0.80%), but it
has no decision authority.

The 1M/3M winner rows are candidates for a later S5 implementation check, not
proof of “classic momentum” in general. Classic 12-1, 6M, and 12M strengthen
dramatically in the recent historical period but fail the frozen early-period
sign gate; selecting them because the recent numbers are exciting would be a
regime-specific post-hoc decision. The two reversal rows are small but stable;
their 85-86% weekly membership turnover is an immediate implementation warning.

## Translation boundary

This run can identify a relationship candidate. It cannot register a factor,
claim a tradable strategy, estimate real costs, or change the running ranking.
Any accepted row still needs a separately reviewed S5 implementation using
real turnover, spread/impact assumptions, and an untouched forward period.

## Implementation follow-up

[H-XSEC-S5-002](h-xsec-s5-002-liquid-tail-implementation.md) completed the
single frozen translation loop. The 3M winner passed its rough overlapping-
sleeve gate; 1M failed Development. Both reversal rows passed at an assumed
10 bp one-way cost but failed at 25 bp and materially worsened drawdown. None
was registered or wired into the application.
