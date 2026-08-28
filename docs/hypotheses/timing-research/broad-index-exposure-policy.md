# Broad-index price-based exposure policy (H-TIME02)

Status: concluded-confirmed. Real, consistent Sharpe and max-drawdown improvement over static buy-and-hold, stable across all 4 MA lengths, holding both in-sample and out-of-sample, for both SPY and QQQ. Directly ruled out the "just lower average exposure" artifact (see Observation log).
Version: v0.2
Registered: 2026-08-28
Concluded: 2026-08-28

A deliberate reframe from every price-trend test run so far this
session (H-SECT01/H-SECT02's trend-conditioned addenda, both rejected
under continuous IC). This paper argues, and tests directly, that the
real value of a slow trend/volatility exposure filter is not a point
forecast — it can show ~zero IC on any given period and still be real,
via an asymmetric payoff: many small, costly whipsaws, offset by
avoiding a small number of large, real drawdowns. That's a portfolio-
*path* question (CAGR given up vs. drawdown/time-underwater avoided),
not a signal-significance question — a different statistical object,
requiring a different kind of test than anything run so far.

## Universe

`SPY`, `QQQ` — the two cleanest broad-beta instruments (no survivorship
issue, longest real history, lowest real friction), tested separately.
Deliberately not sector ETFs or themes — this tests whether a filter
helps *hold broad market beta*, not sector selection (already
concluded, parked).

## Thesis

A real, slow, disclosed exposure policy — combining trend state (price
vs. a long moving average) and volatility state (trailing realized vol
vs. its own trailing history) — reduces real max drawdown and time-
underwater by more than it costs in real CAGR, relative to static
buy-and-hold, and this holds up across nearby parameter choices (not
one lucky number) and out-of-sample.

Falsified by: the CAGR given up exceeds the real drawdown/underwater
benefit at any reasonable weighting of the two, or the result depends
on one specific, non-robust parameter choice, or it doesn't replicate
out-of-sample.

## Method

**Policy** (real, disclosed, hand-picked — not fit):

| Trend (price vs. N-day MA) | Vol (trailing 21d realized, vs. own trailing-252d percentile) | Exposure |
| --- | --- | --- |
| Above | Not elevated (<75th pct) | 1.0 |
| Above | Elevated (≥75th pct) | 0.7 |
| Below | Not elevated | 0.5 |
| Below | Elevated | 0.3 |

