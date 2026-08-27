# Sleeve driver decomposition (H-SECT03)

Status: concluded-rejected (no single driver dominates — a real, useful null, not a failure; see Observation log)
Version: v0.2
Registered: 2026-08-27
Concluded: 2026-08-27

H-SECT02 confirmed 6 sleeves (`XLU`, `XLP`, `QQQ`, `XLY`, `DIA`, `GLD`)
real-correlate with the *composite* macro score. This asks which single
real driver is actually doing the work for each — the composite mixes
13 factors, so "correlates with the composite" doesn't say whether a
sleeve is reacting to real yields, credit stress, volatility, or
inflation expectations specifically. Design-first, same discipline as
H-SECT01/02.

## Universe

The 6 sleeves H-SECT02 confirmed (dropping the 6 that showed no real
signal — not re-testing a null result against new drivers, real
follow-up work should stay targeted). 4 candidate real drivers, chosen
for a named prior mechanism each, not an exhaustive sweep:

| Driver | Series | Prior mechanism |
| --- | --- | --- |
| Real yield | `DFII10` (10Y TIPS) | Duration sensitivity — should hit `QQQ`/`XLY` (growth) hardest |
| Credit stress | `BAMLH0A0HYM2` (HY OAS) | Risk-off liquidity — should hit defensives (`XLU`/`XLP`) and `DIA` |
| Volatility | `VIXCLS` | General stress, the most "composite-like" single driver |
| Inflation expectations | `T10YIE` (10Y breakeven) | Named prior for `GLD` specifically |

Each driver z-scored against its own trailing 60-day history (real
`(latest − trailing_mean) / trailing_stdev`, same formula and window
convention `scoring_v3.py` already uses for `DFII10`/`VIXCLS`; `T10YIE`
and `BAMLH0A0HYM2`'s window matched to `VIXCLS`'s for consistency since
neither has an established window elsewhere for this specific test —
disclosed, not tuned).

## Thesis

For at least some of the 6 sleeves, one driver's real IC with that
sleeve's forward relative return is materially stronger than the
others — i.e. the composite's aggregate signal is traceable to a real,
specific, named mechanism, not diffuse across all 13 factors equally.
No sign assumed per driver/sleeve pair going in — real IC, sign read
off the result, same convention as H-SECT02.

Falsified by: after correction across all 24 (6 sleeves × 4 drivers,
pooled across both forward windows within a driver — see Method), no
driver clears significance for a sleeve materially better than the
others, or the pattern doesn't match any named prior mechanism.

## Method

Same 21-day stride, same two forward windows (63/126) as H-SECT02.
6 sleeves × 4 drivers × 2 windows = 48 raw tests; Benjamini-Hochberg
correction across all 48 together (not per-driver), same standard as
every other multi-test paper in this project.

## What would count as a real checkpoint

One real run of `research_lab/sleeve_driver_decomposition.py` against
the sealed dataset, producing the full 48-test panel.

## Promotion criteria

Informative regardless of outcome — even a null (no single driver
dominates, composite outperforms any one factor) is a real, useful
finding about the composite's own design (H-MACRO08's redundancy logic
working as intended). Not itself gating anything further; feeds
interpretation of H-SECT02, not a new production surface.

## Observation log

| Date | Checkpoint | Reading |
| --- | --- | --- |
| 2026-08-27 | Real run, `research_lab/sleeve_driver_decomposition.py`, same dataset as H-SECT02. 48 tests (6 sleeves x 4 drivers x 2 windows), Benjamini-Hochberg corrected. | **Rejected — no driver dominates.** Only 1 of 48 survived correction (`XLU` vs. real yield, 63d, r=+0.219, adj_p=0.0211) — *below* the ~2.4 a 5% false-discovery-rate baseline predicts by chance alone. This is a real, useful null, not a failure: it means H-SECT02's confirmed sleeve sensitivities are genuinely composite-level effects, not reducible to any one of these 4 named factors — consistent with, and indirectly supporting, H-MACRO08's original finding that the redundancy-aware 3-cluster composite carries real information no single raw indicator does on its own. |
| 2026-08-27 | Disclosed limitation, not a retraction | `BAMLH0A0HYM2` (credit spread) tests only had n=27-30 — this project's vintage-correct fetch only reaches 2023-2026 for that series (same real limitation already disclosed in `macro-research/README.md`'s "Fetched, not yet tested" table). Its non-significance here is underpowered, not informative — a real absence-of-evidence, not evidence-of-absence, for the credit-stress mechanism specifically. |
