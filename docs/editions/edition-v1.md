# Edition V1 — Hierarchical Exposure Allocation Engine

| Field | Record |
| --- | --- |
| Edition | V1 |
| Date | 2026-08-24 |
| Status | Archived product and design baseline, corrected at the first application draft |

This edition records the product thesis at its first durable milestone. It preserves the original ambition while incorporating the architectural corrections established during implementation. It is a historical design reference; the [project checkpoint](../README.md) records the current operating boundary.

## Origin and purpose

The project began with a practical question: how can event-sensitive market views become a coherent, dynamic portfolio rather than an unlimited collection of strategy proposals and isolated backtests?

The original brief considered inflation, employment, central-bank and liquidity events; QE, QT and neutral regimes; cross-sectional themes such as growth, defensive equities and technology sub-industries; and overlapping momentum and mean-reversion factors. It also envisaged aggressive, defensive and long/short portfolio expressions, with equities, gold, digital assets or options admitted only when the applicable universe and risk mandate permitted them.

The central problem is therefore allocation, not idea generation. A credible desk must determine which evidence is active, how much risk it warrants, where that risk already exists, whether several signals express the same economic bet, and which instrument represents the resulting target efficiently. Research losses and early implementation defects are acceptable in a clearly labelled development or simulation environment. Untraceable decisions, fabricated certainty and premature capital deployment are not.

## Governing principles

1. **A signal is not a position.** A CPI surprise, momentum score or earnings revision is evidence. A position follows only after conditioning that evidence on market state, security exposures, the existing portfolio, uncertainty, costs and risk constraints.
2. **A regime modifier is not automatically alpha.** A liquidity or rate regime may alter priors, thresholds and risk budgets. Counting the same observation as both a predictive signal and a multiplier double-counts evidence. A regime component becomes an alpha source only when a distinct, falsifiable hypothesis supports that interpretation out of sample.
3. **Decisions are hierarchical and inspectable.** Each transformation has typed inputs and outputs, an effective time, a revision, confidence or uncertainty, and an explicit reason. An unavailable value remains unavailable.
4. **Portfolio value is assessed after overlap.** A strategy can be individually credible yet receive no allocation because it duplicates existing factor, theme, sector or macro exposure.
5. **Data must be point-in-time and attributable.** Observed, released, available and ingested times are distinct. Universe membership, delistings, corporate actions and data revisions form part of the evidence.
6. **Research, simulation and execution are separate gates.** Progress at one gate neither implies nor requires approval at another. Every displayed recommendation must identify its gate and data state.

## Corrected decision system

```text
Point-in-time market, fundamental, event and options data
                         ↓
              Validation and sealed dataset
                         ↓
 State engine: macro, rates, liquidity, risk and event surprise
                         ↓
         Risk envelope and broad sleeve allocation
                         ↓
              Point-in-time eligible universe
                         ↓
 Cross-sectional discovery: asset, sector, industry and security
                         ↓
       Independent single-name entry and exit timing
                         ↓
 Signal and exposure map: factor, theme, macro and option sensitivities
                         ↓
 Portfolio optimizer: overlap, covariance, costs and constraints
                         ↓
                Target portfolio and deltas
                         ↓
        Instrument expression and execution proposal
                         ↓
                  Monitoring and lifecycle
```

The state engine describes the investable environment using probabilities and uncertainty rather than a single categorical label. Event surprise should be normalized against expectations and historical dispersion, then linked through testable economic mechanisms. For example, an inflation surprise may affect real yields; real-yield changes may affect duration-sensitive equities; security-level duration loadings may explain cross-sectional return differences. The system tests these links separately before testing an allocation rule built from them.

Signals are first combined within economic families. Several momentum horizons can inform one momentum composite, but they do not constitute three independent bets. Family construction should use covariance-aware shrinkage, stability and decay estimates; the portfolio layer then compares families and penalizes remaining redundancy across securities and strategies.

## Opportunity discovery and entry timing

Top-down allocation establishes the risk envelope and funds broad asset or strategy sleeves before the desk selects individual securities. Eligibility comes from an effective-dated universe revision linked to the dataset snapshot, not from a ticker list embedded in application code. Each revision records its membership rules, additions, removals and data requirements so delisted or unavailable securities cannot disappear retrospectively.

Cross-sectional discovery and single-name timing answer different questions. The selector asks which eligible sectors, industries and securities are strongest or weakest relative to their peers. The time-series model asks whether and when a selected security is actionable from its own history. It may return `enter`, `wait`, `hold`, `exit` or `none`. The selector and timing model retain separate revisions, evidence, decay estimates and failure states; combining them must not allow one to disguise weakness in the other.

