# Macro research

Systematic testing of free macro/rates/liquidity indicators — building this
project's own, evidence-based read of risk-on/risk-off/neutral, instead of
inheriting one from commentary. Same lifecycle and rules as the parent
[`docs/hypotheses/`](../README.md); this subfolder exists because "many
aspects to test" needs its own index, not an ever-growing flat table.

**Update, 2026-08-27:** the freeze is lifted. `macro_regime_composite` was
promoted to **naive-v3** (`backend/engine/regime/scoring_v3.py`) after a
real, out-of-sample-validated evidence chain — see
[composite-methodology-v1.md](composite-methodology-v1.md)'s sequencing
section. Staging mode, not production: still not a timing signal, still
carries disclosed gaps (policy-operations cluster excluded, Liquidity/
Guidance out of scope for this composite). Any *further* change still
needs the same bar: real, quantified evidence before promotion, no
exceptions.

## The 3-layer framework

Every candidate indicator is tested through three deliberately separated
layers, not asked directly "does X predict QE/hike/risk-on":

1. **Input signal** — a real, freely and reliably available leading or
   coincident indicator (auction tail, bid-to-cover, MOVE, SOFR-IORB, HY/IG
   spread, breakevens, real yields, initial claims, NFCI, balance sheet,
   TGA, etc.), recorded without pre-deciding what it means.
2. **Fed response** — decomposed into independent dimensions, not one
   hawkish/dovish scalar:

   | Dimension | Outcomes |
   | --- | --- |
   | Rate policy | Hike / Hold / Cut |
   | Balance sheet | QE / Neutral / QT |
   | Liquidity | None / Repo-SRF / Emergency facility |
   | Guidance | Hawkish / Neutral / Dovish |

3. **Market outcome** — kept structurally separate from layer 2, because a
   cut ≠ automatically risk-on (a panic cut can coincide with equities still
   falling):

   | Dimension | Outcomes |
   | --- | --- |
   | Equity | Risk-on / Neutral / Risk-off |
   | Duration | Bull / Neutral / Bear |
   | Credit | Tightening / Neutral / Easing |
   | USD | Strong / Neutral / Weak |
   | Volatility | Expansion / Neutral / Compression |

An indicator's result is a conditional table across these three layers, not
a single "useful/not useful" verdict. An unknown cell stays `?` — never
force-filled to complete the table.

## Per-indicator research card

```markdown
- Hypothesis: why this might lead
- Data source: FRED / Treasury / NY Fed / Yahoo, etc. (free only)
- Frequency: daily / weekly / monthly / event
- Lag: real-time / T+1 / 1 month
- Expected relationship: the prior, stated before looking
- Observed relationship: the real result
- Regime dependency: does it change under QE/QT/high inflation/recession
- False positives: alarmed but nothing happened
- Incremental value: information remaining once other signals are controlled for
```

**Incremental value is the one that matters most.** Many macro indicators
show individual "predictive power" while all being projections of the same
latent state (e.g. HY spread↑, MOVE↑, VIX↑, equities↓, NFCI tightening may
just be five faces of one "risk stress" factor, not five signals). Once
several input signals have real readings, run the existing
[`signal_validation.py`](../../../backend/engine/research/signal_validation.py)
correlation/effective-number-of-bets machinery (already proven on the 8
macro factors and on momentum horizons) against them, same as any
cross-sectional factor set.

## Index

