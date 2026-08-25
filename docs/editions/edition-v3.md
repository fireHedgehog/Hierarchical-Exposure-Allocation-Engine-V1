# Edition V3 — Hierarchical Exposure Allocation Engine

| Field | Record |
| --- | --- |
| Edition | V3 |
| Date | 2026-08-25 |
| Status | Current design record. Supersedes Edition V2 as the active reference; V1 and V2 stay archived, unedited, for historical context. |

## V1 and V2 baseline, in one table

V1 ([archived](edition-v1.md)) established the product thesis and the database-canonical application shell. V2 ([archived](edition-v2.md)) made the six compute stages real over free-tier data, naive scoring accepted by design.

| V1 + V2 established | Left undone |
| --- | --- |
| Governing principles, database-canonical decision graph, six real compute stages over live FRED/Yahoo data | Every strategy was one flat, fused function — no internal granularity, no reusable research infrastructure |
| `strategy_versions` registry with an honest `verification_status` vocabulary | Retiring or adding one internal sub-signal meant editing fused code and risking the whole strategy |
| One narrow, hand-built research tool (`factor_significance_runs`): macro-factor-vs-symbol correlation only | No generalized way to validate a new candidate factor, and no enumerated map of what "validated" should even mean |

## What is real now

Two structural gaps closed, both proven live against real data, not asserted:

**Sub-strategy granularity.** A strategy can be an ensemble of named, independently versioned, independently retireable `strategy_components` — not a fused function. `macd_rsi_single_name_timing` splits into `macd_crossover` and `rsi_overbought_exit`, combined by a role-tagged signal ensemble (they are not peers in a weighted sum; MACD is the only entry trigger, RSI is exit-only — a deliberately different aggregation shape from macro's null-tolerant weighted sum, not a shortcut). Retiring a component is a database status flip, proven live: retiring RSI degrades gracefully; retiring MACD too produces an honest `no_entry_signal_active` result — zero trades, a plain-language reason, never a crash. The pipeline stage that calls into this (`factor_engine.py`) needed no changes to support any of it.

**A general research-evidence layer.** `research_metric_catalog` enumerates the full quant-research taxonomy this edition adopted (71 metrics: data integrity, signal validation, backtest performance, robustness/statistical validation, trading reality, portfolio/risk), each tagged by which strategy family it structurally applies to. `research_run_metrics` holds only what a real run actually produced — an unrun catalog entry renders as an honest dash, never an implied gap. One category has real utilities so far: `backend/engine/research/signal_validation.py` (Rank IC, ICIR, pairwise correlation, effective number of bets via PCA/inverse-Herfindahl, redundancy flagging). Live-proved against real data: macro's 8 factors reduce to an effective number of bets of 2.43 (CPI/core-PCE/PPI correctly flagged as one redundant inflation bet, r=0.92-0.998); momentum's 3 horizons reduce to 1.74.

**The loop closes.** A genuine literature-classic factor — Jegadeesh & Titman's (1993) "12-1" momentum — was added as a real, database-registered `draft` candidate in roughly ten lines inside one existing extraction function, with zero schema, endpoint, or UI changes. It tested as genuinely diversifying, not redundant (effective number of bets rose from 1.74 to 2.11), and both the write path (verified by direct SQL) and the read path (verified by the actual GET endpoint) round-tripped correctly through infrastructure that did not need to know this specific factor existed in advance. This is the edition's central claim: adding or retiring one factor should not require redesigning the system around it, and now, twice, it hasn't.

## What "minimum code" deliberately means here

A zero-recode, fully generic plugin dispatcher was considered and explicitly declined, not silently deferred. The standing design choice: extraction code stays small, explicit, and readable per factor family — one new function or a small addition to an existing one — rather than a generic dispatcher that would be harder to recall, audit, and reason about later than the plumbing it replaces. Diminishing returns apply deliberately: the goal is staying out of a coder/researcher context switch for the common case (add, retire, or grey-test one factor), not eliminating code entirely.

## Still not real

A governed, effective-dated production universe; real options-chain quotes; five of the six catalog categories (backtest performance, robustness, trading reality, portfolio risk, and most of data integrity) have enumerated metrics but no computing utilities yet; only two of five real strategies (`macd_rsi_single_name_timing`, `cross_sectional_momentum`) have component-level granularity; the `manual_override` component type and the `research_runs` supersession/invalidation columns are schema-ready but have no write endpoint yet; paid-provider data; scheduling; broker connectivity; order execution.

## Where this leaves the sequence

Milestone 4 (`docs/engine-milestones.md`) remains the destination: statistical validation, decorrelation, decay, and fitted weights before any naive weight is trusted. This edition delivers the infrastructure that milestone needs to be pursued as ordinary research work rather than each step being its own infrastructure project — the effective-number-of-bets results above are real Milestone 4, step 2 progress, not a demo of the mechanism. The next real step is exploring genuine candidate factors, not building more plumbing to explore them with.
