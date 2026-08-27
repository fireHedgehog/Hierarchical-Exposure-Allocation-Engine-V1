# Timing research

Scope: given a position (or an instrument already selected), *when* to
enter/hold/trim/exit — the action layer. Separate from macro regime
(how much total risk to carry) and asset selection (where that risk is
expressed). Same lifecycle and rules as the parent
[`docs/hypotheses/README.md`](../README.md); own index for the same
reason `macro-research/` got one.

## Relation to what's already tested

Most of this layer's testing already happened at the top level, before
this folder existed. These files stay where they are — `schema.sql`,
`research_lab/` scripts, and other papers already reference their
current paths, so moving them would just be churn for no benefit:

- [Short-term mean reversion](../short-term-mean-reversion.md) — confirmed (1-week window). Live as `short_term_reversal_entry` in `macd_rsi_single_name_timing` naive-v3.
- [Short-term reversal cost robustness](../short-term-reversal-cost-robustness.md) — confirmed, cost-sensitive. Survives to 10bps, breaks down 25-50bps.
- [Dow Theory risk-state](../dow-theory-risk-state.md) — confirmed. Broken trend structure predicts higher forward volatility (a risk-context finding, not an entry/exit trigger itself — same reframe pattern as the macro composite).
- [Dow Theory trend structure](../dow-theory-trend-structure.md) — rejected.
- [Opening gap-down fill](../gap-down-fill.md) — rejected.
- [Large one-day drop reversion](../large-drop-reversion.md) — rejected.

This folder is for new timing papers going forward, plus the layered
question map below — written after noticing these existing papers
cluster almost entirely around *entry*, leaving real gaps on exit,
regime-conditioning, and decay.

## The question, compressed

**Timing layer = conditional transaction trigger.** Given a position
already exists (or doesn't), does a real, cost-surviving price-path
condition change the odds enough right now to act — not "will price go
up," but "should I act on it now."

## Candidate framework — 7 sub-questions

| # | Question | Status |
| --- | --- | --- |
| 1 | Entry edge — does a specific price-path condition have real forward edge vs. an unconditional baseline | Tested: short-term reversal confirmed; Dow Theory trend, gap-down, large-drop all rejected |
| 2 | Exit edge — does the exit rule itself have a real, independently-tested edge | **Corrected, 2026-08-27** — RSI(14)>=70's general predictive validity *was* tested and confirmed (milestone 0.29's event study: r=-0.015, adjusted p=0.0012). An earlier version of this table, and a `schema.sql` comment it was copied from, both wrongly said "never tested" — fixed in both places. The real, still-open gap is narrower: RSI's role specifically as an exit *conditional on an open `short_term_reversal_entry` position* (not the unconditional signal 0.29 tested) has not been isolated |
| 3 | Cost/turnover robustness | Tested for the entry rule (confirmed cost-sensitive); not yet tested for the exit rule on its own |
| 4 | Regime-conditional timing — does entry/exit edge strength change across `macro_regime_composite` states (stressed/neutral/calm) | **Answered, confirmed** (see [`short-term-mean-reversion.md`](../short-term-mean-reversion.md)'s regime-conditioned addendum). 1-week reversal real in all 3 regimes, strongest when stressed. 2-week reversal real in stressed/neutral but flips to mild continuation when calm — new information the pooled test alone didn't show |
| 5 | Holding-period / signal decay — real half-life of a *live, triggered* position, not the forward-return window a paper was tested at | Never started; distinct from #1's forward-window choice |
| 6 | False-positive / whipsaw rate — how often a trigger fires with no real payoff, separate from average edge magnitude | Never started |
| 7 | Cross-instrument consistency — does the same entry/exit rule hold across instrument types (single name vs. sector ETF vs. index) | Never started; connects this folder to `asset-selection-research/` |

## Restart-here: open questions, none started yet

| Question | Note |
| --- | --- |
| RSI(14)>=70's conditional-exit role specifically (#2, narrowed) | The unconditional signal is real (0.29). What's untested is whether it still marks a good exit specifically for positions opened by `short_term_reversal_entry` |
| Cost robustness of the exit rule on its own (#3) | Natural pairing with the entry rule's already-confirmed result |
| Regime-conditional entry/exit edge (#4) | **Run, confirmed.** See `short-term-mean-reversion.md`'s addendum. No OOS split yet on this specific breakdown — real next step, not done |
| Signal decay / holding-period distribution (#5) | Never started |
| False-positive / whipsaw rate (#6) | Never started |
| Cross-instrument consistency (#7) | Never started; blocked on `asset-selection-research/` having a defined universe to test against |

## Index

| Paper | Status | Covers |
| --- | --- | --- |
| [VIX-percentile VXX entry timing](vix-percentile-vxx-entry.md) (H-TIME01) | v1 confirmed (partial); v2/v3 inconclusive, v3 weaker than v2 | New real data this paper required: `VXX` added and fetched (real history only reaches 2018, not 2009). v1: days since `VIXCLS` was last elevated real-predicts `VXX`'s forward return (significant, both windows); percentile level does not. v2 (event study): compression episode (VIX <15, 21-day strict streak) vs. VXX/VIX explosion — direction consistent, closest p=0.063 (n=27). v3 (tolerant, sample-floored, single-axis threshold scan, not cherry-picked): real monotonic direction but *weaker* than v2 (best cell adj_p=0.35) — a real fragility finding. Not yet a standalone tradable rule. |
