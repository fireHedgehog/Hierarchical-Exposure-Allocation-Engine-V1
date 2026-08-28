# Theme confirmation and survival (H-THEME-01, H-THEME-02)

Status: preregistered
Version: v0.1
Registered: 2026-08-28

Two claims sharing one dataset and one script, deliberately bundled
(same cohort, same event definition — splitting them into separate
runs would just be duplicated plumbing). See
[`README.md`](README.md) for vocabulary, the survivorship-bias rule,
and why this folder exists.

## Universe

The four hardcoded ETF-anchor themes in `README.md`'s table
(Cybersecurity, Semiconductor, Software, Robotics/AI) — new symbols,
not yet fetched. `QQQ` as the broad-market reference only, already
available.

## Thesis

**H-THEME-01**: an accepted gap (see README vocabulary) occurring
simultaneously in 2+ of a theme's ETF anchors persists longer than an
isolated accepted gap in a single anchor.

**H-THEME-02**: given H-THEME-01's cohort, the empirical survival
curve `S(t)` — real historical frequency of "still alive" at 1Q, 2Q,
3Q, 4Q post-confirmation — stratified by breadth-at-confirmation
(1 / 2 / 3+ anchors).

Falsified (H-THEME-01) by: no real separation between isolated and
multi-anchor survival at any horizon, or the wrong direction (isolated
gaps persisting longer). H-THEME-02 has no falsification condition of
its own — it's a descriptive curve, reported honestly with its real
sample size and confidence interval, not a significance test.

## Method

**Event**: accepted gap, both anchor definitions recorded in parallel
(`pre_gap_anchor`, `gap_anchor`), ATR-normalized tolerance (starting
point: 0.25x trailing ATR, disclosed, not tuned) instead of a
zero-tolerance breach. Window: quarterly, matching the survival
horizons below — checked at quarter-end, not a short fixed-day window
that then needs re-stitching into quarters.

**Cohort assembly**: for each theme, each quarter, count how many ETF
anchors are simultaneously in an accepted-gap state at quarter start.
Breadth bucket = 1 / 2 / 3+. Point-in-time cohort freeze per the
README's survivorship rule — a later ETF closure or symbol issue never
retroactively removes a historical cohort member.

**Survival**: `S(t) = P(price still above its recorded anchor,
ATR-tolerance applied | confirmed at T0)`, computed separately per
breadth bucket, real Kaplan-Meier-style empirical curve at t = 1Q, 2Q,
3Q, 4Q. Real sample size (`n` themes-quarters per bucket) and a
binomial confidence interval reported at every horizon — not just a
point estimate, per the README's confidence-vs-probability distinction.

**Leader candidates** recorded but not yet analyzed this paper (T0
data collection only) — earliest accepted gap, largest ATR-normalized
gap, highest relative strength at T0. Which one predicts anything is
deferred to a later paper once this one's core cohort/survival
machinery is proven.

## New data this paper requires

14 new ETF tickers (`CIBR`, `HACK`, `IHAK`, `BUG`, `SOXX`, `SMH`,
`PSI`, `XSD`, `IGV`, `SKYY`, `WCLD`, `ROBO`, `BOTZ`, `ARKQ`) via the
existing Yahoo daily-bars provider, same pattern as `VXX`'s addition
for H-TIME01. Real history depth unknown
until fetched — some of these (e.g. `WCLD`, `ARKQ`) are newer funds and
may not reach back to 2004 like this project's existing universe;
disclosed once found, not assumed.

## What would count as a real checkpoint

One real run of a new `research_lab/theme_confirmation_survival.py`
script against the sealed dataset, once the new tickers are fetched.

## Promotion criteria

A confirmed H-THEME-01 result (real, directional breadth-vs-persistence
separation) is real evidence this line of research is worth extending
to H-THEME-03/04 — not itself a production feature. Same bar every
paper in this project carries: no `strategies` row, no frontend
dashboard, until real evidence exists at each layer, gated per the
README's Roadmap table.

## Observation log

| Date | Checkpoint | Reading |
| --- | --- | --- |
| _none yet — design only, no data fetched_ | | |
