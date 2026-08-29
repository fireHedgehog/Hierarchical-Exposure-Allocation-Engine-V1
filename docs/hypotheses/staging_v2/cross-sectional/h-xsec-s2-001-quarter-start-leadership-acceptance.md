# H-XSEC-S2-001 - Predictive Relationship - Quarter-Start Leadership Acceptance

| Field | Value |
| --- | --- |
| Study ID | H-XSEC-S2-001 |
| Legacy ID | None |
| Status | Inconclusive; design retired after run 2026-08-29 |
| Dataset | Frozen 2026-08-29 Stage 2 membership; adjusted prices through 2026-08-27 ET |
| Input | Calendar-quarter gap, relative-strength, and sector-anchor onset rules |
| Target | Complete-next-calendar-quarter leader and group path |
| Production use | None |
| Does not claim | That relative strength, persistent leadership, or event-time price acceptance lacks value |

This file preserves the exact narrow design and its aggregate result. The
[structural audit](h-xsec-s6-001-quarter-clock-design-audit.md) explains why it
cannot answer the broader leadership question. No panel earned production
translation or opened the Theme evidence gate.

## Business question

> When an individual security or sector becomes a leader early in quarter
> `Q0`, does it hold that move through the end of `Q0`, and what happens to the
> leader and its sector during the complete next quarter, `Q1`?

The earlier 12-quarter persistence proposal is removed. “Eight strong quarters
out of 12” was an intuition about visible strength, not the experiment. The
first run now has one clock, three origin panels, two comparisons, and one
result table.

Diffusion is not required to identify a leader. Cross-Sectional research owns
the leader and the coarse sector follow-through result. Theme research may
later study what an already-observed group response means. Timing owns any
entry or exit rule.

## Data gate and maximum honest claim

| Input | Current state | Rule |
| --- | --- | --- |
| Membership | Frozen `2026-08-29` snapshot: 775 price identities and 19 audited anchors; ARKX `HO` and CIBR `HO.FP` correctly share Yahoo identity `HO.PA` | Historical work is a 2026-current-vintage survivor-conditioned diagnostic, not a historical investable universe |
| Price contract | `yahoo-adjclose-scaled-ohlc-v2`, fixed through `2026-08-27` ET; 775/775 accepted, zero failed or remaining | The primary run used 503 non-overlapping members of the 11 Select Sector cohorts |
| Price basis | Explicit adjusted close plus derived adjusted OHLC on one adjustment basis | Never mix raw OHLC with adjusted close |
| Primary groups | The 11 official Select Sector SPDR cohorts | XBI, SOXX, IGV, ARKX, and CIBR are later replications of the same loop, not new hypotheses |
| Broad benchmark | SPY | Other index prices are context only in the first run |
| Earnings labels | Not required | An adjusted price gap is not automatically an earnings gap; SEC filing acceptance is not an earnings timestamp |

Current weights, index signatures, and 2026 membership overlap may be displayed
as present-day context. They may not be used as historical weights, eligibility,
or causal variables. Missing prices remain missing; do not zero-fill, forward-
fill, or replace a failed member after its outcome is known.

## One quarterly clock

`Q0` and `Q1` are adjacent calendar quarters so every security and sector is
compared under the same market interval. They are not issuer fiscal quarters,
and the study contains no earnings-event clock.

1. Use only the first 21 common trading sessions of `Q0` to form candidates.
   Freeze candidates at the close of session 21. A later move cannot replace
   them.
2. Use the rest of `Q0` only to decide whether each frozen candidate held or
   failed. Acceptance becomes observable at the final common `Q0` close.
3. Measure the relationship outcome over the complete `Q1` close-to-close
   return: `adjusted_close[Q1_end] / adjusted_close[Q0_end] - 1`.
4. Take only the first eligible origin per security-panel or anchor in `Q0`.
   Do not reopen it before `Q1` ends.
5. Assign folds by the `Q1` outcome quarter: development through 2018Q4,
   validation from 2019Q1 through 2023Q2, and locked holdout from 2023Q3
   through 2026Q2. An incomplete `Q1` is right-censored.

“Held” means closing-price acceptance. Intraday adjusted-low breach and the
continuous distance from the base remain visible diagnostics, but they do not
silently change the declared close-based rule.

## Frozen panels

All three panels use the same clock and result table. Rank 1 and ranks 2-3 are
reported separately but are not different papers.

### Panel A - gap-led security

Let `g_t = adjusted_open[t] / adjusted_close[t-1] - 1`, and let
`sigma_gap_60` be the standard deviation of that security's same-basis opening
gaps over the prior 60 sessions.

A frozen candidate must satisfy all of the following:

- its first qualifying event in sessions 1-21 has `g_t > 0` and
  `g_t / sigma_gap_60 >= 2`, using 60 valid prior observations and a positive
  denominator;
