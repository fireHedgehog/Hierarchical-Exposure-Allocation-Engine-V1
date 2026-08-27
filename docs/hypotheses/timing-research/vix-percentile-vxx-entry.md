# VIX-percentile VXX entry timing (H-TIME01)

Status: concluded-confirmed (partial — `days_since_elevated` real and significant both windows; `vix_percentile` not significant, unstable sign). Small real sample (~8 years), no OOS check — treat as real but not yet robust. See Observation log.
Version: v0.2
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
