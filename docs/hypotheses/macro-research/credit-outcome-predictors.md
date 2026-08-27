# Credit outcome predictors (H-MACRO04)

Status: observing
Version: v0.1
Registered: 2026-08-27

Layer 1 vs. layer 3's Credit dimension ([framework](README.md)): does each
free input signal predict `BAMLH0A0HYM2` (HY OAS spread)'s own forward
13-week change? Same continuous-target method as H-MACRO02.

**Real constraint, disclosed up front:** the target's own real point-in-time
history only starts 2023-08-28 (see H-MACRO01's finding), so every result
here is bounded to a ~72-sample, single-regime (2023-2025) window regardless
of any predictor's own longer history. `DFEDTAR` excluded from candidates —
frozen constant in this window (discontinued 2008), not a valid predictor
here.

## Results

| Indicator | r | Note |
| --- | --- | --- |
| BAMLC0A0CM | -0.532, p=0.0000 | **Significant.** IG spread now → narrower HY spread ahead — plausibly credit-complex mean reversion, not a distinct signal. |
| NFCI | -0.478, p=0.0002 | **Significant.** Tighter conditions now → narrower spread ahead — same mean-reversion read as VIX below. |
| T10YIE | +0.455, p=0.0004 | **Significant.** |
| VIXCLS | -0.440, p=0.0006 | **Significant.** Same direction/read as NFCI. |
| T5YIE | +0.395, p=0.0027 | **Significant.** |
| DGS10 | +0.294, p=0.0461 | **Significant.** |
| PAYEMS / WALCL / DGS30 / MTSDS133FMS / DFII10 / others | — | Not significant, n=72 throughout. |

## Reading this

All 6 significant results share n=72 and one real regime (2023-2025) — a
real result, but the narrowest evidentiary base of any paper in this folder
so far. The negative-sign pattern on NFCI/VIXCLS most likely reflects
ordinary mean reversion (spreads were already wide when these were
elevated, and normalized afterward) rather than a distinct predictive
mechanism — flagged, not claimed as discovery. Redundancy not checked
(NFCI/VIXCLS/BAMLC0A0CM plausibly one story).

## Promotion criteria

Not claimed — smallest sample size in this folder, single regime, no
redundancy check. Would need real data outside 2023-2025 to say anything
durable. `macro_regime_composite` stays frozen regardless.

## Observation log

| Date | Checkpoint | Reading |
| --- | --- | --- |
| 2026-08-27 | First real run, HY spread forward 13-week change, 22 candidate indicators | See Results table above. |
