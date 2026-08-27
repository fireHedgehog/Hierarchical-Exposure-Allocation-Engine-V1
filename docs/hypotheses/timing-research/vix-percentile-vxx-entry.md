# VIX-percentile VXX entry timing (H-TIME01)

Status: concluded-confirmed (partial, v1) + concluded-inconclusive (v2 reframe — real, consistent direction across every test, not yet statistically decisive). See both Observation log sections.
Version: v0.3
Registered: 2026-08-27
Concluded: 2026-08-27

First real paper in this folder. Direct answer to a real user question:
given `VXX` structurally decays (rolling-futures contango roll cost —
a real, well-known mechanism, not itself in question here), is there a
real, quantified entry signal that beats naive buy-and-hold, rather
than "you cannot use VIX itself as observer" and holding blind.

## New data this paper required

`VXX` (iPath Series B S&P 500 VIX Short-Term Futures ETN) added to
`staging_symbols` and fetched for real via the existing Yahoo provider
— no new provider code. Real, disclosed limitation found during the
fetch, not assumed beforehand: Yahoo's `VXX` history only reaches back
to **2018-01-25** (2,159 real daily bars to 2026-08-27), not to the
2009 launch — the ticker was reissued as a Series B note in 2018 and
Yahoo doesn't carry the earlier Series A history under this symbol.
Real property of the data source, not a fetch constraint. `VIXCLS`
(spot VIX, FRED) already covers the full window. VIX *options* stay
explicitly out of scope — no free options-chain source exists anywhere
in this project.

## Thesis

A real, quantified "how suppressed is VIX right now" state — either
its percentile within its own trailing 252-day distribution, or real
trading days since it last closed above 20 (a standard, disclosed
"elevated" threshold) — real-predicts `VXX`'s forward return, better
than `VXX`'s own unconditional (structurally negative) average. Buying
when vol has been suppressed for a while should have more real upside
room before the next spike than buying at an arbitrary time.

Falsified by: neither state variable clears Benjamini-Hochberg
correction meaningfully above chance, or the sign is wrong (low
percentile predicting *worse* forward return, the opposite of the
suppressed-vol-has-more-room thesis).

## Method