Candidate instruments are configuration, not recommendations. DIA may be evaluated as a configurable US-equity-sleeve vehicle, subject to overlap controls against other broad equity exposures. A point-in-time BTC/USD reference series may support digital-asset research and timing, while IBIT is only a possible listed implementation after its own effective eligibility date. Historical BTC observations must not be relabelled as IBIT returns, quotes, costs or fills. At each decision time the resolver selects only instruments that are actually available, data-ready, liquid and mandate-eligible; if none qualifies, the expression remains unavailable. Neither DIA nor IBIT belongs in hard-coded decision logic, and neither becomes eligible merely because it appears in a design document.

The optimizer evaluates expected contribution at portfolio level, net of covariance risk, crowding, turnover, transaction costs, concentration and liquidity. Its constraints include gross and net exposure, single-name and asset-class limits, factor and theme budgets, and—when options are present—premium, volatility and Greek limits. Its output is a target portfolio, not an order.

## Stock and option expression

Directional conviction is continuous; instrument choice is a separate decision. Long or short stock, calls, puts and defined-risk vertical spreads are candidate expressions rather than distinct strategy systems. Selection depends on target exposure, confidence, horizon, implied volatility, skew, liquidity, event timing, financing, assignment risk and maximum tolerable loss.

A moderately bullish view may justify a smaller stock allocation or a call spread, while a strongly bearish view may justify reduced equity exposure, a short position or a defined-risk put structure. The desk must show why one expression dominates the alternatives and aggregate its delta, gamma, vega, theta, premium and scenario loss with the rest of the portfolio. Options recommendations require trustworthy chain history and executable quotes; otherwise the expression remains unavailable.

## Hypotheses and lifecycle

The unit of research is a falsifiable link, not a complete trading story. A macro example can be decomposed into: surprise to real yield, real yield to duration-factor return, factor loading to cross-sectional dispersion, and the allocation rule to portfolio outcomes after costs. This identifies where a thesis fails instead of reducing the entire explanation to one backtest statistic.

Evaluation should use point-in-time inputs, genuine out-of-sample or walk-forward periods, simple baselines, uncertainty estimates, realistic costs, liquidity and capacity assumptions, and sensitivity across regimes and parameters. Multiple trials are recorded rather than concealed. Return, drawdown, turnover, concentration, factor exposure, information coefficient and decay are interpreted together where relevant; none is a guarantee of future performance.

Factors and strategies progress through `draft`, `active`, `watching` and `retired` states. A promoted definition receives an immutable revision. Evidence, monitoring thresholds and lifecycle reasons remain linked to that revision. Regime-driven weight changes are run-time allocations, not definition changes; an active strategy may correctly receive zero weight. Degradation or redundancy triggers review and, when warranted, retirement with a concise recorded reason.

## Manual-first operation

The initial operating sequence is deliberate and observable: verify provider readiness, fetch data with pacing, validate coverage and freshness, seal an immutable dataset, run one stage, inspect its output, and only then continue to dependent stages. A failed branch blocks its dependants without erasing valid work elsewhere. Credentials remain outside the application database, while verification metadata and every terminal run are auditable.

Automation follows repeated manual reproducibility, idempotency, restartability, concurrency control, monitoring and recovery tests. Broker connectivity and order placement require a separate execution boundary. This sequence allows the research desk to evolve rapidly without presenting incomplete infrastructure as operational readiness.

## Boundary at Edition V1

Edition V1 implements the database-backed application shell: daily decision and hierarchy views, cross-sectional and symbol research surfaces, chart events, position candidates, data inventory, credential health, manual run records, strategy lifecycle records and an explicitly synthetic demonstration snapshot. The database is canonical for run inputs, decisions, lineage and evidence; generated reports are portable views of those records.

Live provider ingestion, real factor or allocation computation, options-chain research, scheduling, broker integration and order execution remain outside this edition. The manual pipeline performs preflight and records honest blockers rather than manufacturing downstream results.

## Next business-logic sequence

1. Complete one end-to-end point-in-time macro ingestion slice, beginning with FRED/ALFRED observations and vintage metadata, then validate and seal the resulting dataset.
2. Compute and display the first probabilistic macro/rates/liquidity state with contributions, uncertainty and freshness visible at every layer.
3. Add a timestamped expectations source for event-surprise research; historical actuals alone must not be treated as forecasts.
4. Build the production security master and versioned broad universe from point-in-time market and reference data.
5. Allocate the top-down risk envelope among broad sleeves before selecting individual names.
6. Introduce one cross-sectional discovery family and its security exposure map, with decay, covariance and walk-forward evidence.
7. Add an independently evaluated single-name time-series model for entry, hold, exit and inactive states.
8. Allocate actionable evidence through a constrained portfolio optimizer, first in simulation and then in repeated shadow runs.
9. Add option-chain history and expression selection only after the underlying target and portfolio-risk accounting are trustworthy.

This broad-first sequence makes the first real computation visible early and narrows from portfolio context to security timing only as its prerequisites become trustworthy. The live implementation gaps and completion evidence are maintained in the [roadmap](../roadmap.md).
