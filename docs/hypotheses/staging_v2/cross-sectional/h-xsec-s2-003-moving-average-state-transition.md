# H-XSEC-S2-003 - Moving-Average State, Transition, and Relative Strength

| Field | Value |
| --- | --- |
| Status | Development complete; no stock candidate; Validation and Holdout locked |
| Type | Predictive relationship |
| Category | Cross-sectional |
| Dataset | Stage 2 adjusted-close/volume library |
| Universe | Highly liquid names with unique 11-sector membership |
| Production authority | None |

## Question

> When a liquid stock first completes a simple four-horizon uptrend, is that an
> informative entry transition, and does relative moving-average strength select
> the better names after the transition?

This deliberately separates four ideas that chart language often mixes:

1. **absolute state** - is this stock above its own trend references now?
2. **transition** - did that state begin today, or has it existed for weeks?
3. **cross-sectional selection** - is it stronger than other eligible stocks?
4. **market context** - is SPY trending, correcting, repairing, or damaged?

No short position is implied. A failed signal can still be useful as a warning
or as evidence that confirmation is needed.

## Why H-XSEC-S2-002 did not test this

The prior screen tested whether month-end trailing-return ranks monotonically
predicted forward-return ranks. Its `3-1`, `6-1`, and `12-1` definitions even
skip the most recent 21 sessions. It contained no moving average, no daily state
transition, and no event age. A stock could first align, fail, and align again
inside one month without any of those paths entering the old observation.

Therefore its momentum null is retained for those exact factors, but it neither
accepts nor rejects this study. This is a new estimand, not a parameter rescue.

## Research spine

