# Changelog

This log records material changes to the product thesis, interaction design, data semantics, application, and operating model. Detailed run results and strategy lifecycle events belong in the database.

## Unreleased

### Engine — metric granularity axis

- New `research_metric_catalog.granularity` column (`component` / `ensemble` / `strategy` / `desk`), independent from `category`: WHAT LEVEL of the strategy hierarchy a metric evaluates, mapped onto the existing `strategy_components` → ensemble math → strategy backtest → desk-portfolio schema. User-identified gap: the 71-metric catalog had flattened single-factor metrics (IC), cross-factor metrics (correlation, effective number of bets), and realized-return metrics (Sharpe, CAGR — the tier an optimizer could fit) into one undifferentiated list. All 71 rows re-tagged; the Research page's catalog panel now groups by level first, then category.

### Engine — first research-loop smoke test

- Added Jegadeesh & Titman's (1993) original "12-1" momentum (12-month return, most recent month skipped) as a real `strategy_components` candidate (`status='draft'`) under `cross_sectional_momentum`, proving the whole research loop end to end with a genuine literature-classic factor: ~10 lines in one existing extraction function, zero schema/endpoint/UI changes, DB insert and API read-path both verified directly. Correlates 0.68 with 6M, 0.44 with 3M, only 0.08 with 1M, not flagged redundant — effective number of bets rose from 1.74 to 2.11 once included, a genuine, honest, diversifying result.

### Engine — research-evidence layer (signal validation / effective number of bets)

- New `research_metric_catalog` (71 entries) enumerates the full quant-research taxonomy across 6 categories — data integrity, signal validation, backtest performance, robustness/statistical validation, trading reality, portfolio/risk — each tagged with which strategy families it structurally applies to. New EAV `research_run_metrics` holds only what a real research run actually computed; an uncomputed catalog entry renders as an honest dash, not an implied gap. `research_runs` extended with `component_key`, `superseded_by_run_id`, and `invalidated_reason` for correcting a research mistake without deleting sealed history (schema-ready; no endpoint uses the latter two yet).
- New `backend/engine/research/signal_validation.py`: Rank IC, IC-series mean/std/ICIR, pairwise correlation matrix, effective number of bets (PCA/inverse-Herfindahl), and redundancy flagging — pure, standalone-tested functions, 11 new tests.
- `POST /api/v1/admin/research/signal-validation/runs` wires real, point-in-time-aligned extraction for macro's 8 factors and momentum's 3 horizons. First live run: macro's 8 factors → effective number of bets 2.43 (CPI/core-PCE/PPI flagged redundant at r=0.92-0.998); momentum's 3 horizons → ENB 1.74 (3M/6M redundant at r=0.75). Real numbers validating the "10 factors, PCA, ENB ≈ 2" framing this milestone was built to prove.
- Research page (Operations → Research) gets a diversification panel per factor family and a full metric-catalog reference table.
- Unrelated bug found and fixed while proving this live: `fetch_data`'s FRED realtime pin used UTC "today," which can run a day ahead of FRED's own server clock right after UTC midnight, causing a reproducible HTTP 400. Fixed with a 1-day safety margin.

### Engine — strategy registry backfill

