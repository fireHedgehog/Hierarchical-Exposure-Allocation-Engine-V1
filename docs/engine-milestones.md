# Engine build milestones

This is a living working document, not an archived baseline. Edit it in place as
milestones complete or the plan changes — git history is the record of how this
page looked before, so nothing here needs to be copied into a new file first.
Durable, rarely-changing product design lives in [roadmap.md](roadmap.md) and
[editions/](editions/); this page tracks the specific free-data-first engine build
sequence agreed on 2026-08-24.

## Version history

| Version | Date | Change |
| --- | --- | --- |
| 0.1 | 2026-08-24 | Initial milestone list: local environment verified, engine build sequence agreed (free-data pilot mode first, production mode after). |
| 0.2 | 2026-08-24 | Milestone 2 (mode toggle) and the first slice of Milestone 3 (`regime_filter`) built and verified end-to-end against the live FRED API. |
| 0.3 | 2026-08-24 | `factor_engine` built: real cross-sectional momentum ranking (Yahoo price data, 10y history) plus a real per-symbol MACD/RSI backtest with trade log and Sharpe/win-rate/drawdown metrics. Macro model expanded to 8 factors (added rates, PPI, core PCE, nonfarm payrolls). `engine/`/`pipeline/stages/` reorganized into one-file-per-concept subpackages. |
| 0.4 | 2026-08-24 | Milestone 3 completed: `allocation_engine` (real risk envelope + decision graph) and `instrument_engine` (-5..+5 conviction scale, real Black-Scholes options pricing) built and verified end-to-end. Added the desk-level backtest aggregate (equal-weighted across all backtested staging symbols). Frontend: chart timeframe selector + RSI/MACD panes, full backtest trade ledger table, chart markers clipped to the visible timeframe (fixes a squish bug on short windows), US Eastern timestamp display. Docs restructured: Edition V2 recorded, roadmap gap descriptions corrected to match what's actually real now. |
| 0.5 | 2026-08-24 | Moved the staging position-sizing default ($1M notional, 2% risk-per-position) from a Python constant into a seeded `staging_budget_config` DB row — the same "download the repo, see the same default, edit it in one inspectable place" contract already established for `staging_symbols`. `position_size()` now takes budget/risk-fraction as required parameters instead of reading a module constant. Milestone 4's scope written out in full below, at the user's explicit request, so a future session knows what "working" means at that stage before starting it. |
| 0.6 | 2026-08-24 | Backfilled the `strategies`/`strategy_versions`/`strategy_diagnostics`/`strategy_lifecycle_events` registry (present in schema since Edition V1, never populated) with the 5 real engine algorithms: `macro_regime_composite`, `cross_sectional_momentum`, `macd_rsi_single_name_timing`, `risk_envelope_allocation`, `conviction_instrument_selection`. Each carries its real hand-picked parameters, an honest thesis/expected-edge disclosure, a `code_reference` to its source file, a `naive-v1` version, a new `verification_status` flag (`registered_only` until Milestone 4's gate passes), `next_review_at` (6 months out), and explicit-NULL `decay_rate`/`estimated_capacity_usd` diagnostics — all seeded via `INSERT OR IGNORE` in schema.sql, not Python or markdown, per the standing "everything is a table, a row, a data entry" rule. The existing Strategy registry/detail pages render all of it with no new UI built. |
| 0.7 | 2026-08-24 | Milestone 4, step 1 (statistical validation) built and run for real: `engine/research/` computes real Pearson correlation + a real two-sided p-value (scipy) between every macro factor's period-over-period change and every staging symbol's forward return, corrected for the resulting multiple-comparisons problem (hand-rolled Benjamini-Hochberg, verified against a hand-checked example). Persisted to new `factor_significance_runs`/`factor_significance_results` tables, triggered on demand (`POST /api/v1/admin/research/factor-significance/runs`) against the latest sealed dataset — deliberately not wedged into the Milestone-3 manual pipeline. First real run: only 66 of 176 pairs were testable (`fetch_data`'s FRED window was 400 days, sized for `regime_filter`'s YoY math — too short for the 5 monthly macro series to reach a usable sample size) and found one result later shown to be a small-sample artifact. |
| 0.8 | 2026-08-24 | Extended `fetch_data`'s FRED window from 400 days to 10 years (`FRED_OBSERVATION_WINDOW_DAYS`, matching `PRICE_FETCH_RANGE`) so every macro series has enough history to test. Re-ran fetch/validate/regime/factor/allocation/instrument end-to-end (6,330 real FRED observations, up from 688) and re-ran the significance research: **all 176 of 176 (factor, symbol) pairs were now testable**, and exactly one survived correction — NFCI vs. XLV, r=+0.18, adjusted p=0.0059, n=516. The earlier 0.7 finding (NFCI vs. XLP, r=-0.61 on only 51 samples) is gone with the larger sample — a concrete, in-repo demonstration of why the small-sample result was never trustworthy in the first place, and why this step has to run before any weight gets fit to it. |

## What "working" means, per milestone

The same word means different things at different milestones. Read the status line for the milestone you're actually in before deciding what "not done yet" implies — this section exists specifically so a future session doesn't over- or under-react to "make it work."

| Milestone | "Working" means | "Working" does **not** require |
| --- | --- | --- |
| 3 (done) | Every displayed number is the output of a real function reading real fetched data. Naive, hand-picked coefficients, collinear factors, and even overfit or already-public formulas are accepted. No page shows "Not available" for anything the engine is capable of computing. | Statistical significance, decorrelation, decay estimation, or the naive rule beating a simple baseline. It's fine — expected — for the naive backtest to lose to buy-and-hold. |
| 4 (not started, scoped below) | Every factor has passed a real significance test and been decorrelated from its peers before its weight is fit (not hand-picked) through an iterative search. Decay is explicitly defined and measured. | Paid data, production-scale infrastructure, or matching a real fund's actual process — only its statistical rigor. |
| 5 (not started) | Same rigor as Milestone 4, extended once the richer paid-provider dataset (earnings, options chains, economic-calendar expectations) is available. | — |

## Milestone 1 — Local environment checked

Status: **done** (2026-08-24).

- Backend: Python venv with `backend/requirements.txt` installed; `pytest -q` — 107/107 passing.
- Frontend: `npm --prefix frontend run build` succeeds; production bundle serves from the backend.
- App: `python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000` boots; all endpoints serve real, database-backed data.

## Milestone 2 — Staging/production mode toggle

Status: **done** (2026-08-24). Table `engine_operating_mode` (singleton row), `PUT /api/v1/admin/engine-mode`, toggle UI on Operations → Credentials.

A DB-backed, UI-visible toggle on the Operations → Credentials page (not a workspace/decision page) switching the engine between:
- **Pilot mode** (default): free-data-only. Runnable by anyone who clones the repo with zero paid credentials.
- **Production mode**: same engine functions, full paid-provider stack, once built.

Real mechanism, verified: `run_pipeline` blocks any stage requiring a `tier='paid'` provider while in pilot mode, and every snapshot a run produces is stamped with the mode active when it ran.

## Milestone 3 — Real engine on free data, staging mode

Status: **done** (2026-08-24). All six compute stages (`fetch_data`, `validate_data`, `regime_filter`, `factor_engine`, `allocation_engine`, `instrument_engine`) are real and verified end-to-end against live FRED + Yahoo data. Only `publish_snapshot` remains scaffolded.

**`regime_filter`**: 8 real macro factors (growth, inflation, PPI, core PCE, employment, liquidity, volatility, rates), every number traceable to a fetched FRED observation.

**`factor_engine`**: real 10-year price history for all 21 tradeable staging symbols, real cross-sectional momentum ranking (blended 1M/3M/6M z-score), and a real per-symbol MACD(12,26,9)/RSI(14) backtest with a full trade log. Verified example (QQQ, 2016-2026): 100 closed trades. Desk-level aggregate across all 22 backtested symbols (2026-08-24 run): mean strategy return +122% vs. mean buy-and-hold +1558% — the naive rule loses to holding, on average, largely dragged down by a handful of extreme decade-long compounders (e.g. NVDA, BTC-USD) in the buy-and-hold comparison. Expected and fine per this project's standing rule: a working, naive, even losing result beats no result, because it leaves something to optimize.

**`allocation_engine`**: a real risk envelope — regime confidence scales a gross-exposure multiplier, cross-sectional composites roll up into sleeve targets — persisted as a real decision graph (desk → risk envelope → sleeves). Verified example (2026-08-24 run): regime confidence 0.49 → 0.99x multiplier → target gross exposure 98.6% across 6 sleeves.

**`instrument_engine`**: the full -5..+5 conviction scale mapped to concrete instrument expressions (|1.0-2.4| equity tilt, |2.5-3.4| credit spread, |3.5-4.4| debit spread, |4.5-5.0| LEAPS), priced with a real Black-Scholes engine (real spot price, real realized volatility, real 10-year Treasury rate). Verified example: IGV at conviction +5.0 → LEAPS long call, 103.37 strike, 545 DTE, 9 contracts, max loss $18,895.61 (2% of the $1,000,000 staging budget). Every options candidate is honestly labeled theoretical-pricing-only (no free options-chain source exists) and carries a required, unresolved blocker — the existing readiness gates correctly keep these non-executable.

Known simplification, stated not hidden: cross-sectional discovery and single-name
timing currently live in the same `factor_engine` stage, even though this project's
own rule calls for them to stay "separately revisioned and evaluated." Splitting them
into their own pipeline stage is future work.

Working rule for this milestone, stated plainly so it doesn't get re-litigated: **a naive, overfit, collinear, or "already-decayed-and-public" factor formula is acceptable here.** The only non-negotiable is that every output number comes from a real function reading real fetched data — never a hand-typed final value standing in for one. Quality, redundancy, and decay get addressed in Milestone 4, not before.

## Milestone 4 — Optimize within pilot mode

Status: not started. Scoped to the staging universe only, still free-tier data. This is deliberately the first milestone where "naive is fine" stops applying — see the vocabulary table above. Every step below is real, non-trivial quant work; none of it is something one agent does casually in an afternoon, and it is explicitly sequenced so rigor comes before fitting, never after.

**Step order matters — later steps depend on earlier ones passing first:**

1. **Statistical validation.** For every existing factor — both the macro composite's 8 inputs (`engine/regime/`) and the cross-sectional momentum blend's 3 horizons (`engine/factors/`) — run a real significance test (e.g. IC t-stat / p-value against forward returns) before that factor is trusted with any weight at all. A factor that doesn't clear significance gets flagged, not silently kept at its current hand-picked weight.
2. **Decorrelation.** Apply PCA / dimensionality reduction across the factors that do pass step 1, macro and cross-sectional separately at first. The goal is to stop double-counting the same underlying bet (e.g. two momentum horizons that are 90% correlated shouldn't each get independent weight) — this is the project's own governing principle ("a regime modifier is not automatically alpha... double-counts evidence," [edition-v1.md](editions/edition-v1.md)) applied concretely with math instead of asserted in prose.
3. **Decay definition.** For each factor that survives steps 1-2, explicitly measure how its predictive power fades with time (half-life, not an assumption). This is the "real library, real research team" tier of work the user named directly — treated as seriously as a systematic fund would, not faked or skipped to reach a number.
4. **Weight fitting — only after 1-3 pass.** Only once a factor is statistically significant, decorrelated from its peers, and has a measured decay does it become eligible for a fitted (not hand-picked) weight — an iterative search (walk-forward, many epochs, starting from a small weight and converging, e.g. 0.001 → ~0.6) rather than the current typed-in constants (`regime/scoring.py`'s `WEIGHTS`, `factors/momentum.py`'s 0.2/0.3/0.5 blend). Macro composite weights and cross-sectional/momentum weights are fit as separate exercises, matching this project's standing rule that cross-sectional discovery and single-name timing stay independently revisioned.
5. **Ensemble across factor families.** Once the cross-sectional (discovery) and time-series (timing) layers each have their own validated, decorrelated, fitted factors, combine them as an ensemble rather than the current single combined `factor_engine` stage — the known simplification flagged in Milestone 3 gets resolved here, not before.

Address the desk-level backtest aggregate's naive-vs-buy-and-hold gap (Milestone 3's honest, expected result) as a natural output of this process, not a separate task bolted on afterward.

## Milestone 5 — Switch to production mode

Status: not started. Gated on Milestone 4 being good enough to trust the plumbing.

- Register Intrinio / Benzinga / Trading Economics only once their adapters exist.
- Production mode unlocks fields pilot mode structurally cannot have (e.g. earnings — ETFs don't report them).
- Re-run the same optimization pass from Milestone 4 with the richer data available.

## Open decision — `publish_snapshot`

Not yet decided whether `publish_snapshot` needs its own implementation or is redundant: `run_pipeline`'s orchestrator already seals the dataset and desk snapshot directly at the end of a run, regardless of this stage's status. Revisit once Milestone 4 work clarifies whether a distinct publish step earns its keep.
