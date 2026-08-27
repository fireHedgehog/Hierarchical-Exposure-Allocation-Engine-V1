# Regime-tilted allocation backtest (H-SECT04)

Status: concluded-rejected, v1 (binary tilt on 4 "significant" sleeves). v2 (proper Fundamental-Law-of-Active-Management test — all 12 sleeves, IC-weighted, real effective breadth): still rejected in practical terms, but for a different, more informative reason — real effective breadth is only ~2.4 (not 12), and even the theoretically-correct combination realizes far less IR than Grinold's formula predicts. See v2 section.
Version: v0.3
Registered: 2026-08-27
Concluded: 2026-08-28

The test H-SECT02's own paper scoped but didn't design: does actually
*tilting* the 12-sleeve universe by regime beat equal-weight/static on
real, out-of-sample risk-adjusted return — the question that would
justify wiring any of this into the allocation engine, vs. leaving
H-SECT02/03 as disclosed context for manual use. GPT's own framing
called this "the most important" question in the whole line of work:
the real null to beat isn't zero, it's "equal-weight already captures
what's useful." Design-first, same discipline as H-SECT01-03.

## Universe

Same 12 sleeves as H-SECT02 (`GLD`, `QQQ`, `DIA`, 9 sector ETFs).
`SPY` kept as a third reference line (buy-and-hold), not part of either
strategy's own universe.

## Thesis

A regime-tilted allocation (see Method) produces a real, better
out-of-sample Sharpe ratio than a monthly-rebalanced equal-weight
static allocation over the same 12 sleeves, without a materially worse
real max drawdown or an unreasonable turnover cost.

Falsified by: tilted Sharpe doesn't beat static Sharpe out-of-sample,
or only beats it by widening drawdown/turnover enough that the
trade-off isn't real value — a directional win on one metric while
losing on the others isn't a confirmation.

## Method

**Tilt rule** (disclosed, hand-picked, not fit — same status as
`risk_envelope_allocation`'s naive-v1 0.5x-1.5x band): using
H-SECT02/03's only *robust* finding (`XLU`/`XLP` defensive rotation;
`QQQ`/`XLY` treated as the calm-regime counterweight since they showed
consistent-sign, OOS-strengthening evidence; `GLD` excluded from the
tilt itself despite H-SECT02's large in-sample effect, since its own
OOS check weakened — a real, disclosed decision to trust the replicated
signal over the larger but less durable one). At each monthly rebalance,
by regime tercile:

- **Stressed**: `XLU`/`XLP` at 1.5x their 1/12 equal-weight baseline,
  `QQQ`/`XLY` at 0.67x, the other 8 sleeves unchanged, all renormalized
  to sum to 1.
- **Calm**: the mirror image (`QQQ`/`XLY` at 1.5x, `XLU`/`XLP` at 0.67x).
- **Neutral**: equal-weight, no tilt.

**Rebalance**: every 21 trading days (~monthly, same `STRIDE_DAYS`
convention as H-SECT02/03), using the regime composite reading as of
that date. Static baseline is also rebalanced back to exact equal-weight
at the same cadence — an active, standard baseline, not passive buy-
and-hold drift, so the comparison isolates the tilt logic itself, not
a rebalancing-frequency effect.

**Return approximation**: period return = `Σ w_i × (sleeve return over
that period)`, target weights held fixed within a period (no daily
intra-period drift tracking) — a disclosed simplification standard for
a monthly-rebalanced first pass, not full daily portfolio simulation.

**Metrics**: real annualized return, volatility, Sharpe (rf=0,
disclosed), real max drawdown (on the cumulative return path), and real
turnover (`Σ|target weight change|` per rebalance, summed). Gross
returns only — no transaction-cost modeling this pass, a known,
disclosed gap (same two-stage pattern as H-STREV01 → H-STREV02's later
cost check).

**Split**: same 2019-01-01 chronological split as H-SECT02, reported
separately in-sample and out-of-sample, no refitting.

