# Application architecture

## Runtime shape

```text
React/Vite decision UI
        |
FastAPI read and administration API
        |
Repository and pipeline services
        |
SQLite snapshots and operational state
        |
Paced, replaceable provider adapters
```

Decision pages are the frequent-use business surface: Today, hierarchy, cross-section, and symbols. Administration is a lower-frequency control plane for credentials, data, manual runs, and strategy lifecycle. It must not become an alternate place to encode decision logic.

## Intended data flow

1. A provider adapter resolves its credential at runtime and fetches data with pacing, caching, and retry controls.
2. Validation records coverage, point-in-time availability, freshness, missingness, and provenance.
3. Accepted input is sealed as a dataset snapshot; raw vendor identity is mapped to stable internal securities.
4. Pipeline stages consume explicit snapshot and revision identifiers. Each stage persists status, inputs, outputs, timestamps, and blockers.
5. A desk snapshot materializes the graph from regime evidence through risk and allocation to instrument candidates.
6. APIs serialize persisted records. The UI explains them without inventing values for null fields.

The same stage interfaces should serve research, simulation, and eventually scheduled operation. Environment and gate status change; the mathematical implementation should not fork into unrelated paths.

## Persistence boundaries

- Canonical: datasets, revisions, parameters, run state, decisions, metrics, lifecycle events, lineage, and provenance.
- External secret store: credential values and tokens.
- Local generated artifacts: plots, tables, and summaries exported from canonical records.
- Git: source, schema, migrations, tests, concise documentation, and explicitly reviewed reproducibility baselines.

The schema is organized around dataset snapshots, stable securities, desk and symbol snapshots, decision graph nodes/edges, cross-sectional factors, position candidates, and data-source provenance. Prefer additive migrations and stable identifiers; do not make ticker strings or vendor row IDs primary identity.

## Design constraints

These are promotion requirements for a production pipeline. The first draft implements the read/operator boundaries and append-only terminal run history; cross-process idempotency keys, run locks, resumable stages, and scheduling remain explicit work before automation.

- Routes default to read-only behavior. State-changing administration actions are explicit and auditable.
- Runs are idempotent for a normalized set of inputs and parameters, and restartable by stage.
- A stale or incomplete upstream stage blocks only dependent stages and remains inspectable.
- Concurrency locks prevent duplicate runs for the same effective date and configuration.
- Pipeline code owns computation; components own presentation; repositories own persistence mapping.
- New abstractions must remove demonstrated duplication or enforce a boundary. Avoid speculative framework layers.
