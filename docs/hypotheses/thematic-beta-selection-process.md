# Thematic beta selection process (H-BETA01)

Status: preregistered
Version: v0.1
Registered: 2026-08-26

Not wired into any pipeline stage.

## Thesis

Not a new price/volume anomaly — a decision-process question. The user's real
trading history is thematic-beta riding (long AI while AI won), not
stock-picking, and the open question is whether *which beta, and when* can be
a disciplined, falsifiable process rather than a market story believed after
the fact.

**Thesis:** a criteria-based process for identifying, confirming, and exiting
a thematic beta bet — graded on the ladder below — produces checkpoints
(leadership persistence, breadth, structural deterioration) that carry real
information about which themes sustain vs. fail, distinct from noise.

**Not a claim that thematic investing has "alpha."** The goal is helping a
thematic investor pick which betas are worth taking, and express that view
more clearly, survivably, and reviewably — not proving ten thousand alphas
exist. A null result here is real and useful: it means the honest answer to
"was I lucky" is yes, and the app's job is risk control, not false confidence.

**Falsification:** across several independent episodes, if breadth
confirmation doesn't predict persistence and the deterioration signal doesn't
precede real drawdowns any better than chance, the process is rejected. One
theme working out is not evidence either way.

## Prior

User's own account, flagged as a single anecdote, not evidence: weighted "AI"
over "quantum computing" as the dominant theme, and won — stated unprompted
as possibly luck. `macro_regime_composite` and `cross_sectional_momentum`
already give a real regime read and a real cross-sectional rank across
theme-level instruments (IGV, XLE, GLD, QQQ, etc.) — this paper doesn't
re-test relative strength (already confirmed, 0.16/0.26). It tests whether
*confirming* a leader with independent structural evidence distinguishes a
durable theme from a lucky spike.

## Minimum ingredients

Single-ingredient discipline, same as Dow Theory's price/volume split:

| # | Ingredient | Buildable now? |
| --- | --- | --- |
| 1 | Price leadership | Yes — `cross_sectional_momentum` (live) |
| 2 | Leadership duration | Yes — existing staging price history |
| 3 | Breadth confirmation | Yes — existing staging price history |
| 4 | Deterioration signal | Yes — reuses H-DOW02's detector |
| 5 | Fundamental/positioning confirmation | **No.** No data provider (`fundamental_analysis` is `draft`/`NULL`; Benzinga/Intrinio `planned`). Named as a gap, not faked. |
| 6 | Theme identification itself | **Qualitative, real-time, human.** Not statistically testable — tracked via the ladder below. |

Ingredients 1-4 don't need new episodes — testable now against every past
leadership rotation in the 2004-2026 dataset. Queued as companion papers, not
built here:

- **H-BETA02** — leadership duration distribution.
- **H-BETA03** — does breadth confirmation predict longer holds.
- **H-BETA04** — does H-DOW02's break detector, applied to the current leader
  specifically, mark a real exit point.

Ingredients 5-6 can't be sped up — blocked on data, or inherently real-time.

## The theme lifecycle ladder (R0-R10)

Same shape as `warsh-reaction-function.md`'s response ladder, for a theme's
lifecycle instead of a policymaker's action. Stalling or skipping back is a
real, recordable outcome.

| Level | Meaning | Measurable how |
| --- | --- | --- |
| R0 | No theme identified | n/a |
| R1 | Candidate theme named | Human-flagged, dated |
| R2 | Price leadership emerging | Real — enters top tier of live rank |
| R3 | Leadership sustained | Real — holds for a minimum duration (from H-BETA02) |
| R4 | Breadth confirming | Real — H-BETA03's mechanism |
| R5 | Fundamental confirmation | **Blocked** — no data provider |
| R6 | Position established | Logged by the user, outside this app |
| R7 | Crowding / broad recognition | Qualitative for now |
| R8 | Deterioration signal fires | Real — H-BETA04's mechanism |
| R9 | Exit / leadership ceded | Real — falls out of top tier |
| R10 | Retrospective close-out | Did R2-R9 fire usefully, not narrated in hindsight |

## Checkpoints and promotion

A checkpoint is a theme reaching a new rung, or a quarterly review confirming
no change. A full cycle plausibly takes years — slower than the Fed paper's
6-week FOMC cadence, disclosed up front. Promotion needs at least 3
independent, fully-cycled episodes before the ladder's checkpoints can be
judged against real outcomes rather than hindsight.

## Observation log

| Date | Theme | Rung | Note |
| --- | --- | --- | --- |
| 2026-08-26 (retrospective) | AI infrastructure capex | R1 (retrospective) | User weighted AI over quantum computing ahead of any formal process. Logged as pre-process, unconfirmed by this paper's own criteria — the prior that motivated the paper, not evidence it works. First live episode to track forward. |
