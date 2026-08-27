# Research hypotheses

## Four decision layers

Every research question here belongs to exactly one of these — a
number/signal that tries to answer two at once is the recurring bug
this project keeps finding (`macro-research/exposure-policy-
calibration.md` is the latest instance). File new hypotheses under the
matching folder, not by which indicator happens to be involved:

| Layer | Question it answers | Folder |
| --- | --- | --- |
| Macro regime | How much total risk should I own right now? | [`macro-research/`](macro-research/README.md) |
| Asset selection | Given that risk budget, where should it be expressed? | [`asset-selection-research/`](asset-selection-research/README.md) |
| Timing | Given a position (or instrument), when do I act — enter/hold/trim/exit? | [`timing-research/`](timing-research/README.md) |
| Portfolio construction | How much in each specific instrument? | Not a hypothesis folder yet — currently `backend/engine/instruments/` (conviction-scaled structure/sizing), naive-v1 |

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
| [Macro research](macro-research/README.md) (subfolder) | 3-layer input/response/outcome framework, own index | in progress | 10 real papers (H-MACRO01-10 + Warsh). Composite (`macro_regime_composite`) live at naive-v3 with real out-of-sample-validated forward-drawdown evidence (H-MACRO09). H-MACRO10 flags the confidence→gross-exposure mapping as a separate, still-untested hypothesis. | n/a |
| [Asset selection research](asset-selection-research/README.md) (subfolder) | 13-asset real sleeve universe (GLD-anchored), own index | in progress (H-SECT06 observing) | 6 papers: H-SECT01-05 concluded (leadership persistence rejected; regime-conditioned relative return confirmed then narrowed by beta-adjustment to just `XLU`+`XLY`; driver decomposition and allocation backtest both rejected). H-SECT06 (gold reaction function) reopened `GLD` specifically as a cold-start event log — is it decoupling toward fiscal-dominance pricing. | n/a |
| [Timing research](timing-research/README.md) (subfolder) | action-layer framework, own index | scope only | When to enter/hold/trim/exit. Existing top-level papers already cover most of entry; RSI(14)>=70 exit flagged as a real gap — live in production, never independently tested. | n/a |
| [Time-series momentum](time-series-momentum.md) | continuous (IC vs. real forward return) | concluded-rejected | Opposite direction at every horizon; replicated on 2004-26 but weaker (only 2 of 5 horizons still significant, was 5 of 5) | 2016+, 2004+ |
| [Low-volatility anomaly](low-volatility-anomaly.md) | continuous (IC vs. real forward return) | concluded-rejected (raw return) | Opposite direction — volatile beat calm | 2016+ |
| [Short-term mean reversion](short-term-mean-reversion.md) | continuous (IC vs. real forward return) | concluded-confirmed (1-week window) | Confirmed and strengthened on 2004-26: r=-0.057 (was -0.02), and now significant at 2 weeks too (was not) | 2016+, 2004+ |
| [MAX effect / lottery demand](max-effect-lottery-demand.md) | continuous (IC vs. real forward return) | concluded-rejected | Opposite direction — extreme-max beat calm-max; r=+0.78 with low-vol above, not independent | 2016+ |
| [Dow Theory trend structure](dow-theory-trend-structure.md) | binary (intact/broken) vs. real forward return | concluded-rejected (opposite direction) | Broken beat intact on forward return, replicated on 2004-26 at similar magnitude | 2016+, 2004+ |
| [Dow Theory risk-state](dow-theory-risk-state.md) | binary (intact/broken) vs. real forward volatility | concluded-confirmed | Broken predicts higher forward volatility, replicated and slightly stronger on 2004-26 | 2016+, 2004+ |
| [Vol-scaled cross-sectional momentum](vol-scaled-cross-sectional-momentum.md) | walk-forward equity curve comparison (Sharpe/drawdown) | concluded-inconclusive | Drawdown improvement vs. naive baseline is mostly just lower average exposure, not the timing mechanism | 2004+ |
| [Short-term reversal cost robustness](short-term-reversal-cost-robustness.md) | walk-forward equity curve, gross vs. net-of-cost at 4 cost levels | concluded-confirmed (cost-sensitive) | Sharpe 1.15 gross; survives to Sharpe 0.77 at 10bps, breaks down by 25-50bps; 148.7% mean turnover | 2018+ (shortest-symbol-constrained) |
| [Thematic beta selection process](thematic-beta-selection-process.md) | graduated ladder (R0-R10) per real theme episode + 3 queued quantitative companion papers | preregistered | 1 real, retrospective, pre-process log entry (AI infra capex, R1) — no conclusion possible yet | n/a |
| [Opening gap-down fill](gap-down-fill.md) | conditional vs. unconditional fill-rate comparison (SPY/QQQ) | concluded-rejected (opposite direction) | Fill rate is high in absolute terms (72-93%) but *lower* than the unconditional baseline (~99.9%) at every spec | 2004+ |
| [Large one-day drop reversion](large-drop-reversion.md) | conditional vs. unconditional recovery-rate comparison (SPY, >=3% drops) | concluded-rejected | Close-based recovery is significantly *slower* than baseline at every window; loose (high-based) check is uninformative, ~ceiling either way | 2004+ |

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
