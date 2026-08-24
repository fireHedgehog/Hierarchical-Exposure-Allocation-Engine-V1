# Project checkpoint

This is the authoritative catch-up page for maintainers and coding agents. Keep it current when a meaningful product boundary, operating rule, or next task changes. The application and database remain authoritative for decisions and research results.

## Current state

- Version: `0.1.0`, the initial manual-first repository edition; no release tag has been created.
- Design record: [Edition V1](editions/edition-v1.md) preserves the corrected product thesis and scope that this implementation establishes.
- Product: a database-driven hierarchical exposure allocation and research application.
- Available: Today desk, decision graph, cross-sectional matrix, data health, symbol signal/chart/event/metric views, and position candidates backed by SQLite snapshots.
- Operating mode: local, manual-first, and read-only with respect to brokers. The included demonstration dataset is synthetic and explicitly seeded.
- Operations: a loopback-only, lower-frequency control plane provides credential readiness and smoke tests, source freshness, dry/full manual run records, and strategy/research lifecycle views below the decision surfaces.
- Not available yet: production provider ingestion, real strategy computation, scheduled runs, broker connectivity, or order placement.
- Initial baseline: the application, schema, versioned documentation, automated checks, and primary browser flows together define the reviewed first substantive application edition.

## Next product task

Build the first real business-logic slice from source to decision:

1. Ingest selected FRED series with ALFRED real-time/vintage metadata into local point-in-time records.
2. Validate source identity, observation dates, availability dates, freshness, completeness, units, and revision lineage.
3. Seal an immutable dataset snapshot only when its required inputs pass validation.
4. Compute and publish the first manual regime state with inspectable inputs, transformations, weights, uncertainty, and nulls.

Then extend the engine vertically through risk budget, cross-sectional allocation, symbol expression, and portfolio constraints. Scheduling remains out of scope until repeated manual runs are safe and reproducible.

## Non-negotiable rules

- The application is the product surface; Markdown is for concise operation and maintenance guidance.
- Database snapshots are canonical for run inputs, decisions, metrics, lineage, lifecycle events, and provenance.
- Unknown data stays null. Stale, synthetic, blocked, and live-capable states must be visibly distinct.
- Research, simulation readiness, and live execution are separate gates.
- Credentials enter only the transient write-only browser request that stores or rotates them. They are never embedded in the frontend bundle, retained in frontend state/storage, returned by an API, or written to Git, logs, research artifacts, or the application database.
- Stable internal security identifiers are independent from ticker and provider identifiers.
- Provider ingestion is paced, cached, restartable, point-in-time aware, and replaceable.
- The system must explain combined portfolio exposure, not merely rank isolated strategies.
- No broker order is submitted without a separately designed and reviewed execution boundary.

## Environment and portability

- Application code and schema are committed; local databases, raw vendor data, caches, secrets, and bulk run artifacts are ignored.
- Secrets are resolved from the operating-system keychain or injected environment variables. The database stores only provider configuration and verification metadata.
- Every promoted computed result must reference immutable dataset and strategy/factor revision identifiers. Portable exports identify those records by hashes, not local file paths.
- A fresh clone must be useful without private data: it supports an honest empty state and an explicit synthetic demo seed.

## Document map

- [Root README](../README.md): product identity and quick start.
- [Edition V1](editions/edition-v1.md): archived initial product thesis, hierarchy, and operating principles.
- [Architecture](architecture.md): boundaries and data flow.
- [Operations](operations.md): credentials, manual runs, testing, and scheduling gate.
- [Strategy lifecycle](strategy-lifecycle.md): evidence, promotion, monitoring, and retirement.
- [ADR 0001](adr/0001-database-canonical-research.md): canonical records and reproducible exports.
- [Changelog](../CHANGELOG.md): material product, design, application, data, and operating changes.
- [`backend/schema.sql`](../backend/schema.sql): executable persistence contract.

Update this checkpoint for the live project state. Preserve only major design baselines under `docs/editions/`; do not use edition documents as runtime inputs.
