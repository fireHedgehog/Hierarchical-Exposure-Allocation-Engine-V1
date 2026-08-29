# Cross-Sectional Research - Staging V2

This folder asks whether price leadership contains a small, usable relationship.
It does not require sector diffusion, an earnings story, or a trading rule.

## Current studies

| Study | Status | Honest reading |
| --- | --- | --- |
| [H-XSEC-S2-001](h-xsec-s2-001-quarter-start-leadership-acceptance.md) | Inconclusive; design retired | Its calendar-quarter, new-top-three chain was unstable. This does not reject relative strength or persistent leadership. |
| [H-XSEC-S6-001](h-xsec-s6-001-quarter-clock-design-audit.md) | Confirmed diagnosis | The clock and eligibility rules systematically omit long-lived leaders and confound leader continuation with sector diffusion. |
| [H-XSEC-S2-002](h-xsec-s2-002-price-volume-factor-screen.md) | Confirmed discovery relationship | Sector-neutral Amihud illiquidity has positive 42/63-session IC and spread in validation and holdout; H-XSEC-S5-001 holds its rough implementation check. |
| [H-XSEC-S5-001](h-xsec-s5-001-amihud-long-only-rough-check.md) | Rough candidate gate passed; research only | A next-session, long-only translation retained positive full/holdout excess under explicit assumed costs. Real slippage and historical PIT membership remain untested. |
| [H-XSEC-S2-003](h-xsec-s2-003-moving-average-state-transition.md) | Development rejected; later folds locked | Four continuous MA-strength rows and four transition curves produced no stock-selection candidate. The correlated index ES panel is a timing follow-up observation only. |
| [H-XSEC-S7-001](h-xsec-s7-001-gold-reaction-function.md) | Observation | Gold reaction-function note; separate from equity leadership. |

## Candidate ledger

This is the reminder list, not a production registry.

| Candidate | Evidence | Turnover / cost / liquidity reading | Status |
| --- | --- | --- | --- |
| Sector-neutral Amihud illiquidity | [Discovery H-XSEC-S2-002](h-xsec-s2-002-price-volume-factor-screen.md); [rough implementation H-XSEC-S5-001](h-xsec-s5-001-amihud-long-only-rough-check.md) | Three monthly sleeves: 7.23% full / 8.57% holdout one-way turnover. Full/holdout excess stayed positive at assumed 25 and 50 bps. Historical 1% ADV capacity p10/median was $0.5m/$1.5m; real spread and impact are unmeasured. | **Candidate passed for further research only. Not registered.** |
| Low dollar volume | [H-XSEC-S2-002](h-xsec-s2-002-price-volume-factor-screen.md) | No implementation run: its holdout IC changed sign even though the long-horizon spread stayed slightly positive. | Parked; do not confuse it with Amihud. |
| Five-session reversal | [H-XSEC-S2-002](h-xsec-s2-002-price-volume-factor-screen.md) | No implementation run: the 10-session discovery cell reversed in holdout. | Parked as decayed evidence. |
| Classical price momentum family | [H-XSEC-S2-002](h-xsec-s2-002-price-volume-factor-screen.md) | 3-1, 6-1, 12-1, 52-week-high, and residual momentum had no useful screen result here. | No current candidate; a different design may revisit leadership. |
| Four-horizon MA strength and first alignment | [H-XSEC-S2-003](h-xsec-s2-003-moving-average-state-transition.md) | Development: continuous ICs were near zero/negative; E1/E5/EB20 sector excess was approximately zero and ES reached only +.23% at 126 sessions. Exact persistent controls were sparse. | No stock candidate; Validation and Holdout stay locked. |

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

The replacement study returned to ordinary monthly characteristic ranking. Of
15 price/volume factors, sector-neutral Amihud illiquidity was the only
relationship with stable validation/holdout IC and spread at its useful 42/63-
session horizon. Its first rough long-only translation survived assumed cost and
liquidity-floor stress, but quote-based slippage is absent and historical
capacity was sometimes small. It remains a candidate, not a production factor.

H-XSEC-S2-003 then tested, without a window grid, whether a newly completed
`20/50/100/200` state contains event-time information and whether continuous MA
distance ranks stocks broad or within sector. Development rejected the stock
relationship: all four continuous curves were near zero or negative and none of
E1/E5/EB20/ES passed the sector-excess, transition, drawdown, and multiplicity
gates together. Broad/bull contexts looked better than isolated/damaged ones,
so the rule behaved more like late confirmation than early-leader discovery.
The ES sanity panel across four correlated indexes is retained only as a prompt
for a separately frozen timing study.