`N` tested at 150, 180, 200, 220 days — a real parameter-stability
check, not a search for the best one. Daily rebalance (a real exposure
*policy* needs daily evaluation, unlike this project's monthly-strided
IC tests — no p-value is being computed here, so the overlapping-
sample concern that motivates striding elsewhere doesn't apply).

**Evaluation** — real, full-path statistics, not IC: CAGR, annualized
vol, Sharpe, max drawdown, time underwater (longest real stretch below
the prior high-water mark), real turnover, real whipsaw count (number
of exposure-level transitions), and real performance specifically
during three disclosed historical windows — 2007-10 to 2009-03 (2008
crisis), 2020-02 to 2020-04 (COVID crash), 2022-01 to 2022-10 (hiking
bear). Compared against static buy-and-hold. Same 2019-01-01
chronological split this project already uses, reported honestly per
the methodology-limitations note (a later temporal subsample, not a
blind holdout).

## What would count as a real checkpoint

One real run of `research_lab/broad_index_exposure_policy_backtest.py`.

## Promotion criteria

A confirmed result — real drawdown/underwater improvement exceeding
the CAGR cost, stable across the 4 MA lengths, holding OOS — would be
a genuine candidate for a new `strategies` row (a real exposure overlay
on top of, or in place of, the current macro-only gross-exposure
scaling). Not promoted from this paper alone even if confirmed —
same bar every paper in this project carries.

## Observation log

| Date | Checkpoint | Reading |
| --- | --- | --- |
| 2026-08-28 | Real run, `research_lab/broad_index_exposure_policy_backtest.py`, full sealed dataset (SPY/QQQ, 2004-2026, 5,469 real daily bars each). Full-sample, in-sample (pre-2019), out-of-sample (2019+), and 3 real crisis windows, at each of MA∈{150,180,200,220}. | **Confirmed — real, consistent improvement on both Sharpe and max drawdown, never reversing across 4 MA lengths x 2 symbols x 3 windows.** See tables below. |

**Full-sample summary (state-dependent policy vs. static buy-and-hold), all 4 MA lengths:**

| Symbol | MA | Policy Sharpe | B&H Sharpe | Policy maxDD | B&H maxDD | Policy CAGR | B&H CAGR |
| --- | --- | --- | --- | --- | --- | --- | --- |
| SPY | 150 | 0.83 | 0.65 | -34.8% | -55.2% | +9.78% | +11.23% |
| SPY | 180 | 0.82 | 0.65 | -32.9% | -55.2% | +9.56% | +11.20% |
| SPY | 200 | 0.84 | 0.65 | -33.0% | -55.2% | +9.95% | +11.17% |
| SPY | 220 | 0.85 | 0.66 | -31.7% | -55.2% | +10.03% | +11.42% |
| QQQ | 150 | 1.01 | 0.79 | -32.6% | -53.4% | +15.08% | +15.98% |
| QQQ | 180 | 0.99 | 0.78 | -31.2% | -53.4% | +14.84% | +15.82% |
| QQQ | 200 | 0.96 | 0.78 | -32.1% | -53.4% | +14.30% | +15.80% |
| QQQ | 220 | 0.98 | 0.79 | -31.7% | -53.4% | +14.65% | +16.06% |

Sharpe improves in all 8 rows (never reverses). Max drawdown improves
by 18-22 percentage points in every row. CAGR cost is real but modest
— 1.0-1.7 points (SPY), 0.9-1.5 points (QQQ). In-sample and OOS splits
(not tabulated here, see script output) show the same pattern: OOS
Sharpe 1.09-1.26 (policy) vs. 0.94-0.99 (B&H) for both symbols; OOS
max drawdown roughly halved (~18-20% vs. 33-35%) at every MA length.

**The H-SECT04 trap, checked directly, not assumed:** a constant
multiplier at the same mean exposure (~0.83x) mechanically cannot
change Sharpe — it scales return and vol together. Measured directly:
static 0.83x exposure reproduces B&H's exact Sharpe (0.65 SPY, 0.78-0.79
QQQ, matching to 2 decimals at every MA length) while its max drawdown
sits *between* B&H and the real policy (-48% SPY, -46.5% QQQ — better
than unhedged B&H simply from being smaller, but far worse than the
state-dependent policy's -32%). This is decisive: the improvement is
real state-dependent timing value, not an artifact of being less
invested on average.

**Crisis windows (MA=200, the mid-parameter choice):**

| Window | Symbol | Policy cumulative | B&H cumulative | Policy maxDD | B&H maxDD |
| --- | --- | --- | --- | --- | --- |
| 2008 crisis | SPY | -24.8% | -46.0% | -32.5% | -55.2% |
| 2008 crisis | QQQ | -21.8% | -40.7% | -32.1% | -53.4% |
| 2020 COVID crash | SPY | -6.3% | -9.2% | -18.0% | -33.7% |
| 2020 COVID crash | QQQ | -0.8% | +0.1% | -18.3% | -28.6% |
| 2022 hiking bear | SPY | -11.1% | -17.7% | -14.5% | -24.5% |
| 2022 hiking bear | QQQ | -15.5% | -29.8% | -19.0% | -34.8% |

5 of 6 crisis-window returns favor the policy; the one exception
(QQQ, COVID) is a real, honest asymmetry worth naming rather than
glossing over: a V-shaped, unusually fast recovery penalizes any
defensive policy that's still de-risked when the rebound starts, so
return comes out roughly flat (-0.8% vs. +0.1%) even though drawdown
is still real and large (-28.6% pt improvement). Max drawdown improves
in all 6/6 — the more decision-relevant number for a holdability-focused
exposure policy, and the one this paper's thesis is actually about.

**Disclosed limitation:** only 3 real crisis episodes exist in this
22-year window (n=6 symbol-crisis pairs) — directionally consistent
but a small real sample, same caveat this project already applies to
rare-event work (`vix-percentile-vxx-entry.md`'s compression episodes).
No formal significance test was run on the Sharpe/drawdown gaps
themselves (same disclosed limitation H-MACRO10 carries) — the case
rests on directional consistency across 4 MA lengths x 2 symbols x 3
sample windows, plus the direct, decisive ruling-out of the average-
exposure artifact.

**Not promoted to a strategy from this paper alone** — same bar every
paper in this project carries (see Promotion criteria).

**Composition with H-MACRO10, real checkpoint, corrects an earlier call:**
multiplicative combination with the live macro-based multiplier
(`envelope_v2.py`) was initially reasoned to be the right default
(independent state variables, either should be able to dampen exposure
on its own) — tested directly, and the reasoning didn't hold.
`research_lab/combined_exposure_policy_backtest.py`, same real 12-sleeve
book and harness H-MACRO10 was itself backtested against: neither
multiplicative nor `min()` combination beats the standalone price-only
policy on Sharpe, in any of full-sample/in-sample/OOS. Macro stress and
SPY-downtrend states overlap enough (both flag 2008 and 2022) that
combining compounds the exposure cut without a proportional risk-
adjusted benefit — real max drawdown improves further (multiply:
-18.5% vs. price-only's -24.5% full sample) but costs more CAGR than
that buys back in Sharpe terms. **Price-only, standalone, has the best
or near-best Sharpe of all five options tested in every window**, and
already beats the current production macro-only formula on both Sharpe
(0.98 vs. 0.88 full sample) and drawdown (-24.5% vs. -34.8%) outright.

This reopens the real question as "should H-TIME02 replace or run
alongside naive-v2, not how to combine them" — a product decision, not
a methodology one. Put to the user directly 2026-08-28: **hold off —
not enough evidence to touch production yet.** One 12-sleeve-book
backtest, with the price filter applied uniformly off SPY's own state
(not tested per-sleeve), is not treated as sufficient grounds to
replace or reweight the live naive-v2 formula. No production change
made. Real next step, if picked up: a per-sleeve (rather than SPY-only)
price-state test, and/or a more formal promotion review, before
touching `envelope_v2.py` or Methodology.
