# Project checkpoint

This is the authoritative catch-up page for maintainers and coding agents. Keep it current when a meaningful product boundary, operating rule, or next task changes. The application and database remain authoritative for decisions and research results.

## Current state

- Version: `0.1.0`, the initial manual-first repository edition; no release tag has been created.
- Design record: [Edition V2](editions/edition-v2.md) is the current design record; [Edition V1](editions/edition-v1.md) stays archived, unedited, for historical context.
- Product: a database-driven hierarchical exposure allocation and research application.
- Available: Today desk, decision graph, cross-sectional matrix, data health, symbol signal/chart/event/metric views, per-symbol and desk-level backtest evaluation, and position candidates backed by SQLite snapshots.
- Operating mode: local, manual-first, and read-only with respect to brokers. A DB-backed engine operating mode (pilot/production, Operations → Credentials) gates any future stage that requires a paid-tier provider; pilot is the default and requires no paid credentials.
- The staging universe (21 tradeable symbols plus 8 FRED macro series, database-driven, auto-seeded on every fresh clone — see [engine milestones](engine-milestones.md)) is a free-data staging fixture, not the governed, effective-dated production universe roadmap phase 2 calls for.
- Operations: a loopback-only, lower-frequency control plane provides an evidence-derived demo-to-real readiness map, a database-driven provider/capability onboarding roadmap, credential smoke tests, source freshness, dry/full manual run records, and strategy/research lifecycle views below the decision surfaces.
- Provider plan: FRED/ALFRED is the only actionable account. Three researched full-desk accounts remain planned, but their adapters and entitlement checks are not implemented and no keys are requested yet.
- Real engine: all six compute stages — `fetch_data`, `validate_data`, `regime_filter`, `factor_engine`, `allocation_engine`, `instrument_engine` — are implemented and proven against live FRED and Yahoo data, every value traceable to a fetched observation or a function over one (deliberately naive/overfit scoring throughout; see [engine milestones](engine-milestones.md)). Only `publish_snapshot` remains scaffolded.
- Not available yet: a production security master and versioned universe, real options-chain quotes (options are priced with a real Black-Scholes engine off real inputs, not a market quote — honestly labeled theoretical-pricing-only), walk-forward/IC/decay evidence, covariance-aware portfolio construction, scheduled runs, broker connectivity, or order placement.

## Next product task

The engine's free-data pilot slice (all six compute stages, through `instrument_engine`) is done — see [engine milestones](engine-milestones.md) for status and verified examples. Next:

1. Build the point-in-time security master and versioned universe (roadmap phase 2) — the staging universe remains a free-data fixture with no governed, effective-dated eligibility contract.
2. Decide whether `publish_snapshot` needs its own implementation or is redundant now that the orchestrator seals snapshots directly (see engine-milestones.md's open decision note).
3. Milestone 4: optimize within pilot mode — the naive factor/backtest formulas are real but currently lose to buy-and-hold on average; start reducing that gap.

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
- [Edition V2](editions/edition-v2.md): current design record — what's real now, what V1 established, what's still not real.
- [Edition V1](editions/edition-v1.md): archived initial product thesis, hierarchy, and operating principles.
- [Roadmap](roadmap.md): durable demo-to-real sequence, completion evidence, and the UI surface unlocked by each phase.
- [Engine milestones](engine-milestones.md): living working doc for the current free-data-first engine build sequence; edited in place, versioned by a table at its top, not archived per change.
- [Architecture](architecture.md): boundaries and data flow.
- [Operations](operations.md): credentials, manual runs, testing, and scheduling gate.
- [Strategy lifecycle](strategy-lifecycle.md): evidence, promotion, monitoring, and retirement.
- [ADR 0001](adr/0001-database-canonical-research.md): canonical records and reproducible exports.
- [Changelog](../CHANGELOG.md): material product, design, application, data, and operating changes.
- [`backend/schema.sql`](../backend/schema.sql): executable persistence contract.

Update this checkpoint for the live project state. Preserve only major design baselines under `docs/editions/`; do not use edition documents as runtime inputs.
