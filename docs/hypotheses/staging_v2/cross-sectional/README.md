# Cross-Sectional Research - Staging V2

This folder asks whether price leadership contains a small, usable relationship.
It does not require sector diffusion, an earnings story, or a trading rule.

## Current studies

| Study | Status | Honest reading |
| --- | --- | --- |
| [H-XSEC-S2-001](h-xsec-s2-001-quarter-start-leadership-acceptance.md) | Inconclusive; design retired | Its calendar-quarter, new-top-three chain was unstable. This does not reject relative strength or persistent leadership. |
| [H-XSEC-S6-001](h-xsec-s6-001-quarter-clock-design-audit.md) | Confirmed diagnosis | The clock and eligibility rules systematically omit long-lived leaders and confound leader continuation with sector diffusion. |
| [H-XSEC-S2-002](h-xsec-s2-002-continuous-leadership-state.md) | Design; not run | Observe emergence, persistence, and accepted price shocks on an event-time clock, then measure the full forward path. |
| [H-XSEC-S7-001](h-xsec-s7-001-gold-reaction-function.md) | Observation | Gold reaction-function note; separate from equity leadership. |

## What the first run did and did not find

The completed run found that one very specific chain was not stable:

```text
new top-three name in the first 21 calendar-quarter sessions
-> still top three at calendar-quarter end
-> leader and sector continue during the next complete calendar quarter
```

That chain excluded any name already top three at the prior quarter-end. It also
missed leaders beginning after session 21 and delayed the outcome clock until
the next calendar quarter. A stock can therefore lead the market for years and
appear only occasionally in the event ledger.

The next study starts from daily leadership state and event time. Sector
diffusion remains a secondary result. Earnings-specific work stays parked until
actual event timestamps and company-specific fiscal periods exist.
