# Hierarchical Exposure Allocation Engine

A local research and simulation desk for turning market conditions into traceable portfolio exposure and reviewable stock or defined-risk option expressions.

An abundance of candidate strategies is not evidence. A useful desk must decide which evidence matters now, how strongly it should influence the portfolio, and how the resulting exposures interact. This project makes that reasoning visible from the market regime down to the proposed instrument, while preserving the data lineage behind every conclusion.

The application is the daily product surface. Its decisions, metrics, lifecycle records, and provenance come from versioned database snapshots; the documentation explains how the system is designed, operated, and evolved.

## How the desk thinks

Each decision passes through a hierarchy:

1. **Market context** identifies the prevailing regime and the evidence supporting it.
2. **Risk envelope and broad sleeves** convert that context into allowable net and gross exposure across asset classes and strategy families.
3. **Point-in-time eligibility** determines which securities were genuinely available, supported, liquid, and permitted at the decision time.
4. **Cross-sectional discovery** ranks sectors, industries, and securities within the funded sleeves to find relative strength and weakness.
5. **Symbol timing** evaluates each candidate's own history and records whether it should be entered, held, exited, deferred, or left inactive.
6. **Portfolio construction** converts independently reviewed evidence into target weights and reconciles covariance, overlap, concentration, liquidity, factor, premium, and Greek constraints.
7. **Instrument expression** translates an approved target into a currently eligible long or short stock, call, put, or defined-risk structure appropriate to the view and market conditions.
8. **Monitoring** measures realized behavior, decay, and regime fit so strategies can be promoted, reweighted, or retired.

Research validity, simulation readiness, and live execution are separate gates. Every promoted conclusion is expected to reference point-in-time inputs and explicit strategy or factor revisions, with unavailable evidence remaining visibly unavailable.

