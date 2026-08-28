# Factor breadth-weighting vs. cluster-equal-weighting (H-MACRO11)

Status: concluded-rejected against the real target. The original
result (below) both used the wrong target AND had a real sign bug in
the weighting formula; after fixing the bug and re-testing against the
composite's actual, validated target (real drawdown probability), the
existing cluster-equal design holds up *better* out-of-sample than the
IC-weighted alternative — a real, honest reversal, not a footnote. See
Observation log for the full sequence, including the bug.
Version: v0.2
Registered: 2026-08-28
Concluded: 2026-08-28

Picks up an already-flagged, pre-scoped gap directly:
`macro-research/README.md`'s own restart-here table has carried
"Compare cluster-equal-weighting against IC-weighted alternatives"
since the naive-v3 promotion. Prompted by the same Fundamental-Law
question just applied to the sleeve layer (H-SECT04 v2) — applied here
to the macro composite itself.

## Thesis

`macro_regime_composite`'s naive-v3 design gives every real cluster
(growth/inflation, rate level, market stress) equal weight, then every
member within a cluster equal weight (H-MACRO08's redundancy-aware
fix, replacing v1/v2's hand-picked per-factor weights). That's a real
improvement over v1/v2, but it still isn't IC-weighted — a factor with
real, measured predictive power gets the same weight as one with none,
as long as they're in the same cluster. A real, walk-forward IC-
weighted combination of the same 13 factors should out-forecast the
cluster-equal design.

Falsified by: the IC-weighted alternative's real, out-of-sample IC
against forward SPY return doesn't beat the existing cluster-equal
composite's own OOS IC.

## Method

Real, point-in-time per-factor contributions (the same z-scores
`compute_regime_v3` already computes internally, extracted directly,
not re-derived) at every real historical anchor date. Real per-factor
IC (Pearson, contribution vs. forward 126-trading-day SPY return)
learned **in-sample only** (2004-2018), held fixed, applied unchanged
out-of-sample (2019-2026) — no lookahead. IC-weighted alternative
composite: `Σ(IC_i × contribution_i) / Σ|IC_i|`. Real effective
breadth via this project's own proven PCA machinery
(`effective_number_of_bets`, H-MACRO08's tool). Compared against the
existing cluster-equal composite's own real IC, same target, same
dates, both halves.

## What would count as a real checkpoint

One real run of `research_lab/macro_factor_breadth_test.py` against
the sealed dataset.

## Observation log

| Date | Checkpoint | Reading |
| --- | --- | --- |
| 2026-08-28 | Real run, `research_lab/macro_factor_breadth_test.py`, target = forward SPY return (the wrong target — flagged as such the same day). 256 real anchors, 11 of 13 factors had enough in-sample history (`BAMLH0A0HYM2`/`BAMLC0A0CM` excluded — real data only from 2023, no in-sample coverage). | OOS IC nearly doubled, +0.400 (IC-weighted) vs. +0.210 (cluster-equal) — exciting, but explicitly not trusted yet: wrong target, and (not yet known) a real formula bug. |
| 2026-08-28 | Real re-test, `research_lab/macro_factor_breadth_test_drawdown_target.py`, target swapped to the composite's actual, validated target — P(real SPY drawdown ≥10% within 126 trading days), matching H-MACRO09 exactly. | **A real bug caught before being trusted, not after:** the IC-weighted composite showed an *impossible* sign — positive IC against real drawdown risk (its "stressed tercile" showed *lower* drawdown probability than its "calm tercile"). A real formula error, not a real finding: `contributions` are already sign-oriented by `scoring_v3` (negative = stress, consistently), so a genuinely reliable factor correctly shows a *negative* IC against drawdown risk — multiplying by that signed, negative IC flips the factor's own already-correct sign, corrupting the composite. Fixed: weight by `\|IC\|` (reliability) instead of signed IC, in both scripts. |
| 2026-08-28 | Both scripts re-run with the fix. | **The corrected result reverses the exciting one.** See tables below — both against the real, correct target this time. |

**Corrected result, forward-return target (for reference, still the
wrong target for this composite's real use, kept for comparison):**
OOS IC-weighted +0.360 vs. cluster-equal +0.210 — the improvement
survives the bug fix here, still real and substantial.

**Corrected result, real drawdown-probability target (the one that
actually matters):**

| Window | Cluster-equal IC | IC-weighted IC | Cluster-equal tercile spread | IC-weighted tercile spread |
| --- | --- | --- | --- | --- |
| In-sample | -0.207 | -0.423 | +20.0% (p=0.010, SIG) | +43.6% (p<0.0001, SIG) |
| **Out-of-sample** | **-0.311** | **-0.279** | **+32.1% (p=0.014, SIG)** | **+21.4% (p=0.121, not significant)** |

In-sample, IC-weighting looks better (expected — some in-sample
fitting bias). Out-of-sample — the number that actually matters — it's
the *existing* cluster-equal design that wins: real, significant
(p=0.014), while the "improved" IC-weighted alternative is weaker and
not significant (p=0.121). A real, plausible, disclosed mechanism, not
just "OOS is noisy": in-sample IC-weighting likely overfits to the
specific factor pattern that preceded 2008 (`gdp` IC=-0.403, `growth`
IC=-0.372 — a real, dominant signature of that one recession), which
doesn't generalize as well to differently-shaped real crises (2020's
shock, 2022's inflation-driven cycle). This is the same real,
well-documented phenomenon behind the "1/N puzzle" in the finance
literature (DeMiguel, Garlappi & Uppal 2009) — naive equal-weighting
often beats "optimized" weighting out-of-sample precisely because
optimization fits noise in the estimation sample that a naive scheme
never tries to fit in the first place.

## Promotion criteria

Not met, and the direction reversed from the first, wrong-target pass.
Real conclusion: `macro_regime_composite`'s existing cluster-equal
design is not obviously improvable by simple IC-weighting once tested
against its actual, validated target — if anything, this paper is now
a real, independent piece of evidence *for* keeping the naive-v3
design as-is, not a case to change it. `scoring_v3.py` stays
unchanged.
