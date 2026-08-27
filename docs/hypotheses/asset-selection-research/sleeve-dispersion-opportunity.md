# Sleeve dispersion / opportunity-set (H-SECT07)

Status: concluded-inconclusive — real, coherent full-sample pattern (6/10 significant); 0/10 clears significance out-of-sample, though same-signed throughout (not reversed) and plausibly underpowered rather than genuinely absent. See Observation log before treating this as a settled gate.
Version: v0.2
Registered: 2026-08-27
Concluded: 2026-08-27

Deliberately asks a different-shaped question than H-SECT01-05: not
"which sleeve wins" but "is there currently a real prize available to
win at all." User's own framing, directly: park *direction*, ask
whether cross-sectional differentiation is currently rich or poor —
the asset-selection layer's analogue of the macro layer's "risk
expensive/cheap." Stock-level breadth stays parked (no component
data), but sleeve-level dispersion/concentration is real and testable
with data already in hand.

## Thesis

Real, currently-observable cross-sectional differentiation among the
12 sleeves (dispersion, correlation, spread, leadership gap, breadth)
predicts how much real differentiation exists in the *forward* period
— i.e. a currently rich-opportunity state predicts a forward period
where the best and worst sleeves are further apart, not just noise
around a constant spread. This does not assume *which* sleeve wins
(H-SECT01 already rejected that trend-continuation claim) — only
whether the size of the prize itself is real and predictable.

Falsified by: none of the 5 state variables × 2 forward windows clear
Benjamini-Hochberg correction meaningfully above the ~0.5-of-10 chance
baseline.

## Method

5 real state variables, each computed at every monthly-strided date
using a trailing 63-day window (same window already used elsewhere in
this folder, not re-tuned):

| Variable | Definition |
| --- | --- |
| `dispersion` | Cross-sectional stdev of the 12 sleeves' trailing 63d returns |
| `mean_pairwise_corr` | Mean of all 66 pairwise correlations, trailing 63 real daily returns |
| `top3_minus_bottom3` | Mean(top 3 trailing returns) − mean(bottom 3 trailing returns) |
| `leadership_gap` | Top sleeve's trailing return − mean of the other 11 |
| `sleeve_breadth` | Count of the 12 sleeves beating `SPY` on trailing 63d return (0-12) — the sleeve-level analogue of stock breadth, real with data already in hand |

**Outcome**: the same `top3_minus_bottom3` spread, but computed on
*forward* realized returns (63/126 trading days ahead — reusing this
folder's standard two windows) — the real, model-free "prize that
existed," not whether any specific strategy captured it. Continuous IC
(Pearson) between each state variable and the forward spread, 21-day
stride, Benjamini-Hochberg correction across all 10 tests (5 variables
× 2 windows).

## What would count as a real checkpoint

One real run of `research_lab/sleeve_dispersion_opportunity.py` against
the sealed dataset, producing the 10-test panel.

## Promotion criteria

This is the gate, not the payoff — per the user's own explicit
sequencing. If confirmed, the natural next step is *within* high-
opportunity states, what selects winners (regime velocity, then the
conjunctive `XLU`-only trigger, both already scoped in this folder's
restart-here table). If rejected, the recommended conclusion is
structural, not "try another sector hypothesis": this ETF-level layer
may not carry a real, minable selection edge at all, and the honest
next move is to stop generating more sleeve-selection papers, not
widen the search.

## Observation log

| Date | Checkpoint | Reading |
| --- | --- | --- |
| 2026-08-27 | Real run, `research_lab/sleeve_dispersion_opportunity.py`, full 2004-2026 sample. 10 tests (5 state variables × 2 windows), Benjamini-Hochberg corrected. | **Strong, coherent full-sample result: 6 of 10 significant** — a ~0.5 chance baseline. `dispersion`, `top3_minus_bottom3`, and `leadership_gap` all real-correlate positively with forward spread at both windows (r=0.18-0.34) — a currently-differentiated cross-section really does predict a differentiated forward period. `mean_pairwise_corr` and `sleeve_breadth` showed no real signal. |
| 2026-08-27 | Out-of-sample split, `research_lab/sleeve_dispersion_opportunity_oos.py`, same 2019-01-01 convention as every other check in this folder. | **Doesn't replicate: 8/10 significant in-sample (2004-2018) drops to 0/10 out-of-sample (2019-2026).** Every correlation stays the *same sign* out-of-sample (no reversals — `dispersion` 63d: r=+0.328 in-sample → r=+0.168 out-of-sample), so this reads as a real effect that weakened and became underpowered on a smaller OOS sample (91 periods at 63d) rather than a spurious full-sample fluke that flipped. But it does not clear the same bar H-MACRO09, H-SECT02's `XLU` result, or H-SECT05 cleared. Recorded `concluded-inconclusive`, not confirmed — the full-sample number in isolation would have overstated this. |

**Read honestly, not as a clean pass or fail:** the in-sample period (2004-2018) includes 2008 — a real, extreme dispersion/spread episode that plausibly drives most of the full-sample correlation. Whether that's "real dispersion persistence, just needs a bigger OOS sample to detect" or "a crisis-period artifact that shouldn't generalize" isn't resolved by this run. Recommendation, not yet acted on: treat this as a real, promising-but-unconfirmed signal, not the gate the roadmap's later steps (regime velocity, conjunctive triggers) should be unconditionally built on top of.