| Paper | Status | Covers |
| --- | --- | --- |
| [Warsh Fed reaction function](warsh-reaction-function.md) (H-W01) | observing | Layers 1-3, chair-specific |
| [Rate decision predictors](rate-decision-predictors.md) (H-MACRO01) | observing | All 22 layer-1 indicators vs. layer 2's Rate dimension (hike/cut only — holds not classified yet, no FOMC calendar). 4/22 significant. |
| [Balance sheet predictors](balance-sheet-predictors.md) (H-MACRO02) | observing | All 23 layer-1 indicators vs. layer 2's Balance sheet dimension, continuous IC (not discrete events — see paper for why). 10/23 significant. |
| [Equity outcome predictors](equity-outcome-predictors.md) (H-MACRO03) | observing | All 24 layer-1 indicators vs. layer 3's Equity dimension (SPY forward return). 17/24 significant. Direct test of "bad news is good news": VIX confirms it, NFCI doesn't. |
| [Credit outcome predictors](credit-outcome-predictors.md) (H-MACRO04) | observing | 22 indicators vs. HY spread forward change. 6/22 significant, but smallest sample in the folder (n=72, single 2023-2025 regime). |
| [Volatility outcome predictors](volatility-outcome-predictors.md) (H-MACRO05) | observing | 23 indicators vs. VIX forward change. 7/23 significant at 1q — nearly all point the same way as H-MACRO03/04: stress now predicts calming, not more stress. |
| [Duration outcome predictors](duration-outcome-predictors.md) (H-MACRO06) | observing | 23 indicators vs. 10Y yield forward change. 18/23 significant — richest result in the folder; rate-level mean-reversion vs. fundamentals-continuation, two distinct real mechanisms. |
| [USD outcome predictors](usd-outcome-predictors.md) (H-MACRO07) | observing | 24 indicators vs. broad dollar index forward change (new series, `DTWEXBGS`). 15/24 significant; rate-mean-reversion group plausibly chains from H-MACRO06's own finding. |
| [Indicator redundancy](indicator-redundancy.md) (H-MACRO08) | observing | **The prerequisite for any composite.** 17-23 raw indicators → only ~3.5-4.1 effective independent bets. Real factor structure: inflation/growth, rate level, market stress, policy operations — 4 clusters, not 17-26 signals. |
| [Composite forward risk](composite-forward-risk.md) (H-MACRO09) | observing | Reframed composite test (risk-context, not timing): stressed reading is 5-7x more likely to precede a real ≥10% SPY drawdown within 3-6mo (p<0.0001 both windows). |
| [Composite forward risk — out-of-sample](composite-forward-risk-oos.md) | observing | Chronological split at 2019-01-01. Replicates cleanly on held-out data; 6mo effect is *stronger* out-of-sample (+42.9pp vs. +21.8pp in-sample) — the opposite of overfitting. |
| [Composite threshold sensitivity](composite-threshold-sensitivity.md) | observing | 14/16 threshold×split combinations significant. 6-month window robust across every choice tested — not an artifact of the original -10%/tercile pick. |
| [Exposure policy calibration](exposure-policy-calibration.md) (H-MACRO10) | preregistered | Flags a real conceptual gap (external review): `risk_envelope_allocation`'s confidence→gross-multiplier mapping is a *separate, untested* hypothesis from H-MACRO09's validated confidence→drawdown-probability finding. No experiment run yet. |

**Layer 3 complete** — all 5 market-outcome dimensions (Equity, Credit,
Volatility, Duration, USD) now have a real indicator-vs-target table.

**One indicator-vs-target table per paper, by design** — each new layer-2/3
target dimension (Balance sheet, Liquidity, Guidance, Equity, Credit, ...)
gets its own paper testing all indicators against it, not one giant matrix.
Once several exist, they get correlated against each other and distilled
into a real composite — weighting scheme genuinely undetermined, not
assumed; a real design question for when there's more than one dimension's
real result to weigh.

## Fetched, not yet tested

14 new real FRED series verified live and now fetched by every real pipeline
run (`SERIES_METADATA`, `backend/pipeline/stages/common.py`), alongside the
existing 8 — no schema change needed, `fred_observations` is already
series-agnostic. Real usable history, checked directly against the API, not
assumed:

