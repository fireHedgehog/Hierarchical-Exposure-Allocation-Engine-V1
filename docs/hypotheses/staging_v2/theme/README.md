# Theme Research - Staging V2

This type starts after a theme is already recognized. It asks whether breadth
helps describe how long that leadership survives; it does not discover winners
or issue trade timing.

## H-THEME-S2-001 - Theme Confirmation and Survival

| Field | Value |
| --- | --- |
| Legacy ID | H-THEME-01 / H-THEME-02 |
| Role | S2 - Predictive Relationship |
| Status | Preregistered; wait for Stage 2 fetch completion |
| Dataset | Disposable Stage 2 daily bars and membership snapshot |
| Input | Breadth at the start of an accepted theme-leadership episode |
| Target | Survival at 1, 2, 3, and 4 quarters |
| Production use | None |
| Does not claim | Which theme becomes a winner or when to trade it |

Hypothesis: conditional on a theme already becoming a leader, broader member
confirmation precedes longer survival than isolated leadership.

## Initial loop

| Loop axis | Initial values |
| --- | --- |
| Theme anchor | `CIBR`; `SOXX`; `IGV` membership groups |
| Event definition | Accepted leadership using a predeclared anchor and ATR tolerance |
| Breadth | Buckets frozen after data-coverage audit and before outcome inspection |
| Horizon | 1Q; 2Q; 3Q; 4Q |
| Cohort rule | Freeze admitted members at entry; never delete later losers |

The current membership snapshot is not point-in-time. Cohort freezing prevents
later mutation but cannot reconstruct historical constituents. Robotics/AI is
excluded until a real membership anchor exists.

| Theme | Event spec | Breadth | Horizon | Cohorts/N | Survival | Interval | Delta vs isolated | Effect rank | p | BH q | q rank | Stable | Verdict |
| --- | --- | --- | --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| _unrun_ | | | | | | | | | | | | | |

## Manual gates

1. Finish the fetch and audit actual coverage.
2. Approve the event anchor, ATR tolerance, breadth buckets, and cohort rule.
3. Run every approved theme through the same loop.
4. Do not add diffusion, automatic clustering, probability, or policy studies
   unless this first relationship shows a stable, economically useful shape.
