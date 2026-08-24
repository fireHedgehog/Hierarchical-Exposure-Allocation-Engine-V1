# Edition V2 — Hierarchical Exposure Allocation Engine

| Field | Record |
| --- | --- |
| Edition | V2 |
| Date | 2026-08-24 |
| Status | Current design record. Supersedes Edition V1 as the active reference; V1 stays archived, unedited, for historical context. |

## V1 baseline, in one table

Edition V1 (2026-08-24, [archived](edition-v1.md)) established the product thesis and the application shell: a database-canonical hierarchical desk, a manual-first pipeline with honest blockers, and a strict rule that every decision value must be computed, never hand-typed. At V1, the engine itself computed nothing — every pipeline stage past preflight was scaffolded, and the six-symbol demo was a synthetic fixture.

| V1 established | V1 left undone |
| --- | --- |
| Governing principles (signal ≠ position, regime ≠ automatic alpha, hierarchical + inspectable, overlap-aware, point-in-time, gated research/simulation/execution) | All real computation — regime, factor, allocation, instrument stages were scaffolded |
| Database-canonical decision graph, snapshots, provenance | A non-synthetic dataset or desk snapshot |
| Manual pipeline shape (preflight → fetch → validate → regime → factor → allocation → instrument → publish) | Any provider adapter beyond a credential smoke test |
| Pilot/production mode concept | A governed universe (the six ETFs were a UI presentation fixture only) |

## What is real now

Every stage below is a real function over real fetched data (free-tier only — FRED/ALFRED for macro, Yahoo's unofficial chart API for prices). Naive, unoptimized, sometimes overfit formulas are accepted by design at this stage; a hand-typed final value never is. Only `publish_snapshot` remains scaffolded.

```text
fetch_data          real FRED (8 series) + Yahoo (21 staging symbols, 10y daily bars)
validate_data        freshness/completeness checks, per-series max-age thresholds
regime_filter        8-factor macro composite → regime label + confidence
factor_engine         cross-sectional momentum ranking (1M/3M/6M blended z-score)
                       + independent per-symbol MACD/RSI backtest (trade log, Sharpe,
                         win rate, drawdown) + desk-level equal-weighted aggregate
allocation_engine      regime confidence → gross exposure multiplier → sleeve targets
                       (real decision graph: desk → risk envelope → 6 sleeves)
instrument_engine       -5..+5 conviction → equity tilt / credit spread / debit spread /
                          LEAPS, priced with real Black-Scholes (real spot, real realized
                          vol, real 10Y Treasury rate)
publish_snapshot        still scaffolded — orchestrator seals snapshots directly instead
```

The staging universe (`staging_symbols`, database-driven, auto-seeded on every fresh clone) is 21 tradeable symbols chosen for free-data availability and multi-decade listing history: TLT, IEF, SPY, QQQ, DIA, GLD, BTC-USD (research reference only, never a position candidate), all 11 sector SPDRs, AAPL, NVDA, SMH, IGV — plus the 8 FRED macro series. This is a staging fixture, not the governed, effective-dated production universe V1's roadmap phase 2 still calls for.

## What "real" does and doesn't mean here

A real function reading real data over a naive formula can still lose to a coin flip, and it does here: the desk-level backtest aggregate (`GET /api/v1/desk/latest` → `backtest`) shows the naive MACD/RSI rule underperforming simple buy-and-hold on average across the staging universe. That is an honest, working result, not a defect — the project's standing rule is that a naive-but-real, even overfit, result beats an unimplemented stub, because it leaves something to optimize. Optimizing the naive formulas is Milestone 4 ([engine-milestones.md](../engine-milestones.md)), deliberately not attempted yet.

Options pricing is real Black-Scholes theoretical pricing, not a market quote — there is no free options-chain source. Every options candidate carries a required, unresolved `theoretical_pricing_only` blocker so the existing readiness gates correctly keep it non-executable. This is the same "never fabricate certainty" principle from V1 applied to a new layer, not an exception to it.

## Still not real

Same shape as V1's list, narrower now: a governed, effective-dated production universe with corporate actions and delistings; real options-chain quotes/open interest/implied volatility; walk-forward/IC/decay/turnover/capacity evidence for the factor and timing layers; covariance-aware portfolio construction (today's allocation is a naive multiplier plus equal-weight-baseline tilts, not an optimizer); paid-provider data (Intrinio/Benzinga/Trading Economics); scheduling; broker connectivity; order execution.

## Where this leaves the sequence

See [roadmap.md](../roadmap.md) for the durable phase-by-phase gap table (kept current, not archived) and [engine-milestones.md](../engine-milestones.md) for the specific free-data-first build sequence and its version history. This document is a snapshot of the design record at V2; edit it only for a future major boundary (V3) — day-to-day status belongs in engine-milestones.md and docs/README.md, not here.
