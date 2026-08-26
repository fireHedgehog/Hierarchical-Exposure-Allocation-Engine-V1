# Research hypotheses

A hypothesis starts here, as a versioned working paper — not as a database row. This
folder exists because research itself has a data-structure problem: one candidate
idea's evidence is a nominal category (hawkish/dovish), another's is a continuous
series, another's is a duration ("holds for 1 week vs. 10 weeks"), another's is just
true/false. Forcing every hypothesis into one rigid SQL schema before anyone knows
its real shape is premature structure — the exact mistake this folder replaces (see
`docs/engine-milestones.md` 0.23). A Markdown file has no schema to design in
advance; it can hold whatever shape a specific hypothesis actually needs.

## Lifecycle

1. **Preregister.** Create `<slug>.md` here from the template below. State the thesis,
   what would falsify it, and what counts as a real checkpoint, before collecting
   evidence — the same discipline a real research desk applies before looking at
   data, so the thesis doesn't quietly bend to fit whatever shows up.
2. **Observe.** Append one dated entry per real checkpoint to the paper's observation
   log. If a checkpoint needs a real computed statistic, write an ad-hoc script in
   [`backend/research_lab/`](../../backend/research_lab/README.md) — throwaway code,
   no quality bar, never imported by production, never touches the database — reusing
   this project's hypothesis-agnostic stats utilities where useful
   (`backend/engine/research/significance.py` — Pearson significance,
   Benjamini-Hochberg correction — and `backend/engine/research/signal_validation.py`
   — IC, correlation, effective number of bets). Name the script to match this paper,
   e.g. `warsh_reaction_function.py`.
3. **Reach a conclusion.** A paper concludes when it has enough real checkpoints to
   state, plainly, whether the thesis holds, doesn't hold, or needs a different
   frame — not on a fixed date. `warsh-reaction-function.md` targets roughly 10-20
   checkpoints before treating itself as a candidate classifier rather than a
   narrative.
4. **Graduate, or archive.** A concluded, real thesis gets engineered into the
   pipeline at that point: a `strategies` row, `strategy_components`, real SQL —
   whatever shape *that specific hypothesis* actually turned out to need, decided
   with the full evidence in hand instead of guessed at registration time. A
   thesis that doesn't hold gets marked `archived` in the index below and stays as
   a record of what was tried, not deleted.

This mirrors the same principle the rest of this project already applies at every
other layer (`docs/README.md`'s non-negotiable rules): unknown/undecided stays
unstructured, and research, and engineering are separate gates. This folder is the
gate before research even reaches the DB.

## Index

Dataset column flags which real dataset window a paper's evidence came
from — `2016+` (the pre-0.38 rolling window) or `2004+` (post-0.38, GLD-
anchored, includes 2008) — since the two aren't apples-to-apples and most
of this table predates the longer window. Re-running a `2016+` paper
against `2004+` data is real, queued follow-up work, not yet done, unless
noted otherwise.

| Hypothesis | Type of evidence | Status | Real finding | Dataset |
| --- | --- | --- | --- | --- |
| [Warsh Fed reaction function](warsh-reaction-function.md) | categorical (hawkish/dovish/neutral/inconclusive) per FOMC/speech event | observing | 1 real checkpoint (Jul 2026 FOMC, hawkish); awaiting Jackson Hole | n/a |
| [Time-series momentum](time-series-momentum.md) | continuous (IC vs. real forward return) | concluded-rejected | Opposite direction at every horizon; replicated on 2004-26 but weaker (only 2 of 5 horizons still significant, was 5 of 5) | 2016+, 2004+ |
| [Low-volatility anomaly](low-volatility-anomaly.md) | continuous (IC vs. real forward return) | concluded-rejected (raw return) | Opposite direction — volatile beat calm | 2016+ |
| [Short-term mean reversion](short-term-mean-reversion.md) | continuous (IC vs. real forward return) | concluded-confirmed (1-week window) | Confirmed and strengthened on 2004-26: r=-0.057 (was -0.02), and now significant at 2 weeks too (was not) | 2016+, 2004+ |
| [MAX effect / lottery demand](max-effect-lottery-demand.md) | continuous (IC vs. real forward return) | concluded-rejected | Opposite direction — extreme-max beat calm-max; r=+0.78 with low-vol above, not independent | 2016+ |
| [Dow Theory trend structure](dow-theory-trend-structure.md) | binary (intact/broken) vs. real forward return | concluded-rejected (opposite direction) | Broken beat intact on forward return, replicated on 2004-26 at similar magnitude | 2016+, 2004+ |
| [Dow Theory risk-state](dow-theory-risk-state.md) | binary (intact/broken) vs. real forward volatility | concluded-confirmed | Broken predicts higher forward volatility, replicated and slightly stronger on 2004-26 | 2016+, 2004+ |
| [Vol-scaled cross-sectional momentum](vol-scaled-cross-sectional-momentum.md) | walk-forward equity curve comparison (Sharpe/drawdown) | concluded-inconclusive | Drawdown improvement vs. naive baseline is mostly just lower average exposure, not the timing mechanism | 2004+ |

## Template for a new hypothesis

```markdown
# <Name> (H-<slug>)

Status: preregistered | observing | concluded-confirmed | concluded-rejected | concluded-inconclusive | archived
Version: v0.1
Registered: <date>

## Thesis

What is being claimed, stated so it could be wrong.

## Prior

What's known going in (history, literature, adjacent evidence) — a prior to update,
not a training set to fit.

## What would count as a real checkpoint

The concrete, recurring real-world event this hypothesis will be checked against
(an earnings call, an FOMC meeting, a data release), and what data type each
checkpoint produces.

## Promotion criteria

Roughly how many real checkpoints, or what kind of result, would justify engineering
this into the pipeline (or rejecting it).

## Observation log

| Date | Event | Reading | Note |
| --- | --- | --- | --- |
```
