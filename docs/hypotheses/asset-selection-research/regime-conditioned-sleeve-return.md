# Regime-conditioned sleeve relative return (H-SECT02)

Status: concluded-confirmed (out-of-sample replicated for XLU/XLP; QQQ/XLY/DIA strengthen OOS; GLD weakens OOS but same sign — see Observation log)
Version: v0.3
Registered: 2026-08-27
Concluded: 2026-08-27

Design-first, same discipline as H-SECT01. Picked over #2/#4/#5/#6 from
the folder's 7-question framework because it's the one that actually
tests a *different* mechanism than H-SECT01's rejected claim: H-SECT01
asked whether a sleeve's own past return predicts its future return
(trend continuation); this asks whether the macro *state* — independent
of the sleeve's own trend — predicts which sleeve outperforms. A real,
separate hypothesis, not a re-run of the rejected one with new
decoration.

## Universe

The 13-asset real sleeve universe from this folder's README ("Real
universe" section): `SPY` as benchmark; 12 candidate sleeves — `GLD`,
`QQQ`, `DIA`, `XLB`, `XLE`, `XLF`, `XLI`, `XLK`, `XLP`, `XLU`, `XLV`,
`XLY`. All confirmed real, identical 2004-12-01 to 2026-08-26 history.

## Thesis

A sleeve's forward relative return, `R_sleeve − R_SPY`, over the next
3 or 6 months is real-correlated with `macro_regime_composite`'s score
today — i.e. `E[R_sleeve − R_SPY | macro state]` is a real, non-zero,
sleeve-specific function of state, not just noise around zero. This is
a plausibility-consistent thesis (real-yield-sensitive sleeves like
`QQQ`/`XLK` underperforming when the composite is stressed; defensive
sleeves like `XLU`/`XLP` or `GLD` outperforming) but the test doesn't
assume a sign per sleeve going in — it's a real correlation test, sign
read off the result.

Falsified by: after Benjamini-Hochberg correction across all 24 tests
(12 sleeves × 2 windows), the number of significant results isn't
meaningfully above what a 5% false-discovery-rate baseline would
produce by chance alone (~1 of 24).

## Method

