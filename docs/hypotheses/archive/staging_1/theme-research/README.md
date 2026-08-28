# Theme research

Scope: **Conditional Theme Survival / Diffusion Research.** Not "which
asset will go up" — this folder starts from an already-observed winner
and asks how the *theme it belongs to* evolves from there. Same
lifecycle and rules as the parent
[`docs/hypotheses/README.md`](../README.md); own index for the same
reason `macro-research/` and `timing-research/` got one.

Relationship to the other subfolders: `asset-selection-research/` asks
*which* sleeve to hold; `timing-research/` asks *when* to act on a
single position. This folder is neither — it's about a *cluster's*
lifecycle (inception, breadth, survival, diffusion), sitting one level
above both. Genuinely hierarchical in the sense the project's own name
implies: `Market -> Sector -> Theme -> Leader`.

## The estimand, stated precisely

Not `P(become a winner)`. This folder only ever conditions on:

```
P(theme survives to t | already an accepted, theme-confirmed winner)
```

Winner-selection is the research design, not a bug to apologize for —
same reasoning [[project_five-levels-of-algorithm-maturity]] and this
project's other conditional work already relies on.

## The real survivorship-bias rule (distinct from the above)

Conditioning on winners is *not* survivorship bias. A real,
separate risk exists anyway: using **today's** ETF constituents to look
back at a past theme silently erases any member that was later
delisted, acquired, or dropped from its ETF — inflating the measured
survival rate. The fix is a point-in-time rule, not a disclaimer:

**Once a symbol enters a cohort at its event date, the cohort is
frozen. A later delisting, acquisition, or ETF-removal never deletes
it from history.**

Declared explicitly in every paper here: *this research intentionally
conditions on ex-post observed winners, but does not remove subsequent
losers from an admitted cohort.*

## Universe: real stage-2 data now exists, not yet activated

Corrected 2026-08-28: individual-stock/ETF-constituent data now exists
in this project (`backend/universe/stage-2-2026-08-27.json`, 693 real
symbols, `staging_universe_membership`) — the "no individual-stock data
exists" framing below was accurate when this paper was designed and no
longer is. This project's own deliberate, repeated choice to stay at
the ETF/beta level rather than single-name picking still holds
([[project_deweight-timing-toward-beta]]) — stage-2's constituent rows
exist for real cross-sectional *membership* research (which anchor(s) a
symbol belongs to), not as an invitation to build single-name timing
signals. They also load `active=0` on purpose (see
`backend/universe/loader.py`'s own disclosed reasoning) — real,
queryable rows, but not yet fetched, and deliberately not folded into
the live product's cross-sectional universe without a separate,
considered decision (see the `active` flag's own note there — it's
overloaded with "feeds the live Today-desk ranking," not just "fetch
this").

**Real anchor coverage, as actually compiled** (not the earlier,
aspirational 4-per-theme table this section used to show):

| Theme | Real stage-2 anchor(s) | Gap |
| --- | --- | --- |
| Cybersecurity | `CIBR` | `HACK`/`BUG` not compiled |
| Semiconductor | `SOXX` | `SMH` exists as a plain symbol, not compiled with membership data |
| Software | `IGV` | `SKYY`/`WCLD` not compiled |
| Robotics / AI | *(none)* | `ROBO`/`BOTZ`/`ARKQ` never compiled — a real, open gap, not silently dropped |

A single real anchor per theme is enough to run H-THEME-01/02 (breadth
is 1-vs-2-vs-3+ *within* a theme's real constituent count, not across
multiple redundant ETFs tracking the same theme) — the original
4-anchor table was itself over-scoped for what the hypothesis actually
needs. Robotics/AI has no real anchor yet; adding one (`BOTZ` is the
more liquid of the two real candidates) is real, bounded, later work if
this theme turns out to matter, not a blocker to starting 01/02 on the
three themes that already have real data.

## Clustering: hardcoded for V0, not discovered

Correlation- or embedding-based cluster discovery is a genuinely
different hypothesis ("can clustering find a theme") from this
folder's actual question ("once a theme is already recognizable, how
does it evolve"). Conflating them was the mistake in the first draft
of this design. V0 hardcodes the table above; automatic discovery is a
later, separate paper (see Roadmap) only if V0's naive version finds
something worth the extra complexity.

## Core vocabulary (disclosed terms, used consistently across this folder's papers)

- **Accepted gap**: a symbol gaps up from a base price and does not
  materially violate that base for a following window. Two candidate
  anchors recorded in parallel, not pre-committed: `pre_gap_anchor`
  (previous close) and `gap_anchor` (gap-day open). "Materially
  violate" is ATR-normalized tolerance, not a zero-tolerance breach.
- **Theme confirmation / breadth**: count of a theme's ETF anchors
  simultaneously in an accepted-gap state — `1`, `2`, `3+`. Not a
  ratio in V0, deliberately (few anchors per theme; a ratio invites
  false precision).
- **Leader**: recorded as several T0-observable candidates, not one
  hindsight pick — earliest accepted gap, largest ATR-normalized gap,
  highest relative strength at T0. Which candidate actually predicts
  anything is its own later question (see Roadmap), not assumed.
- **Survival**: `S(t) = P(theme still alive at t | confirmed at T0)`,
  real empirical Kaplan-Meier-style curve, not an IC/p-value object.
  Death: leader breaks its anchor AND breadth falls below the
  confirmation threshold AND does not recover within a disclosed
  window.
- **Diffusion**: NOT pre-labeled good or bad. A state variable — the
  fraction of the *full* universe (not just the original cluster)
  newly showing the accepted-gap pattern by a later quarter. Its
  relationship to survival is the open question this folder builds
  toward, not an assumed sign.

## Roadmap — build in order, gate later steps on earlier results

| # | Paper | Status | Gate to start |
| --- | --- | --- | --- |
| H-THEME-01 | Accepted gaps occurring in multiple anchors of the same hardcoded theme persist longer than an isolated accepted gap | Preregistered, see [`theme-confirmation-survival.md`](theme-confirmation-survival.md) | None — first real checkpoint |
| H-THEME-02 | Given H-THEME-01's cohort, the full empirical survival curve `S(t)` across 1Q/2Q/3Q/4Q, stratified by breadth at confirmation | Preregistered, same paper (same dataset, natural pairing) | None — runs alongside 01 |
| H-THEME-03 | Diffusion state changes the hazard of theme termination | Not started | Only if 01/02 show real, meaningfully different survival curves across breadth levels — no shape, no reason to add diffusion yet |
| H-THEME-04 | After diffusion, some themes enter a temporary contraction state and resume leadership rather than terminate; estimate `P(resumption | diffusion)` as a multi-state (not binary) transition | Not started | Only after H-THEME-03 finds diffusion is real and directional |
| (later, optional) | Correlation- or embedding-based automatic cluster discovery, replacing the hardcoded table | Not started | Only if the hardcoded-cluster version above finds something worth generalizing |

Building H-THEME-03/04 before 01/02 show shape would be designing the
dashboard's intelligence before the first experiment has any evidence
to react to — deliberately not doing that.
