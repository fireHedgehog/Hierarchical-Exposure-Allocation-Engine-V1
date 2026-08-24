# Edition V1 — Hierarchical Exposure Allocation Engine

| Field | Record |
| --- | --- |
| Edition | V1 |
| Date | 2026-08-24 |
| Status | Archived product and design baseline, corrected at the first application draft |
| Source | [Original bilingual design discussion](https://chatgpt.com/share/6a8b94dd-ff30-83ec-b068-3a01b2c9b763) |

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
 Signal families: momentum, reversal, quality, revisions and themes
                         ↓
 Exposure map: security, factor, theme, macro and option sensitivities
                         ↓
 Risk budget: net/gross, concentration, liquidity, premium and Greeks
                         ↓
         Correlation, covariance and redundancy controls
                         ↓
                    Portfolio optimizer
                         ↓
                Target portfolio and deltas
                         ↓
        Instrument expression and execution proposal
                         ↓
                  Monitoring and lifecycle
```

The state engine describes the investable environment using probabilities and uncertainty rather than a single categorical label. Event surprise should be normalized against expectations and historical dispersion, then linked through testable economic mechanisms. For example, an inflation surprise may affect real yields; real-yield changes may affect duration-sensitive equities; security-level duration loadings may explain cross-sectional return differences. The system tests these links separately before testing an allocation rule built from them.

Signals are first combined within economic families. Several momentum horizons can inform one momentum composite, but they do not constitute three independent bets. Family construction should use covariance-aware shrinkage, stability and decay estimates; the portfolio layer then compares families and penalizes remaining redundancy across securities and strategies.

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
4. Introduce one cross-sectional signal family and its security exposure map, with decay, covariance and walk-forward evidence.
5. Allocate that evidence through explicit risk budgets and a constrained portfolio optimizer, first in simulation and then in repeated shadow runs.
6. Add option-chain history and expression selection only after the underlying target and portfolio-risk accounting are trustworthy.

This vertical sequence makes the first real computation visible early. It does not require every future dataset or strategy to exist before business logic begins.
