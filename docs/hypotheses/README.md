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

**Disclosed exception:** [`theme-research/`](theme-research/README.md)
(added 2026-08-28) genuinely spans two layers — which theme (asset
selection) and how long it stays live (timing-flavored survival/hazard
estimation). The table's warning above is about one *signal* secretly
answering two questions at once (the exact bug `exposure-policy-
calibration.md` found in `envelope.py`'s collapsed confidence-to-
multiplier formula). This is different: theme-research keeps its two
outputs explicit and separate — "which theme is active" and "its
empirical survival curve" are reported side by side, never fused into
one opaque number — so it's a deliberate, disclosed exception to one-
folder-per-layer, not a repeat of that bug.

## Known methodology limitations (project-wide, read before trusting any p-value here)

Three real, verified gaps apply across many papers in this tree — recorded
once here rather than re-stated in every affected file. Checked against
the real code on 2026-08-28, not asserted from memory.

1. **Macro data is not true point-in-time.** `fetch_data.py` pins FRED's
   `realtime_start`/`realtime_end` to the pipeline's own run date for the
   *entire* historical fetch — every historical row gets today's
   fully-revised value, not the value actually known/published at that
   historical date. A true point-in-time backtest needs a separate ALFRED
   vintage query per historical anchor date; this project has never done
   that (see "Parked" below). **Real impact measured, not guessed**
   (`research_lab/point_in_time_revision_magnitude_check.py`, live ALFRED
   comparison): `GDPC1`'s raw *level* for Q3 2008 differs by ~44% between
   its first-release vintage and today — but that's dominated by BEA's
   periodic chained-dollar base-year rebasing, which largely cancels out
   in a ratio. The number that actually matters — the real YoY growth
   rate `scoring_v3.py` computes (`is_yoy=True`) — differs by only
   **-0.48 percentage points** (+0.74% as known in Dec 2008 vs. +0.27%
   as known today) for that same quarter, the single highest-IC case in
   H-MACRO11. `PAYEMS` and `CPIAUCSL` level revisions were already small
   at the source (-0.2 to -0.4% and +0.13% respectively). **Honest
   verdict: real, but modest, not the dominant driver of any finding in
   this tree** — this project's own choice to z-score YoY *growth rates*
   rather than raw levels (made for economic reasons, not for this) turns
   out to also provide real, if partial, protection against exactly this
   gap. Concentrated in `INDPRO`, `PAYEMS`, `GDPC1`, `CPIAUCSL`,
   `PCEPILFE`, `PPIACO` (the `growth_inflation` cluster) — any paper
   using `macro_regime_composite` or these factors directly inherits
   this, now-measured, modest exposure (`macro-research/` in full;
   `asset-selection-research/`'s regime-conditioned addenda in H-STREV,
   H-SECT02/05/09/11). Daily market-observed series (`DGS10`, `DGS30`,
   `DFII10`, `VIXCLS`, credit spreads) and every **pure-price** paper
   (H-SECT01, H-SECT07, H-SECT08, H-SECT10, both SPY-trend-conditioned
   re-tests, all of `timing-research/`) are genuinely unaffected — they
   never touch FRED data at all.
2. **"OOS" language has been overclaimed.** The 2019-01-01 chronological
   split has been reused across many papers (H-MACRO09 and its own OOS
   follow-up, threshold-sensitivity, H-SECT02, H-SECT07, H-SECT08,
   H-MACRO11). Each individual paper's walk-forward discipline was real
   (weights learned in-sample only, held fixed, no lookahead *within* that
   test) — but reusing the same holdout across a growing set of hypotheses
   is a real, cumulative form of the thing OOS splits exist to prevent.
   Read "holds OOS" throughout this tree as **"holds in a later temporal
   subsample," not a blind, untouched holdout** — real evidence of
   robustness, not proof against overfitting.
3. **Overlapping samples inflate reported significance.** The common
   `STRIDE_DAYS=21` sampling against 63- or 126-day forward windows still
   leaves 67-83% overlap between adjacent samples — striding reduces
   pseudo-replication, it does not eliminate it. Pearson/Fisher tests
   assume independent observations; a single event (2008, 2020) can
   inflate the effective sample size of "successes." Treat reported p-values
   and probability differentials as directionally real, not exact — see
   `research_lab/macro_significance_robustness_check.py` for a real
   block-permutation re-test of the two most consequential findings
   (H-MACRO09, H-MACRO11) that respects this real autocorrelation instead
   of assuming independence.

**Parked, not fixed:** true per-date ALFRED vintage fetching (gap #1's
real remedy) is a real, substantial software change — re-architecting
`fetch_data.py` to do many historical vintage calls instead of one,
meaningfully slower against the real FRED API. Deliberately not
undertaken now, per direct instruction: research validity gaps get
disclosed and worked around statistically where possible, not used to
justify a radical software rewrite. The measured, modest real impact
above (-0.48pp on the single highest-IC case) makes this an easier
park, not a harder one — revisit if/when this specific gap becomes the
binding constraint on a real decision, not before.

## Data sources, by type

A second, orthogonal axis to the 4 layers above — what kind of data a
hypothesis draws on, not which decision it answers. Recorded here so
"expand the universe" has a real menu to pick from later, not a vague
gesture. Currently in use: the first two rows only, by design — the
project's current phase is deliberately price/volume (+ macro) only.

