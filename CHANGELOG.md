# Changelog

This log records material changes to the product thesis, interaction design, data semantics, application, and operating model. Detailed run results and strategy lifecycle events belong in the database.

## Unreleased

No changes have been recorded after the initial edition. The next planned product slice is FRED/ALFRED point-in-time ingestion, dataset validation and sealing, and a manually executed regime state.

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