Same real point-in-time composite series as H-SECT01's regime bucketing
(historical recompute via `compute_regime_v3`, anchored on `CPIAUCSL`'s
own observation dates). For each sleeve and each forward window (63,
126 trading days): continuous IC (Pearson) between the composite score
at date *t* and `(R_sleeve − R_SPY)` over `[t, t+window]`, sampled at a
21-trading-day stride (~monthly) — same `STRIDE_DAYS` convention as
`composite_forward_risk.py`, needed here because this *is* a
correlation-style test (unlike H-SECT01's episode extraction, which
correctly used no stride). Benjamini-Hochberg correction across the
resulting 24 p-values (`engine/research/significance.py`, already
proven on this project's other multi-test research runs). For any
sleeve/window that survives correction, also report the real mean
relative return by regime tercile (stressed/neutral/calm) — the direct
`E[R_sleeve − R_SPY | state]` reading, for interpretability.

## What would count as a real checkpoint

One real run of `research_lab/regime_conditioned_sleeve_return.py`
against the sealed 2004-2026 dataset, producing the full 24-test
IC/p-value table plus the corrected significance flags.

## Promotion criteria

A confirmed sleeve-level sensitivity here is quotable on its own
(real, useful context for manual sleeve tilting) but does not by
itself justify an automated regime-conditioned allocation rule. That
would need a separate, later hypothesis: a real out-of-sample backtest
comparing a regime-tilted sleeve allocation against equal-weight/static
on Sharpe, drawdown, and turnover — scoped, not designed in detail
here, and only worth doing if this paper confirms the underlying
correlation exists at all. It does (see below) — recommended next step,
not started.

## Observation log

| Date | Checkpoint | Reading |
| --- | --- | --- |
| 2026-08-27 | Real run, `research_lab/regime_conditioned_sleeve_return.py`, dataset `real-macro-f7bd88ff-07eb-46d3-877f-701968666524`. 12 sleeves x 2 windows = 24 tests, Benjamini-Hochberg corrected, monthly-strided (n=252-255 per test). | **Confirmed, strong: 11 of 24 significant after correction — a 5% false-discovery-rate baseline predicts ~1.2 by chance alone.** Every significant sleeve's sign matches a plausible, known mechanism, not an unexplained pattern: defensives and gold outperform SPY when the composite is stressed; growth/cyclical sleeves outperform when it's calm. See table below. |

**Significant sleeves (adjusted p < 0.05), by |r|, with regime-tercile mean relative return:**

| Sleeve | Window | r | adj_p | Stressed | Calm | Reading |
| --- | --- | --- | --- | --- | --- | --- |
| XLU (utilities) | 126d | -0.285 | 0.0001 | +3.37% | -2.16% | Defensive — outperforms SPY when stressed |
| XLP (staples) | 126d | -0.254 | 0.0005 | +2.31% | -3.51% | Defensive — same pattern |
| XLU | 63d | -0.225 | 0.0023 | +2.13% | -1.56% | Confirms 126d at the shorter window |
| XLY (discretionary) | 63d | +0.215 | 0.0032 | -1.35% | +0.66% | Cyclical — underperforms SPY when stressed |
| DIA (Dow 30) | 126d | -0.208 | 0.0043 | +0.59% | -1.21% | Relative safe-haven vs. SPY (less mega-cap-growth weight) |
| GLD (gold) | 126d | -0.204 | 0.0044 | +7.64% | -5.43% | Largest effect — classic flight-to-gold in stress |
| XLP | 63d | -0.199 | 0.0049 | +1.65% | -1.46% | Confirms 126d |
| XLY | 126d | +0.192 | 0.0065 | -2.20% | -0.67% | Confirms 63d |
| DIA | 63d | -0.184 | 0.0087 | +0.64% | -0.93% | Confirms 126d |
| QQQ | 63d | +0.170 | 0.0155 | -0.16% | +2.08% | Duration-sensitive — underperforms SPY when stressed |
| QQQ | 126d | +0.144 | 0.0481 | +0.22% | +2.78% | Confirms 63d, weaker |

`XLE` and `XLV` were close but didn't survive correction (adj_p 0.056-0.075) — disclosed as real near-misses, not folded into the confirmed set. `XLB`, `XLF`, `XLI`, `XLK` showed no real signal (adj_p > 0.19).

**Caveat, same shape as H-MACRO09 before its own OOS follow-up:** this is one in-sample pass, no chronological split yet. The result is economically coherent (every sign matches a known mechanism — defensive rotation, gold-as-hedge, growth/duration sensitivity) rather than an unexplained pattern, which lowers the risk this is a pure multiple-comparisons artifact, but doesn't replace an actual out-of-sample check.

| 2026-08-27 | Out-of-sample split, `research_lab/regime_conditioned_sleeve_return_oos.py`. Same 2019-01-01 chronological split H-MACRO09 used, full 24-test panel re-run independently on each half (no refitting). In-sample 2004-2018 (n≈3,545 days), out-of-sample 2019-2026 (n≈1,923 days). | **Three real patterns, disclosed separately rather than averaged into one verdict:** |

| Pattern | Sleeves | Reading |
| --- | --- | --- |
| Robust both halves | `XLU`, `XLP` | Significant, same sign, both windows, both halves — the strongest, most durable finding. Defensive rotation isn't a full-sample artifact. |
| Strengthens out-of-sample | `QQQ`, `XLY`, `DIA` | Same sign both halves, but only cleared significance in 2019-2026 (e.g. `QQQ` 63d: r=+0.106 n.s. in-sample → r=+0.283 SIG out-of-sample). Consistent direction, not a sign flip — plausibly real (mega-cap tech concentration in `QQQ`/growth exposure rose over the sample), not overfitting-shaped, but weaker evidence than the robust pair. |
| Weakens out-of-sample, same sign | `GLD` | Significant in-sample (r=-0.265, driven substantially by 2008) but not out-of-sample (r=-0.142, still same sign, still includes 2020/2022). The full-sample number likely overstates how reliable gold's stress-hedge behavior is going forward. |

Net: the defensive-rotation core (`XLU`/`XLP`) is the one piece of this paper that clears the same bar H-MACRO09 did. The rest is real but should be weighted down accordingly in any follow-up allocation test, not treated as equally strong evidence.
