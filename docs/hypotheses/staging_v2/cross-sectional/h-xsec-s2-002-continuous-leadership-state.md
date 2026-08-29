# H-XSEC-S2-002 - Predictive Relationship - Continuous Leadership State

| Field | Value |
| --- | --- |
| Study ID | H-XSEC-S2-002 |
| Legacy ID | None |
| Status | Design; not run |
| Dataset | Frozen 2026-08-29 Stage 2 membership; accepted adjusted price history through 2026-08-27 ET |
| Input | Daily adjusted price strength versus SPY, group anchor, and frozen peers |
| Target | Forward excess return, drawdown, rank survival, and price acceptance over 10/21/42/63/126 sessions |
| Production use | None |
| Does not claim | Earnings causality, historical PIT investability, or an entry/exit policy |

## Business question

> When a stock first becomes unusually strong, or remains unusually strong for
> a long time, what happens next to that stock? Does later group participation
> add information, or merely describe a mature trade?

The leader is primary. Sector diffusion is reported later and may be positive,
negative, or irrelevant. A leader relationship does not fail merely because
other members do not follow.

## One loop, three views

Build a daily cross-sectional panel over the broad frozen universe and each
declared group. Measure 21/63/126/252-session total return relative to SPY and
the group anchor, plus peer percentile. Preserve the continuous values; ranks
and thresholds are table coordinates, not fitted factors.

| View | Observation | Why it exists |
| --- | --- | --- |
| Emergence | First entry into a high strength percentile after being materially lower | Finds the early NVDA/MU-style transition instead of waiting for a calendar boundary |
| Persistence | A name already strong for 21, 63, or 126 sessions | Keeps long-lived leaders instead of excluding prior winners |
| Acceptance | Abrupt or smooth price move remains above its pre-move base for 5, 10, or 21 sessions | Separates a price consensus that held from a one-day shock; no earnings label is inferred |

An event begins on the first qualifying daily transition. It cannot reopen
until the name leaves that state, which prevents every day of one trend from
becoming a fake independent event. Persistence snapshots are sampled on a
fixed monthly clock and are a separate view, so they do not compete with onset
events.

## Result surface

For every view, freeze the state using information available at that close and
measure the same forward paths:

- security excess return versus SPY and group anchor;
- maximum drawdown and worst loss before any gain target;
- peer-percentile path and probability of remaining in the top decile;
- group-anchor and non-leader-member excess as secondary diffusion fields; and
- event count, distinct names, sectors, and non-overlapping calendar periods.

The compact output is one matrix, not one document per cell:

| View | State bin | Leader age / acceptance | Fold | Events / names / sectors | 10d | 21d | 42d | 63d | 126d | Max DD | Rank survival | Group response | Reading |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| emergence / persistence / acceptance | percentile or strength bin | declared bin | development / validation / holdout | pending | pending | pending | pending | pending | pending | pending | pending | secondary | not run |

Also print an event-time path at days `0, 5, 10, 21, 42, 63, 126` and a rank-
transition matrix. Means alone are insufficient: show median, positive fraction,
10th/90th percentiles, and maximum drawdown. This is the missing depth in the
first run, not extra hypotheses.

## Reading rule

A useful relationship needs a visible strength gradient, stable sign across
validation and holdout, and survival after leaving out the largest name and
sector. The magnitude may be small. No p-value, one spectacular stock, or
sector diffusion requirement can promote it.

If emergence works but persistence does not, the candidate is an early-
recognition relationship. If persistence works across leader ages, it supports
long-duration relative strength. If only diffusion predicts reversal, that is
a later Theme or Timing question. All other readings remain honest nulls.

## Boundary

This design uses price event time. An earnings version must be a later study
using the actual public earnings timestamp, reaction session, and the issuer's
own fiscal period. SEC filing acceptance alone is only a proxy and must not be
silently renamed as an earnings event.