- it was outside its declared group's top three at the preceding quarter-end;
  and
- at session 21 it ranks 1 or 2-3 in its group by `Q0`-to-date return, with
  positive absolute return, SPY excess, and group-anchor excess.

Its base is `adjusted_close[t-1]`. Define:

```text
hold_margin = minimum(adjusted_close[t..Q0_end] / base - 1)
```

It is `held` only when `hold_margin >= 0` and it remains top three with positive
SPY and group-anchor excess at `Q0` end. Preserve raw gap size, normalized gap
size, hold margin, and the fraction of the original gap retained; do not build
another threshold grid.

This is a corporate-action-consistent adjusted-OHLC gap. It is not the literal
raw tape gap and has no earnings attribution. Whether adjusted open also clears
the prior adjusted high is a `breakaway_gap` diagnostic, not an eligibility
rule.

### Panel B - relative-strength onset without a material gap

This panel catches a leader that rises without one Panel A-sized gap. Small
ordinary opening differences may still exist and must not be called “no gap.”
A frozen candidate must:

- have no Panel A event in sessions 1-21;
- be outside its group top three at the preceding quarter-end; and
- rank 1 or 2-3 at session 21 by `Q0`-to-date return, with positive absolute
  return, SPY excess, and group-anchor excess.

The base is its first common `Q0` adjusted close. Its hold margin uses closes
from session 22 through `Q0` end. It is `held` only when the margin is
non-negative and the same top-three and positive-excess conditions remain true
at `Q0` end. Positive relative-return day fraction is descriptive; the panel
does not claim every non-gap onset formed smoothly.

### Panel C - sector-anchor onset

This asks whether a sector itself starts leading, rather than inferring sector
strength from one stock.

It is a secondary Cross-only panel with the same quarterly clock, not part of
the individual-leader-to-sector chain and not an origin for Theme.

A sector anchor must be outside the top three of the 11 primary sector anchors
at the preceding quarter-end, then rank in the top three by SPY-relative
`Q0`-to-date return at session 21 with positive absolute and SPY-relative
return. Its base is the first common `Q0` adjusted close. It is `held` only when
it never closes below that base after session 21 and remains a positive top-
three sector at `Q0` end.

Member breadth is not an acceptance requirement. The member median and
participation change are later results, so a sector led by one early name is
not discarded before it can be studied.

## What follows in Q1

For security Panels A and B, report:

- security return, SPY excess, group-anchor excess, maximum drawdown, and
  quarter-end peer rank;
- whether the security remains top three at `Q1` end; and
- group-anchor SPY excess plus the equal-weight and median SPY excess of the
  fixed `Q0` roster after excluding every frozen origin leader.

For Panel C, report anchor SPY excess, fixed-roster equal-weight member excess,
member-median excess, maximum drawdown, and the identity of any new top-three
member. Participation change is a diagnostic column only.

Each sector-quarter is counted once. When several origin leaders exist, exclude
all of them from the non-origin member result; NVDA and MU cannot manufacture
their own sector follow-through. Sector evidence is adequate only when the
anchor path exists and at least 80% of the fixed non-origin roster has both
`Q0`-end and `Q1`-end prices.

## Two comparisons, no fitted score

1. Compare frozen rank-1 and rank-2/3 leaders with same-`Q0`, same-group ranks
   4-10 that also had positive absolute, SPY-relative, and anchor-relative
   return at session 21.
2. Within each panel, compare `Q0`-end held candidates with failed candidates
   formed under the same origin rule.

Compute each comparison inside group-quarter first, then weight usable quarters
equally. For a security with more than one declared group view, average its
security-level views before the quarter aggregate. A group-quarter missing one
side reports counts but does not enter that difference.

Do not fit a composite, optimize thresholds, or select a panel by p-value.
Always show origin magnitude because held and failed origins may start with
different strength; the comparison is a conditional relationship, not proof
that acceptance caused the outcome.

