# Theme relative strength vs. broad index (H-SECT10)

Status: concluded-rejected — clean, well-powered, no ambiguity. See Observation log.
Version: v0.2
Registered: 2026-08-28
Concluded: 2026-08-28

Genuinely different specification from H-SECT01 (rejected), not a
re-run: H-SECT01 tested the 9 sector ETFs against *each other* (top-3-
of-9 ranking) at a 63-day block window. This tests `SMH`/`IGV`
specifically against *one broad index at a time* (`QQQ`, `SPY`, `DIA`
— never tested together before; neither theme ETF was in H-SECT01-09's
universe at all), at real, shorter "a few weeks" windows. Real
distinct question: does a theme's strength relative to the market it
sits inside persist, not whether it beats other sectors.

## Universe

`SMH` (semiconductors), `IGV` (software) — both real, full 2004-2026
history, confirmed directly against `data/desk.db`. Benchmarked
separately against `QQQ`, `SPY`, `DIA` (3 broad indices, deliberately
not pooled into one "the market" figure — a theme could show real
strength against one and not another, e.g. `SMH` vs. `DIA`
(low semis exposure) plausibly differs from `SMH` vs. `QQQ`, which
already carries heavy semis weight through its own mega-caps).

## Thesis

A theme's relative strength against a specific broad index — real
trailing block return, theme minus index, non-overlapping blocks —
real-predicts its own relative strength in the *next* block, at a
short (10 or 21 trading day) window. Secondary: current relative
strength also predicts the theme's own forward *absolute* return, not
just its relative one.

Falsified by: none of the 12 tests (6 pairs × 2 windows) clears
Benjamini-Hochberg correction meaningfully above chance.

## Method

Same non-overlapping-block discipline H-SECT01's rigorous check used
(the one that actually held up, vs. the daily-overlap version that
turned out to be a mechanical artifact) — real, independent blocks,
no shared days between consecutive readings. For each of the 6
(theme, benchmark) pairs and each window (10, 21 trading days): split
the full real history into non-overlapping blocks, compute
`relative_strength = theme block return − benchmark block return` per
block, continuous IC (Pearson) between block *N*'s relative strength
and block *N+1*'s — a direct persistence test, not a binary win/lose
call, to get real power out of the larger number of blocks a shorter
window provides (≈550 real blocks at 10 days, ≈260 at 21, vs.
H-SECT01's 86 at 63 days). 12 tests total, Benjamini-Hochberg
corrected. Secondary check, same data, no extra multiple-comparisons
cost: IC between block *N*'s relative strength and the theme's own
*absolute* forward return in block *N+1*.

## What would count as a real checkpoint

One real run of `research_lab/theme_relative_strength.py` against the
sealed dataset.

## Promotion criteria

A confirmed result here is real, useful context about which broad
index a theme's strength is best measured against — not itself an
allocation rule. Same bar every paper in this arc has carried: a real
correlation existing does not by itself justify an automated rule
(H-SECT04 already showed a real sleeve-level correlation can fail to
survive becoming one).

## Observation log

| Date | Checkpoint | Reading |
| --- | --- | --- |
| 2026-08-28 | Real run, `research_lab/theme_relative_strength.py`, full 2004-2026 history. 24 tests (2 themes × 3 benchmarks × 2 windows × 2 checks), Benjamini-Hochberg corrected. | **Clean rejection — 0 of 24 significant**, against a ~1.2 chance floor. No near-misses (best raw p corresponds to adj_p=0.80), no monotonic pattern across benchmarks or windows, real sample size at every cell (n=259 at 21d, n=545 at 10d — not a power problem the way H-TIME01 was). |

**One real, secondary observation, not itself a claim:** 23 of the 24 raw correlations are negative (the lone exception: IGV vs. QQQ predicting absolute forward return at 21d, r=+0.027, itself far from significant). A real, consistent sign — mild hint of short-window relative-strength *reversal* rather than persistence — but every single one is statistically indistinguishable from zero, so this stays a noted pattern, not a finding. Consistent with H-SECT01's own rejection (sector-vs-sector persistence, different universe/window) and this session's broader, repeated result: short-horizon technical persistence does not show real structure in this data, however the universe, benchmark, or window is specified. `SMH`/`IGV` relative strength against `QQQ`/`SPY`/`DIA` specifically does not change that picture.
