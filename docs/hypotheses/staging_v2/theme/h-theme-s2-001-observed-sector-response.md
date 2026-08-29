# H-THEME-S2-001 - Predictive Relationship - Observed Sector Response and Q2 Path

| Field | Value |
| --- | --- |
| Study ID | H-THEME-S2-001 |
| Legacy ID | None |
| Status | Diagnostic only; run 2026-08-29 |
| Dataset | Frozen outputs from H-XSEC-S2-001 |
| Input | Calendar-quarter Q1 leader and sector response class |
| Target | Complete-next-calendar-quarter Q2 sector path |
| Production use | None |
| Does not claim | That diffusion lacks value under a valid continuous leader clock |

The [Cross-Sectional loop](../cross-sectional/h-xsec-s2-001-quarter-start-leadership-acceptance.md)
froze its quarter-start origins and completed their `Q1` paths, but no A/B
panel earned the Theme gate. The requested Q2 loop was still executed over the
frozen union so the rejected path is recorded; it authorizes no Theme claim or
production use.

## Business question and boundary

> After an early individual leader has either produced or failed to produce a
> sector response in `Q1`, does that observed response precede a different
> sector path in `Q2`?

Cross owns `Q0` leader formation, `Q0` acceptance, and coarse `Q1` leader and
sector follow-through. Theme consumes those frozen rows. It cannot create an
anchor-led alternative origin, backdate later breadth, or discard Cross
episodes that did not confirm.

Only security Panels A and B can feed Theme. Cross Panel C begins with a sector
anchor rather than an individual leader and ends inside Cross; Theme may not
invent an origin leader or handoff for it. If this study opens, it receives the
frozen union of all Panel A and B episodes; origin type remains a label and is
not selected after Cross results are known.

Diffusion remains lower priority. It may describe healthy continuation, late
recognition, saturation, crowding, or nothing useful. It is never required to
identify the original leader and cannot authorize an exit; Timing owns any
later policy study.

## Data and claim limit

The primary groups are the 11 official Select Sector SPDR cohorts. XBI, SOXX,
IGV, ARKX, and CIBR may later repeat the same method without receiving new
study IDs.

All historical results use the frozen 775-identity 2026 membership snapshot. They describe
today's surviving members in earlier price history, not the members an
investor could have known then. Every result shows eligible-member and price-
coverage counts. Current disclosed weights are never historical weights.

No Theme row is built until the required members have accepted
`yahoo-adjclose-scaled-ohlc-v2` receipts. Freeze the `Q0` roster and every
origin leader; never replace a missing or failed member later.

## One observable response view

At `Q1` end, display ingredients rather than a fitted health score:

| Sector-quarter | Origin types / held states | Q1 leader-set excess / top-3 fraction | Anchor SPY excess | Non-origin member-median excess | Participation change | Handoff set | Q1 response |
| --- | --- | --- | ---: | ---: | ---: | --- | --- |
| `group confirmed` (283 episodes) | A+B; held and failed retained | +6.9% / 12.3% | +5.2% | +5.6% | +22.6% | 200 handoffs | group confirmed in Q1 only |
| `leader only` (100 episodes) | A+B; held and failed retained | +8.5% / 30.8% | -3.7% | -3.9% | -14.9% | 37 handoffs | leader only in Q1 |
| `leader failed` (132 episodes) | A+B; held and failed retained | -12.4% / 3.8% | -5.4% | -4.9% | -16.6% | 117 handoffs | leader and group failed in Q1 |
| `unclassified` (297 episodes; 196 adequate) | Mixed or incomplete | +0.3% / 11.6% | -1.9% | -1.2% | -5.2% | 221 handoffs | unclassified |

The origin leader set contains every frozen Panel A/B security in that sector-
quarter, including `Q0` failures. Its Q1 SPY excess and anchor excess are the
medians across that frozen set. `Leader positive` means both are positive;
`leader negative` means both are non-positive; any other sign pair is mixed.
Every origin leader needs a Q1 endpoint or the leader-set evidence is missing.

Apply these mutually exclusive response labels in order:

- `unclassified` when leader-set evidence is missing or group coverage is
  inadequate;
- `group confirmed` when anchor and fixed-roster non-origin member-median SPY
  excess are both positive in `Q1`, with leader-set status reported separately;
- `leader only` when the leader set is positive and both adequately observed
  group paths are non-positive;
- `leader failed` when the leader set is negative and both group paths are
  non-positive; and
- `unclassified` for every remaining mixed sign pattern.

Group coverage is adequate only when the anchor path exists and at least 80%
of the fixed non-origin roster has both `Q0`-end and `Q1`-end prices. Mixed or
missing group evidence therefore stays `unclassified`. A handoff is a separate
flag: no origin leader remains top three while one or more different frozen-
roster members enter it; those entrants form the frozen handoff set.
Participation change is continuous and descriptive; no breadth threshold is
part of the first run.

## Frozen Q2 test

The unit is one sector-quarter. All frozen A/B origins in that sector-quarter
form the leader set, and all are excluded from the non-origin member result.

1. Preserve the Cross `Q0` origin and acceptance exactly.
2. Assign the response label only after the final common `Q1` close.
3. Measure the complete `Q2` anchor SPY excess, fixed-roster equal-weight and
   member-median excess, maximum drawdown, origin-leader-set top-three survival
   fraction, and handoff-set top-three survival fraction.