| Type | Examples | Status |
| --- | --- | --- |
| Market numeric | OHLCV, returns, volatility, cross-sectional price behavior | In use — every paper outside `macro-research/` |
| Macro numeric | FRED rates/inflation/liquidity/growth | In use — `macro-research/` |
| Alternative structured | Flows, options, short interest | Not connected. Named as a real gap in `asset-selection-research/README.md`'s crowding/convexity question (#6) |
| Unstructured | Text, earnings, themes, news | Not connected. `thematic-beta-selection-process.md` (H-BETA01) is parked specifically because it needs this tier |

**Within "market numeric," not every symbol is general-purpose.**
`staging_symbols.research_scope` (`general` / `narrow_proxy` /
`reference_only`) exists so a broad cross-sectional sweep — a future
H-SECT-style study, or a future ML feature pipeline — doesn't silently
pool in a structurally-different instrument. `VXX` (a rolling-futures
ETN with a real, persistent decay mechanism — see `timing-research/
vix-percentile-vxx-entry.md`) is `narrow_proxy`: a real, valid proxy
for its *own* deliberately-scoped hypothesis, never a general asset.
`BTC-USD` is `reference_only` (never spliced into a listed instrument's
history, per `roadmap.md`). Every general-purpose production query
(`factor_engine`, `allocation_engine`, `instrument_engine`) and every
broad research sweep (`research_repository.py`'s significance/momentum/
timing-signal studies) filters `research_scope = 'general'` — a new
narrow-scope symbol added for one paper must be labeled at the same
time it's added, not left to pollute the general universe by default.

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
| [Macro research](macro-research/README.md) (subfolder) | 3-layer input/response/outcome framework, own index | in progress | 11 real papers (H-MACRO01-11 + Warsh). Composite (`macro_regime_composite`) live at naive-v3 with real out-of-sample-validated forward-drawdown evidence (H-MACRO09). H-MACRO10 found and fixed a real directional bug in the exposure formula (naive-v2, live). H-MACRO11: tested IC-weighting vs. naive-v3's cluster-equal design — a first pass looked exciting but had a real sign bug; fixed and re-tested against the composite's real target, the existing design wins OOS. Real evidence naive-v3 is already well-designed, not a case to change it. | n/a |
| [Asset selection research](asset-selection-research/README.md) (subfolder) | 13-asset real sleeve universe (GLD-anchored) + 2 theme ETFs, own index | in progress (H-SECT06 observing) | 10 papers. H-SECT01-05: leadership persistence rejected; regime-conditioned relative return confirmed then narrowed by beta-adjustment to just `XLU`+`XLY`; driver decomposition and allocation backtest both rejected. H-SECT06: gold reaction function, cold-start event log, observing. H-SECT07-09: dispersion (real full-sample, failed OOS), regime velocity (clean rejection), conjunctive `XLU` trigger (significant but fragile). H-SECT10: `SMH`/`IGV` relative strength vs. `QQQ`/`SPY`/`DIA` specifically — clean rejection, well-powered. | n/a |
| [Timing research](timing-research/README.md) (subfolder) | action-layer framework, own index | in progress | When to enter/hold/trim/exit. Regime-conditioned reversal edge run and confirmed (real in all 3 regimes at 1 week; 2-week reversal flips to mild continuation specifically in calm regimes — logged in `short-term-mean-reversion.md`). RSI(14)>=70 exit's general signal is real (0.29) — a `schema.sql` comment wrongly said "never tested," corrected 2026-08-27. H-TIME01: added real `VXX` data, found days-since-VIX-last-elevated real-predicts `VXX`'s forward return, its current percentile level doesn't. H-TIME02 (`broad-index-exposure-policy.md`): reframed price-trend testing from point-forecast IC (rejected everywhere else this project tried it) to full-path portfolio evaluation — a real, disclosed trend+vol exposure policy on SPY/QQQ beats static buy-and-hold on Sharpe and max drawdown, consistently across 4 MA lengths, in-sample and OOS; directly ruled out the "just lower average exposure" artifact. Composition with the live macro-based exposure scaling (H-MACRO10) tested directly, not just reasoned about — neither multiplicative nor `min()` combination beats the standalone price-only policy on Sharpe; price-only alone currently looks better than production's macro-only formula on this one backtest. Held off on any production change (user call, 2026-08-28) pending a per-sleeve rather than SPY-only version and a formal promotion review. | n/a |
| [Theme research](theme-research/README.md) (subfolder) | Conditional Theme Survival / Diffusion Research, own index | preregistered, no data fetched yet | Disclosed exception spanning asset-selection + timing layers (see note above the layers table). H-THEME-01/02 preregistered (`theme-confirmation-survival.md`): does an accepted gap confirmed across multiple ETF anchors of a hardcoded theme persist longer than an isolated one, and what's the real empirical survival curve stratified by breadth. V0 deliberately ETF-anchor-only (14 new tickers needed, not yet fetched) and hardcoded-cluster-only (no automatic discovery) — both scope-narrowing decisions made explicitly, not defaults. H-THEME-03/04 (diffusion hazard, contraction/resumption) deliberately not started — gated on 01/02 showing real stratification first. | n/a |
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
