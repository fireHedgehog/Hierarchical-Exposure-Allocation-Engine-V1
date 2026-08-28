# Project checkpoint

This is the authoritative catch-up page for maintainers and coding agents. Keep it current when a meaningful product boundary, operating rule, or next task changes. The application and database remain authoritative for decisions and research results.

## Current state

- Version: `0.1.0`, the initial manual-first repository edition; no release tag has been created.
- Design record: [Edition V2](editions/edition-v2.md) is the current design record; [Edition V1](editions/edition-v1.md) stays archived, unedited, for historical context. Editions mark rare, order-of-magnitude boundaries only — this checkpoint and [engine milestones](engine-milestones.md) carry ordinary progress.
- Product: a database-driven hierarchical exposure allocation and research application.
- Available: Today desk, decision graph, cross-sectional matrix, data health, symbol signal/chart/event/metric views, per-symbol and desk-level backtest evaluation, and position candidates backed by SQLite snapshots.
- Operating mode: local, manual-first, and read-only with respect to brokers. A DB-backed engine operating mode (pilot/production, Operations → Credentials) gates any future stage that requires a paid-tier provider; pilot is the default and requires no paid credentials.
- The staging universe (database-driven, auto-seeded on every fresh clone — see [engine milestones](engine-milestones.md)) is a free-data staging fixture, not the governed, effective-dated production universe roadmap phase 2 calls for. Two real layers, deliberately not the same thing: 32 tradeable symbols plus 8 FRED macro series are `active` (real fetched price history, feed the live Today-desk product); a separate, frozen `backend/universe/stage-2-2026-08-27.json` snapshot adds 677 more real symbols (SPY/QQQ/DIA/sector/thematic ETF constituents) as research-only rows, loaded inactive on purpose — genuinely queryable for cross-sectional membership research (`staging_universe_membership`), but never fetched or exposed to the live product until someone deliberately activates them. `active` and fetching are deliberately separate flags (`fetch_only`): a symbol can be fetched for real research use without joining the live product's ranked/allocated/proposed universe.
- Operations: a loopback-only, lower-frequency control plane provides an evidence-derived demo-to-real readiness map, a database-driven provider/capability onboarding roadmap, credential smoke tests, source freshness, dry/full manual run records, and strategy/research lifecycle views below the decision surfaces. The pipeline can be run stage-by-stage (`stop_after`, e.g. "fetch data only") with live progress; `Macro · stored data` instead reuses the newest sealed real dataset and recomputes a complete desk snapshot without contacting FRED/Yahoo or rewriting dataset events. `fetch_data_stage` remains restartable and paced for the runs that genuinely need new data — see [engine milestones](engine-milestones.md) 0.92.
- Provider plan: FRED/ALFRED is the only actionable account. Three researched full-desk accounts remain planned, but their adapters and entitlement checks are not implemented and no keys are requested yet.
- Real engine: all six compute stages — `fetch_data`, `validate_data`, `regime_filter`, `factor_engine`, `allocation_engine`, `instrument_engine` — are implemented and proven against live FRED and Yahoo data, every value traceable to a fetched observation or a function over one (deliberately naive/overfit scoring throughout; see [engine milestones](engine-milestones.md)). Only `publish_snapshot` remains scaffolded.
- Sub-strategy granularity (`strategy_components`) and a general research-evidence layer (`research_metric_catalog`, 71 metrics across 6 categories; `research_run_metrics`) are real for two strategies and one research category respectively. Adding or retiring one candidate factor is proven to cost minimum code, not a redesign; see [engine milestones](engine-milestones.md) 0.13–0.16.
- Research Staging V2 is active under [`docs/hypotheses/staging_v2/`](hypotheses/staging_v2/README.md): four concise type READMEs carry each loop and result table. Macro S2/S6 have an exact-runtime block-permutation audit; S2-002 additionally routes all 26 stored FRED series through one 840-cell indicator-outcome matrix instead of forcing a single return or exposure winner. It found no stable SPY return-magnitude route, but retained distinct damage, volatility, leadership, duration, inflation-pricing, policy-response, and gold relationships; VIX remained one useful fast input rather than the whole macro model. Timing H-TIME-S2-001 then tested 36 matched dislocation-repair cells across SPY/QQQ/DIA/IWM: zero stable repair cells, 11 continuation-risk cells, 17 inconclusive, and eight rare-event insufficient. High absolute rebound rates did not beat equally weak matched states, so an immediate buy-the-break timing translation is rejected while eventual recovery remains possible. S3-CV's current-vintage numeric translation remains accepted for staging (`55.4/100` environment position and `21.5%` six-month adverse-frequency reference), while calibrated probability remains blocked by missing historical release-time PIT. H-MACRO-S4-002 remains inconclusive and authorizes no production translation. Prior experiments remain under [`archive/staging_1/`](hypotheses/archive/staging_1/README.md) only as temporary context.
- Not available yet: a production security master and versioned universe, real options-chain quotes (options are priced with a real Black-Scholes engine off real inputs, not a market quote — honestly labeled theoretical-pricing-only), walk-forward/decay/fitted-weight evidence, covariance-aware portfolio construction, scheduled runs, broker connectivity, or order placement.

## Next product task

