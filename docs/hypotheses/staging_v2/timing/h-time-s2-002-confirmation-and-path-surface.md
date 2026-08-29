# H-TIME-S2-002 - Predictive Relationship - Confirmation and Path Surface

| Field | Value |
| --- | --- |
| Study ID | H-TIME-S2-002 |
| Legacy ID | None |
| Status | Design |
| Dataset | `library-fetch-ongoing` through 2026-08-27 ET, contract `yahoo-adjclose-scaled-ohlc-v2`; close-only reference dataset `real-macro-0f184797-d738-4ecd-a615-83b0020c5753` |
| Input | Close-known damage, trend, acceptance, compression, and deterioration transitions |
| Target | Post-landmark return path, adverse path, comparative competing-barrier incidence, and damage incidence |
| Production use | None |
| Does not claim | Validated alpha, an optimal threshold, a calibrated risk probability, a short signal, or authority to change the Timing UI |

No experiment in this document has been run. Empty result tables are the output
contract, not missing paperwork.

## Product question

Cross-sectional ranking chooses a candidate. Timing must answer a different
question:

> Once a candidate exists, does an observable price transition identify a
> different subsequent return or damage path than a comparable, still-at-risk
> candidate state?

Negative outcomes are warning relationships, not short signals. A relationship
must first survive here before a separate S3 risk calibration, S4 decision
policy, or S5 trading implementation may exist.

## Why a new loop is justified

