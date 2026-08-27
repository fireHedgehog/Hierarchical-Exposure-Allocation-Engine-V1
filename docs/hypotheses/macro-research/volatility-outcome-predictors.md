# Volatility outcome predictors (H-MACRO05)

Status: observing
Version: v0.1
Registered: 2026-08-27

Layer 1 vs. layer 3's Volatility dimension ([framework](README.md)): does
each free input signal predict `VIXCLS`'s own forward change? Two windows
(1m, 1q) since vol mean-reverts faster than a typical macro cycle.

## Results (1-quarter forward window; 1-month mostly weaker/not significant)

| Indicator | r | Note |
| --- | --- | --- |
| BAMLH0A0HYM2 | -0.393, p=0.0000 | **Significant.** Wider spread now → **lower** forward vol. n=142. |
| BAMLC0A0CM | -0.319, p=0.0005 | **Significant.** Same direction. n=142. |
| T5YIE | +0.126, p=0.0002 | **Significant.** Full history, n=1089. |
| T10YIE | +0.121, p=0.0004 | **Significant.** Full history. |
| INDPRO | +0.137, p=0.0001 | **Significant.** Stronger growth → **higher** forward vol — full history. |
| ICSA | -0.113, p=0.0008 | **Significant.** More claims now → lower forward vol. Full history. |
| NFCI | -0.086, p=0.0159 | **Significant.** Tighter conditions now → lower forward vol. Full history. |
| Everything else | — | Not significant. |

At 1-month, only ICSA is significant (r=-0.093) — the pattern is real but
mostly a quarterly-horizon effect, not a monthly one.

## Reading this — a pattern across papers, not just this one

Every significant indicator here except INDPRO points the same way: elevated
stress *now* (wide credit spreads, tight NFCI, high claims) predicts **lower**
forward volatility — mean reversion, not continuation. Read together with
H-MACRO03 (VIX up → higher forward SPY return) and H-MACRO04 (NFCI/VIX up →
narrower forward credit spread), a real, coherent cross-paper story is
forming: market-based stress measures tend to predict *calming*, not further
deterioration, across equity, credit, and volatility alike. Not asserted as
one unified factor yet — that's exactly what the redundancy check across all
four papers needs to test before anyone calls it one thing.

INDPRO breaks the pattern (stronger growth → *higher* forward vol) — matches
H-MACRO03's own INDPRO finding (stronger growth → lower forward equity
return), a real, separate "good news is bad news" story, not a labeling
error.

## Promotion criteria

Not claimed. Same open items as every paper in this folder: no redundancy
check, no OOS split. `macro_regime_composite` stays frozen regardless.

## Observation log

| Date | Checkpoint | Reading |
| --- | --- | --- |
| 2026-08-27 | First real run, VIX forward 1m/1q change, 23 candidate indicators | See Results table above. |
