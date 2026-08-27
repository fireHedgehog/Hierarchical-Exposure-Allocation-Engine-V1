# Regime-tilted allocation backtest (H-SECT04)

Status: concluded-rejected (real correlation exists — H-SECT02 — but doesn't translate to a meaningful allocation edge at this tilt design)
Version: v0.2
Registered: 2026-08-27
Concluded: 2026-08-27

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
