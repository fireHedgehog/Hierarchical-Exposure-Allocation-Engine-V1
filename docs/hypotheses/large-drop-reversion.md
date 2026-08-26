# Large one-day drop reversion (H-CRASHREV01)

Status: preregistered
Version: v0.1
Registered: 2026-08-26

Not wired into any pipeline stage. Preregistered from a second informal claim
the user came across alongside H-GAPFILL01: every year SPY has a day down
over 3%, and within a few days it "definitely" fills back.

Related to, but a genuinely different claim from, `short-term-mean-
reversion.md` (H-STREV01, already confirmed) — H-STREV01 tested the *average*
forward-return relationship across every staging symbol's ordinary trailing
weekly return, and found a real but modest effect (r=-0.057 at 1 week). This
claim is narrower and much stronger: SPY specifically, conditioned on an
*extreme* single-day move (>=3%, not an ordinary weekly return), and claims
near-certain full recovery, not just a positive average tilt. Reusing
H-STREV01's confirmed result here would overclaim what it actually showed —
a real average reversal effect does not imply "definitely recovers," and
this paper exists specifically to check that stronger claim on its own
terms, at its own specification.

## Thesis

When SPY has a single trading day with a close-to-close return of -3% or
worse, price recovers to at least the pre-drop closing level within a short,
disclosed window, at a rate meaningfully higher than an unconditional
baseline — not necessarily "definitely" (100%), but real, and higher than
what an ordinary short-term reversal effect alone (H-STREV01's r=-0.057)
would predict.

This would be falsified by a recovery rate not meaningfully different from
the unconditional baseline rate of SPY trading back up to any given
reference level within the same window (same non-negotiable baseline-
comparison discipline as H-GAPFILL01 — SPY's real long-run upward drift
means a high raw recovery rate is not automatically evidence of a real,
drop-specific effect).

## Prior

H-STREV01 (already confirmed, this folder): a real, modest, average reversal
effect exists at the ~1-week horizon across the whole staging universe under
ordinary conditions. Whether that same mechanism strengthens, weakens, or
disappears when conditioned on a genuinely extreme single-day move is an
open, separate, testable question — extreme moves are exactly where market-
microstructure explanations (forced selling, gap-driven liquidity, VIX
spikes) sometimes behave differently from the average case, in either
direction.

## What would count as a real checkpoint

Computed via `backend/research_lab/large_drop_reversion.py` (read-only
against the sealed dataset, real close prices, full 2004-2026 SPY history —
long enough to include multiple real >=3% single-day drops across different
regimes, including 2008 and 2020):

- **Drop:** a real single trading day with close-to-close return <= -3%.
- **Recovered:** the real close (or, as a looser secondary check, the real
  intraday high) on any day within the window reaches or exceeds the
  pre-drop closing level.
- **Window:** three real windows tested, since "a few days" is vague and a
  3% single-day move is a larger event than an ordinary gap — 5, 10, and 20
  trading days.
- **Baseline:** the same recovery-rate calculation computed unconditionally
  over the same real SPY history, for direct comparison, at each window.
- **Sample size, disclosed honestly up front:** real >=3% single-day drops
  in SPY are rare events (a handful to a few dozen across 2004-2026,
  clustered in 2008/2020/other real stress episodes) — this will be a small-
  N test by construction, not a large pooled one like most other papers in
  this folder. A small real sample is still a real result; it is disclosed
  here so a wide confidence interval isn't later mistaken for a weak effect.

## Promotion criteria

A real, meaningful gap between the conditional recovery rate and the
unconditional baseline, at more than one window, given the honestly small
sample size named above. Given how few real qualifying days exist, this
paper may conclude with a real but wide-uncertainty finding rather than a
sharp one — stated as such, not forced into false precision.

## Observation log

| Date | Checkpoint | Reading | Note |
| --- | --- | --- | --- |