The original product thesis is preserved in [Edition V1](docs/editions/edition-v1.md); [Edition V2](docs/editions/edition-v2.md) is the current design record, covering the free-data engine build described below. The [developer's letter](docs/developer-letter.md) explains why research and production are kept deliberately separate — disposable, isolated experiments in `docs/hypotheses/` and `backend/research_lab/`, versus a stable, database-driven staging application that keeps running end to end no matter what research finds.

## What the current draft provides

The initial application draft includes:

- a Today workspace for portfolio posture and top-down decision flow;
- a hierarchy graph and cross-sectional comparison of allocation candidates;
- data-health and provenance views backed by SQLite snapshots;
- symbol pages with current signal state, chart annotations, historical execution events, metrics, and position candidates;
- an Operations workspace for evidence-backed demo-to-real readiness, provider and credential health, data inventory, manual pipeline runs, and strategy lifecycle records;
- an explicit synthetic demonstration seed and an honest empty state for a fresh database.

Operational controls sit below the business-facing research surfaces because they are used less frequently. Manual execution is intentional at this stage: inputs, stage outcomes, and failures should be observable before scheduling is introduced.

## Quick start

Prerequisites: Python 3.10+ and Node.js 20 LTS or 22+.

```bash
make setup
make seed-demo
make serve
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). The demonstration dataset is synthetic, opt-in, and labelled throughout the interface.

To inspect a fresh empty workspace, run `make serve` before seeding or set `HEAE_DATABASE_PATH` to a new database path.

For active development, run the API and interface separately with `make dev-api` and `make dev-ui`. Run the complete automated check suite with:

```bash
make verify
```

## Current status

Version `0.1.0` is the initial manual-first application draft. It provides the application shell, persistence model, operational controls, synthetic examples, and inspection surfaces needed to develop the engine in small, testable vertical slices.

The manual pipeline's six compute stages — from fetching source data through classifying the market regime, ranking candidates, sizing exposure, and proposing an instrument — are real, running on free-tier data (FRED for macro, Yahoo for prices) over an 805-row database-seeded staging library with 32 active rows. A separate, dated and disposable [`stage-2-2026-08-29.json`](backend/universe/stage-2-2026-08-29.json) snapshot carries 775 real index and sector/thematic ETF price identities; its 773 non-overlapping additions are research-only rather than live-product candidates. One stage (publishing the final snapshot) remains a placeholder. Some strategies are now built from smaller, independently swappable pieces rather than one fixed formula, and a research scorecard checks how much genuinely new information a candidate factor adds before it's trusted. See [engine milestones](docs/engine-milestones.md) for verified status and examples. Live paid-provider ingestion, a governed production universe, scheduling, broker connectivity, and order handling remain outside this milestone. The application is therefore a research and simulation environment; its records are not trading instructions.

Runtime databases, caches, vendor data, and generated run artifacts live outside version control. Provider secrets are resolved from the operating-system keychain or injected environment variables. They are neither stored in the application database nor returned to the browser after submission. See [Operations](docs/operations.md) for credential setup, verification behavior, and the scheduling gate.

## Data-provider onboarding

FRED and Yahoo ingestion are implemented and have already produced the stored data used by the six-stage free-data engine. FRED remains the only actionable provider account; there are **zero additional registrations needed now**. A healthy credential proves access, while stored-data health and engine readiness remain separate checks.

The researched full-desk plan currently adds three accounts later:

- [Intrinio](https://intrinio.com/pricing) for the US security master, equity history, corporate actions, and historical options;
- [Benzinga](https://www.benzinga.com/apis/) for fundamentals, earnings estimates and results, and licensed call transcripts;
- [Trading Economics](https://docs.tradingeconomics.com/get_started/) for point-in-time economic-calendar expectations and survey consensus.

Do not purchase or enter those three keys yet. Their adapters, entitlement-specific smoke tests, and licensing checks must exist first. Operations → Credentials is the database-driven onboarding guide and shows the current account count, capability coverage, registration timing, official links, and next action.

## Next milestone

The free-data engine build (all six compute stages) is done — see [engine milestones](docs/engine-milestones.md). Next:

1. review the continuous event-time leadership design in [H-XSEC-S2-002](docs/hypotheses/staging_v2/cross-sectional/h-xsec-s2-002-continuous-leadership-state.md) before running it; the earlier calendar-quarter Cross/Theme result is retained only as a diagnosed failed design, while optional SEC Item 2.02 ingestion remains a filing-time proxy rather than an earnings timestamp;
2. build the point-in-time security master and versioned universe (roadmap phase 2) — the staging universe is still a free-data fixture, not a governed, effective-dated eligibility contract;
3. decide whether `publish_snapshot` needs its own implementation or is redundant now that the orchestrator seals snapshots directly;
4. optimize within pilot mode (Milestone 4) — the naive factor/backtest formulas are real but currently lose to buy-and-hold on average.

Scheduling becomes appropriate only after repeated manual runs are reproducible and operationally safe.

The complete capability sequence and the evidence required to move each surface from demonstration data to real decisions are maintained in the [Roadmap](docs/roadmap.md).

## Documentation

- [Project checkpoint](docs/README.md) — current state, operating rules, and the authoritative next task
- [Edition V2](docs/editions/edition-v2.md) — current design record: what's real now, what's still not
- [Edition V1](docs/editions/edition-v1.md) — archived: the first professional statement of the product thesis and desk design
- [Roadmap](docs/roadmap.md) — the durable capability sequence from synthetic demonstration to real decision support
- [Architecture](docs/architecture.md) — system boundaries, data flow, and trust model
- [Operations](docs/operations.md) — local operation, credentials, manual runs, and scheduling criteria
- [Strategy lifecycle](docs/strategy-lifecycle.md) — evidence, promotion, monitoring, and retirement
- [ADR 0001](docs/adr/0001-database-canonical-research.md) — canonical research records and reproducible exports
- [Changelog](CHANGELOG.md) — material product, design, data, and implementation changes

## Contributor and runtime notes

- Application code and the SQL schema are versioned; local databases, raw vendor data, caches, secrets, and bulk outputs are ignored.
- SQLite is the current local persistence layer. Stable internal identifiers remain independent from provider-specific symbols and identifiers.
- Provider integrations should be paced, cached, restartable, point-in-time aware, and replaceable.
- Computed results should retain immutable dataset and strategy revision references so they can be reproduced or exported without relying on local file paths.
- A fresh clone must remain useful without private data through its empty state and explicit synthetic seed.

The current engineering checkpoint is maintained in [docs/README.md](docs/README.md); update that file when a material product boundary, operating rule, or next task changes.