| Panel | Fold | Held state / comparison | Usable Q0 | Leaders / groups | Origin magnitude | Hold margin | Q1 leader excess / top-3 survival | Q1 max drawdown | Anchor excess | Non-origin median / equal weight | Participation delta | Worst leave-one-out | Reading |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | --- | --- |
| A | development | H250/F612; L-C +3.2% n=387; H-F +1.4% n=162 | 54 | 862/440; 80.5% adequate | H 7.55z / F 4.91z | +7.1% | H +4.2% / F +3.5%; top-3 17.7%; R1 +5.8% / R2-3 +2.0% | -15.3% | +0.5% | +1.5% / +2.2% | +4.9% | leader after ISRG +3.1%; group after XLV +0.2%/+1.2% | inconclusive / localized |
| A | validation | H86/F206; L-C +0.8% n=138; H-F +3.8% n=44 | 18 | 292/165; 100% adequate | H 5.78z / F 4.86z | +6.0% | H +2.4% / F +1.8%; top-3 12.1%; R1 +4.3% / R2-3 +0.4% | -18.3% | +0.1% | +0.0% / +0.9% | -1.3% | leader after TSLA +0.9%; group after XLU -0.3%/-0.6% | inconclusive / localized |
| A | holdout | H45/F172; L-C +1.7% n=102; H-F +10.7% n=26 | 12 | 217/112; 100% adequate | H 6.52z / F 4.80z | +5.0% | H +4.1% / F +1.9%; top-3 16.3%; R1 +0.3% / R2-3 +2.5% | -13.7% | -0.5% | -1.3% / -0.2% | +9.6% | leader after XLK +1.7%; group after XLE -1.5%/-2.3% | inconclusive / localized |
| B | development | H127/F261; L-C +1.3% n=231; H-F -2.9% n=43 | 53 | 388/274; 82.3% adequate | H +13.7% / F +10.5% | +11.6% | H +1.5% / F +3.5%; top-3 16.1%; R1 +0.3% / R2-3 +3.5% | -14.4% | -0.9% | -0.4% / +0.1% | -2.1% | leader after XLV +0.2%; group after XLP -1.4%/-0.6% | inconclusive / localized |
| B | validation | H60/F147; L-C -1.1% n=110; H-F -0.3% n=35 | 18 | 207/130; 100% adequate | H +16.2% / F +12.9% | +15.1% | H +0.3% / F -0.4%; top-3 9.3%; R1 -0.6% / R2-3 +1.5% | -18.4% | +1.2% | +1.4% / +1.8% | +1.4% | leader after XLY -1.0%; group after XLE +0.6%/+0.9% | inconclusive / localized |
| B | holdout | H36/F82; L-C -0.3% n=64; H-F +7.3% n=14 | 12 | 118/78; 100% adequate | H +12.9% / F +10.9% | +10.7% | H -2.8% / F -1.3%; top-3 8.0%; R1 +2.6% / R2-3 -1.3% | -17.4% | -1.9% | -1.6% / -0.7% | -1.2% | leader after TPR -4.2%; group after XLU -2.3%/-1.9% | inconclusive / localized |
| C | development | H49/F55; L-C -2.8% n=29; H-F -0.8% n=24 | 50 | 104/104; 82.4% adequate | H +4.0% / F +2.8% | +4.6% | H -0.5% / F -0.1%; top-3 33.8%; R1 -2.6% / R2-3 +0.6% | -8.3% | -0.5% | +0.5% / +1.1% | -23.1% | after XLP: anchor -1.0% / members -0.0% | inconclusive / localized |
| C | validation | H13/F22; L-C +2.0% n=13; H-F -1.9% n=7 | 17 | 35/35; 100% adequate | H +7.7% / F +3.8% | +9.4% | H -1.9% / F -0.0%; top-3 33.3%; R1 -4.0% / R2-3 +2.3% | -13.5% | -1.9% | +1.6% / +2.7% | -11.8% | after XLV: anchor -2.9% / members +0.9% | inconclusive / localized |
| C | holdout | H8/F11; L-C -6.3% n=5; H-F -5.8% n=6 | 11 | 19/19; 100% adequate | H +4.7% / F +4.2% | +5.5% | H -6.1% / F -3.4%; top-3 37.5%; R1 -8.2% / R2-3 -1.0% | -8.6% | -6.1% | -5.2% / -4.6% | -29.5% | after XLU: anchor -8.9% / members -7.9% | inconclusive / localized |

Use only four readings:

- `group confirmed`: both sector paths have the same positive direction in
  validation and holdout; report leader continuation or failure separately so
  a successful sector discovery through handoff is not discarded;
- `leader only`: leader continuation is stable while adequately observed
  anchor and member paths are both non-positive;
- `both failed`: leader continuation and both adequately
  observed group paths are stably non-positive; or
- `inconclusive / localized`: coverage is insufficient, folds disagree, or a
  named security or sector controls the result.

Missing or mixed sector evidence can never become `leader only`.

### Result reading

The loop processed 2,242 frozen leaders and 4,474 matched rank-4/10 controls.
Panel A retained a localized leader relationship in holdout (held leaders
+4.1% versus SPY), but the same episodes had -0.5% anchor and -1.3%
non-origin-member paths. Panel B's held-leader result changed from +0.3% in
validation to -2.8% in holdout. Panel C was directly adverse in holdout:
-6.1% anchor excess and -5.2% member-median excess. None passes the declared
fold and leave-one-out standard.