4. Assign development, validation, and holdout by the `Q2` outcome quarter,
   using the same calendar boundaries as Cross, then weight quarters equally.
   Do not treat security rows as independent sector samples.
5. Report every frozen episode, right-censor incomplete `Q2`, and show
   leave-one-sector and leave-one-origin-leader results.

Because the response is observed at `Q1` end, only `Q2` may be its outcome.
Within-`Q1` returns cannot be reused as proof that the response predicted
itself.

| Q1 response | Fold | Usable quarters / sectors | Q2 anchor excess | Q2 non-origin median / equal weight | Q2 max drawdown | Leader / handoff survival | Participation Q1 delta -> Q2 level | Worst leave-one-out | Reading |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- | --- | --- |
| group confirmed | development | 49/162 | -0.4% | +0.2% / +0.7% | -8.1% | 12.1% / 10.5% | +19.1% -> 49.5% | after XLV -0.7%; after INCY 11.2% leader survival | inconclusive / localized |
| group confirmed | validation | 18/78 | +0.5% | +0.5% / +1.3% | -10.1% | 10.9% / 19.2% | +20.8% -> 50.9% | after XLK -0.0%; after CRWD 9.5% leader survival | inconclusive / localized |
| group confirmed | holdout | 12/42 | -3.4% | -3.6% / -1.9% | -8.3% | 12.3% / 17.5% | +27.5% -> 39.1% | after XLF -4.8%; after ECHO 10.2% leader survival | inconclusive / localized |
| leader only | development | 36/51 | -0.1% | +1.2% / +1.9% | -7.3% | 9.2% / 9.3% | -15.2% -> 54.5% | after XLU -0.7%; after VLO 7.3% leader survival | inconclusive / localized |
| leader only | validation | 14/27 | -1.4% | -2.1% / -0.5% | -9.8% | 13.9% / 9.9% | -14.7% -> 43.8% | after XLF -2.2%; after COST 10.3% leader survival | inconclusive / localized |
| leader only | holdout | 8/19 | +3.0% | +1.7% / +2.9% | -8.1% | 16.8% / 16.7% | -6.1% -> 48.4% | after XLE +0.5%; after NRG 5.0% leader survival | inconclusive / localized |
| leader failed | development | 34/64 | -1.1% | +0.3% / +0.3% | -8.1% | 9.7% / 17.7% | -12.0% -> 49.2% | after XLV -1.6%; after ALGN 8.3% leader survival | inconclusive / localized |
| leader failed | validation | 17/34 | -0.3% | +0.4% / +0.2% | -11.7% | 15.7% / 8.8% | -14.8% -> 47.9% | after XLI -0.8%; after T 13.7% leader survival | inconclusive / localized |
| leader failed | holdout | 11/30 | +1.3% | +0.6% / +1.0% | -7.6% | 16.0% / 9.3% | -20.7% -> 52.7% | after XLK +0.7%; after GNRC 11.5% leader survival | inconclusive / localized |
| unclassified | development | 53/200 | +0.5% | +1.4% / +2.0% | -8.7% | 9.0% / 14.0% | -4.7% -> 54.4% | after XLU +0.3%; after CF 8.7% leader survival | inconclusive / localized |
| unclassified | validation | 18/55 | -0.2% | +0.4% / +0.8% | -10.6% | 13.3% / 10.3% | -6.9% -> 49.8% | after XLK -0.5%; after CNP 12.4% leader survival | inconclusive / localized |
| unclassified | holdout | 10/39 | -0.4% | -1.3% / +0.0% | -7.1% | 12.4% / 19.1% | -2.8% -> 45.5% | after XLRE -1.0%; after NEE 11.2% leader survival | inconclusive / localized |

The allowed readings are `durable group confirmation`, `leader-only response`,
`adverse or late broadening`, and `inconclusive / localized`. No label becomes
a trade instruction.

The 812 sector-quarter episodes are deliberately represented by the four
response rows and fold table rather than copied into 812 Markdown rows. The
single disposable script rebuilds the frozen episode ledger. Most importantly,
the apparently healthy Q1 `group confirmed` state changed from +0.5%/+0.5%
anchor/member excess in validation to -3.4%/-3.6% in holdout Q2. The
`leader only` state flipped the other way. No response is stable enough to
interpret as durable diffusion, saturation, or handoff.

## Parked until this simple loop earns expansion

| Item | Reopen only when |
| --- | --- |
| Within-quarter diffusion clock | The Q1-end response has a stable Q2 relationship and a finer clock could change an actionable decision |
| Saturation or crowding | Broad participation is observed often enough and independently precedes future breakdown rather than merely describing a past rise |
| Earnings or price-shock propagation | Cross has an approved event clock; an earnings version also has a trustworthy fiscal-event timestamp |
| Unlabeled price communities | Named sector/theme groups demonstrably miss a useful relationship |

## Run record

All receipts and the Cross loop completed first. The Q2 diagnostic then consumed
the frozen union of every A/B episode, including failures, across all 11
sectors. The evidence gate stayed closed and every response reading is
`inconclusive / localized`; no Timing policy, threshold grid, new Theme
document, or production translation is nominated.