The engine's free-data pilot slice (all six compute stages, through `instrument_engine`) is done, and the sub-strategy/research-evidence infrastructure (engine milestones 0.13–0.16) is proven — see [engine milestones](engine-milestones.md) for status and verified examples. Next:

1. Manually audit Macro S2-002's routed meanings and Timing H-TIME-S2-001's rejected immediate-repair thesis. If timing continues, preregister observable repair confirmation as a new relationship study rather than retuning the failed dislocation grid; do not collapse the macro matrix into an exposure score.
2. Milestone 4: pursue real candidate factors using the now-proven research loop (add via `strategy_components`, run signal-validation research, promote or retire by status flip) — decorrelation has real first evidence (effective number of bets); decay and fitted weights remain undone.
3. Build the point-in-time security master and versioned universe (roadmap phase 2) — the staging universe remains a free-data fixture with no governed, effective-dated eligibility contract.
4. Decide whether `publish_snapshot` needs its own implementation or is redundant now that the orchestrator seals snapshots directly (see engine-milestones.md's open decision note).

Each stage follows the same contract proven since `regime_filter`: a real function over real (free-tier) data, naive/overfit scoring accepted for now, a hand-typed output never accepted. Scheduling remains out of scope until repeated manual runs are safe and reproducible.

## Non-negotiable rules

- The application is the product surface; Markdown is for concise operation and maintenance guidance.
- Database snapshots are canonical for run inputs, decisions, metrics, lineage, lifecycle events, and provenance.
- Unknown data stays null. Stale, synthetic, blocked, and live-capable states must be visibly distinct.
- Research, simulation readiness, and live execution are separate gates.
- Credentials enter only the transient write-only browser request that stores or rotates them. They are never embedded in the frontend bundle, retained in frontend state/storage, returned by an API, or written to Git, logs, research artifacts, or the application database.
- Stable internal security identifiers are independent from ticker and provider identifiers.
- Universe eligibility is database-driven, effective-dated, and versioned; a frontend or strategy must not define it with hard-coded ticker lists.
- Research references and execution instruments are distinct, effective-dated identities. An underlying series may inform a target, but an instrument may be simulated or proposed only while that symbol was actually available and eligible.
- Cross-sectional discovery and single-name time-series timing remain separately revisioned and evaluated layers.
- Provider ingestion is paced, cached, restartable, point-in-time aware, and replaceable.
- Provider access, adapter integration, entitlement coverage, stored-data health, and engine readiness remain separate states.
- The system must explain combined portfolio exposure, not merely rank isolated strategies.
- No broker order is submitted without a separately designed and reviewed execution boundary.

## Environment and portability

- Application code and schema are committed; local databases, raw vendor data, caches, secrets, and bulk run artifacts are ignored.
- Secrets are resolved from the operating-system keychain or injected environment variables. The database stores only provider configuration and verification metadata.
- Every promoted computed result must reference immutable dataset and strategy/factor revision identifiers. Portable exports identify those records by hashes, not local file paths.
- A fresh clone must be useful without private data: it supports an honest empty state and an explicit synthetic demo seed.

## Document map

- [Root README](../README.md): product identity and quick start.
- [Developer's letter](developer-letter.md): why research and production stay separate — the isolation boundary, the polytherapy/single-ingredient framing, and why the staging application must keep running even when every research factor fails.
- [Edition V2](editions/edition-v2.md): current design record — the six compute stages made real over free-tier data.
- [Edition V1](editions/edition-v1.md): archived initial product thesis, hierarchy, and operating principles.
- [Roadmap](roadmap.md): durable demo-to-real sequence, completion evidence, and the UI surface unlocked by each phase.
- [Engine milestones](engine-milestones.md): living working doc for the current free-data-first engine build sequence; edited in place, versioned by a table at its top, not archived per change.
- Methodology (Operations → Methodology, in-app, not a Markdown file): every named desk, real or explicitly null, one card each — top-level parameter, code reference, and real APA7 citations where a technique comes from published literature. Deep structural detail (versions, sub-components, diagnostics) is deliberately not duplicated here; it lives on each desk's Strategy registry record. Updated in the app on request at milestones, not automatically.
- [Architecture](architecture.md): boundaries and data flow.
- [Operations](operations.md): credentials, manual runs, testing, and scheduling gate.
- [Strategy lifecycle](strategy-lifecycle.md): evidence, promotion, monitoring, and retirement.
- [Research hypotheses](hypotheses/README.md): pre-database working papers for candidate research ideas — a hypothesis lives here, versioned, until it reaches a real conclusion; only then does it become a `strategies` row.
- [`backend/research_lab/`](../backend/research_lab/README.md): the code-side counterpart — throwaway, no-quality-bar scripts for testing a hypothesis; never imported by production, never writes to the database. Skip it in review/cleanup by default; see its README for the exact rule.
- [ADR 0001](adr/0001-database-canonical-research.md): canonical records and reproducible exports.
- [Changelog](../CHANGELOG.md): material product, design, application, data, and operating changes.
- [`backend/schema.sql`](../backend/schema.sql): executable persistence contract.

Update this checkpoint for the live project state. Preserve only major design baselines under `docs/editions/`; do not use edition documents as runtime inputs.
