# H-XSEC-S5-002 - Liquid Tail Implementation Check

| Field | Value |
| --- | --- |
| Study ID | H-XSEC-S5-002 |
| Status | Completed; 3M and two reversal translations pass the frozen rough gate; no production authority |
| Type | Trading implementation |
| Category | Cross-sectional |
| Parent evidence | [H-XSEC-S2-004](h-xsec-s2-004-liquid-leadership-and-reversal.md) |
| Dataset | Stage 2 dual-basis adjusted-OHLC/volume library |
| Production authority | None |

## Question

Do the four liquid-stock tail relationships retained by H-XSEC-S2-004 survive
one coherent, next-open long-only implementation after measured portfolio
turnover and explicit assumed costs?

This is not another factor search. It freezes the four accepted S2 rows and
changes only the portfolio translation. No result can add a fifth signal,
change a lookback, or modify the running application ranking.

## Frozen implementation

| Item | Rule |
| --- | --- |
| Calendar | Exact SPY trading-session spine |
| Formation | Last SPY session of each calendar week |
| Signal knowledge | Adjusted closes through formation close only |
| First fill | Following shared session's adjusted open |
| Investable pool | Dynamic Top-100 by trailing 21-session median raw-dollar volume; raw close at least $5 |
| Selection | Highest-score decile, equal weight inside each sleeve |
| Winner signals | `momentum_1m`, `momentum_3m` |
| Reversal signals | `reversal_5d`, `sector_relative_reversal_5d` |
| Winner holding translation | Equal average of the latest 13 weekly sleeves, approximating the parent 63-session horizon without liquidating the whole position weekly |
| Reversal holding translation | Current weekly sleeve only, matching the parent five-session horizon |
| Return clock | Non-overlapping adjusted-open-to-adjusted-open weekly portfolio returns |
| Matched benchmark | Same-date dynamic Top-100 equal-weight gross portfolio, reformed weekly at the same adjusted open; candidate costs are not credited to the benchmark |
| Market reference | Not computed: the anchor SPY series has no adjusted open; raw open or close-to-close is not substituted into an open-to-open implementation |
| Missing data | Null; a period is omitted if a held name lacks either exact shared-session open |

The winner construction is deliberately a 13-sleeve portfolio. Treating a
63-session signal as if every position were sold and repurchased each week
would manufacture turnover that the intended holding period does not require.
The reversal construction has no such protection: its one-week horizon makes
its observed membership churn an actual implementation burden.

## Costs, capacity, and folds

- Measure one-way target-weight turnover as
  `0.5 * sum(abs(current_weight - prior_weight))`; first entry is 100%.
- Apply `0/5/10/25/50 bps` per unit of measured one-way turnover. These are
  declared scenarios, not historical bid/ask or impact estimates.
- Report the one-way cost in bps that reduces annualized return to the matched
  Top-100 benchmark. This break-even is descriptive, not a spread estimate.
- Report the most restrictive account size at 1% of each holding's trailing
  median dollar volume; no arbitrary account-size pass line is imposed.
- Report Development (through 2018), Validation (2019 through 2023-H1), Recent
  (2023-H2 onward), and Full. A weekly period must start and end inside its fold.

## Frozen gate

A row passes this rough S5 gate only when:

1. gross annualized excess over the matched Top-100 benchmark is positive in
   Development, Validation, and Recent; and
2. Full and Recent excess remain positive at the common 10 bps one-way cost
   scenario.

The 25/50 bps rows are stress readings, not alternate gates. A pass keeps a
candidate alive for manual translation; it does not register a factor. A fail
retires only that implementation, not the observed S2 relationship.

## Run record

The read-only script `backend/research_lab/liquid_tail_implementation.py` ran
against 775/775 accepted receipts, 5,469 SPY sessions, and the parent's 1,056
weekly formations. A calculation-unchanged verification run returned the same
portfolio table. Exact-open availability left 963 usable 1M weeks, 985 usable
3M weeks, and 1,021 usable reversal weeks; missing periods were omitted rather
than filled. The anchor SPY series has no adjusted open, so the declared market
reference was not computed.

## Result

Annualized excess below is candidate CAGR minus the gross matched Top-100 CAGR.

| Signal | Dev gross | Validation gross | Recent gross | Full gross | Full / recent net at 10 bp | Weekly turnover | Break-even one-way cost | Gate |
| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | --- |
| `momentum_1m` | -0.13% | +3.74% | +9.37% | +1.70% | +1.31% / +8.92% | 7.3% | 43.8 bp | **Fail** |
| `momentum_3m` | +0.40% | +4.70% | +7.96% | +2.10% | +1.70% / +7.53% | 7.2% | 52.7 bp | **Pass** |
| `reversal_5d` | +6.83% | +10.75% | +6.71% | +8.01% | +2.98% / +1.26% | 85.6% | 16.1 bp | **Pass** |
| `sector_relative_reversal_5d` | +8.89% | +12.25% | +6.73% | +9.58% | +4.43% / +1.27% | 86.6% | 19.0 bp | **Pass** |

The common cost surface prevents the gate from hiding implementation fragility:

| Signal | Fold | 0 bp | 5 bp | 10 bp | 25 bp | 50 bp |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `momentum_1m` | Full | +1.70% | +1.51% | +1.31% | +0.73% | -0.24% |
| `momentum_1m` | Recent | +9.37% | +9.14% | +8.92% | +8.25% | +7.14% |
| `momentum_3m` | Full | +2.10% | +1.90% | +1.70% | +1.10% | +0.11% |
| `momentum_3m` | Recent | +7.96% | +7.75% | +7.53% | +6.88% | +5.81% |
| `reversal_5d` | Full | +8.01% | +5.47% | +2.98% | -4.17% | -15.12% |
| `reversal_5d` | Recent | +6.71% | +3.96% | +1.26% | -6.50% | -18.38% |
| `sector_relative_reversal_5d` | Full | +9.58% | +6.98% | +4.43% | -2.89% | -14.09% |
| `sector_relative_reversal_5d` | Recent | +6.73% | +3.97% | +1.27% | -6.50% | -18.39% |

At 10 bp, the full-sample 3M portfolio returned 12.56% annualized versus
10.86% for its matched Top-100, with 0.59 Sharpe and -60.87% maximum drawdown
versus -56.96% for the benchmark. Its 1%-ADV capacity p10/median was
$26.3m/$44.6m. It is the cleanest implementation candidate, but the drawdown
does not improve on the liquid universe.

Both reversal translations pass the deliberately permissive 10 bp gate but
fail at 25 bp, and their maximum drawdowns worsen to -66.67% and -73.05%
versus -55.20% for the matched Top-100. Their recent net excess is only about
1.3% at 10 bp. They remain friction-sensitive research candidates, not robust
implementation candidates. Real spread/impact data is the next evidentiary
requirement; another assumed-cost grid would add no useful information.

The 1M relationship remains descriptive but this translation is rejected by
its negative Development result.

## Manual product translation

Manual audit accepted a deliberately narrow research-UI translation, not a
strategy registration. The read-only Cross-sectional ranking page now defaults
to the current dynamic liquid Top-100 and shows the 3M top-decile state, its
13-week sleeve persistence, and the natural average sleeve weight. The earlier
technical composite remains available and is labelled technical context rather
than validated alpha. Raw and sector-relative five-session losers appear only
in a separate execution-fragile rebound watch with no candidate weight. The
page recomputes from stored bars and exact shared SPY dates; refreshing it never
fetches a provider or writes a ranking table.

This translation preserves a useful product surface while keeping the evidence
boundary explicit. It does not register a factor, authorize an allocation, or
promote either reversal candidate.