## What would count as a real checkpoint

One real run of `research_lab/regime_tilted_allocation_backtest.py`,
producing both strategies' real metrics on both halves.

## Promotion criteria

A real, out-of-sample Sharpe improvement without a materially worse
drawdown, holding under the disclosed gross-only assumption, would be
the first real evidence justifying an actual `strategies` registration
for a regime-conditioned sleeve tilt — still not automated execution,
matching every other naive-v1 desk in this project. Falling short here
doesn't invalidate H-SECT02/03 (a real correlation existing doesn't
guarantee it survives being turned into an actual weighted, costed
allocation rule) — a different, harder bar, by design.

## Observation log

| Date | Checkpoint | Reading |
| --- | --- | --- |
| 2026-08-27 | Real run, `research_lab/regime_tilted_allocation_backtest.py`, same dataset as H-SECT02/03. | **Rejected — the Sharpe improvement is real in sign but economically trivial, and weakest exactly where it matters most.** |

| Period | Static Sharpe | Tilted Sharpe | Difference | Static max DD | Tilted max DD | Tilted turnover |
| --- | --- | --- | --- | --- | --- | --- |
| Full sample | 0.83 | 0.86 | +0.022 | -46.95% | -46.19% | 10.70 (260 periods) |
| In-sample (2004-2018) | 0.67 | 0.69 | +0.025 | -46.95% | -46.19% | 6.88 |
| Out-of-sample (2019-2026) | 1.04 | 1.04 | **+0.008** | -22.11% | -22.11% | 3.36 |

Drawdown is essentially identical between strategies in every period (both hit the same 2008 trough). Out-of-sample — the period that matters for a real go/no-go call — the tilt adds a Sharpe improvement indistinguishable from noise, despite a real, non-trivial turnover cost (3.36 summed absolute weight-change over 91 rebalances) that isn't even priced yet (gross-only). A real, disclosed interpretation, not just "it failed": only 4 of the 12 sleeves get tilted, so even a ±33-50% weight change on those 4 is mechanically small against a diversified 12-asset equal-weight book — the sleeve-level correlation H-SECT02 found is real, but diluted to near-nothing at the portfolio level by this design. A more concentrated design (fewer sleeves, bigger tilt, or tilting gross exposure instead of within-equity mix — closer to what `risk_envelope_allocation` already does) might do better; this specific design's answer is no.

**This closes the loop GPT's own framing asked for:** the real null (equal-weight already captures what's useful) was NOT beaten. Per that framing's own conclusion — "if it has [no benefit], macro layer should only handle gross risk, not section selection" — `macro_regime_composite` stays scoped to gross exposure (`risk_envelope_allocation`, already live), and this specific sleeve-tilt idea does not get engineered into the pipeline.

## v2: proper Fundamental-Law-of-Active-Management test

