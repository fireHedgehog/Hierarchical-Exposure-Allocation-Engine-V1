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
4. The state engine sets the risk envelope and broad sleeve budgets before security selection begins.
5. An immutable universe revision records which securities were eligible within those sleeves at the effective time and why.
6. A cross-sectional selector ranks eligible sectors, industries, and securities; an independently revisioned time-series model then records each candidate's entry, hold, exit, wait, or inactive state.
7. The portfolio stage maps exposures, controls overlap and constraints, and persists target weights and deltas.
8. Instrument expression evaluates stock, short, option, or defined-risk implementations only for approved targets.
9. Each stage consumes explicit dataset, universe, and model revision identifiers and persists status, inputs, outputs, timestamps, and blockers.
10. A desk snapshot materializes the graph, APIs serialize persisted records, and the UI explains them without inventing values for null fields.

The same stage interfaces should serve research, simulation, and eventually scheduled operation. Environment and gate status change; the mathematical implementation should not fork into unrelated paths.

## Persistence boundaries

- Canonical: datasets, security identities, universe definitions and immutable revisions, effective-dated memberships, model revisions, parameters, run state, decisions, metrics, lifecycle events, lineage, and provenance.
- Application configuration: provider onboarding, capability mappings, and readiness-gate definitions. Planned providers remain separate from actionable credential adapters, and readiness status is derived from canonical evidence rather than stored as a completion flag.
- External secret store: credential values and tokens.
- Local generated artifacts: plots, tables, and summaries exported from canonical records.
- Git: source, schema, migrations, tests, concise documentation, and explicitly reviewed reproducibility baselines.

The schema is organized around dataset snapshots, stable securities, desk and symbol snapshots, decision graph nodes/edges, cross-sectional factors, position candidates, and data-source provenance. The production universe contract still needs definitions, immutable revisions, effective-dated membership, inclusion and exclusion reasons, and links to the exact dataset snapshot used to resolve eligibility. Prefer additive migrations and stable identifiers; do not make ticker strings or vendor row IDs primary identity.

## Universe and model contracts

A security master says what an instrument is; a universe revision says whether it was eligible for a specific decision. Membership must preserve ticker changes, delistings, corporate actions, listing history, provider mappings, asset class, venue and the applicable liquidity or mandate rules. Candidate symbols enter through this data contract, never through frontend or strategy-code constants.

An economic exposure, its research reference, and its execution instrument are separate identities. For example, a point-in-time BTC/USD reference series may drive a digital-asset signal, while IBIT is only one possible listed implementation after its own effective eligibility date. Historical BTC observations must never be relabelled as IBIT returns, quotes, costs, or fills. The instrument resolver selects only symbols that are listed, data-ready, liquid, and mandate-eligible at the decision time; no qualifying vehicle produces an explicit unavailable result.

Cross-sectional discovery and time-series timing have separate typed outputs and immutable revisions. The selector produces a ranked candidate set relative to a declared peer group. The timing model consumes an eligible candidate and produces a dated action state from that security's own history. A combined portfolio run references both revisions, retains null or blocked outputs, and can therefore attribute failure to the appropriate layer.

## Design constraints

These are promotion requirements for a production pipeline. The first draft implements the read/operator boundaries and append-only terminal run history; cross-process idempotency keys, run locks, resumable stages, and scheduling remain explicit work before automation.

- Routes default to read-only behavior. State-changing administration actions are explicit and auditable.
- Runs are idempotent for a normalized set of inputs and parameters, and restartable by stage.
- A stale or incomplete upstream stage blocks only dependent stages and remains inspectable.
- Concurrency locks prevent duplicate runs for the same effective date and configuration.
- Pipeline code owns computation; components own presentation; repositories own persistence mapping.
- New abstractions must remove demonstrated duplication or enforce a boundary. Avoid speculative framework layers.
