# Equity outcome predictors (H-MACRO03)

Status: observing
Version: v0.1
Registered: 2026-08-27

Layer 1 vs. layer 3's Equity dimension ([framework](README.md)): does each
free input signal predict SPY's own forward return — and a direct test of
the user's own intuition (stress today → policy intervention → rally, i.e.
"bad news is good news at t-1").

## Thesis

If a real Fed-put-style mechanism exists, a stress indicator's level should
correlate *positively* with SPY's forward return (stress precedes
intervention precedes a rally) — the opposite of the naive "bad news is bad
news" sign. Real, pooled, continuous IC per indicator, two forward windows
(1m/3m), `research_lab/equity_outcome_predictors.py`.

## Results (3-month forward window; 1-month mostly agrees in sign, weaker)

| Indicator | r | Direction | Note |
| --- | --- | --- | --- |
| BAMLH0A0HYM2 | +0.675 | Wider spread → **higher** return | n=137, confined to 2023-2025 |
| BAMLC0A0CM | +0.567 | Same | n=137, same caveat |
| IORB | +0.470 | Higher rate → higher return | n=242 |
| ICSA | +0.203 | **More** claims (weaker labor) → higher return | n=1081, full history |
| WTREGEN | +0.185 | — | n=1081 |
| VIXCLS | +0.129 | **Higher fear → higher return** | n=1081, full history — the user's own hypothesis, directly |
| WALCL | +0.143 | — | n=1081 |
| PCEPILFE | +0.132 | Higher inflation → higher return | n=1081 |
| CPIAUCSL | +0.116 | Same direction | n=1081 |
| GDPC1 | +0.106 | — | n=1081 |
| INDPRO | -0.163 | **Stronger growth → lower return** ("good news is bad news") | n=1081 |
| T10YIE | -0.154 | **Lower breakeven → higher return** | n=1081 — the other half of the user's hypothesis |
| DGS10 | -0.133 | — | n=1081 |
| MTSDS133FMS | -0.139 | — | n=1081 |
| NFCI | -0.129 | **Tighter conditions → lower return** (opposite of VIX) | n=1081 |
| T5YIE | -0.128 | — | n=1081 |
| DGS30 | -0.109 | — | n=1081 |
| DFEDTAR | -0.113 | — | n=1081 |
| DFII10 | -0.090 | — | n=1081 |
| PPIACO / PAYEMS / SOFR / DFEDTARU / DFEDTARL / DFII30 | — | Not significant | |

All 24 candidates ran — no "not done" rows; SPY's daily history and the
5-day stride gave every indicator, even 3-year ones, enough samples.

## Reading this — directly against the user's hypothesis

**VIX confirms it cleanly**: higher fear *predicts higher* forward
return, both windows, full 22-year history — the real "bad news is good
news" pattern, not a guess. **Breakeven inflation confirms the other half**:
lower T10YIE predicts higher forward return, matching "...but T10YIE down."

**NFCI does not fit the same story** — it's *negatively* correlated
(tighter conditions → lower forward return), the naive "bad news is bad
news" direction, opposite of VIX. Two stress gauges, opposite signs. Not
glossed over: NFCI is a slower, composite index; VIX is a fast, market-
priced one — plausibly capturing continuation vs. reversal at different
horizons, but that's a real, separate hypothesis, not asserted here.

**Growth/inflation data adds a second real pattern**: INDPRO negative
(strong growth → lower return, "good news is bad news," a hawkish-Fed
story) while CPI/PCE are positive — worth a dedicated redundancy pass, not
force-explained here.

## Promotion criteria

Not claimed. Real, striking, economically legible correlations, but: no
redundancy check (VIX/NFCI/T10YIE/T5YIE/credit-spreads/INDPRO are likely
several overlapping stories, not six independent ones), no OOS split, and
the credit-spread/IORB results share the same short-window caveat as
H-MACRO01/02. `macro_regime_composite` stays frozen regardless.

## Observation log

| Date | Checkpoint | Reading |
| --- | --- | --- |
| 2026-08-27 | First real run, SPY forward 1m/3m return, 24 candidate indicators | See Results table above. |
