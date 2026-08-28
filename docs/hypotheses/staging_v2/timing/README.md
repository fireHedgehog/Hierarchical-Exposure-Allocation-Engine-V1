# Timing Research - Staging V2

Timing asks when to act on an already-selected candidate. Existing staging code
continues to run until a later translation is explicitly approved.

## Current study

| Study | Role | Status | Production use |
| --- | --- | --- | --- |
| H-TIME-S2-001 - Dislocation Repair Surface | S2 | Completed; no repair edge | None |

## Why this follows the macro audit

The Macro V2 audit found useful relationships with damage, volatility,
leadership, duration, inflation pricing, and policy response, but no stable
macro route to SPY return magnitude. That null is retained: policy paths likely
contain information, but the available history is not broad or point-in-time
enough to turn it into an honest single-instrument danger-timing signal.
Macro therefore remains environment and shock context here; an observable price
dislocation starts the timing clock.

This study tests a market repair prior, not a causal "Fed put." Identifying an
actual Fed put would require announcement-time target/path surprises or an
equivalent market-implied policy series, not the later realized policy-rate
level. Federal Reserve research likewise separates target, path, yield, dollar,
and risk-premium channels rather than treating policy as one scalar input; see
[Bernanke and Kuttner (2005)](https://www.nber.org/papers/w10402) and
[Hausman and Wongswan (2006)](https://www.federalreserve.gov/econres/ifdp/global-asset-prices-and-fomc-announcements.htm).

## H-TIME-S2-001 frozen design

### Question

After a visible price dislocation, does a partial repair occur before an equal
additional loss? Does the answer change with the type and severity of the break?

The old gap-fill paper honestly rejected "a gap almost always fills quickly,"
but its unconditional control usually began at or above the reference price,
while a gap event began below it. Its near-100% control fill rate therefore did
not answer whether an equally damaged non-gap state repairs more slowly. The
current stored SPY open series also produces implausibly few gap-down days. This
version uses close-only events and equal-distance barriers instead.

### Event and target grid

The signal is known at day `t` close. Every target begins at `t+1`; the trigger
day's recovery cannot be earned. One event per specification remains active
until its frozen reference is repaired or 63 trading days pass. A deeper move
inside that episode is not a new independent event.

| Axis | Frozen values |
| --- | --- |
| Primary instruments | SPY, QQQ, DIA, IWM; never pooled without date-clustered inference |
| Abrupt shock | 1-day return / prior 20-day daily volatility <= -1.5, -2.0, -2.5 |
| 100DMA break | First close below SMA100 by at least 0.0, 0.5, 1.0 prior-volatility units |
| Drawdown transition | First cross below -5%, -10%, -15% from the prior 63-day high |
| Horizons | 5, 10, 20, 63 trading days |
| Temporal panels | Development 2004-2014; validation 2015-2019; final test 2020-2026 |

For an event close `P` and frozen structural reference `R`, define a barrier
unit `B = max(R - P, P * prior 20-day daily volatility)`. The volatility floor
prevents an almost-zero first cross below SMA100 from manufacturing enormous
normalized path values.

- primary outcome: hit `P + 0.5B` before `P - 0.5B` within the horizon;
- strict outcome: hit `P + B` before `P - B`;
- path outcomes: terminal repair and maximum additional loss in units of `B`,
  plus the fraction of days still below the one-unit repair barrier.

This distinguishes a fast repair from a trade that eventually wins only after
an unacceptable additional drawdown.

### Matched baseline

Each event is paired, without replacement inside its instrument and temporal
panel, to a non-event day with:

1. the same above/below-SMA200 state;
2. the same fixed trailing-volatility bucket;
3. the same fixed drawdown-depth bucket;
4. no same-specification event within five trading days.

Among eligible controls, choose the closest pre-event volatility, drawdown, and
SMA200-slope state. Give the control the event's same percentage barrier
distance. This asks whether the abrupt transition adds repair information beyond
an already similar weak market state. An unmatched event stays visible in
coverage but cannot enter the paired effect estimate.

### Validation and result table

The grid is a surface, not a threshold-selection contest. Report every cell.
The primary statistic is the paired difference in partial-repair-before-failure
rate. Final-test `p` uses sign flips of event-date clusters, so SPY/QQQ/DIA/IWM
on the same market day are not four independent observations. Benjamini-
Hochberg correction applies within each event family across thresholds and
horizons.

Run 2026-08-29 with
[`timing_dislocation_repair_surface.py`](../../../../backend/research_lab/timing_dislocation_repair_surface.py)
on sealed dataset `real-macro-0f184797-d738-4ecd-a615-83b0020c5753`:
36 frozen cells, 5,000 event-date-cluster sign flips per cell.

| Family | Threshold | Matched / unmatched | Mean vol / drawdown match gap |
| --- | --- | ---: | ---: |
| Abrupt shock | z <= -1.5 | 654 / 4 | 1.0% / 0.6% |
| Abrupt shock | z <= -2.0 | 454 / 2 | 1.0% / 0.5% |
| Abrupt shock | z <= -2.5 | 289 / 1 | 1.0% / 0.4% |
| 100DMA break | 0.0 vol deep | 430 / 21 | 1.2% / 0.6% |
| 100DMA break | 0.5 vol deep | 336 / 16 | 1.3% / 0.6% |
| 100DMA break | 1.0 vol deep | 268 / 18 | 1.3% / 0.6% |
| Drawdown transition | 5% | 167 / 29 | 1.7% / 0.8% |
| Drawdown transition | 10% | 53 / 33 | 3.0% / 1.0% |
| Drawdown transition | 15% | 32 / 11 | 2.8% / 1.4% |

Every cell's primary result is compressed below. Each `D/V/T` entry is the
paired repair-rate delta in development/validation/final test; each following
entry is final-test `q` and verdict.

| Family | Threshold | 5D delta; q/verdict | 10D delta; q/verdict | 20D delta; q/verdict | 63D delta; q/verdict |
| --- | --- | --- | --- | --- | --- |
| Abrupt shock | z <= -1.5 | -15.3/-18.4/-7.9%; .243 inconclusive | -18.2/-16.5/-12.7%; .021 continuation | -18.6/-17.1/-14.3%; .013 continuation | -18.9/-17.1/-14.8%; .013 continuation |
| Abrupt shock | z <= -2.0 | -13.5/-15.8/-7.6%; .371 inconclusive | -18.5/-10.9/-15.3%; .031 continuation | -18.0/-11.9/-18.3%; .013 continuation | -18.5/-11.9/-18.3%; .013 continuation |
| Abrupt shock | z <= -2.5 | -11.3/-15.2/+4.9%; .625 inconclusive | -14.8/-10.6/-4.9%; .625 inconclusive | -14.8/-9.1/-4.9%; .625 inconclusive | -15.5/-9.1/-6.2%; .625 inconclusive |
| 100DMA break | 0.0 vol | -12.6/-11.9/-13.8%; .055 continuation | -12.0/-11.9/-13.8%; .055 continuation | -12.0/-11.9/-13.8%; .055 continuation | -12.0/-11.9/-13.8%; .055 continuation |
| 100DMA break | 0.5 vol | -19.9/-7.2/-3.9%; .669 inconclusive | -19.2/-8.4/-3.9%; .669 inconclusive | -19.2/-8.4/-3.9%; .669 inconclusive | -19.2/-8.4/-3.9%; .669 inconclusive |
| 100DMA break | 1.0 vol | -21.4/-16.9/-15.3%; .142 inconclusive | -20.6/-16.9/-16.7%; .112 inconclusive | -21.4/-15.4/-16.7%; .112 inconclusive | -21.4/-15.4/-16.7%; .112 inconclusive |
| Drawdown transition | 5% | +8.4/-26.1/-19.7%; .203 inconclusive | +7.2/-21.7/-31.1%; .022 continuation | -1.2/-4.3/-19.7%; .203 inconclusive | -3.6/-13.0/-13.1%; .341 inconclusive |
| Drawdown transition | 10% | +3.6/0.0/+4.5%; 1.000 insufficient | -7.1/0.0/0.0%; 1.000 insufficient | -28.6/0.0/-22.7%; .341 insufficient | -28.6/0.0/-27.3%; .228 insufficient |
| Drawdown transition | 15% | 0.0/0.0/0.0%; 1.000 insufficient | 0.0/0.0/-13.3%; .674 insufficient | -7.7/+25.0/-26.7%; .341 insufficient | +7.7/-25.0/-26.7%; .341 insufficient |

`stable repair` requires positive repair-rate deltas in validation and test,
test `q <= 0.10`, and positive final-test direction in at least three of four
broad indexes. A stable negative result is `continuation risk`; everything else
is `inconclusive`. This is an S2 relationship label, not an entry rule.

Implementation audit before the accepted run: the first script pass used raw
`R - P` as the normalization unit. A shallow SMA100 cross can make that value
arbitrarily close to zero and produced economically meaningless path ratios.
No result from that pass was accepted; the one-prior-volatility floor above was
added before the recorded run while leaving the event grid unchanged.

### Path and concentration audit

The accepted run produced zero `stable repair`, 11 `continuation risk`, 17
`inconclusive`, and eight `insufficient` cells. Absolute event repair rates were
often high, but matched controls repaired more often. This is the distinction
between a general US-equity recovery prior and an incremental timing edge.

| Representative final-test cell | Event / control partial repair | Strict-rate delta | Terminal delta | Additional-loss delta |
| --- | ---: | ---: | ---: | ---: |
| z <= -1.5, 10D | 59.3% / 72.0% | -8.5% | -0.38B | -0.46B |
| z <= -1.5, 63D | 60.3% / 75.1% | -13.8% | +0.41B | -0.42B |
| First 100DMA break, 5D | 56.2% / 70.0% | -20.0% | -1.10B | -0.77B |
| 5% drawdown transition, 10D | 27.9% / 59.0% | -9.8% | -0.31B | -0.20B |
| z <= -2.5, 5D | 60.5% / 55.6% | +7.4% | -0.21B | -0.18B |

The z <= -1.5 10-day result held separately in SPY (-10.6 percentage
points), QQQ (-3.9), DIA (-27.7), and IWM (-9.1). The shallow 100DMA-break
5-day result was also negative in all four (-13.0, -30.8, -6.1, -10.4).
The 5% drawdown-transition 10-day result was negative in all four (-26.7,
-47.1, -62.5, -9.5). Final-test observations were distributed through every
year from 2020 to 2026; none of these representative results is a single-2020
episode artifact.

The 63-day z <= -1.5 terminal delta eventually turned positive while its
repair probability and additional-loss path stayed worse. That is an honest
version of "eventually a golden dip": eventual recovery did not make the break
a good immediate timing signal. The rare 10%/15% drawdowns had too few
validation episodes and remain insufficient regardless of large-looking cells.

### Conclusion

This experiment finds no excess immediate-repair edge after a close-based
dislocation. Common abrupt shocks and a first shallow 100DMA break instead
identified a worse near-term path than an already similar weak-state control.
This does not advise shorting, disprove eventual recovery, or revoke the old
small average-reversal result; it rejects "the break itself is an extra reason
to buy immediately" as a broad-index timing claim.

No live timing bar or policy changes. A separately preregistered next study may
ask whether waiting for observable price confirmation avoids this continuation
phase. Cross-asset context should not be added merely to rescue the rejected
immediate-entry thesis.

## Later context pass, not part of the first result

If a repair relationship survives, a frozen second pass may test event-close
TLT/DGS10, broad-dollar, QQQ-DIA, and VIX states as continuous context. Only then
may the data suggest labels such as discount-rate shock, growth/liquidity shock,
or equity-local dislocation. Those labels must not be invented first and fitted
backward.

Immediate entry versus waiting for observable confirmation (for example, a
higher close or a short moving-average recapture) is a later S4 policy question.
Costs and executable next-session pricing remain S5. Neither is smuggled into
this relationship test.

## Manual gates

1. H-TIME-S2-001 is complete and changes no live timing code.
2. Preserve its nulls, unmatched events, and crisis concentration.
3. Preregister confirmation timing separately; do not tune this grid again.
4. Keep gap/open research paused until the stored OHLC behavior is explained.
