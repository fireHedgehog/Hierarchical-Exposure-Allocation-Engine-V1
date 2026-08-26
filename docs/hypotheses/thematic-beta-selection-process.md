# Thematic beta selection process (H-BETA01)

Status: preregistered
Version: v0.1
Registered: 2026-08-26

Not wired into any pipeline stage. This is a working paper, not a registered
strategy — see `docs/hypotheses/README.md` for why, and what "graduate" means.

## Thesis

This is deliberately not a search for a new price/volume anomaly — every prior
paper in this folder already covers that ground at the single-name level. The
claim here is about a *decision process*, stated directly by the user: their
own real trading history has been almost entirely thematic-beta riding (long
AI while AI won), not single-name stock-picking, and the open question is
whether *which beta to hold, and when* can be made into a disciplined,
falsifiable, repeatable process — as opposed to a market story that gets
believed and then explained away as skill regardless of outcome.

**Thesis:** A disciplined, criteria-based process for identifying, confirming,
and exiting a thematic beta bet — graded against a real, dated, graduated
checkpoint ladder — produces selection decisions whose own checkpoints
(price-leadership persistence, cross-sectional breadth confirmation,
structural deterioration) carry real, measurable information about which
themes go on to sustain and which quietly fail, distinct from noise.

**This is explicitly not a claim that thematic investing has "alpha."** Per the
user's own framing: the point is not proving ten thousand alphas exist in the
market. It is giving a thematic investor — who is going to take beta bets
regardless — a systematic way to select which betas are worth taking, and to
express that view more clearly, more survivably, and more reviewably, through
research, risk control, and tool selection. A process that adds nothing over
noise is a real, useful, negative finding: it means the honest answer to "was
I lucky" is "yes," and the app's job becomes risk control and review, not
false confidence.

**Falsification:** across multiple real, independently-selected thematic
episodes (see checkpoint definition below), if the process's own quantitative
checkpoints show no real relationship to which episodes actually sustained
leadership vs. immediately reverted — i.e., breadth confirmation doesn't
predict persistence, and the structural-deterioration signal doesn't precede
real drawdowns any better than a coin flip — the process is rejected as a
selection aid. Any one theme "working out" is not evidence either way; only a
real relationship across several independent episodes counts.

## Prior