User's own direct, correct methodological point: v1 (and every test in
this whole session) asked "is this one bet individually significant" —
never Grinold's actual question, "does combining many weak-but-real
bets across real breadth produce portfolio-level value" (`IR ≈ IC ×
√BR`). v1's binary tilt threw away all 8 non-"significant" sleeves'
real (if individually weak) information — exactly the mistake the
Fundamental Law says not to make.

**Method** (`research_lab/breadth_weighted_allocation_backtest.py`):
real per-sleeve IC (126d, composite vs. forward relative return),
computed for **all 12 sleeves**, not just H-SECT02's flagged-significant
subset — walk-forward correct: ICs learned only from the in-sample
half (2004-2018), held fixed, applied unchanged to both halves (no
lookahead). Combined score `score_i(t) = IC_i × composite(t)` (standard
IC-weighted alpha-score construction), converted to long-only weights
(`weight_i ∝ base_weight_i × (1 + score_i)`, clipped ≥0, renormalized
to the same gross exposure as static — isolating pure selection skill
from the exposure-timing effect H-MACRO10 already tested separately).
Real effective breadth via this project's own proven PCA machinery
(`effective_number_of_bets`, the same tool behind H-MACRO08's ~4-cluster
finding) — not a naive count of 12.

| Date | Checkpoint | Reading |
| --- | --- | --- |
| 2026-08-28 | Real run, full dataset, walk-forward IC. | **A genuinely different, more informative rejection than v1's.** |

**Real effective breadth: 2.44, not 12.** The 12 sleeves' own real
return correlations mean there are only ~2.4 truly independent bets
among them — most of the "12-sleeve diversification" was always
illusory; the sleeves mostly move together (market beta dominates).
Mean |IC| across all 12 (including the weak ones): 0.142. Grinold's own
formula then predicts `IR ≈ 0.142 × √2.44 ≈ 0.222` — a real, meaningful
theoretical improvement.

| Window | Static Sharpe | Breadth-weighted Sharpe | Realized diff | Grinold-predicted diff |
| --- | --- | --- | --- | --- |
| Full sample | 0.834 | 0.844 | +0.010 | +0.222 |
| In-sample | 0.666 | 0.679 | +0.014 | +0.222 |
| Out-of-sample | 1.036 | 1.041 | +0.005 | +0.222 |

**The realized improvement is real (positive in every window, never
reverses) but ~15-40x smaller than the theory predicts.** Three real,
identifiable reasons, not "the theory is wrong": (1) the ICs plugged
into the formula are in-sample-measured correlations, not proven
out-of-sample forecasting skill — H-SECT05 already showed most of
these individual ICs (`GLD` especially) don't survive real out-of-
sample or beta-adjustment, so the formula's input overstates true
forward skill; (2) the long-only, gross-preserving constraint
mechanically compresses achievable IR relative to Grinold's own
unconstrained (long-short) assumption, a well-known real effect, not
specific to this dataset; (3) none of this is costed — real turnover
(7.21 full sample) would likely erase the entire realized 0.01 Sharpe
gain at any real transaction-cost level this project has already
tested elsewhere (H-STREV02's 10-50bps sensitivity).

**Honest verdict:** the Fundamental Law framing is the *right* way to
think about this — and it surfaced a real, standalone-valuable finding
(effective breadth ≈2.4, not 12) that v1's binary design could never
have revealed. But even applied correctly, this universe's real,
learnable breadth is too thin and the real ICs too weak-and-unstable
for the theoretical improvement to survive contact with a long-only,
walk-forward, cost-aware reality. Same net conclusion as v1, reached
by a completely different and more rigorous route: this sleeve-tilt
idea does not get engineered into the pipeline.

## v3: extended universe (adds SMH, IGV; BTC-USD reference-only)

Same v2 method, bigger real universe — 14 tradable sleeves
(`research_lab/breadth_weighted_allocation_backtest_extended.py`).
`BTC-USD` reported separately, info-only, never in the tradable book —
this project's own existing rule (`roadmap.md`: "research reference
only, never a position candidate"), not overridden here. Its own IC
against this dataset could not be computed — no real `BTC-USD` bars in
the currently sealed dataset snapshot, disclosed rather than guessed.

| Metric | 12-sleeve (v2) | 14-sleeve (v3) |
| --- | --- | --- |
| Real effective breadth | 2.44 | 2.48 |
| Mean \|IC\| | 0.142 | 0.137 |
| Grinold-predicted IR | 0.222 | 0.215 |
| Realized Sharpe diff, OOS | +0.005 | +0.007 |

`SMH` shows a real, moderate IC (+0.207, similar magnitude to `XLF`);
`IGV` is near zero (+0.003). Adding them barely moves effective
breadth (2.44 → 2.48) — they're correlated enough with the existing 12
that they don't add real independence, only raw count. Same
conclusion as v2, now confirmed robust to a bigger candidate universe:
the bottleneck is real correlation among ETF-level sleeves, not the
number of tickers tested.
