# H-XSEC-S6-001 - Structural Diagnosis - Quarter-Clock Leadership Audit

| Field | Value |
| --- | --- |
| Study ID | H-XSEC-S6-001 |
| Legacy ID | None |
| Status | Confirmed diagnosis |
| Dataset | Frozen 2026-08-29 Stage 2 membership; accepted adjusted price history through 2026-08-27 ET |
| Input | H-XSEC-S2-001 rules, code, and aggregate output |
| Target | Whether the design can observe emergence and persistence of a long-lived price leader |
| Production use | None |
| Does not claim | That relative strength lacks value, or that the price library has been exhausted |

## Verdict

H-XSEC-S2-001 answered its narrow question, but it was the wrong compression of
the business idea. It tested a calendar-quarter transition chain, not general
cross-sectional leadership. Its inconclusive result retires that design; it
does not retire leader strength, sector strength, or price acceptance.

## Where the design loses the signal

| Frozen choice | What it actually measures | What it systematically misses |
| --- | --- | --- |
| Common calendar `Q0/Q1` | A convenient market reporting grid | Company fiscal quarters and event-time paths; no fiscal calendar is present in the input |
| Candidate only in sessions 1-21 | Quarter-start onset | Any leader beginning on session 22 or later |
| Prior-quarter top three excluded | A new rank entrant | Persistent leaders, including the most economically interesting long-duration winners |
| Rank 1-3 at day 21 | A coarse within-sector snapshot | Gradual rank improvement, broad-universe leadership, and strength outside an arbitrary top-three cutoff |
| Held through `Q0` end | A late closing-price survivor label | When acceptance became visible and what happened during the waiting period |
| Complete next `Q1` outcome | A delayed three-month block return | 5/10/21/42/63-session continuation, reversal, and drawdown paths from the actual event |
| Leader plus anchor plus non-origin members | A multi-step propagation chain | A real single-name edge when the sector never diffuses |
| Quarter-equal aggregate | Protection from thousands of correlated stock rows | Rich cross-sectional distributions and transitions; holdout still contains only 12 outcome quarters |

The fiscal-year objection is decisive only for an earnings hypothesis: each
company's earnings clock must use its own event timestamp and fiscal period.
For a pure price-leadership hypothesis, the cleaner repair is not a different
fiscal calendar; it is an event-time clock measured from the day leadership is
first observed or reconfirmed.

## What the completed numbers mean

| Result | Narrow interpretation | Forbidden interpretation |
| --- | --- | --- |
| Panel A holdout leader excess `+4.1%` | Some accepted gap-led names continued | A stable rule: rank 1 underperformed ranks 2-3, group paths were negative, and only 12 holdout quarters existed |
| Panel B validation `+0.3%`, holdout `-2.8%` | The smooth quarter-start entrant rule was unstable | Smooth leadership never persists |
| Panel C holdout anchor `-6.1%` | This sector top-three onset rule failed in that fold | Sector strength has no information |
| Theme response flips | The delayed leader-to-diffusion-to-Q2 chain was unstable | Diffusion is always bearish or useless |

NVDA and MU illustrate the selection problem rather than repair it. Once a name
ended a quarter already in the top three, the next quarter excluded it from new
leader formation. Their strongest persistent stretches were therefore not a
continuous sample. The named trace table contains isolated re-entry episodes,
not their full leadership careers.

## Decision

- Keep H-XSEC-S2-001 as an honest record of a failed design.
- Do not tune its 21-session, top-three, or quarter-end thresholds.
- Do not translate it into production or a Timing policy.
- Replace the research clock with H-XSEC-S2-002; keep diffusion secondary.
- Keep earnings-labelled research parked until actual earnings timestamps and
  company-specific fiscal periods are available.
