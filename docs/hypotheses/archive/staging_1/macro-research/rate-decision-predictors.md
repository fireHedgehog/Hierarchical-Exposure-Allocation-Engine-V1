# Rate decision predictors (H-MACRO01)

Status: observing
Version: v0.1
Registered: 2026-08-27

Layer 1 vs. layer 2's Rate dimension ([framework](README.md)): does each
free input signal's level, ahead of a real rate decision, actually predict
the direction?

## Thesis

Real ground truth, derived from data, not hand-curated: every day the Fed
funds target level changes is a real hike (+1) or cut (-1) event —
`DFEDTAR` (pre-2008-12-16) + `DFEDTARU`/`DFEDTARL` midpoint (after) give one
continuous real series, 2004-2026. **Holds are deliberately not classified
in this v1** — that needs a real FOMC meeting calendar, which isn't a FRED
series and isn't built yet. Disclosed, not hidden: this paper only answers
"hike vs. cut," not "act vs. hold."

For each layer-1 indicator: does its level (nearest real prior observation)
ahead of an event correlate with the event's direction?

## Method

`research_lab/rate_decision_predictors.py`. Real Pearson test per indicator,
Benjamini-Hochberg corrected across all testable indicators together. A
result is only computed if the indicator has at least 10 real events inside
its own real data-coverage window — below that, marked not done with the
real reason, never force-filled.

## Results

| Indicator | Result | Note |
| --- | --- | --- |
| NFCI | r=-0.476, adj. p=0.005 | **Significant.** Looser conditions → hike; tighter → cut. n=54. |
| VIXCLS | r=-0.405, adj. p=0.012 | **Significant.** Higher vol → cut. n=54. |
| T10YIE | r=+0.430, adj. p=0.008 | **Significant.** Higher breakeven inflation → hike. n=54. |
| T5YIE | r=+0.457, adj. p=0.005 | **Significant.** Same, shorter tenor. n=54. |
| ICSA | r=-0.253, adj. p=0.261 | Not significant. n=54. |
| MTSDS133FMS | r=-0.158, adj. p=0.571 | Not significant. n=54. |
| WTREGEN | r=-0.114, adj. p=0.571 | Not significant. n=54. |
| DFII10 | r=-0.111, adj. p=0.571 | Not significant. n=54. |
| PCEPILFE | r=-0.112, adj. p=0.571 | Not significant. n=54. |
| CPIAUCSL | r=-0.110, adj. p=0.571 | Not significant. n=54. |
| PAYEMS | r=-0.123, adj. p=0.571 | Not significant. n=54. |
| GDPC1 | r=-0.101, adj. p=0.583 | Not significant. n=54. |
| DGS10 | r=+0.135, adj. p=0.571 | Not significant. n=54. |
| WALCL | r=+0.150, adj. p=0.571 | Not significant. n=54. |
| INDPRO | r=-0.053, adj. p=0.826 | Not significant. n=54. |
| PPIACO | r=-0.032, adj. p=0.913 | Not significant. n=54. |
| DGS30 | r=+0.019, adj. p=0.941 | Not significant. n=54. |
| DFII30 | r=-0.259, adj. p=0.531 | Not significant. **n=31**, not 54 — real coverage starts 2010, pre-2010 hikes excluded. |
| SOFR | r=+0.004, adj. p=0.983 | Not significant. **n=25** — real coverage starts 2018. |
| IORB | r=-0.303, adj. p=0.571 | Not significant. **n=17** — real coverage starts 2021 (renamed from IOER). |
| BAMLH0A0HYM2 | **not done** | Only 6 real events fall inside this indicator's real coverage window (starts 2023-08-28) — need ≥10. Too little history, not a design mismatch. |
| BAMLC0A0CM | **not done** | Same — only 6 real events since 2023-08-28. |

## Reading this

4 of 22 significant, all market-based/forward-looking (financial conditions,
volatility, breakeven inflation) — none of the slower macro releases (CPI,
PPI, payrolls, GDP) individually predicted direction on their own at this
event-level test. A real, plausible pattern, not yet a conclusion: single-
indicator IC, no redundancy check between NFCI/VIXCLS/T10YIE/T5YIE run yet
(queued — see [framework](README.md)'s incremental-value step, since these
four could easily be projections of one latent "market stress/inflation
expectation" factor rather than four independent signals).

## Promotion criteria

Not claimed. This is one real run, hike vs. cut only, no hold
classification, no redundancy check yet, and no out-of-sample split. A real
candidate for `macro_regime_composite`'s Rate dimension only after the
redundancy check and a hold-inclusive version exist — `macro_regime_composite`
itself stays frozen at naive-v2 regardless (see the subfolder README).

## Observation log

| Date | Checkpoint | Reading |
| --- | --- | --- |
| 2026-08-27 | First real run, 54 derived events, 22 candidate indicators | See Results table above. |
