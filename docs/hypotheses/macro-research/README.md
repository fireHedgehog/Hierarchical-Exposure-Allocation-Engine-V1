# Macro research

Systematic testing of free macro/rates/liquidity indicators — building this
project's own, evidence-based read of risk-on/risk-off/neutral, instead of
inheriting one from commentary. Same lifecycle and rules as the parent
[`docs/hypotheses/`](../README.md); this subfolder exists because "many
aspects to test" needs its own index, not an ever-growing flat table.

**Non-negotiable:** `macro_regime_composite` (the live, production regime
classifier) stays exactly as it is — naive-v2, unchanged — until this
research produces real, quantified grey-zone evidence for a specific,
proposed change. No promotion without evidence; there is currently none.

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

**Still queued:**
- Liquidity (SRF/discount-window — no confirmed clean FRED series, likely
  needs the NY Fed's own operation results, unverified) and Guidance (needs
  real FOMC text, an NLP problem, not a correlation test) — both real,
  named gaps, not silently skipped.
- A hold-inclusive H-MACRO01 once a real FOMC meeting calendar exists.
- A debt-ceiling event study; regime-duration; regime-conditional
  cross-sectional performance.

**8 real papers now exist** (2 layer-2 dimensions, all 5 layer-3 dimensions,
plus the redundancy check) — the free-data potential in what's readily
fetchable is largely mined for a first pass. Composite design is next.