The user's own account, used as a single, explicitly-flagged anecdote, not
evidence: over the current AI infrastructure capex cycle, they weighted "long
AI" over "long quantum computing" as the dominant theme, and AI won. Stated
directly, unprompted: this could easily have been luck, and a real process
has to be judged by whether it would have said the same thing *before* the
outcome was known, using criteria that don't quietly bend to fit whichever
theme happened to win — the same discipline this project already applies
everywhere else (`docs/hypotheses/README.md`'s own lifecycle rule, and the
project's standing rule against the garden of forking paths).

Existing context this paper builds on rather than duplicates:
`macro_regime_composite` already produces a real regime classification
(risk-on/risk-off character), and `cross_sectional_momentum` already produces
a real, live cross-sectional ranking across the 22-symbol staging universe —
several of which are themselves basket/theme-level instruments (IGV
software, XLE energy, GLD gold, QQQ broad tech), not single stocks. This
paper does not re-test whether relative strength predicts relative strength
(already tested repeatedly — 0.16, 0.26, and the 12-1 momentum promotion
above all found real signal there). It tests a different, so-far-untested
question: does *confirming* a leader's standing with independent structural
evidence (breadth, sustained duration, an eventual deterioration signal)
actually distinguish a durable theme from a lucky spike.

## Minimum ingredients

Broken into named, separately falsifiable pieces on purpose — the same
single-ingredient discipline this project already applies to every other
multi-part hypothesis (e.g. Dow Theory's price-structure vs. volume-
confirmation split). Each ingredient is marked with what it needs and
whether that exists today:

| # | Ingredient | Real question | Buildable now? |
| --- | --- | --- | --- |
| 1 | Price leadership | Which theme/instrument is currently winning, and by how much | Yes — `cross_sectional_momentum` (live) |
| 2 | Leadership duration | Once a leader emerges, how long does leadership typically persist before reverting, as a real, measured distribution rather than a guess | Yes — new, from existing staging price history, no new data |
| 3 | Breadth confirmation | Does a leader confirmed by co-moving related proxies persist longer/more reliably than an unconfirmed single-name spike | Yes — new, from existing staging price history, no new data |
| 4 | Deterioration signal | Does a structural break in the current leader (the already-validated H-DOW02 swing-break detector, applied specifically to whoever is leading right now) mark a real, useful exit point | Yes — reuses H-DOW02's proven detector unchanged |
| 5 | Fundamental/positioning confirmation | Does real capex/earnings/guidance acceleration, or real positioning/crowding data, confirm a theme independent of price | **No.** This project has no fundamentals or positioning data provider today (`fundamental_analysis` is a registered `strategies` row with `status='draft'`, `current_version=NULL`; Benzinga/Intrinio are `planned`, not integrated). Named honestly as a real gap, not faked with a price-derived proxy standing in for it. |
| 6 | Theme identification itself | Recognizing a candidate theme early enough to matter | **Inherently qualitative, real-time, human-judgment.** Not a statistical test — see the ladder below. This is the piece closest to the user's own "how do I control the boundary" question, and it is the one piece this project cannot make falsifiable in the usual sense; it can only be tracked, dated, and reviewed honestly over real time. |

Ingredients 1-4 do **not** require waiting for new real-time episodes — they
can be tested right now, with real statistical power, against every past
leadership rotation already present in the 2004-2026 staging dataset (every
time GLD, QQQ, XLE, IGV, or another staging symbol traded places at the top
of the real cross-sectional rank is one real, historical data point). This is
the fast-accumulating half of this research program, and is queued as three
companion papers below rather than built inside this one, per the same
single-ingredient discipline. Ingredients 5-6 cannot be sped up this way —
they are honestly slow, small-N, and either blocked on data (5) or inherently
real-time and human (6). This split is the direct answer to "I don't know how
to control the boundary": the boundary is exactly where a real, existing
dataset stops being able to answer the question honestly.

### Companion papers (named, not yet built)

- **H-BETA02 — leadership duration distribution.** Ingredient 2. Walk the
  full 2004-2026 staging history; every time a symbol enters the top rank of
  the real cross-sectional ranking, measure how long it stays there before
  falling out. Produces a real, empirical answer to "how long should I
  expect to ride this," replacing a gut-feel duration with a measured one.
- **H-BETA03 — breadth confirmation value.** Ingredient 3. For every real
  historical leadership episode, test whether co-movement among related
  staging symbols at the moment leadership is established predicts a longer
  subsequent hold vs. an unconfirmed, isolated leader.
- **H-BETA04 — leader-specific deterioration signal.** Ingredient 4. Apply
  H-DOW02's already-validated swing-structure-break detector specifically to
  whichever symbol currently holds the top cross-sectional rank, and test
  whether a break in *the leader specifically* precedes a real drop in
  leadership/forward return, distinct from H-DOW02's original universe-wide
  volatility finding.

## The theme lifecycle ladder (R0-R10)

Each named candidate theme episode is read against this ladder over real
calendar time — analogous to `warsh-reaction-function.md`'s response ladder,
but for a theme's lifecycle stage rather than a policymaker's action. A
theme can stall, skip back, or never advance past R1; that is a real,
recordable outcome, not a failure of the ladder.

| Level | Meaning | Measurable how |
| --- | --- | --- |
| R0 | No candidate theme identified | n/a |
| R1 | Candidate theme named | Human-flagged, dated, logged as a hypothesis, not yet confirmed by anything quantitative |
| R2 | Price leadership emerging | Real: theme's proxy instrument(s) enter the top tier of the live cross-sectional rank for the first time |
| R3 | Price leadership sustained | Real: top-tier rank holds for a real minimum duration (threshold set from H-BETA02's own finding once it exists, not guessed here) |
| R4 | Breadth confirming | Real: multiple independently-selected, thematically-related staging proxies show the same directional tilt simultaneously (H-BETA03's mechanism) |
| R5 | Fundamental confirmation | **Blocked.** No data provider yet (ingredient 5) — this rung cannot be honestly reached until one exists |
| R6 | Position established | Not computed by this app — a real, sized decision the user makes and logs themselves, outside this app's execution scope |
| R7 | Crowding / broad recognition | Qualitative, human-flagged for now; a real quantitative proxy (positioning/flow/options-skew data) is a future candidate once available, not invented here |
| R8 | Structural deterioration signal fires | Real: H-DOW02's swing-break detector trips on the current leader specifically (H-BETA04's mechanism) |
| R9 | Exit / leadership formally ceded | Real: theme's proxy falls out of the top tier of the live cross-sectional rank |
| R10 | Retrospective close-out | Real, but only possible long after the fact: did the full real-world cycle match the thesis, and did R2-R9 fire in a genuinely useful order — not narrated as if they had after the outcome was already known |

## What would count as a real checkpoint

A checkpoint is a named candidate theme reaching a new rung on the ladder, or
a real calendar review (at least quarterly) confirming no change. Because a
full theme cycle (identification through exit through retrospective
close-out) plausibly takes multiple years, this paper will accumulate real
checkpoints slowly — likely slower than `warsh-reaction-function.md`, which
at least has a real FOMC meeting every six weeks. This is disclosed up front,
not discovered later: this paper should not be expected to reach a real
conclusion on the R0-R10 process itself for a long time. The three companion
papers exist specifically so this program produces real, useful evidence
long before that.

## Promotion criteria

None claimed yet — this is a cold-start hypothesis with one real, in-progress
episode and zero completed full cycles. Promotion requires at least 3
independent, fully-cycled real episodes (reaching R9 or clearly stalling out
before it) before the ladder's own checkpoints can be judged against real
outcomes rather than narrated in hindsight. Until then, this stays a
tracked, honest working paper — exactly the same posture `warsh-
reaction-function.md` holds today, for the same reason: real-world checkpoints
cannot be manufactured faster than they occur.

## Observation log

| Date | Theme | Rung | Note |
| --- | --- | --- | --- |
| 2026-08-26 (retrospective, exact origination date unconfirmed) | AI infrastructure capex | R1 (retrospective) | User's own account: weighted AI over quantum computing as the dominant theme, ahead of any formal process existing. Logged explicitly as pre-process and unconfirmed by any of this paper's own criteria at the time — this entry is the prior that motivated the paper, not evidence the process works. First live episode to track forward from here in real time. |