- Registered the 5 real engine algorithms (macro regime composite, cross-sectional momentum, MACD/RSI single-name timing, risk envelope allocation, conviction-scaled instrument selection) in the `strategies`/`strategy_versions` registry that has existed since Edition V1 but was never populated. Each carries real parameters, a `naive-v1` version, a `verification_status` flag (`registered_only` until Milestone 4's statistical gate passes), a `next_review_at` date, and honestly-NULL decay/capacity diagnostics. Seeded in schema.sql, not code or documentation prose — queryable via the existing Strategy registry pages with no new UI.

### Engine — Milestone 4 statistical validation, first slice

- Added `backend/engine/research/`: real Pearson correlation + p-value (scipy) between every macro factor and every staging symbol's forward return, with a hand-rolled, tested Benjamini-Hochberg correction for the resulting multiple-comparisons problem. Run on demand against a sealed dataset (new `POST /api/v1/admin/research/factor-significance/runs`), persisted to new `factor_significance_runs`/`factor_significance_results` tables — deliberately kept separate from the Milestone-3 manual pipeline.
- Extended `fetch_data`'s FRED observation window from 400 days to 10 years (`FRED_OBSERVATION_WINDOW_DAYS`) after the first significance run showed the 5 monthly macro series had too few observations to test at all. With the full window, all 176 (factor, symbol) pairs are testable; exactly one survives correction (NFCI vs. XLV, r=+0.18, adjusted p=0.0059, n=516). The earlier 400-day run's one "significant" result (NFCI vs. XLP on 51 samples) disappeared with more data — evidence for, not against, why this validation step exists before any weight gets fit.
- **Macro research 2**: promoted `macro_regime_composite` naive-v1 -> naive-v2 (`backend/engine/regime/scoring_v2.py`). Real markets price a macro release's surprise against an already-priced-in expectation, not its raw level (Andersen, Bollerslev, Diebold & Vega, 2003; Balduzzi, Elton & Green, 2001) — the same logic behind CME FedWatch-style policy-rate expectations (Krueger & Kuttner, 1996). No free consensus/survey feed exists yet, so the honest, disclosed proxy is a trailing statistical mean of each series' own history (an adaptive-expectations stand-in, Muth 1961), not a market consensus. Same weights and aggregation as naive-v1; only the per-factor scoring formula changed. naive-v1 stays in the codebase untouched for reproducing already-sealed snapshots. New `strategy_versions` row (not a rewrite) records the promotion with real citations.
- **Modular swap-safety proof**: `cross_sectional_momentum` promoted naive-v1 -> naive-v2 (`backend/engine/factors/momentum_v2.py`) to demonstrate that one engine algorithm can be revised and isolation-tested standalone, then swapped into `factor_engine.py` as a one-line change, without breaking the pipeline or any existing test — the pluggable-strategy contract every engine module already follows (self-contained file, standalone test, no shared mutable state). The statistical content is real but secondary: v1's fixed 1M/3M/6M blend weights (0.2/0.3/0.5) are replaced by weights from a real Pearson/Benjamini-Hochberg significance test against pooled forward returns, run fresh every pipeline run. First live run (10y real Yahoo data, 2026-08-25): 1M not significant (r=+0.010, adjusted p=0.284), 3M and 6M significant (r=+0.053/+0.078, p<0.001, n>10,000 pairs each) — consistent with the published momentum literature (Jegadeesh & Titman, 1993), though this pass is coding-agent depth, not a literature review or research-team-grade validation. Equal-weight fallback keeps the score visible if nothing clears correction. v1's code stays untouched and importable; new `strategy_versions` row records the promotion.
- **Sub-strategy granularity, first slice**: new `strategy_components` table registers named, independently versioned, independently retireable sub-signals inside a strategy — the granularity gap identified after 0.12's swap-safety proof (a top-level strategy could already be swapped safely; its internal sub-signals could not be, individually). Supports two component types from day one — `computed` (a real function, value comes from the engine each run) and `manual_override` (a human-set standing value with no data source, e.g. a normally-neutral geopolitical/war-risk override settable to an extreme like -100, with a full audit trail) — though only `computed` components exist yet. `macd_rsi_single_name_timing` promoted naive-v1 -> naive-v2 (`backend/engine/timing/backtest_v2.py`), splitting into `macd_crossover` (entry+exit) and `rsi_overbought_exit` (exit only), combined by a role-tagged signal ensemble rather than macro's null-tolerant weighted average — the two are not peers in a sum, they play different roles in a sequential rule, and forcing one aggregation shape onto both would be wrong, not simpler. Live-proved against real data: retiring `rsi_overbought_exit` (a DB flag flip) degrades gracefully, changing QQQ's backtest return while every pipeline stage still completes; retiring `macd_crossover` too — removing the only registered entry trigger — produces an explicit `no_entry_signal_active` status with zero trades and a plain-language reason, never a crash or a fabricated rule. `get_strategy()` and the Strategy detail page now surface components end-to-end.
- Added a Methodology page (Operations → Methodology), later thinned: one card per named desk — top-level parameter, code reference, and real APA7 citations where a technique comes from published literature (Jegadeesh & Titman 1993, Appel 2005, Wilder 1978, Black & Scholes 1973, Pearson 1895, Benjamini & Hochberg 1995) — with a step-by-step formula walkthrough per layer dropped after it went stale (it still named the retired `backtest.py` after `backtest_v2.py` shipped) and duplicated content that now lives correctly in the DB-driven strategy registry instead. Every named desk is listed, real or explicitly null: the 5 implemented layers plus 2 new `draft` placeholders with no implementation yet (sentiment/text mining, fundamental/EPS analysis — see roadmap.md), each carrying a granularity note for what to define before writing code. An in-app page, not a Markdown file, updated on request at milestones rather than continuously.
- Persisted the -5..+5 `conviction` score (`conviction_from_composite()`) onto `cross_section_rows` and `position_candidates` — it was driving structure selection (equity tilt vs. credit/debit spread vs. LEAPS) this whole time but was computed and discarded, never actually visible. Now shown as a real number on the Today page's Cross-sectional evidence matrix and each Proposed position expression card.
- Added an Operations → Research page presenting every (factor, symbol) pair honestly (significant highlighted, non-significant explicitly labeled rather than implying zero effect), and widened `strategy_versions.verification_status` to a full honest vocabulary (`registered_only`, `verified`, `not_significant`, `collinear`, `decayed`, `outdated`) — none of them disable the underlying naive-v1 function, which keeps running regardless. The Strategy registry list page now shows `code_reference`, `verification_status`, `next_review_at`, and a real `last_checked_at`; running significance research now auto-writes a real diagnostic onto `macro_regime_composite` without overclaiming the composite itself is verified.

### Product design and privacy

- Removed the external shared-conversation reference from the archived Edition V1; the project-owned edition now stands on its own as the design record.
- Clarified the broad-first decision path: sleeve allocation, point-in-time universe, cross-sectional discovery, independent single-name timing, portfolio target, and downstream instrument expression.
- Recorded DIA and IBIT only as configurable universe candidates with distinct sleeve and overlap controls, not as recommendations or hard-coded seed additions.
- Separated underlying research references from effective-dated execution instruments: BTC may inform a digital-asset target, while IBIT can be evaluated only during its actual availability and must never receive fabricated pre-listing history or trades.
- Added a concise capability roadmap that states each demo-to-real gap, its completion evidence, and the application surface it unlocks.
- Added an Operations readiness map whose ordered gates, dependencies, acceptance criteria, evidence, and next action come from the database; current state is derived from canonical records, and synthetic fixtures cannot qualify.

### Operations and data readiness

- Added a database-driven onboarding roadmap that distinguishes four planned provider accounts from five data-capability groups and shows the registration timing, official links, licensing cautions, and next action in the Credentials UI.
- Established the current provider plan: FRED/ALFRED for the first regime slice, followed later by Intrinio, Benzinga, and Trading Economics for the complete desk. Planned providers cannot accept credentials before their adapters exist.
- Changed FRED smoke-test health validity from seven days to 365 days while retaining the separate 15-minute repeat-call cooldown and immutable historical verification records.
- Kept provider access distinct from adapter integration and operational data: a healthy FRED key does not imply that ingestion is implemented or a dataset is ready.

### Engine — free-data pilot mode, all six compute stages real

- Implemented real `fetch_data`, `validate_data`, `regime_filter`, `factor_engine`, `allocation_engine`, and `instrument_engine` pipeline stages. Only `publish_snapshot` remains scaffolded. Every value traces to a fetched observation or a function over one; nothing is a hand-typed placeholder.
- Added a database-driven staging symbol table (TLT, IEF, SPY, QQQ, DIA, GLD, BTC-USD, all 11 sector SPDRs, AAPL, NVDA, SMH, IGV — 21 tradeable symbols plus the 8 FRED macro series), auto-seeded on every fresh clone so the free-data pilot runs with zero configuration.
- `regime_filter`: 8-factor macro model (growth, inflation, PPI, core PCE, employment, liquidity, volatility, rates) against live FRED/ALFRED data.
- `factor_engine`: real cross-sectional momentum ranking (blended 1M/3M/6M z-score, Yahoo 10-year price history) and an independent, real per-symbol MACD(12,26,9)/RSI(14) backtest with a full trade log, Sharpe ratio, win rate, and max drawdown — plus a desk-level equal-weighted aggregate across every backtested symbol.
- `allocation_engine`: a real risk envelope — regime confidence scales gross exposure, cross-sectional composites roll up into sleeve targets — persisted as a real decision graph (desk → risk envelope → sleeves).
- `instrument_engine`: a full -5..+5 conviction scale mapped to concrete instrument expressions (equity tilt, credit spread, debit spread, LEAPS long call/put), priced with a real Black-Scholes engine fed by real spot price, real realized volatility, and the real 10-year Treasury rate. Every options candidate is honestly labeled theoretical-pricing-only (no free options-chain quotes exist) and carries a required, unresolved blocker so it cannot pass as executable.
- Added a real, gated engine operating mode (pilot/production; Operations → Credentials): pilot blocks any stage requiring a paid-tier provider and stamps every snapshot it produces with the active mode.
- Moved the staging position-sizing default ($1M notional, 2% max risk per position) from a Python constant into a seeded `staging_budget_config` database row, matching the `staging_symbols` pattern — a fresh clone and every running instance see the same inspectable, editable default instead of one buried in source.
- Frontend: chart timeframe selector (1M/3M/6M/1Y/5Y/10Y/Max) with RSI and MACD panes alongside volume, a full backtest trade ledger table (independent of the chart's selected timeframe — the chart only draws markers inside the visible window; the table always shows full history), and market-time (US Eastern) timestamp display everywhere.
- See [docs/engine-milestones.md](docs/engine-milestones.md) for current status and [docs/editions/edition-v2.md](docs/editions/edition-v2.md) for the updated design record.

The next planned product slice is the point-in-time security master and versioned universe (roadmap phase 2), and a decision on `publish_snapshot`.

## 0.1.0 — Initial edition — 2026-08-24

Status: first substantive application edition; not tagged or released. The preserved design baseline is [Edition V1](docs/editions/edition-v1.md).

### Product and design

- Defined a hierarchical trade desk that converts macro regime evidence into risk budget, cross-sectional allocation, symbol expression, and portfolio constraints.
- Made the decision path inspectable from the Today desk down to symbol signals, events, chart context, metrics, and position candidates.
- Separated research evidence, simulation readiness, and any future live-execution gate instead of treating a persuasive strategy narrative as approval.
- Placed lower-frequency controls under Operations so daily decision surfaces remain primary.
- Established a manual-first operating model: observe and reproduce every stage before introducing scheduling.
- Adopted lightweight institutional discipline through explicit strategy revisions, evidence, promotion, monitoring, and retirement without turning documents into the runtime product.

### Application

- Added database-driven desk, hierarchy, cross-sectional, data-health, symbol research, and strategy lifecycle views.
- Added explicit current signal state and distinct signal, pattern, and execution markers on symbol charts.
- Added an honest empty state and an opt-in synthetic demonstration dataset with both simulation-ready and blocked examples.
- Added a lower-frequency Operations area for provider readiness, data inventory, manual pipeline runs, and strategy/research records.

### Data and operations

- Added point-in-time dataset snapshots, decision provenance, stable identifiers, honest null handling, and immutable sealed demo snapshots.
- Added operating-system keychain credential storage, read-only environment fallback, and a cached FRED v2 health check; secret values never enter the application database.
- Added database-indexed research runs and fingerprinted artifact manifests. Generated reports are optional exports, while database records remain canonical.
- Added concise architecture, operations, strategy lifecycle, reproducibility, and project-checkpoint documentation.

### Correctness and security

- Excluded runtime databases, provider secrets, local configuration, raw data, caches, and bulk artifacts from version control.
- Restricted operator APIs to loopback; mutations additionally validate the local origin and an action-specific request header.
- Sanitized provider failures before display and prevented credential values from being returned, logged, or persisted in SQLite.
- Made verification health fail closed after rotation, expiry, restart-sensitive environment changes, or invalid future timestamps.
- Required published desk snapshots to reference sealed datasets with consistent live, demonstration, and classification provenance.
