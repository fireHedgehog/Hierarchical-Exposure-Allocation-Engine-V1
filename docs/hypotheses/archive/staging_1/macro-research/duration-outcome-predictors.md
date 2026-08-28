# Duration outcome predictors (H-MACRO06)

Status: observing
Version: v0.1
Registered: 2026-08-27

Layer 1 vs. layer 3's Duration dimension ([framework](README.md)): does
each free input signal predict `DGS10`'s own forward 13-week change?
Falling yield = bond bull, rising = bond bear. Same continuous-target
method as H-MACRO02/04/05.

## Results

18 of 23 significant — the richest single result in this folder so far.
Two distinct, coherent stories, not one:

**Rate-level variables mean-revert** (elevated level now → yield falls
forward):

| Indicator | r | n |
| --- | --- | --- |
| IORB | -0.577 | 241 |
| DFII30 | -0.313 | 814 |
| DFII10 | -0.279 | 1077 |
| DGS30 | -0.270 | 1077 |
| SOFR | -0.247 | 408 |
| BAMLH0A0HYM2 / BAMLC0A0CM | -0.189 both | 137 |
| DFEDTARU / DFEDTARL | -0.091 both | 873 |
| DFEDTAR | -0.075 | 1077 |

**Growth/inflation fundamentals show continuation** (higher reading now →
yield rises further):

| Indicator | r | n |
| --- | --- | --- |
| WTREGEN | +0.267 | 1076 |
| WALCL | +0.242 | 1076 |
| GDPC1 | +0.118 | 1077 |
| PCEPILFE | +0.113 | 1077 |
| CPIAUCSL | +0.107 | 1077 |
| PPIACO | +0.099 | 1077 |
| T5YIE | +0.077 | 1077 |

Not significant: INDPRO, PAYEMS, NFCI, VIXCLS, MTSDS133FMS, ICSA, T10YIE.

## Reading this

A coherent bond-market split: things that are already *elevated rate
levels* pull back toward the mean (rates don't stay extreme forever), while
things that measure *fundamental pressure* (growth, inflation, Treasury
supply via WTREGEN/WALCL) predict continued upward pressure — two real,
different mechanisms, not contradictory. Redundancy not checked (the 4
mean-reversion-side rate variables are plausibly one story; the 4
fundamentals-side variables plausibly another).

## Promotion criteria

Not claimed — same open items as the rest of this folder: no redundancy
check, no OOS split. `macro_regime_composite` stays frozen regardless.

## Observation log

| Date | Checkpoint | Reading |
| --- | --- | --- |
| 2026-08-27 | First real run, 10Y yield forward 13-week change, 23 candidate indicators | See Results tables above. |
