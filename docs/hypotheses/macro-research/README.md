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

**Queued, not yet built:** an input-signal panel with research cards for
auction tail, bid-to-cover, MOVE, SOFR-IORB, HY/IG spread, breakevens, real
yields, initial claims, NFCI; extending the raw macro factor list with free
FRED series (Fed balance sheet, TGA, 30Y yield, real GDP, federal deficit);
a debt-ceiling-raise event study; regime-duration ("higher for longer, how
long"); regime-conditional cross-sectional performance (connects this folder
to `cross_sectional_momentum`).