| Series | What | Real history in this project |
| --- | --- | --- |
| `WALCL` | Fed total assets | 2004-2026 |
| `WTREGEN` | TGA balance | 2004-2026 |
| `DGS30` | 30Y yield | 2004-2026 |
| `GDPC1` | Real GDP | 2004-2026 (quarterly; freshest print can be ~150 days old — corrected from an initial 120-day guess after a real fetch found 147) |
| `MTSDS133FMS` | Federal deficit | 2004-2026 |
| `ICSA` | Initial claims | 2004-2026 |
| `T10YIE` / `T5YIE` | Breakeven inflation | 2004-2026 |
| `DFII10` | 10Y TIPS real yield | 2004-2026 |
| `DFII30` | 30Y TIPS real yield | 2010-2026 |
| `SOFR` | Overnight funding rate | 2018-2026 (real start; SOFR didn't exist before) |
| `IORB` | Interest on reserve balances | 2021-2026 (real start; renamed from IOER) |
| `BAMLH0A0HYM2` | HY OAS spread | **2023-2026 only** — real, verified: this project's point-in-time-correct fetch (pinned `realtime_start`) only reaches ICE's real-time vintage archive, which doesn't extend as far back as the series' current/non-vintage display |
| `BAMLC0A0CM` | IG OAS spread | **2023-2026 only** — same real vintage-archive limit |

Still missing, real free source exists but needs new provider code (not
FRED — `fiscaldata.treasury.gov`, keyless): Treasury auction tail,
bid-to-cover. **Not free anywhere found:** MOVE index.

## A pattern across papers, not asserted as one thing yet

H-MACRO03/04/05 largely agree: elevated stress *now* (VIX, NFCI, credit
spreads) tends to predict *calming* ahead (higher equity return, narrower
spreads, lower vol), not further deterioration — a real "stress mean-
reverts" story spanning three independently-run papers. H-MACRO06/07 agree
with each other on a related but distinct mechanism: elevated *rate levels*
mean-revert, and that plausibly chains into dollar weakness. Neither is
confirmed as one underlying factor — that's exactly what the redundancy
check below has to test before anyone calls it that.

**Redundancy check done (H-MACRO08): ~4 real independent factor clusters**,
not 17-26 indicators — inflation/growth, rate level, market stress, policy
operations. This is the concrete input for composite design.

**8 real papers now exist** (2 layer-2 dimensions, all 5 layer-3 dimensions,
plus the redundancy check) — the free-data potential in what's readily
fetchable is largely mined for a first pass, and the composite is live at
naive-v3. If this gets picked up again, restart from the table below
rather than re-deriving what's missing.

## Restart-here: every known gap, in one place

| Gap | Why it's parked | What would close it |
| --- | --- | --- |
| Policy-operations cluster (WALCL/WTREGEN/IORB/SOFR) not in the live composite | Sign genuinely ambiguous — balance-sheet expansion can mean crisis liquidity injection (risk-off) or accommodative ease (risk-on), context-dependent | A real sub-hypothesis distinguishing the two cases before assigning any sign, not a guess |
| Liquidity dimension (SRF/discount-window) | No confirmed clean free FRED series | Verify whether the NY Fed's own operation-result data is usable; if not, stays parked |
| Guidance dimension (Fed speech/statement tone) | Needs real text, an NLP problem, not a correlation test | Real FOMC statement/speech text source — none connected yet |
| H-MACRO01 (Rate) has no "Hold" outcome | No real FOMC meeting calendar in this project | Curate or source a real meeting-date calendar, then re-run with 3-class outcomes |
| Debt-ceiling event study | Never started | Curate real debt-ceiling-raise dates (legislative record, free); small-N event study, same shape as the Warsh paper |
| Regime-duration ("higher for longer, how long") | Never started | Same duration-distribution method already scoped for H-BETA02, applied to a regime state |
| Regime-conditional cross-sectional performance | Never started for `cross_sectional_momentum` itself. A related question (section leadership persistence, regime-conditioned) was tested as [H-SECT01](../asset-selection-research/section-leadership-persistence.md) and rejected — leadership doesn't persist at a quarterly horizon, so its regime-interaction sub-test wasn't promoted either | Does `cross_sectional_momentum`'s own edge (not leadership persistence) change across `macro_regime_composite` states — still open |
| Composite threshold/design alternatives beyond what was tested | Naive-v1 bar accepted this as shippable, not because it's optimal | Compare cluster-equal-weighting against IC-weighted alternatives, once there's appetite for a deeper pass |
| Exposure policy calibration (H-MACRO10) — does confidence's validated drawdown-probability actually calibrate to `risk_envelope_allocation`'s 0.5x-1.5x gross multiplier | Never started; a portfolio-optimization/utility question, not a correlation test | Real out-of-sample backtest: static vs. scaled exposure on Sharpe/drawdown — see the paper |

## [Composite methodology (design v1)](composite-methodology-v1.md)

Not a hypothesis — a design document, written before any code per direct
instruction. Answers: how to handle a factor that's 3 weeks stale with a
new print due in a week (hold flat, never fabricate); what to normalize
against (a real z-score against each factor's own trailing history,
replacing the existing naive-v2 hand-picked-scale approximation); how to
aggregate (weighted sum, weights from H-MACRO08's real ~4-cluster
structure, not the raw 17-26 indicator list); and the real validation step
before touching schema or pipeline code (a face-validity backtest against
known historical dates). `macro_regime_composite` stays frozen through
every step until real backtest evidence exists.

**[Face-validity backtest results](composite-face-validity-backtest.md)**:
3 of 4 known crisis dates matched (2008, 2020, 2022). One real miss
(2021-11 late-cycle top) — the composite read risk-off while equities were
near highs, driven by real inflation-surprise and tightening NFCI readings
that preceded the actual 2022 crash. Raised a real, resolved design
question: not a timing signal, a risk-context read (see below) — the user's
own correction, confirmed by:

**[Forward risk results](composite-forward-risk.md) (H-MACRO09)**: reframed
to "how likely is a real drawdown," pooled across ~255 real dates instead
of 5. A composite reading in the bottom tercile is **5-7x more likely** to
precede a real ≥10% SPY drawdown within 3-6 months than a calm reading
(+22-27pp, p<0.0001 both windows) — a real, quantified, significant answer
to "how likely, how confident, how strong."