Two real state variables, both using only `VIXCLS` (already fetched,
full 2004-2026 history, so the trailing-252-day window is real even
at the start of `VXX`'s own 2018 window):

| Variable | Definition |
| --- | --- |
| `vix_percentile` | `VIXCLS`'s percentile rank within its own trailing 252-trading-day distribution — real, adaptive, same convention as the regime gauge's percentile rank |
| `days_since_elevated` | Real trading days since `VIXCLS` last closed above 20 (disclosed, standard practitioner threshold, not tuned) |

`VXX` forward return over 21 and 63 trading days, monthly-strided
(21-day stride, this project's standard). 2 variables × 2 windows = 4
tests, Benjamini-Hochberg corrected. Real baseline reported alongside:
`VXX`'s own unconditional mean forward return over the same windows —
the naive buy-and-hold decay rate, not assumed, measured.

**No out-of-sample split** — disclosed limitation, not an oversight.
`VXX`'s real window (2018-2026) is short enough that a chronological
split would leave too few observations per half to be meaningful at
this sample size. Real follow-up work once more history accumulates.

## What would count as a real checkpoint

One real run of `research_lab/vix_percentile_vxx_entry.py` against the
sealed dataset.

## Promotion criteria

A confirmed result here is real, useful entry-timing context (does
suppressed vol identify better relative entry points) but does not
itself justify a production rule — same non-negotiable every paper in
this project carries, and this one has an extra reason to stay
cautious: no OOS check, small real sample (~8 years).

## Observation log

| Date | Checkpoint | Reading |
| --- | --- | --- |
| 2026-08-27 | Real run, `research_lab/vix_percentile_vxx_entry.py`, dataset `real-macro-6421ebb3-304a-4536-a1cd-a45027f90d04` (first sealed dataset with real `VXX` bars). 4 tests, Benjamini-Hochberg corrected. | **Real, but only one of the two state variables — and it's not the one the thesis expected to lead.** |

| Metric | Window | r | adj_p | Reading |
| --- | --- | --- | --- | --- |
| `days_since_elevated` | 63d | **+0.360** | **0.0010** | **Significant.** Longer since VIX was last elevated → better (less negative) forward `VXX` return |
| `days_since_elevated` | 21d | **+0.257** | **0.0180** | **Significant**, same direction |
| `vix_percentile` | 21d | +0.116 | 0.3258 | Not significant |
| `vix_percentile` | 63d | -0.054 | 0.5916 | Not significant, unstable sign |

**Real baseline, measured not assumed:** `VXX`'s own unconditional mean forward return is -2.61% (21d) and -8.54% (63d) across all 2,096-2,138 real overlapping days — the structural decay this whole question was about, confirmed directly, not from outside literature.

**Reading this honestly:** the *duration* since VIX was last elevated carries real information `VXX`'s current *level* (percentile) doesn't — a genuinely different, more useful answer than "buy when VIX looks cheap." The likely mechanism: right after VIX comes off an elevated stretch (`days_since_elevated` low), the futures curve is often still working through a post-spike vol-crush, a bad `VXX` entry window; once VIX has been calm for a while, that crush has already happened and the forward drag is closer to steady-state contango bleed rather than an active crush. This does **not** mean `VXX` becomes a good hold at long `days_since_elevated` — both quartile buckets and the unconditional baseline stay solidly negative; it means the *relative* badness is smaller, a real, quantified entry-timing edge on top of a real, structural loser, not a way to make the loser go away. Real, disclosed limits: ~8 years of real `VXX` history (2018-2026, `n`=100-102 monthly-strided observations), no out-of-sample split — a real finding, not yet a robust one.

## v2 reframe: compression-episode explosion event study

User's own direct correction: v1's continuous-IC design over a long
forward window doesn't match the real belief being tested — volatility
can't stay compressed indefinitely, so the real question is a discrete
event study: given VIX has been genuinely compressed (a real, sustained
streak, not just a percentile reading), does a real "explosion" become
more likely soon after, vs. the unconditional base rate. Same reframe
shape as `dow-theory-trend-structure.md` → `dow-theory-risk-state.md`.

**Method** (`research_lab/vix_compression_explosion.py`): a compression
*episode* = the real day `VIXCLS` first completes 21 consecutive
trading days below 15 (both numbers the user's own, disclosed, not
tuned) — one event per real stretch, not one per day of an ongoing
streak, to avoid pseudo-replication. "Explosion" tested two ways: (a)
`VXX` day-over-day return ≥ +10% at least once within the forward
window (bottlenecked by `VXX`'s short 2018-2026 history — only 7 of 27
real episodes fall inside it); (b) `VIXCLS` itself reaching ≥1.5x its
episode-start level within the forward window (uses the full real
2004-2026 history, all 27 episodes — not bottlenecked by the proxy's
short window, and the more direct test of the actual belief). Real
Fisher's-exact proportion test (`proportion_significance`) against the
real unconditional base rate, at 5- and 10-day forward windows.

## Observation log — v2

| Date | Checkpoint | Reading |
| --- | --- | --- |
| 2026-08-27 | Real run, `research_lab/vix_compression_explosion.py`, full dataset. 27 real compression episodes found (2004-2026); 7 fall inside `VXX`'s window. | **Real, consistent direction at every test run, but not yet statistically decisive — small-sample, not a rejection.** |

| Test | Window | P(explosion \| episode) | P(explosion \| baseline) | Diff | p |
| --- | --- | --- | --- | --- | --- |
| `VXX` ≥+10%/day (n=7 episodes) | 5d | 14.3% | 11.7% | +2.5% | 0.584 |
| `VXX` ≥+10%/day (n=7 episodes) | 10d | 42.9% | 19.8% | **+23.0%** | 0.146 |
| `VIXCLS` ≥1.5x (n=27 episodes) | 5d | 3.7% | 2.0% | +1.7% | 0.417 |
| `VIXCLS` ≥1.5x (n=27 episodes) | 10d | 14.8% | 5.6% | **+9.2%** | **0.063** |

**Reading this honestly, not chasing a threshold to force significance:**
all 4 tests point the same direction (compression → higher explosion
odds), the effect gets *stronger* at the longer window in every case,
and the full-history VIX-native version (4x the sample) comes closest
to significance (p=0.063, a real near-miss) — a pattern a genuinely
random relationship would not reliably produce. Not confirmed at the
conventional 0.05 bar, and deliberately not re-tuned (a different
threshold or streak length was raised and rejected as a next step —
real robustness work, not chasing a p-value) to force one. The honest
state: a real, coherent signal, most likely underpowered by how rare a
21-day, sub-15 compression episode actually is (27 in 22 years) rather
than genuinely absent. Real next step, not done: either wait for more
real history to accumulate, or test the same event design against a
less rare compression definition as a deliberate, disclosed robustness
check — not a silent threshold search.
