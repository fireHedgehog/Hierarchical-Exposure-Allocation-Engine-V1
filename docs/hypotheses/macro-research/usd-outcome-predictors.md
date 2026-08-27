# USD outcome predictors (H-MACRO07)

Status: observing
Version: v0.1
Registered: 2026-08-27

Layer 1 vs. layer 3's USD dimension ([framework](README.md)): does each
free input signal predict `DTWEXBGS` (trade-weighted broad dollar
index)'s own forward 13-week change? New series added for this paper —
real, free, 2006-2026 (verified live before use, same discipline as every
other series in this folder).

## Results

15 of 24 significant. Two groups, and the second one connects to
H-MACRO06's own finding:

**Growth/activity → dollar strengthens forward:**

| Indicator | r | n |
| --- | --- | --- |
| INDPRO | +0.220 | 1023 |
| PPIACO | +0.133 | 1023 |
| MTSDS133FMS | +0.110 | 1023 |
| T10YIE | +0.076 | 1023 |
| PAYEMS | +0.075 | 1023 |

**Elevated rate/stress levels → dollar weakens forward:**

| Indicator | r | n |
| --- | --- | --- |
| IORB | -0.260 | 241 |
| DFEDTAR | -0.169 | 1023 |
| ICSA | -0.173 | 1023 |
| DFII10 | -0.151 | 1023 |
| VIXCLS | -0.129 | 1023 |
| DFII30 | -0.118 | 811 |
| DGS30 | -0.111 | 1023 |
| DGS10 | -0.107 | 1023 |
| WTREGEN | -0.078 | 1023 |

Not significant: CPIAUCSL, PCEPILFE, NFCI, GDPC1, T5YIE, BAMLH0A0HYM2,
BAMLC0A0CM, SOFR, DFEDTARU, DFEDTARL, WALCL.

## Reading this

The second group is the same real mean-reversion mechanism H-MACRO06 found,
one layer downstream: elevated rate levels (IORB, real yields, DGS10/30)
predict *falling* rates ahead (H-MACRO06), and falling rates plausibly
predict a *weaker* dollar (rate-differential unwind) — this paper's negative
signs on the same indicators are consistent with that chain, not a separate
coincidence. Not proven as one causal chain here — a real candidate for a
follow-up that tests the chain directly rather than two separate marginal
correlations.

## Promotion criteria

Not claimed. Same open items as the rest of this folder. `macro_regime_composite`
stays frozen regardless — and this paper's own target series (`DTWEXBGS`)
isn't used by it at all today.

## Observation log

| Date | Checkpoint | Reading |
| --- | --- | --- |
| 2026-08-27 | First real run, USD index forward 13-week change, 24 candidate indicators | See Results tables above. |
