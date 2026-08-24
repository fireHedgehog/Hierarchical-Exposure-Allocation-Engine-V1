# Operations

## Local start

```bash
make setup
make seed-demo
make serve
```

`make seed-demo` is explicit and synthetic. Omit it to inspect the empty state. Use `make verify` before review or commit.

The application binds to `127.0.0.1` by default. Operations reads require a direct loopback connection; mutations additionally require an approved local browser origin and an action-specific confirmation header. This is a local operator boundary, not multi-user authentication. Do not expose the Operations API remotely without designing real authentication and authorization.

## Credential management

The Operations surface shows each provider's purpose, expected secret source, configured and verified states, last verification time, official help links, and smoke-test action. Its write-only form submits a new secret to the backend once; no read endpoint or later render returns it.

During development, resolve secrets from the operating-system keychain or injected environment variables. A local ignored `.env` may be exported by the shell for convenience; commit only the commented, value-free `.env.example`. Store only non-secret metadata in SQLite, such as the credential alias, revision, verification result, and timestamps.

A successful smoke test is cached. Routine page loads and pipeline runs use the latest acceptable verification instead of repeatedly calling a provider. FRED currently has a 15-minute repeat-call cooldown and a separate seven-day health-validity window; both are application-owned provider policies. Reverify when requested, health validity expires, an API rejects the credential, or configuration changes.

Environment-backed verification fails closed after a service restart, because the process cannot prove that the injected value is unchanged. Verify it again after restarting. A verification timestamp more than five minutes ahead of the server clock is invalid; correct the clock and run a new smoke test. Credential writes, deletes, and smoke tests are serialized per provider only inside one application process in this local draft; keep a single API worker until a shared coordination mechanism is implemented.

## Manual daily run

Before beta, an operator starts each run and reviews every stage:

1. Preflight credential status, source availability, configuration, and the effective market date.
2. Fetch into a restartable staging area with provider pacing and request accounting.
3. Validate symbols, timestamps, coverage, corporate actions, missingness, and freshness.
4. Seal the accepted dataset snapshot; never silently rewrite it.
5. Run regime, risk budget, allocation, symbol, and instrument stages in dependency order.
6. Review blockers, nulls, exposure changes, provenance, and candidate actionability in the UI.
7. Publish the desk snapshot for viewing. Publishing is not order authorization.

The first-draft run record stores stage state, start and finish times, record counts, snapshot references, a concise message, and an error code. Before scheduling, add normalized input hashes, explicit output references, an idempotency key, locking, and resumable-stage semantics.

In the first draft, only preflight is implemented. Dry preflight records later stages as skipped; a full manual attempt stops at the unimplemented fetch stage and publishes nothing. That blocker is deliberate and visible in the UI.

## Scheduling gate

Do not add cron merely because the command works once. Scheduling becomes eligible after the manual pipeline has:

- deterministic/idempotent inputs and stage outputs;
- per-run locking, timeouts, bounded retries, and provider rate limits;
- observable freshness, failures, partial completion, and alert ownership;
- tested recovery from interrupted fetches and computation;
- reproducible snapshots and a stable operator review process;
- a defined holiday/calendar policy and acceptance criteria.

The first schedule should ingest and compute only. Broker execution remains a separate, later safety boundary.

## Local state and recovery

Runtime databases, SQLite journals, raw data, caches, secrets, and generated run bundles are ignored by Git. Back them up through the local operating environment if they matter. Never use a copied mutable database as evidence without its dataset/run hashes. Curated reproducibility baselines are small, reviewed exceptions under `docs/baselines/`.
