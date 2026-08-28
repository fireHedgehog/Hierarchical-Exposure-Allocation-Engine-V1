# Indicator redundancy (H-MACRO08)

Status: observing
Version: v0.1
Registered: 2026-08-27

The prerequisite before any composite ([framework](README.md)): are the
indicators tested across H-MACRO01-07 really ~20+ independent signals, or a
much smaller number of latent factors under different names? Real pairwise
correlation + effective-number-of-bets (`signal_validation.py`, already
proven on the original 8 macro factors, ENB=2.43).

## Method

`research_lab/macro_indicator_redundancy.py`. Two honest passes, not one
forced window — pooling would either truncate 20 years of real history or
silently drop the shortest-history series:

- **Deep-history pass**: 17 indicators with ~full 2004-2026 coverage, n=283
  aligned dates.
- **Recent pass**: all 23 indicators (adds credit spreads, SOFR, IORB,
  DFII30, DTWEXBGS), bounded to the shortest real history in the set
  (2023-08-28+), n=39.

## Results

**Deep-history: 17 raw indicators → 4.13 effective independent bets.**
21 pairs flagged redundant (|r| ≥ 0.7). The dominant cluster is inflation/
growth: CPIAUCSL, PCEPILFE, GDPC1, PAYEMS, PPIACO, WALCL all pairwise ≥0.77
(CPIAUCSL↔PCEPILFE: r=+0.998) — six names, one real signal. Rates cluster
separately (DGS10↔DGS30: +0.956; DFII10↔DGS10/30: +0.89-0.94).
NFCI↔VIXCLS: +0.744 — the two "market stress" indicators that showed
opposite signs in H-MACRO03/04 are still real-correlated in level.

**Recent (2023-2025): 23 indicators → 3.46 effective independent bets.**
62 redundant pairs — even more collapsed, smaller sample and a single
regime doing the flattening. Notable: IORB↔SOFR r=+0.996 (mechanically
linked by design, not a finding); BAMLC0A0CM↔BAMLH0A0HYM2 r=+0.965 (same
credit complex, expected).

## Reading this — what this means for the composite

Real, load-bearing finding: roughly **4 independent factor clusters**, not
17-26 indicators:

1. **Inflation/growth** — CPI, core PCE, PPI, GDP, payrolls, and (loosely)
   the balance sheet all move together.
2. **Rate level** — 10Y/30Y nominal and real yields.
3. **Market stress** — NFCI, VIX (correlated in level, r=+0.744, even
   though H-MACRO03/04 found they predict *different* signs of forward
   outcomes — a real, unresolved tension between "how correlated are they
   now" and "do they predict the same thing," worth its own note, not
   glossed over).
4. **Policy operations** — TGA/WALCL, IORB/SOFR (the latter two are the
   same rate by construction).

A composite built from the raw 17-26 indicators would double-, triple-, or
sextuple-count cluster 1 alone. A real composite should draw from these ~4
clusters (one representative or a real within-cluster average each), not
the raw list — this is the concrete input the human+agent composite design
needs.

## Promotion criteria

Not a strategy candidate — this is a methodology finding for how any future
composite gets built, not itself a predictive signal. `macro_regime_composite`
stays frozen regardless.

## Observation log

| Date | Checkpoint | Reading |
| --- | --- | --- |
| 2026-08-27 | First real run, two passes (deep-history n=283, recent n=39) | See Results above. ENB 4.13/17 (deep), 3.46/23 (recent). |