| Panel | Frozen leaders | Origin / acceptance diagnostic | Close-held with intraday breach |
| --- | ---: | --- | ---: |
| A | 1,371 | Average raw gap +4.9%; 88.5% breakaway; 4.66x retained | 16.0% |
| B | 713 | Day-21 anchor excess +12.5%; positive-relative-day fraction 53.8% | 0.4% |
| C | 158 | Day-21 SPY excess +3.9%; most frequent new Q1 top-three members TPL (6), EQT (5), MLM (5) | Not applicable |

## Current observation view, not another study

| As of / Q0 | Subject | Group | Panel | Origin magnitude | Base | Current hold margin | Q0 rank | Forming / held / failed / immature | Price coverage |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| 2026-08-27 / 2026Q2 | 25 Panel-A origins | 11 sectors | A | Frozen | Per security | 10 held / 15 failed | Frozen ranks | Q1 immature | 100% |
| 2026-08-27 / 2026Q2 | 3 Panel-B origins | 3 sectors | B | Frozen | Per security | 0 held / 3 failed | Frozen ranks | Q1 immature | 100% |
| 2026-08-27 / 2026Q2 | XLK | XLK | C | +8.5% | 134.75 | +20.0% | 1 | held; Q1 immature | 100% |
| 2026-08-27 / 2026Q3 | 19 Panel-A origins | 10 sectors | A | Frozen | Per security | 9 still top three | Current ranks | forming | 100% |
| 2026-08-27 / 2026Q3 | 11 Panel-B origins | 8 sectors | B | Frozen | Per security | 3 still top three | Current ranks | forming | 100% |
| 2026-08-27 / 2026Q3 | XLE / XLP | sector anchors | C | Frozen | Per anchor | XLE remains top three | Current ranks | forming | 100% |

Named traces were inspected only after the complete table:

| Name | Q0 / panel | Origin | Rank 21 | Hold margin / decision | Q1 SPY excess / rank |
| --- | --- | --- | ---: | --- | --- |
| MU | 2008Q2 / A | 2008-04-03 | 1 | -6.1% / failed | -23.7% / 47 |
| MU | 2009Q1 / B | 2009-01-02 | 1 | -9.2% / failed | +8.3% / 27 |
| MU | 2011Q1 / A | 2011-01-13 | 2 | +0.3% / held | -34.8% / 58 |
| MU | 2013Q1 / A | 2013-01-02 | 3 | +4.6% / held | +40.7% / 3 |
| MU | 2019Q3 / A | 2019-07-01 | 2 | +2.2% / failed | +16.5% / 9 |
| NVDA | 2011Q1 / A | 2011-01-06 | 1 | +2.8% / failed | -13.7% / 46 |
| NVDA | 2018Q1 / A | 2018-01-03 | 3 | +6.6% / failed | -1.2% / 36 |
| NVDA | 2021Q4 / A | 2021-10-26 | 3 | +5.5% / failed | -2.6% / 26 |
| NVDA | 2023Q1 / B | 2023-01-03 | 1 | +44.3% / held | +43.6% / 3 |
| NVDA | 2024Q1 / A | 2024-01-18 | 2 | +1.9% / held | +32.4% / 1 |

The opposing MU/NVDA paths are examples of the aggregate instability, not a
reason to select a threshold or override the complete leave-one-out result.

## Parked, not active experiments

| Item | Why it is parked |
| --- | --- |
| Post-recognition diffusion, handoff, saturation, and breakdown | One reduced Theme study may consume frozen Cross results only after this loop is reviewed |
| Broad-index topology | SPY/QQQ/DIA/IWM prices may be context columns; a separate transition hypothesis is not a current priority |
| Earnings-labeled gap | Requires actual fiscal-event classification and a trustworthy first-public/reaction-session clock |
| Volume, capacity, and price-community extensions | Add only if the simple price relationship survives and the extra field answers a concrete implementation question |

## Inherited evidence, not erased

- [H-SECT01](../../archive/staging_1/asset-selection-research/section-leadership-persistence.md)
  found one-quarter top-three sector persistence exactly at chance. Panel C is
  justified only because it conditions on an early-quarter onset that then
  holds; if that condition adds nothing, retire it.
- [H-SECT10](../../archive/staging_1/asset-selection-research/theme-relative-strength.md)
  found 0/24 supported 10- and 21-session ETF relationships. It did not test
  an early individual leader, `Q0` acceptance, and complete-`Q1` follow-through.
- [H-SECT07](../../archive/staging_1/asset-selection-research/sleeve-dispersion-opportunity.md)
  found no stable 2019+ relationship. Dispersion therefore stays out of the
  first loop.

## Run record

The receipt gate, three panels, comparisons, folds, rank split, leave-one-name
and leave-one-sector checks, and named traces are complete in one disposable
script:
`backend/research_lab/quarter_start_leadership_acceptance.py`. The Theme gate
was not earned. No horizon, threshold, timing rule, production factor, or
database schema change is authorized by this result.
