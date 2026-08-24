# Strategy and factor lifecycle

Strategies and factors are managed application records, not prose chapters. A management view should expose their current revision, state, owner, universe, evidence, monitoring metrics, dependencies, public source link when applicable, and lifecycle history.

## States

```text
draft -> active -> watching -> retired
```

`draft` covers idea and research work until the team needs finer workflow states. `watching` means a challenger or active strategy is under explicit evidence or degradation review. A state transition appends an event with time, revision, reason, and the previous/new state; evidence remains linked through research-run records. Retirement requires a reason and is reversible only through a new reviewed revision; historical runs keep their original revision.

## Revisions and decisions

Keep three kinds of change distinct:

- Definition change: logic, universe, feature, parameter policy, or implementation changes; create a new revision and never edit it after promotion.
- Lifecycle change: promotion, degradation, suspension, or retirement; append a lifecycle event.
- Run-time allocation: regime and portfolio constraints alter today's weight; persist the contribution and reason on that run without pretending the strategy definition changed.

Code may live in Git and a record may link to a public commit or file. The database remains canonical for which revision ran, with which data and parameters, and what it produced.

The first draft exposes the registry read-only and has no strategy mutation API. Draft version rows are not yet sealed against direct local SQL. A future promotion workflow must enforce revision immutability at the database boundary before strategy editing is enabled in the app.

## Evidence for promotion

Evidence is proportionate to risk, not paperwork volume. Before eligibility, record at minimum:

- point-in-time inputs, delisted names/corporate actions, and leakage checks;
- walk-forward or otherwise genuinely out-of-sample evaluation;
- transaction costs, slippage, turnover, liquidity, and capacity assumptions;
- return distribution and drawdown, not only Sharpe;
- signal IC and decay where meaningful, with sample size and uncertainty;
- exposure, concentration, correlation, and sensitivity to parameters/regimes;
- failure conditions, monitoring thresholds, and comparison with a simple baseline.

Passing an isolated backtest does not guarantee allocation. The portfolio layer decides whether the strategy adds useful exposure after overlap, constraints, and current regime are considered.

## Monitoring and retirement

Monitor live/shadow observations against the revision's recorded expectations. Mark degraded when data quality, implementation drift, capacity, decay, or realized behavior breaches a threshold. Retire when the economic rationale is invalid, evidence no longer supports it, it is redundant, or reliable operation is no longer justified.

Keep governance lightweight for the current team: one explicit reviewer, a concise reason, linked evidence, and a reversible state transition. Add approvals or separation of duties only when capital, users, or regulation makes them necessary.