Simple moving-average rules have long been studied as time-series signals
([Brock, Lakonishok, and LeBaron, 1992](https://doi.org/10.1111/j.1540-6261.1992.tb04681.x)).
They are not identical to ordinary trailing-return momentum: moving-average
timing can produce different payoffs
([Han, Yang, and Zhou, 2013](https://doi.org/10.1017/S0022109013000586)), and a
multi-horizon trend factor explicitly combines short-, intermediate-, and
long-horizon price information
([Han, Zhou, and Zhu, 2016](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2182667)).

Most directly, the ratio of the 21-day to 200-day moving average has published
cross-sectional evidence that is stronger on the long side
([Avramov, Kaplanski, and Subrahmanyam, 2021](https://doi.org/10.1002/rfe.1118)).
That supports testing moving-average distance; it does not prove that a first
four-line alignment is useful.

Industry momentum can absorb an important part of individual-stock momentum
([Moskowitz and Grinblatt, 1999](https://doi.org/10.1111/0022-1082.00146)).
That is why broad ranking is a real result here and within-sector ranking is a
decomposition, not an automatic replacement.

Market conditioning is kept because momentum has historically varied with
prior market state
([Cooper, Gutierrez, and Hameed, 2004](https://doi.org/10.1111/j.1540-6261.2004.00665.x))
and can fail violently during rebounds after market damage
([Daniel and Moskowitz, 2016](https://www.nber.org/papers/w20439)). We freeze one
small specification instead of searching thousands of moving-average rules;
that search is a known data-snooping trap
([Sullivan, Timmermann, and White, 1999](https://doi.org/10.1111/0022-1082.00163)).
[Practitioner screens](https://www.chartmill.com/trading-ideas/317-High-RS-Stock-MM)
using price, `SMA20/50/100/200`, and relative strength show that the intuition
is common; they are motivation, not evidence.

## Frozen data and eligibility

| Choice | Frozen value |
| --- | --- |
| Price basis | Adjusted close for every SMA, signal, breakout, and return |
| Moving averages | `SMA20`, `SMA50`, `SMA100`, `SMA200`; no window grid |
| Equity cohort | Current-vintage names with one unique Select Sector mapping; anchor ETFs excluded |
| Price gate | Signal-date raw close >= `$5` |
| Primary liquidity gate | Median prior-21-session raw dollar volume >= `$25m` |
| Liquidity sensitivity | `$10m`; it cannot rescue a failed primary result |
| History gate | 200 valid prior sessions for the security and reference ETF |
| Continuous formation | Final trading session of each month |
| Event formation | Every valid trading session |
| Daily response path | Sessions 1 through 126 after executable entry |
| Reported checkpoints | 5, 10, 21, 42, 63, and 126 complete holding intervals |
| Folds | Development signal dates through 2018-12-31; validation 2019-01-01 through 2023-06-30; locked holdout from 2023-07-01 |

The dollar-volume gate means **highly liquid**, not large-cap: market
capitalization is not in this dataset. The current-vintage historical roster is
the already-declared discovery limitation and is not relitigated here.

Stock prices come from the Stage 2 library; SPY, QQQ, DIA, IWM, and the sector
ETFs come from the sealed anchor dataset on the same SPY session calendar. XLC
begins on 2018-06-19 and XLRE on 2015-10-08. Their earlier observations remain
null: no ETF is backfilled and no SPY substitute is used. Consequently a stock
enters the primary sector-relative sample only after its actual sector ETF has
the frozen 200-session history. Coverage by sector is an output, not a reason to
rewrite this rule after seeing returns.
The sealed anchor schema predates the dual-basis migration: its legacy `close`
column is the stored adjusted-close series, while the newer `adjusted_close`
column is null. Reading `COALESCE(adjusted_close, close)` therefore preserves
the adjusted basis; raw anchor OHLC is never used.

The 21-session liquidity median requires 21 finite, positive raw-dollar-volume
observations. Each reported response curve uses only formations whose `t+1`
entry and full 126-session endpoint both remain inside the same fold. Short
horizons are not backfilled with formations near a fold boundary; therefore all
points on one curve describe the same cohort and no Development return borrows
prices from Validation.

## Frozen state, episode, and signal definitions

For adjusted close `P` and `L in {20, 50, 100, 200}`:

```text
d_L = log(P / SMA_L)
D4  = mean(d_20, d_50, d_100, d_200)
MAD = log(SMA20 / SMA200)
A4  = 1 when P > SMA20, SMA50, SMA100, and SMA200
S4  = 1 when P > SMA20 > SMA50 > SMA100 > SMA200
```

- `D4` is the equally weighted four-horizon cross-sectional strength.
- `MAD` is the simpler 20/200 literature benchmark. If only MAD works, the
  four-line construction added nothing.
- Broad ranks preserve sector/theme leadership. Within-sector ranks separately
  reveal stock-specific leadership. Neither may replace the other.

One `A4` episode begins when `A4` changes from zero to one and ends on the first
later close with `A4=0`. A new event requires a real intervening state failure;
choppy one-day episodes stay in the data as honest failed attempts.
Unavailable history is not zero: the first day on which SMA200 becomes
observable cannot manufacture an event. The first eligible episode must have a
prior observable close with `A4=0`; an episode already active when history first
becomes observable is skipped until it genuinely fails and restarts.

The single event loop contains four economically different entry concepts:

| Event | Once-per-episode definition at close `t` | What it tests |
| --- | --- | --- |
| `E1` | The `A4` episode begins | First stand/recapture; earliest trial |
| `E5` | `A4` age first reaches five consecutive closes | Waiting for observable acceptance |
| `EB20` | First close in the episode above the prior 20-session highest close | Close-confirmed short breakout |
| `ES` | First close in the episode with `S4=1` | Waiting for fully ordered trend |

`EB20` is the only breakout lookback. There is no 20/50/100/200 breakout grid.
Adjusted close can test a close-confirmed breakout, not an intraday breakout,
gap, stop fill, or traded high. Events may coincide; the coverage table records
that overlap instead of pretending they are independent discoveries.

## Exact event clock and exits

For a signal known after close `t`:

```text
entry close = t + 1
fixed exit  = t + 1 + h, h in {5, 10, 21, 42, 63, 126}
```

A five-session result therefore contains five complete close-to-close holding
intervals. A missing entry or endpoint is null; prices are never carried
forward. All fixed exits describe one response curve, not six separately
selectable strategies.

The month-end continuous `D4/MAD` observations use the same executable clock:
rank after close `t`, enter at adjusted close `t+1`, and measure through
`t+1+h`. Moving averages include the signal-date close and require their full
stated number of finite observations.

Month-end means the final session on the shared SPY calendar; a missing stock
close stays missing rather than falling back to that stock's last close. A
missing close inside an SMA window makes the state unavailable and resets its
episode. `EB20` is strictly `P_t > max(P[t-20:t])` with all 20 prior closes
present.

One supplemental strategy-shaped exit is reported:

- `E1`, `E5`, and `EB20`: after entry, observe the first close with `A4=0` and
  exit at the following close;
- `ES`: observe the first close with `S4=0` and exit at the following close;
- cap either rule at 126 sessions.

This state exit is descriptive in S2. Stops, costs, and a chosen holding rule
belong to S5 if a relationship survives.

## Observable market context

“A bottom” cannot be known at the bottom. The honest real-time label is a repair
attempt. SPY supplies one fixed two-by-two state known at the signal close:

| SPY close vs SMA50 | SPY SMA50 vs SMA200 | Label |
| --- | --- | --- |
| Above | Above | Bull |
| At/below | Above | Correction |
| Above | At/below | Repair attempt |
| At/below | At/below | Bear |

Also record `A4 breadth`, the fraction of eligible names currently above all
four averages: `<=20%` isolated, `>20% to <=50%` building, and `>50%`
broad/diffuse. Regime and breadth are diagnostics only. A winning context cell
cannot rescue an overall null without a later, separately frozen hypothesis.

## What the one loop tests

| Axis | Frozen cells | Role | May the best-looking cell be selected afterward? |
| --- | --- | --- | --- |
| Continuous signal | `D4`, `MAD` | Cross-sectional ranking | Only through the fold policy below |
| Event | `E1`, `E5`, `EB20`, `ES` | Stand vs acceptance vs breakout vs ordering | Only through the fold policy below |
| Horizon | Daily 1-126; report 5/10/21/42/63/126 | One decay curve | No isolated best-horizon claim |
| Stock benchmark | Sector ETF primary; SPY secondary; absolute return visible | Separate stock selection from beta | No benchmark substitution |
| Cross-section | Broad and within-sector | Theme/sector-common vs stock-specific | Both stay visible |
| Liquidity | `$25m` primary; `$10m` sensitivity | Capacity robustness | No substitution |
| Context | Four SPY states and three breadth states | Heterogeneity diagnosis | No general-rule rescue |
| Index sanity panel | SPY, QQQ, DIA, IWM under the identical rule | Time-series robustness | No choosing the winning ETF |

Applying the same frozen rule to several instruments is not itself tuning. It
becomes tuning if the windows, confirmation age, breakout length, liquidity
gate, horizon, benchmark, regime, or ETF are chosen after viewing their returns.
Any such change is a new hypothesis revision and all already viewed dates become
development evidence.

SPY, QQQ, DIA, and IWM are highly correlated observations, not four independent
confirmations. The index panel reports their equal-weight mean as its headline,
then every instrument separately. It is descriptive, receives no curve-level
inference in this Cross paper, and cannot promote a stock-selection factor by
itself. Each ETF event is compared with that same ETF's persistent-state
non-event dates in the same fold, SPY state, and trailing-63-session volatility
quintile; missing matches stay null.
The volatility quintile is a past-only expanding rank of that ETF's trailing
63-session realized volatility and requires at least 252 earlier volatility
observations. Persistent comparison dates must precede the event date.

## Return path, profit window, and half-life

For event `e`, entry `t+1`, stock `i`, and its sector ETF `B`:

```text
x_i(h) = log(P_i[t+1+h] / P_i[t+1])
       - log(B[t+1+h]   / B[t+1])
C_all,e(h) = event-date-equal-weight mean of x_i(h) across all valid event names
```

Displayed `C` is `C_all`. For the transition-value curve, restrict the event leg
to names with at least three exact controls, call its date mean `C_matched,e`,
and subtract the paired same-date matched-control mean:

```text
Delta_e(h) = C_matched,e(h) - Control_matched,e(h)
```

Raw full-sample `C` asks whether the event made money relative to its sector;
the smaller paired `Delta` asks whether “first/new” added information over
already-established leaders. They are deliberately displayed with separate
coverage and must not be algebraically combined as if they were one cohort.

The daily curve is compressed into non-overlapping marginal blocks:

| Block | Interpretation |
| --- | --- |
| 1-5 | First week |
| 6-10 | Second week |
| 11-21 | Rest of first month |
| 22-42 | Second month |
| 43-63 | Third month |
| 64-126 | Months four through six |

For consecutive endpoints `a,b`, marginal excess is `C(b)-C(a)` and marginal
excess per session divides that value by `b-a`. This distinguishes “earned only
in week one, then plateaued” from “earned in week one, then reversed.”

Report these descriptive duration measures for both development and later
folds; none is an automatic exit rule:

- `peak day`: earliest day from 1-126 with maximum positive `C`;
- `T50 accrual`: first day by which 50% of that positive peak was earned;
- `giveback half-life`: first day after the peak with `C` at or below 50% of
  the peak; `>126` if not observed, `NA` if the peak is not positive;
- `state median life`: median sessions until `A4` fails (`S4` for `ES`), with
  episodes still alive at 126 right-censored; use the Kaplan-Meier median and
  show `>126` when more than half remain alive;
- `exhaustion`: first two consecutive marginal blocks that are non-positive.

A flat later curve is a plateau, not a reversal. A negative later block with
positive cumulative `C` is partial giveback. Only `C<=0` after a prior positive
peak is full reversal.

State age is measured at signal close. Precisely, `T_fail` is the first
`k in 1..126` whose close `t+k` makes the relevant state false, and
`S(h)=Pr(T_fail>h)`; no observed failure by 126 is right-censored. Trading still
enters at `t+1`. A failure at `t+k` is observable at that close and the
supplemental state exit uses close `t+k+1`, capped at close `t+127`.

## Controls and dependence

The primary stock control for each event date is same-sector eligible names
whose relevant state is at least 21 sessions old, in the same `D4` quintile and
liquidity quintile. `ES` uses persistent `S4`; the other events use persistent
`A4`. If no valid control exists, the delta is null rather than silently
broadening the match.

Both control quintiles are formed on that signal date inside that sector's
primary `$25m` eligible cohort, using average ranks for ties and fixed 20%
percentile bins (`Q5` is highest). At least three endpoint-valid controls are
required for each event-name; controls are equally weighted and may be reused
for another event-name. Names firing the event being evaluated that day are
excluded. First compute each event-name minus its matched-control mean, then
equal weight event-names within date, then treat event dates as the inferential
observations. Eligibility and age use information at signal close only; a
control's later state failure remains in its realized path.

The `$10m` sensitivity is a complete alternate eligibility pass: it recomputes
its own within-sector D4 and liquidity quintiles so newly admitted names can be
matched, but it keeps breadth context on the `$25m` primary cohort. It remains
descriptive and cannot rescue a primary failure.

For the continuous panel, Broad ranks all eligible stocks once and requires at
least 30 names. Within-sector computes Spearman IC and high-minus-low log-return
spread separately in sectors with at least 10 names and at least two names in
each extreme quintile, then equal weights valid sectors. Each formation is one
time observation; stock-months are never pooled as independent observations.

Multiple stocks firing on one date are first equal weighted into one date
cohort. Repeated genuine episodes remain, but repeated days within one episode
are not new events. Dependence is handled with fixed, non-overlapping calendar
blocks (January-June and July-December), keeping event dates, controls, and
overlapping 126-session paths together.

Inference is deliberately small:

- continuous family: one curve-level block statistic for each of `D4/MAD x
  broad/within-sector`, then BH across those four rows;
- event family: one curve-level block statistic for each of `E1/E5/EB20/ES`,
  then BH across those four rows;
- individual horizons, contexts, liquidity sensitivity, and ETF rows describe
  the curve and robustness; they are not extra chances to pass.

The curve statistic is fixed as the one-sided maximum t-statistic across the
six reported checkpoints: IC for a continuous row and `Delta` sector excess
for an event row. The denominator is the half-year block-cluster standard error.
Its raw p-value is `(1 + null >= observed) / 10,001`, from 10,000 whole-block
sign flips with seed `20260829`; one draw uses the same block signs for every
horizon and row in a family. The four row p-values in each family receive BH
correction. Fewer than eight non-empty blocks or 30 dates is `insufficient`.
The Development nomination guardrail is `q <= .10`. A small q can flag a curve
for review, but the adjacent-path and fold rules below still decide whether it
is a candidate.

## Fold and selection protocol

The same disposable loop supports three manually released outputs:

1. **Development:** print every frozen row and its complete path. Nominate at
   most one simplest event family and one duration label: short (5/10), medium
   (21/42), or long (63/126). “No candidate” is valid.
2. **Validation:** apply that exact nomination. It may retain or retire; it may
   not change SMA windows, event definition, benchmark, or duration band.
3. **Holdout:** reveal 2023H2 onward only after the nomination is frozen. It is
   opened once. A changed rule after this point needs new forward evidence.

This is still one code loop and one document, not automated dispatch or a paper
per cell. The manual output gate merely prevents the holdout from becoming a
menu.

For nomination, a duration band is coherent only when both of its checkpoints
have `C>0` and `Delta>0`; the earliest coherent band is the descriptive profit
window, not an optimized exit. If several event rows satisfy every gate, the
fixed simplicity order is `E1`, `E5`, `EB20`, then `ES`. For the continuous
benchmark, retain the simpler `MAD` whenever both `MAD` and `D4` pass. At the
longer checkpoint of a nominated band, close-based event median maximum
drawdown must be no worse (no more negative) than its matched control median;
there is no hidden tolerance.

## Development result - 2026-08-29

The read-only implementation is
[`moving_average_state_transition.py`](../../../../backend/research_lab/moving_average_state_transition.py).
It loaded 775/775 accepted receipts, truncated every price array at
2018-12-31 before computing a response, and used 10,000 half-year block sign
flips. Validation and Holdout were neither calculated nor printed.

### 1. Coverage and overlap

Only signals with a complete fold-contained 126-session path enter these
counts. `A4 episodes` equals the number of genuine, observable E1 name-events.

| Fold | Mean eligible | A4 episodes | E1 dates/names | E5 dates/names | EB20 dates/names | ES dates/names | Same-name/day overlap |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Development | 329.5 | 47,449 | 3,055 / 47,449 | 2,716 / 22,234 | 2,852 / 25,420 | 2,937 / 27,913 | 33,120 (37.5%) |
| Validation | locked | | | | | | |
| Holdout | locked | | | | | | |

XLC supplies no Development observation because its real 2018 inception plus
the 200-session history gate extends beyond the fold. XLRE contributes a mean
4.3 names after its real 2015 inception. The other nine sector ETFs begin with
the 2004 library calendar; nothing was backfilled.

### 2. Continuous cross-section

Each cell is `mean month-end Rank IC / Q5-Q1 log-return spread`; `p/q` applies
once to the full six-checkpoint curve. There are 153 true month-end formations
and 26 half-year blocks.

| View / signal | 5d | 10d | 21d | 42d | 63d | 126d | Curve p / q |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Broad `D4` | -.012 / -.11% | -.013 / -.07% | -.022 / -.20% | -.035 / -.48% | -.038 / -.85% | -.033 / -.94% | .9585 / .9585 |
| Broad `MAD` | -.011 / -.17% | -.002 / +.04% | -.020 / -.19% | -.034 / -.62% | -.033 / -.78% | -.029 / -.70% | .7812 / .9585 |
| Within-sector `D4` | -.012 / -.07% | -.011 / +.03% | -.006 / +.11% | -.014 / +.06% | -.014 / +.00% | -.014 / -.12% | .9088 / .9585 |
| Within-sector `MAD` | -.009 / -.11% | +.002 / +.09% | -.004 / +.07% | -.013 / -.16% | -.013 / -.25% | -.009 / -.06% | .6971 / .9585 |

There is no positive continuous relative-strength relationship in Development.
The broad rows become mildly negative at longer horizons; that is an
exploratory anti-momentum observation, not the one-sided hypothesis tested here.

### 3. Event checkpoints

The compact curve order is `5/10/21/42/63/126`. Absolute market drift is kept
separate from stock-selection excess.

| Event | Absolute return | Return vs SPY | `C`: return vs sector | `Delta`: vs persistent | C dates/names | Delta dates/names | Curve p / q |
| --- | --- | --- | --- | --- | ---: | ---: | --- |
| E1 | +.10/+.24/+.61/+1.29/+1.89/+3.64% | -.04/-.06/-.10/-.16/-.27/-.38% | -.06/-.09/-.07/-.04/-.07/-.04% | +.23/+.58/+.31/+.19/-.11/-1.59% | 3,055 / 47,449 | 116 / 142 | .3437 / .9547 |
| E5 | +.10/+.22/+.64/+1.36/+1.93/+3.51% | -.05/-.10/-.12/-.11/-.25/-.45% | -.07/-.08/-.06/+.01/-.05/-.12% | -.23/-.21/-.39/-1.49/-1.08/-1.34% | 2,716 / 22,234 | 86 / 101 | .9003 / .9547 |
| EB20 | +.08/+.21/+.54/+1.29/+1.91/+3.59% | -.04/-.08/-.12/-.11/-.13/-.30% | -.07/-.11/-.15/-.01/+.00/-.04% | -.33/-.50/-1.26/-1.66/-2.01/-3.21% | 2,852 / 25,420 | 80 / 89 | .9547 / .9547 |
| ES | +.13/+.34/+.81/+1.63/+2.32/+3.73% | -.04/+.00/+.08/+.18/+.11/-.07% | -.04/-.00/+.10/+.19/+.22/+.23% | -.20/-.17/-.45/-1.76/+.11/-1.98% | 2,937 / 27,913 | 63 / 69 | .8641 / .9547 |

The exact two-quintile persistent-control match is sparse. `Delta` therefore
describes only 63-116 event dates per row and must not be confused with the much
broader `C` result. That limitation does not create a candidate: `C` itself is
approximately zero for E1, E5, and EB20, while ES is only +.23% after 126
sessions and fails the transition and multiplicity gates.

### 4. Edge path and duration

Marginal sector excess is shown for the six non-overlapping blocks. Matched
126-session MDD is event/control.

| Event | 1-5 | 6-10 | 11-21 | 22-42 | 43-63 | 64-126 | Peak / T50 | KM state median | State-exit C / mean hold | 126d MDD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | --- | --- |
| E1 | -.06% | -.03% | +.02% | +.02% | -.03% | +.02% | day 35 / 35 | 4 | -.10% / 9.2d | -14.51% / -13.48% |
| E5 | -.07% | -.01% | +.02% | +.07% | -.05% | -.07% | day 41 / 41 | 11 | -.11% / 13.6d | -13.70% / -13.90% |
| EB20 | -.07% | -.04% | -.04% | +.14% | +.01% | -.04% | day 43 / 40 | 10 | -.12% / 13.5d | -15.19% / -13.99% |
| ES | -.04% | +.04% | +.10% | +.09% | +.03% | +.01% | day 112 / 33 | 4 | -.06% / 9.8d | -15.34% / -13.55% |

No state survives 126 sessions in the pooled Development event sample. The
next-close state exits are all slightly negative relative to sector. Waiting
five days or for a breakout does not repair the relationship.

### 5. Context and correlated-index diagnostics

Context did not enter the pass/fail gate. The 126-session sector excess shows a
consistent descriptive split: simple MA transitions did worse when breadth was
isolated or SPY was damaged, and became mildly positive only after the market
was already broad.

| Event | Bull | Correction | Repair | Bear | Broad breadth | Building | Isolated |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| E1 | +.62% | +.27% | -1.48% | -3.27% | +.74% | +.21% | -2.54% |
| E5 | +.45% | -.08% | -1.82% | -2.52% | +.70% | -.04% | -3.20% |
| EB20 | +.56% | +.61% | -1.78% | -3.91% | +.77% | +.05% | -2.80% |
| ES | +.46% | +.98% | -1.68% | -1.15% | +.66% | +.04% | -.41% |

For the correlated SPY/QQQ/DIA/IWM sanity panel, each cell is equal-weight ETF
absolute return / delta versus prior persistent-state dates. It cannot promote
the stock-selection study.

| Event | 5d | 21d | 63d | 126d |
| --- | --- | --- | --- | --- |
| E1 | +.05% / -.08% | +.53% / +.20% | +2.18% / +.72% | +3.92% / -.90% |
| E5 | +.08% / +.00% | +.47% / -.07% | +2.44% / +.05% | +4.32% / -1.35% |
| EB20 | +.32% / +.38% | +.58% / +.51% | +2.46% / +1.03% | +4.17% / -.26% |
| ES | +.10% / +.29% | +.80% / +1.47% | +2.64% / +2.17% | +4.80% / +.86% |

`ES` is the one useful follow-up observation: all four indexes had positive
21-session deltas (`+.76/+2.41/+.63/+2.09%` for SPY/QQQ/DIA/IWM) and 63-session
deltas (`+1.83/+5.82/+.97/+.05%`); three of four remained positive at 126
sessions (`+.26/+1.31/+1.90/-.04%`). Their event/matched-date counts were
`115/104`, `100/71`, `112/92`, and `109/71`. This is not four independent
confirmations, has no frozen timing-family inference, and was not the primary
stock estimand. It may motivate one separate timing hypothesis; it is not a
result to promote from this paper.

### 6. Liquidity sensitivity and candidate ledger

At `$10m`, all four continuous IC curves remained near zero or negative with
`q=.9710`; event-curve q-values were `.9588`. The 5/21/63/126 Delta paths were:

| Event | 5d | 21d | 63d | 126d | Delta dates/names |
| --- | ---: | ---: | ---: | ---: | ---: |
| E1 | -.10% | -.19% | -.39% | -2.12% | 151 / 192 |
| E5 | +.31% | +.18% | -.48% | -1.77% | 106 / 120 |
| EB20 | -.39% | -1.05% | -1.35% | -.77% | 110 / 127 |
| ES | -.24% | -1.04% | -1.38% | -4.67% | 84 / 95 |

| Literal candidate | Development | Validation | Holdout | Status |
| --- | --- | --- | --- | --- |
| None | No stock row passes `C`, `Delta`, path, MDD, and q together | locked | locked | **No cross-sectional candidate** |
| Separate `ES` index-timing hypothesis | Correlated diagnostic only | not designed | not opened | Follow-up observation, not a candidate here |

## Decision policy

| Finding | Honest translation |
| --- | --- |
| `D4` passes the curve guardrail and remains directionally stable | Four-horizon cross-sectional candidate |
| `D4` fails but `MAD` survives unchanged | Keep the simpler 20/200 distance |
| `C` is positive but `Delta` is null | The trend state may help; “first” adds no entry edge |
| E1 fails but E5 survives validation and holdout | Waiting for acceptance, not first recapture |
| EB20 survives while E1/E5 fail | Breakout confirmation, not merely standing above averages |
| ES alone survives | Mature ordered trend, not early discovery |
| Only one ETF or one context looks good | Diagnostic heterogeneity, not a general candidate |
| First-week block is positive and later blocks plateau | Short earning window; no evidence of reversal |
| Later blocks give back at least half the peak | Measured decay; record its giveback half-life |

A candidate needs economically positive sector-relative `C`, positive
transition `Delta`, a coherent adjacent short/medium/long path in development
and validation, no worse median drawdown than its persistent control, and a
row-level multiplicity guardrail. Holdout may only retain or retire it. Passing
S2 authorizes an S5 turnover/cost/portfolio test, never production registration.

No result from this study automatically registers or changes a production
factor.