[H-TIME-S2-001](README.md#h-time-s2-001-frozen-design) rejected the broad claim that a visible dislocation is an extra
reason to buy immediately. Common abrupt shocks, shallow SMA100 breaks, and a
5% drawdown transition often had a worse near-term path than equally weak
matched states. It did **not** test whether waiting for observable confirmation
avoids that continuation phase.

[H-XSEC-S2-003](../cross-sectional/h-xsec-s2-003-moving-average-state-transition.md) rejected four-MA strength as a stock-selection candidate in
Development. Its correlated SPY/QQQ/DIA/IWM `ES` panel nevertheless had positive
21/63-session observations. That is motivation for a Timing hypothesis, not
four independent confirmations and not permission to unlock the Cross folds.

The new work therefore tests transitions and paths rather than another
unconditional `indicator -> forward return` grid. Simple technical rules have
long precedent, but also a serious data-snooping history: see
[Brock, Lakonishok, and LeBaron (1992)](https://doi.org/10.1111/j.1540-6261.1992.tb04681.x),
[Moskowitz, Ooi, and Pedersen (2012)](https://doi.org/10.1016/j.jfineco.2011.11.003),
[Han, Zhou, and Zhu (2016)](https://doi.org/10.1016/j.jfineco.2016.01.029), and
[Sullivan, Timmermann, and White (1999)](https://doi.org/10.1111/0022-1082.00163).
Those papers motivate the families; they do not pre-validate this dataset.

## One loop, four experiments

All four families share one data tensor, event clock, matching engine, return
path, and statistical contract. This is one file and eventually one disposable
script, not one paper per threshold.

| Family | Parent state | Observable transition | Primary relationship question | What it does not yet decide |
| --- | --- | --- | --- | --- |
| A. Damage confirmation | An H-TIME-S2-001-style dislocation | Repair evidence appears before further failure | Does a newly confirmed episode have a better subsequent path than the still-unconfirmed risk set? | Whether or how long to wait |
| B. Trend birth and acceptance | A liquid candidate is not yet in the tested trend state | First trend/price breakout, then 1/3/5/10-session acceptance | Is the transition different from a mature state, and does persistence add information beyond an equally aged rejected transition? | Position size or entry policy |
| C. Compression and directional release | Volatility is low and has stayed compressed | Adjusted-price range releases upward or downward | Does compression precede expansion, and does revealed direction alter the subsequent path? | A trade in either direction |
| D. Trend deterioration warning | A qualified uptrend is already active | Trend support fails in an ordered sequence | Does a warning precede more damage than a same-age warning-free trend? | A trim or cash policy |

The four families are not four chances to select a winner. Family-level
inference and a single candidate ledger make the search breadth explicit.

## Data readiness and boundary

The design-time inventory is an infrastructure check, not an experiment result.

| Layer | Design-time state | Allowed use |
| --- | --- | --- |
| Stage 2 library | 775 accepted members; 767 have at least 252 bars; cutoff 2026-08-27 ET | Primary individual-security panel |
| Adjusted OHLC + raw volume | Adjusted open/high/low/close, raw close, raw volume, and adjustment factor are populated under `yahoo-adjclose-scaled-ohlc-v2` | Post-signal path origin, gap/range integrity checks, MAE/MFE, barriers, and Yang-Zhang volatility |
| Time zone | 769 symbols use `America/New_York`; six do not | Main loop uses New York symbols only; the other six remain excluded until an explicit cross-zone information clock exists |
| Market references | SPY, QQQ, DIA, IWM and sleeve ETFs have adjusted close in a sealed dataset, but explicit adjusted OHLC is absent | Close-only reference and index transfer panels; no benchmark next-open, gap, ATR, or intraday-barrier claim |
| Sector identity | 503 names have a usable frozen Select Sector mapping; the remainder do not | Sector matching where real; `unmapped` remains its own visible group |
| Earnings events | No earnings timestamp is stored | No earnings-gap or announcement-timing claim |
| Macro history | Historical releases are not release-time PIT | Context diagnostic only, never a primary timing input |

The roster is a current-2026 vintage. Historical stock results are therefore
survivor-conditioned discovery evidence. That limitation stays visible but does
not block this disposable screen. Observations after this design freeze are the
only genuinely prospective evidence.

Before a later run, the script must fail closed unless every included stock has
internally consistent adjusted OHLC and a positive adjustment factor. Zero-volume
bars are excluded from volume statistics. If both an upper and lower barrier are
touched in the same daily bar, order is unknowable and the episode is reported
as `same-bar ambiguous`; the script must not invent which came first.

## Shared eligibility and the layer boundary

The primary stock panel represents candidates that the application could have
shown, not every historical ticker on every date.

| Gate | Frozen rule |
| --- | --- |
| Universe | Stage 2, `research_scope = general`, unique security mapping, New York exchange clock |
| History | Current close plus 252 earlier valid sessions; missing bars are null, never carried forward |
| Price | Signal-close raw close at least $5 |
| Liquidity | Median raw-close times raw-volume over sessions `t-20` through `t` at least $25m |
| Candidate-qualified state | Point-in-time reconstruction of the current descriptive V0 rank: above SMA20/50/100/200 and composite score in the top quintile among names eligible on that historical close |
| Candidate score inputs | 3m/6m/12m excess return versus SPY at 25%/25%/15%, 52-week-high proximity at 15%, four-MA distance at 10%, and MA slope at 10% |
| Selection clock | Every input and percentile is recomputed only from information available by that historical close; today's 767-name score distribution is never backfilled into history |
| Selection claim | None; conditioning on V0 tests timing after the current product selector, not whether V0 itself is alpha |

For exact reconstruction, 3m/6m/12m are 63/126/252-session simple stock
returns minus the same-clock SPY simple return; high proximity is
`P(t)/max(P(t-251), ..., P(t))-1`; four-MA distance is the mean of
`log(P/SMA20)`, `log(P/SMA50)`, `log(P/SMA100)`, and `log(P/SMA200)`; and slope
is the formula frozen in the matching section below. Each input receives its
0-to-100 cross-sectional midrank percentile among history/price/liquidity-
eligible names before the A4 gate, then the listed weights are summed without
display rounding. Candidate qualification requires that score to be in that
date's top quintile as well as A4.

Families B and C require candidate qualification on their parent-event close.
Families A and D require qualification at least once in the preceding 21
sessions, representing a recently selected or held candidate. The all-liquid
sample remains a predeclared diagnostic; it cannot replace a failed
candidate-conditioned result.

Whenever `market state` is required below, it means the close-known Cartesian
state of SPY above/below its SMA200 and SPY prior-20-session realized-volatility
quintile. The quintile is formed from the 252 earlier completed `sigma20`
estimates, excluding the current estimate. It is never inferred from a later
regime label.

The close-only index transfer panel applies the same state definitions to SPY,
QQQ, DIA, and IWM without the V0 gate for Families A, B, and D only. Family C
has no index transfer panel because Yang-Zhang volatility and adjusted ranges
require consistent open/high/low data. These four correlated series are one
market panel, not four replications.

## Common event and observation clock

For a signal first known after close `t`:

```text
stock path origin                  = adjusted open at t+1
stock endpoint                     = adjusted close after h complete sessions
unbenchmarked adjusted stock path  = stock path origin to stock endpoint; not a policy P&L
diagnostic excess                  = stock close t to close t+h minus reference close t to close t+h
```

The close-only index transfer path begins at signal close `t` and ends at close
`t+h`. It is a non-executable association diagnostic and is never pooled with,
or subtracted from, the stock next-open path.

Primary holding horizons are `1, 3, 5, 10, 21, 42, 63` sessions. They form one
response curve. No isolated best horizon may be reported as a strategy.

Define prior close-to-close volatility `sigma20` as the population standard
deviation (`ddof=0`) of 20 complete returns and the common path unit
`U = P(t) * sigma20`. Stock MAE/MFE and barriers use
adjusted low/high after entry. Close-only references use close barriers and
cannot be compared as if they had intraday observation.

Every landmark comparison starts both treated and control paths at the adjusted
open after the landmark close and ends them on the same calendar session. A path
starting after a later landmark is never subtracted from a path beginning at the
original parent event. Immediate-versus-wait P&L belongs to a later S4 policy.

For adjusted-high/low barriers, an opening gap that crosses a barrier resolves
at the open. If neither barrier is crossed at the open and both are touched
later in the same daily bar, order is unknown and the outcome is `same-bar
ambiguous`; directional lower and upper bounds remain visible.

Event generators suppress overlapping parent events under their family-specific
clocks. A deeper move inside an active parent episode is a path outcome, not a
fresh independent event. A follow-up landmark or censoring clock never silently
reopens its parent generator.

## Family A - confirmation after damage

The three definitions and their normalization transfer unchanged from
H-TIME-S2-001 to the stock panel. The original accepted SPY/QQQ/DIA/IWM episodes
remain a separate close-only transfer panel; they are not executable stock
episodes. Reusing definitions prevents a second threshold search from rescuing
the rejected immediate-entry claim.

| Parent event | Frozen definition | Why retained |
| --- | --- | --- |
| `D-SHOCK` | 1-day return / prior-20-day volatility `<= -1.5` | Common continuation-risk case |
| `D-SMA100` | First close below SMA100, no extra depth requirement | Observable shallow structural break |
| `D-DD5` | First cross below 5% drawdown from prior 63-session high | Common damage transition |

The event close and H-TIME-S2-001 structural reference `R` are frozen at the
parent event. Family A inherits its exact prior unit
`B_A = max(R - P, P * sigma20)`; it does not substitute the common `U` above.
Search at most 20 sessions for:

| Confirmation | First close satisfying | Interpretation |
| --- | --- | --- |
| `C-HALF` | `P >= event close + 0.5B_A` | Partial repair already earned |
| `C-TWO` | Two consecutive closes above their immediately prior closes | Minimal path persistence |
| `C-SMA20` | Price recaptures the contemporaneous SMA20 | Short-trend repair |
| `C-REF` | Price recaptures frozen structural reference `R` | Original break is repaired |

Run a separate competing-risk process for every parent-event and confirmation
definition; the four confirmations may co-occur and are not mutually exclusive
causes. Confirmation and `-0.5B_A` failure are both observed on closes, so one
cannot mechanically occur earlier merely because it uses an intraday low.
Timeout at day 20 is administrative right-censoring, not a competing cause.
This 20-session process does not change parent-event de-duplication: under each
parent specification, no new parent starts until frozen `R` is repaired or 63
sessions have elapsed, exactly as in H-TIME-S2-001. Confirmation, failure, or
day-20 censoring cannot reopen that parent clock.

At each confirmation lag `l`, compare newly confirmed episodes with matched
episodes that are still alive, unfailed, and unconfirmed under that same
definition at `l`. Both forward paths begin at the next adjusted open. Controls
remain assigned to their landmark group for the fixed forward window even if
they confirm later (`intention-to-state`); later confirmation is not used to
censor or reassign them. This prevents immortal-time and informative-crossover
bias without inventing an immediate-versus-wait policy.

## Family B - trend birth and price acceptance

This family tests a transition, then asks whether waiting for acceptance adds
information. It does not retest persistent `above SMA` days as if every day were
a new signal.

| Transition | First close satisfying | Frozen boundary for acceptance |
| --- | --- | --- |
| `T-S50/200` | Price recaptures both SMA50 and SMA200 after at least 20 sessions outside that joint state | Both contemporaneous averages |
| `T-STACK` | `P > SMA20 > SMA50 > SMA100 > SMA200` after an observable non-stack state | Full ordered-stack state |
| `T-B63` | Close above the prior 63-session highest close while above SMA200 | Signal-day 63-session high |
| `T-B252` | Close above the prior 252-session highest close while above SMA200 | Signal-day 252-session high |

Acceptance landmarks are `1, 3, 5, 10` consecutive **subsequent** closes after
the transition; the transition close is day zero and does not count as landmark
day one. The state or frozen breakout boundary must remain satisfied at every
session through the landmark. For each literal landmark, an episode is
`accepted` if it satisfies that full path and `rejected` if it violates the
boundary at least once during the same `l` sessions. Both groups must have valid
data through the landmark close. The post-landmark path begins at the next
adjusted open; the classification window itself is never counted as return.

The primary incremental estimand is:

```text
accepted transition path - landmark-matched rejected transition path
```

The raw transition path and a same-date matched mature-state path are also
visible: a mature state has satisfied the tested boundary for at least 20
sessions without a new transition. This separates `the state has a path
association` from `the first transition is special` and `observable acceptance
adds incremental information`.

At landmark `l`, accepted and rejected observations come from the same
transition-date cohort and are compared only after the common landmark. Group
assignment is then frozen even if a rejected name later recaptures the boundary.
This equal observation window avoids immortal-time classification and does not
claim that either group was executable before the landmark. For `T-STACK`, all
stock and index observations through 2018 were already seen in H-XSEC-S2-003
and are hypothesis-generation evidence only; they cannot count as fresh
Development or replication evidence.

## Family C - compression and directional release

Compression may predict future volatility without predicting direction. These
are two separate hypotheses and must remain separate in the result tables.

Yang-Zhang volatility uses adjusted open/high/low/close because it incorporates
overnight and intraday components
([Yang and Zhang, 2000](https://doi.org/10.1086/209650)). The primary estimator
is 20-session Yang-Zhang volatility ranked against its own trailing 252-session
history. Family C therefore requires 272 complete prior price sessions. The
signal-date volatility percentile uses the 252 earlier completed 20-session
Yang-Zhang estimates and excludes the current estimate from its own rank.

For each complete 20-session window let `o=log(O/C_prev)`, `c=log(C/O)`, and
`rs=log(H/O)log(H/C)+log(L/O)log(L/C)`. `var` uses the sample denominator
`n-1`; `mean(rs)` uses all `n` rows. Freeze
`k=0.34/(1.34+(n+1)/(n-1))` with `n=20` and
`YZ^2=var(o)+k*var(c)+(1-k)*mean(rs)`, annualized by `sqrt(252)` only for
display. Any missing or non-positive adjusted OHLC value invalidates that
window; values are never filled.

| Axis | Frozen cells |
| --- | --- |
| Compression level | Volatility percentile `<= 20%` |
| Compression duration | 5 and 10 consecutive sessions |
| Frozen range | Prior 20 and 63-session adjusted high/low, excluding the compression-eligibility close |
| Upward release | First adjusted close above the frozen range high |
| Downward release | First adjusted close below the frozen range low |
| Release timeout | 21 sessions after compression becomes eligible |

Let `t0` be the compression-eligibility close. Experiment C1 asks whether
compression increases the cumulative incidence of either release and whether
volatility subsequently expands. Its expansion outcome is frozen for **every**
parent and control, including no-release/time-out rows, as
`YZ(t0+1:t0+20) / YZ(t0-19:t0)`. The eligibility close belongs only to the
prior window. Experiment C2 begins only after release direction is known:
upward release tests continuation; downward release tests future damage, never
a short return. Its release-anchored YZ ratio is secondary and uses the same
non-overlapping convention around release close `r`.

Controls share the exact date, sector/risk set, range length, and market state,
then meet the common continuous-covariate calipers for volatility, score,
drawdown, and slope; they do not have the required compression duration. The
design therefore tests the history of compression, not merely the fact that
current volatility is low. C1 assignment remains fixed for its 21-session
observation window even if a control later qualifies as compressed; later
qualification neither censors nor reassigns it.

Those parent-time controls identify C1 only. For a treated C2 release at lag
`l`, define an untreated name's `shadow parent` as exactly `l` sessions before
that same release date. At that shadow parent the untreated name must be in the
same low-volatility quintile but fail the required 5/10-session duration; freeze
its own 20/63-session range there. It must not acquire qualifying compression
before release, must remain inside the frozen range through lag `l-1`, and must
make its first break of **either** side at lag `l` in the treated direction.
This makes parent date, lag, direction, and range construction identical without
inventing an origin after results are visible. Both paths begin after the
release close; opposite directions are never pooled.

Volatility-managed portfolios are motivation, not a guaranteed result;
[Moreira and Muir (2017)](https://doi.org/10.1111/jofi.12513) and the
out-of-sample counterevidence in
[Cederburg et al. (2020)](https://doi.org/10.1016/j.jfineco.2020.04.015)
justify reporting both benefits and failure modes.

## Family D - trend deterioration warning

This family asks whether an already qualified trend provides useful advance
warning of damage. It does not ask whether negative signals profit as shorts.

| Warning | First close satisfying after a qualified trend | Intended timing meaning |
| --- | --- | --- |
| `W-A4` | First failure of `P > SMA20, SMA50, SMA100, SMA200` after at least 20 A4 sessions | Earliest broad support loss |
| `W-SMA50` | First close below SMA50 while SMA50 remains above SMA200 | Intermediate support loss |
| `W-X20/50` | SMA20 first crosses below SMA50 while price remains above SMA200 | Trend deceleration |
| `W-SMA200` | First close below SMA200 | Late structural damage |

Overlapping warnings within one uptrend episode are recorded in an overlap
matrix. They are not counted as independent confirmations. The episode resets
only after candidate qualification and the required 20-session trend age are
re-established.

For a warning known at close `t`, the forward path begins at adjusted open `E`
on `t+1`. The warning-day low is already history and cannot count as subsequent
damage. Forward 5%/10% damage is the minimum adjusted low relative to
`E` within 21/42/63 sessions. Competing `+1U/-1U` barriers are centered on `E`,
where `U` was frozen using the warning close and prior `sigma20`.

Also report tail expected shortfall, forward realized volatility, and warning-
to-damage lead time. The matched control is a still-qualified, warning-free
trend of similar age on the same date, not a generic non-event candidate. This
control assignment remains fixed even if the control later emits a warning;
that later state is not informative censoring. This file reports comparative
risk differences and risk ratios. Absolute incidence curves are descriptive;
if a warning relationship survives, a later H-TIME-S3 study may calibrate
probabilities and a later S4/S5 study may evaluate trim, cash, turnover, or
costs. This S2 file may not display a fitted `risk = 73%`.

## Matching contract

No family may compare an event only with an unconditional random day.

Every named continuous covariate is frozen as follows at the close-known match
clock: `volatility = sigma20`; `drawdown = P(t) / max(P(t-63:t-1)) - 1`;
`score` is the unrounded historical V0 weighted midrank-percentile composite;
`slope = mean[SMA50(t)/SMA50(t-20)-1,
SMA200(t)/SMA200(t-20)-1]`; `SMA200 slope` is its single-average component
`SMA200(t)/SMA200(t-20)-1`; and `trend age` is the number of consecutive closes
through the match clock satisfying `P > SMA20, SMA50, SMA100, SMA200`, capped at
252 for distance matching. For Family D only, both warning and control trend
age stop at `t-1`, immediately before the warning/pseudo-warning close. The V0
score inputs and weights are exactly those in the eligibility table; ties
receive their average rank. Covariates are taken from the parent/transition
close unless a row explicitly says release or warning close.

| Panel | Primary control | Required balance |
| --- | --- | --- |
| Family A landmark | Same-date episodes under the same parent definition, still alive and unconfirmed at lag `l` | Parent severity and lag exact; nearest parent-event volatility, drawdown, score, and slope |
| Family B transition | Same-date candidate already in the same state for at least 20 sessions, with no new transition | State definition and market state exact; nearest close-known volatility, drawdown, score, and slope |
| Family B landmark | Same transition-date cohort, classified rejected at the common lag `l` | Transition and lag exact; nearest transition-day volatility, drawdown, score, and slope only |
| Family C1 parent | Same-date names with the same current low-volatility eligibility but without required compression duration | Range length and market state exact; nearest volatility, drawdown, score, and slope |
| Family C2 release | Same-date shadow-parent pair defined above, with same-direction and same-range release at lag `l` without qualifying compression | Direction, range, and lag exact; nearest shadow-parent volatility, drawdown, score, and slope |
| Family D warning | Same-date trends still qualified and warning-free | Warning family and market state exact; nearest pre-warning trend age, volatility, drawdown, score, and slope |
| Unmapped stock | Same risk set and date in explicit `unmapped` group | Never impute a sector |
| Index transfer | Same instrument's non-event dates in the same historical panel and market state, outside that specification's active episode and not within five sessions of its event | Globally optimal 1:1 match without replacement on continuous `sigma20`, drawdown, and SMA200 slope under the same 0.50-SD caliper |

For mapped stocks, date, sector, and risk-set eligibility are exact. Continuous
covariates use globally optimal, without-replacement Mahalanobis matching with
a 0.50 pooled-standard-deviation caliper on every covariate and a frozen 1:1
treated-control ratio within each literal cell; greedy row order is not allowed.
Report pre/post standardized mean differences, with `|SMD| <= .10`
as the balance target. Coverage reports unmatched events rather than loosening
rules after seeing results. The secondary self-history stock match is a
sensitivity, not a replacement for failed same-date matching.

## Historical panels and prospective clock

| Panel | Dates | Honest label |
| --- | --- | --- |
| Development | 2005-01-01 to 2014-12-31 | Design-era discovery |
| Temporal replication | 2015-01-01 to 2019-12-31 | Historical replication, already indirectly inspected by prior project research |
| Recent stress | 2020-01-01 to the known pre-freeze close 2026-08-28 ET; stored data currently ends 2026-08-27 | Regime/stress stability, **not** an untouched holdout |
| Prospective shadow | 2026-08-31 ET onward | Only genuinely unseen evidence; accumulate without threshold edits |

All thresholds are frozen before the loop is implemented. Historical panels
remain separately visible. No panel may be renamed `out of sample` merely
because the script did not use it to calculate a coefficient.

`T-STACK` is the literal exception to the generic panel clock: its stock and
index observations through 2018 were already viewed in H-XSEC-S2-003 and remain
design-era evidence. Only 2019 may populate its temporal-replication column and
2020 onward its recent-stress column. The same per-cell count gates still apply;
if 2019 has fewer than 25 dates, that literal row is `insufficient`. Nothing in
this Timing study populates or unlocks the prior Cross study's folds.

## Outcome tensor

Every valid event produces the same path record.

| Outcome class | Measures |
| --- | --- |
| Return | Mean and median adjusted-open-to-close stock path; separately clock-matched close-to-close SPY and mapped-sector-ETF diagnostic excess |
| Path | MAE (most negative origin-relative return), MFE (most positive), peak-to-later-trough maximum drawdown, and time under path origin |
| Competing barriers | Family A `+0.5B_A/-0.5B_A`; other families `+0.5U/-0.5U` and `+1U/-1U`; same-bar ambiguity and directional bounds |
| Tail | 10th percentile and ES10 primary; ES5 descriptive only with at least 400 valid date portfolios; 5%/10% damage incidence |
| Timing | Time to confirmation/release/damage, supported-horizon set, effect half-life, and family-applicable false-break rate |

`ES10` is the mean of date-portfolio returns at or below their empirical 10th
percentile; `ES5` is defined analogously. Higher (less negative) is better. For
an unmapped stock only the SPY diagnostic excess exists; sector excess is null,
never imputed.

The `supported-horizon set` lists every predeclared horizon with the expected
effect sign and stepdown-adjusted `p <= .10`; it is never compressed to a
cherry-picked maximum. `Effect half-life` is defined only when the absolute
effect peaks by day 21 and retains its expected sign afterward: it is the first
later tested horizon at or below half the peak magnitude, or `>63D` if no such
horizon appears. Otherwise it is `N/A`. False-break rate applies only to
`T-B63`, `T-B252`, and Family C releases: it is the fraction whose close returns
inside the frozen range during the next five sessions. Other definitions
report `N/A`.

Competing outcomes use the non-parametric Aalen-Johansen cumulative-incidence
estimator rather than treating a failure as ordinary right-censoring
([Aalen and Johansen, 1978](https://gwern.net/doc/statistics/survival-analysis/1978-aalen.pdf)).
Each parent-by-definition process uses mutually exclusive causes. Timeout is
administrative right-censoring, and the design assumes that this administrative
censoring is independent of the unobserved later cause. A high/low process adds
`same-bar ambiguous` as a third cause and reports bounds that assign every
ambiguous row upward versus downward. State duration without a competing event
uses Kaplan-Meier. No proportional-hazards assumption is required. Absolute
curves are descriptive; comparative horizon-specific date-portfolio risk
differences enter inference. A naive row bootstrap of an Aalen-Johansen curve
is not used.

## Dependence, multiplicity, and data snooping

Each inferential family has one primary endpoint. Other horizons and path
statistics diagnose shape and are included in the stepdown family; they cannot
replace a failed primary endpoint.

| Inferential family | Primary comparative endpoint |
| --- | --- |
| A | Newly confirmed minus intention-to-state unconfirmed 21-session mean stock return |
| B | Newly accepted minus same-age rejected-transition 21-session mean stock return |
| C1 | Difference in either-direction release cumulative incidence by day 21 |
| C2-up | Compressed minus non-compressed upward release 21-session mean stock return |
| C2-down | Compressed minus non-compressed downward release 21-session 5% damage incidence |
| D | Warning minus warning-free trend 42-session 5% damage incidence |

The primary observation is a calendar-date portfolio, not a stock row. Build a
complete NYSE-session calendar, attach each cell's event/control portfolio to
its session, and equal-weight valid names within date. This prevents
one market-wide selloff containing hundreds of stocks from becoming hundreds of
independent observations.

| Layer | Frozen method |
| --- | --- |
| Confidence intervals | 10,000-draw stationary bootstrap over complete calendar-session blocks; empty sessions carry no pseudo-return and each statistic is recomputed from valid event dates inside every draw; primary mean block length 63 sessions |
| Block sensitivity | Repeat headline cells with mean block lengths 20 and 126 |
| Symbol dependence | Symbol-cluster resampling sensitivity after the date-level primary estimate |
| Family-level search | Null-recentered studentized max-absolute-t omnibus statistic and Romano-Wolf stepdown adjusted p-values, using the same stationary-bootstrap draws |
| Cell diagnostics | Raw p and stepdown-adjusted p; no independence assumption across nested horizons or thresholds |
| Crisis concentration | Leave-one-calendar-year-out headline effect and top-five event-date contribution |
| Cross-asset agreement | Every broad index separately; same-day indexes remain one clustered market episode |

For literal cell `j`, let `theta_j` be its date-portfolio effect and let
`se_j` be the standard deviation of its stationary-bootstrap estimates. The
observed statistic is `T_j = theta_j / se_j`. Bootstrap draw `b` uses the
null-centered statistic
`T*_bj = (theta*_bj - theta_j) / se_j`; the maximum absolute statistic across
the still-active hypotheses supplies the omnibus and Romano-Wolf stepdown
reference distribution. Raw `theta*_bj / se_j` is never used as a null draw.

The stationary bootstrap preserves local time dependence
([Politis and Romano, 1994](https://doi.org/10.1080/01621459.1994.10476870)).
The family-level test acknowledges that a broad rule search tends to produce a
lucky winner; see [White (2000)](https://doi.org/10.1111/1468-0262.00152) and
[Romano and Wolf (2005)](https://doi.org/10.1111/j.1468-0262.2005.00615.x).
Hansen SPA is deferred to a later S4 study because it requires aligned daily
policy loss-differential series that do not exist in this S2 outcome tensor.

## Candidate gates

Statistical significance alone cannot create a candidate. Each literal row must
pass all applicable common and family-specific gates.

| Common gate | Frozen requirement |
| --- | --- |
| Coverage | Per literal cell: at least 100 distinct event dates overall, 25 in both temporal-replication and recent-stress panels, and 20 occupied non-overlapping 63-session blocks; apply the explicit `T-STACK` evidence-clock exception above |
| Historical stability | Same expected direction in temporal replication and recent stress |
| Breadth | Same direction in at least 3 of 4 broad indexes where a close-only transfer exists, or at least 60% of sector groups having at least 25 distinct matched dates in that literal cell |
| Dependence-aware inference | Romano-Wolf stepdown adjusted p <= .10 for the primary endpoint |
| Concentration | Removing one year does not reverse the headline sign |

Rows failing coverage are `insufficient`, not rejected. Rows with a stable
economic effect but weak inference are `inconclusive`, not promoted. A family
with one lucky threshold but no plateau is rejected as a usable surface even if
that cell has a small p-value.

| Family | Economic gate | Required plateau |
| --- | --- | --- |
| A | At least +0.50 percentage-point 21-session matched return effect, with non-negative MAE and ES10 deltas | Same direction for at least two confirmation definitions and two adjacent horizons |
| B | At least +0.50 percentage-point 21-session accepted-minus-rejected return effect, with non-negative MAE and ES10 deltas | Same direction at adjacent acceptance landmarks and two adjacent horizons |
| C1 | At least +5 percentage-point day-21 release-incidence difference **and** at least +0.10 parent-anchored YZ-ratio difference | Same direction across both compression durations or both range lengths |
| C2-up | At least +0.50 percentage-point 21-session matched return effect, with non-negative MAE and ES10 deltas | Same direction across adjacent horizons and both compression durations |
| C2-down | At least +5 percentage-point 21-session damage-risk difference, with median lead time at least 2 sessions | Same direction across adjacent horizons and both compression durations |
| D | At least +5 percentage-point 42-session damage-risk difference, with median lead time at least 2 sessions | Same direction at two adjacent horizons and at least two warning stages |

## Result-table contract

### 1. Data integrity and coverage

| Family | Eligible symbols | Unique dates / episodes | Positive cause | Negative cause | Censored | Unmatched | Same-bar ambiguous |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A. Damage confirmation | - | - | - | - | - | - | - |
| B. Trend acceptance | - | - | - | - | - | - | - |
| C. Compression release | - | - | - | - | - | - | - |
| D. Deterioration warning | - | - | - | - | - | - | - |

### 2. Full relationship surface

Every frozen cell is emitted as a row in machine-sortable order.

| Family | Signal | Threshold / landmark | Horizon | Dev effect | Replication effect | Recent effect | Bootstrap CI | Raw p | Stepdown p | Verdict |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | --- |
| - | - | - | - | - | - | - | - | - | - | Not run |

### 3. Path economics

| Family / signal | Return delta | Median delta | MAE delta | MFE delta | ES10 delta | Damage-risk delta | Time below origin | Supported horizons / half-life |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| - | - | - | - | - | - | - | - | Not run |

### 4. Compression expansion

| Duration / range | Parent / control dates | Release CIF by 21D | Risk difference | Parent-anchored YZ ratio event / control | YZ-ratio difference | Verdict |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| - | - | - | - | - | - | Not run |

### 5. Confirmation and competing risks

| Parent / definition | Descriptive CIF by 5/10/20D | Comparative risk difference | Failure first | Censored | Ambiguous | Median time | `B_A` or `U` |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| - | - | - | - | - | - | - | - |

### 6. Stability and dependence

| Candidate row | SPY | QQQ | DIA | IWM | Sector agreement | Leave-one-year-out | Block 20/63/126 | Stepdown p | Verdict |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- | ---: | --- |
| - | - | - | - | - | - | - | - | - | Not run |

### 7. Candidate ledger

| Literal candidate | Relationship | Path | Stability | Inference | Production authority |
| --- | --- | --- | --- | --- | --- |
| None before run | Not run | Not run | Not run | Not run | None |

## What may happen after the run

| Finding | Honest next step |
| --- | --- |
| Confirmation has a better path than its landmark risk set | Design a separate long/cash S4 policy; do not rewrite this relationship file |
| Trend transition works but acceptance adds nothing | Retain the state association; reject the special acceptance landmark |
| Compression predicts expansion but not direction | Risk/volatility input only; no long entry claim |
| Upward release works only after compression | Candidate directional-release state; confirm prospectively |
| Deterioration predicts damage with lead time | Open S3 probability calibration before displaying a risk percentage |
| Only the current-vintage stock panel works | Discovery-only; do not claim index or prospective generality |
| Only one asset, year, threshold, or horizon works | Heterogeneity/noise diagnostic; no candidate |
| All families fail | Preserve the null and keep the Timing product on an honestly labelled placeholder algorithm |

## Manual gates

1. Approve this matrix before writing or running its disposable script.
2. Reuse one loader and one event tensor; do not create one script per row.
3. Run no provider fetch and write nothing to the application database.
4. Emit every frozen cell and every empty/insufficient status.
5. Do not alter the Timing UI, strategy registry, or production scoring from an
   S2 result.
6. If this design changes after any result is viewed, rename the revision and
   treat all viewed dates as development evidence.
