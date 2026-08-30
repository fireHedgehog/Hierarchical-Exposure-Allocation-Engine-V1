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
| [H-XSEC-S2-004](h-xsec-s2-004-liquid-leadership-and-reversal.md) | Completed; four diagnostic candidates | Exact-date, next-open Top-100 tails found 1M/3M leader continuation and raw/sector-relative weekly reversal. No production translation or cost claim. |
| [H-XSEC-S5-002](h-xsec-s5-002-liquid-tail-implementation.md) | Completed; one clean and two fragile rough passes | A 13-sleeve 3M implementation passed all folds and 10 bp; 1M failed Development. Both weekly reversals passed 10 bp but failed 25 bp and worsened drawdown. |
| [H-XSEC-S7-001](h-xsec-s7-001-gold-reaction-function.md) | Observation | Gold reaction-function note; separate from equity leadership. |

## Candidate ledger

This is the reminder list, not a production registry.

| Candidate | Evidence | Turnover / cost / liquidity reading | Status |
| --- | --- | --- | --- |
| Sector-neutral Amihud illiquidity | [Discovery H-XSEC-S2-002](h-xsec-s2-002-price-volume-factor-screen.md); [rough implementation H-XSEC-S5-001](h-xsec-s5-001-amihud-long-only-rough-check.md) | Three monthly sleeves: 7.23% full / 8.57% holdout one-way turnover. Full/holdout excess stayed positive at assumed 25 and 50 bps. Historical 1% ADV capacity p10/median was $0.5m/$1.5m; real spread and impact are unmeasured. | **Candidate passed for further research only. Not registered.** |
| Low dollar volume | [H-XSEC-S2-002](h-xsec-s2-002-price-volume-factor-screen.md) | No implementation run: its holdout IC changed sign even though the long-horizon spread stayed slightly positive. | Parked; do not confuse it with Amihud. |
| Liquid 3M winner tail | [Discovery H-XSEC-S2-004](h-xsec-s2-004-liquid-leadership-and-reversal.md); [implementation H-XSEC-S5-002](h-xsec-s5-002-liquid-tail-implementation.md) | Thirteen weekly sleeves produced +2.10% full annualized excess, +1.70% at 10 bp, all three fold signs positive, 7.2% weekly turnover, and 52.7 bp break-even. Max drawdown was -60.87% versus -56.96% for Top-100. | **Rough implementation gate passed; further research only. Not registered.** |
| Liquid 1M winner tail | [Discovery H-XSEC-S2-004](h-xsec-s2-004-liquid-leadership-and-reversal.md); [implementation H-XSEC-S5-002](h-xsec-s5-002-liquid-tail-implementation.md) | The overlapping-sleeve translation retained positive full/recent cost stress but Development gross excess was -0.13%. | Implementation rejected; retain only as descriptive S2 context. |
| Liquid five-session reversal | [Discovery H-XSEC-S2-004](h-xsec-s2-004-liquid-leadership-and-reversal.md); [implementation H-XSEC-S5-002](h-xsec-s5-002-liquid-tail-implementation.md) | Raw/sector-relative implementations passed the frozen 10 bp gate, but rotate 85-87% weekly, break even at only 16-19 bp, fail at 25 bp, and worsen maximum drawdown to -66.67%/-73.05%. | Rough gate passed but friction-sensitive; park until real spread/impact data. |
| Classical 12-1 / 6M / 12M winner tails | [H-XSEC-S2-002](h-xsec-s2-002-price-volume-factor-screen.md); [tail retest H-XSEC-S2-004](h-xsec-s2-004-liquid-leadership-and-reversal.md) | The broad monotone screen found nothing useful. Tail excess is large recently, but each frozen row was slightly negative in Development. | Not stable candidates; do not select the recent regime after seeing it. |
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

H-XSEC-S2-004 fixed the estimand rather than adding another indicator grid. It
kept small/lower-liquidity names as a control, formed a dynamic Top-100 liquid
pool on one SPY session calendar, entered at next adjusted open, and measured
winner and loser tails separately. The result is U-shaped: the top winner tail
continues while the weakest short-term tail also rebounds, so the old near-zero
full-distribution IC was not proof that both effects were absent. Only the
1M/3M winner tails and the two five-session reversal rows clear the frozen S2
diagnostic gate. H-XSEC-S5-002 then translated only those four rows: 3M momentum
survived a 13-sleeve, next-open implementation; 1M failed its early fold; and
both weekly reversals proved too friction- and drawdown-sensitive for production
translation without real spread and impact data.
