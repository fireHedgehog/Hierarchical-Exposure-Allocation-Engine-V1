# Balance sheet predictors (H-MACRO02)

Status: observing
Version: v0.1
Registered: 2026-08-27

Layer 1 vs. layer 2's Balance sheet dimension ([framework](README.md)): does
each free input signal predict `WALCL`'s subsequent direction?

## Thesis

Balance sheet is a continuous stock, unlike Rate's discrete FOMC steps — a
naive weekly up/down "event" would mostly capture routine operational
noise (reserve-management bill purchases, technical reinvestment), the
exact conflation the framework README flags (Balance sheet ≠ Liquidity;
never collapse to `QE=true`). So this paper deliberately uses a different,
better-fitting test: real, pooled, continuous IC — does each indicator's
level predict `WALCL`'s own forward 13-week (~1 quarter) % change?

## Method

`research_lab/balance_sheet_predictors.py`. `WALCL`'s weekly observations,
sampled every 4 weeks (stride, controls overlap). Real Pearson test per
indicator vs. that sample date's forward 13-week change, Benjamini-Hochberg
corrected. Rate series (`DFEDTAR`/`U`/`L`) are legitimate candidates here —
cross-dimension prediction is a real question, not excluded.

## Results

| Indicator | Result | Note |
| --- | --- | --- |
| IORB | r=-0.671, adj. p<0.0001 | **Significant.** n=63 (real coverage from 2021). |
| BAMLC0A0CM | r=-0.658, adj. p=0.0002 | **Significant.** n=36 — real, but entirely inside 2023-2025's QT era; may be regime-specific, not a universal relationship. |
| BAMLH0A0HYM2 | r=-0.535, adj. p=0.0026 | **Significant.** Same n=36 caveat. |
| DFII30 | r=-0.258, adj. p=0.0010 | **Significant.** n=212. |
| DFEDTARU | r=-0.243, adj. p=0.0010 | **Significant.** n=228. |
| DFEDTARL | r=-0.243, adj. p=0.0010 | **Significant.** Identical to DFEDTARU — expected, the range moves together. |
| SOFR | r=-0.310, adj. p=0.0037 | **Significant.** n=106. |
| NFCI | r=+0.202, adj. p=0.0026 | **Significant.** Tighter conditions → larger forward expansion (real, plausible: QE-in-stress pattern). n=281. |
| PCEPILFE | r=-0.142, adj. p=0.0460 | **Significant.** Higher core inflation → forward contraction. n=281. |
| GDPC1 | r=-0.138, adj. p=0.0504 | Borderline, not significant. n=281. |
| CPIAUCSL | r=-0.127, adj. p=0.0662 | Not significant. n=281. |
| VIXCLS | r=+0.127, adj. p=0.0662 | Not significant. n=281. |
| PAYEMS | r=-0.115, adj. p=0.0925 | Not significant. n=281. |
| ICSA | r=+0.121, adj. p=0.0795 | Not significant. n=281. |
| WTREGEN | r=-0.087, adj. p=0.2321 | Not significant. n=281. |
| INDPRO / PPIACO | r≈-0.074 both, adj. p=0.2970 | Not significant. n=281. |
| DGS10 | r=-0.066, adj. p=0.3374 | Not significant. n=281. |
| DFII10 | r=-0.057, adj. p=0.4091 | Not significant. n=281. |
| T10YIE | r=-0.047, adj. p=0.4974 | Not significant. n=281. |
| DGS30 | r=-0.035, adj. p=0.6124 | Not significant. n=281. |
| T5YIE | r=-0.073, adj. p=0.2970 | Not significant. n=281. |
| MTSDS133FMS | r≈0.000, adj. p=0.9963 | Not significant. n=281. |
| DFEDTAR | r=-0.008, adj. p=0.9276 | Not significant. n=281. |

No "not done" rows this time — the continuous framing gave even the
shortest-history series (credit spreads, n=36; SOFR, n=106) enough pooled
samples to clear the floor, unlike H-MACRO01's discrete-event framing where
they were the ones left undone. The test shape matters as much as the data.

## Reading this

10 of 23 significant (vs. 4 of 22 for Rate) — real, and a coherent story:
rate-level and credit-tightening signals predict forward contraction,
NFCI's stress signal predicts forward expansion. Not yet a conclusion:
redundancy check not run (DFEDTARU/DFEDTARL are trivially collinear by
construction; IORB/SOFR/DFII30 likely correlated with each other and with
the rate series); the two credit-spread results are real but confined
entirely to one regime window (2023-2025 QT era) and could be an artifact
of that specific period rather than a durable relationship.

## Promotion criteria

Not claimed. Redundancy check and a longer-regime replication (once more
history accumulates past this QT cycle) needed before this is a real
candidate for anything. `macro_regime_composite` stays frozen regardless.

## Observation log

| Date | Checkpoint | Reading |
| --- | --- | --- |
| 2026-08-27 | First real run, WALCL forward 13-week change, 23 candidate indicators | See Results table above. |
