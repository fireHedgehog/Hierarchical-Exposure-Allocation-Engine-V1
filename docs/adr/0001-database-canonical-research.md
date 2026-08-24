# ADR 0001: Database-canonical research with reproducible exports

- Status: Accepted for the first draft
- Date: 2026-08-24

## Context

Backtests and factor experiments need durable evidence, but hand-maintained result Markdown quickly becomes stale and cannot drive the application. Keeping only a mutable database, however, makes a useful result difficult to review or reproduce outside that local environment.

## Decision

The database is canonical for research definitions and revisions, dataset snapshots, normalized parameters, runs, metrics, diagnostics, lifecycle events, lineage, and provenance. The UI and APIs read those records.

A run may export a generated bundle at `artifacts/runs/<run-id>/`:

- `manifest.json` identifies the run/schema version, code commit and dirty state, dataset snapshot IDs and hashes, strategy/factor revision IDs, normalized parameters and hash, environment/tool versions, creation time, and hashes of every exported file.
- `summary.md` is generated from the run record and clearly labelled as an output, not edited as a source of truth.
- `figures/` and `tables/` contain generated diagnostics referenced by the manifest.

Bulk bundles are local and ignored by Git. A small result needed for regression review may be deliberately promoted to `docs/baselines/<name>/<version>/` after checking licenses, removing secrets/vendor payloads, and retaining its manifest. A promoted baseline is a test/review fixture; the database record it identifies remains the canonical research result.

Do not maintain a parallel hand-written `result-docs/{name}-{version}.md` history. Strategy/factor changes and retirement reasons are structured lifecycle events; material application changes belong in `CHANGELOG.md`.

## Consequences

- The application can query, compare, and visualize research without parsing documents.
- A result can be reproduced and audited through immutable identities and hashes.
- Generated summaries remain convenient for sharing without creating two editable truths.
- Export and baseline-promotion tooling must validate manifests and prevent secret or licensed raw-data leakage.
