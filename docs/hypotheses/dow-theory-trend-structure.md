# Dow Theory trend structure (H-DOW01a)

Status: concluded-rejected (opposite direction, on this universe/window; see Observation log)
Version: v0.1
Registered: 2026-08-26

Not wired into any pipeline stage. Deliberately split into sub-hypotheses,
price-structure-only first — volume confirmation is a real, separate,
second ingredient (H-DOW01b, not yet registered), tested independently
before either is combined into a single "dow_factor," per this project's
own single-ingredient discipline.

## Thesis

While an asset's swing-price structure shows a Higher High followed by a
Higher Low (an intact uptrend, in the classical Dow Theory / technical-
analysis sense), forward returns are higher than when that structure has
just broken (a Lower High or Lower Low). This is *not* a claim that
intact structure predicts a rise — only that it predicts continuation
better than a broken structure does, over the near term, until reversed.

This would be falsified by a real test showing no significant difference,
or the opposite direction, between forward returns during an intact vs. a
broken swing structure.

## Prior

Classical Dow Theory (Charles Dow's original editorials; systematized by
Hamilton and Rhea) is the historical root of trend-continuation-until-
reversed thinking in technical analysis; the specific Higher-High/Higher-
Low swing-structure formulation used here is the standard, mechanical
operationalization from classical technical-analysis practice (Edwards &
Magee, *Technical Analysis of Stock Trends*, 1948, the foundational text
for swing-based trend definition). Distinct from the peer-reviewed
factor papers cited elsewhere in this project: Dow Theory is a
practitioner tradition, not a peer-reviewed anomaly, and is disclosed as
such rather than dressed up as more rigorous than it is. One real,
peer-reviewed test does exist and is worth citing honestly: Brown,
Goetzmann & Kumar (1998), "The Dow Theory: William Peter Hamilton's Track
Record Reevaluated," *The Journal of Finance* — a real academic
back-test of Hamilton's actual historical Dow Theory buy/sell calls,
finding genuine, if modest, timing value.

## What would count as a real checkpoint

A continuous, statistically testable claim: a mechanical, non-discretionary
swing-point detector (a fractal rule — a bar is a swing high if its real
high is the maximum of a symmetric window around it, e.g. 5 bars each
side; mirrored for swing lows), applied point-in-time (a swing point only
counts once enough bars have passed to confirm it — no look-ahead). At
each test date, the intact-vs-broken structure state, derived only from
swing points already confirmed by that date, as a 0/1 indicator paired
with the real forward return — the same point-biserial approach already
used for the MACD/RSI event study (0.29). Computed via
`backend/research_lab/dow_theory_trend_structure.py` (read-only against
the sealed dataset, never the production DB).

## Promotion criteria

Real, significant IC in the predicted direction. If confirmed, H-DOW01b
(volume confirmation) gets tested next, independently, before any
combination is attempted — does trend continuation actually get stronger
when the up-legs are volume-confirmed, or is that classical Dow Theory
detail not adding real information once price structure is already
accounted for? Only after both are separately evidenced does combining
them into one "dow_factor" become a real next step, not before.

## Observation log

| Date | Checkpoint | Reading | Note |
| --- | --- | --- | --- |
| 2026-08-26 | Real IC test, mechanical fractal swing-structure state (intact HH/HL vs. broken LH/LL) vs. 21-day forward return, `research_lab/dow_theory_trend_structure.py` against dataset `real-macro-d9a319bd-09e0-443b-93b3-2e6ec70f4170`, stride=5 | **Rejected, opposite direction.** r=-0.039 (adjusted p=0.0001, n=10,219: 3,945 intact days, 6,274 broken days). Mean 21-day forward return during an intact HH/HL structure: +1.19%, vs. +1.71% during a broken (LH/LL) structure — broken structure did *better* going forward, not worse. | Real, not softened. This is the **fourth** rejection this session with the identical directional signature — `low-volatility-anomaly.md`, `time-series-momentum.md`, `max-effect-lottery-demand.md`, now this one — four independently specified tests (trend sign, realized volatility, tail-max return, and now swing-structure state), each testing a genuinely different mechanism, all landing the same way: orderly/calm/intact conditions underperform, disrupted/broken/volatile conditions outperform, on this universe over 2016-2026. Four-for-four is no longer plausibly four separate coincidences — it is real, structural evidence that this specific window's dominant character is closer to "buy weakness/disruption" than "follow strength/order." Still not proof it generalizes beyond this window (the whole reason `docs/developer-letter.md` keeps this out of the staging pipeline regardless), but it is now the strongest, most-replicated finding of this entire research pass — stronger, in a sense, than the one confirmed factor (short-term reversal), because it showed up independently across four unrelated specifications rather than one. Volume-confirmation (H-DOW01b) not tested — the base price-structure claim was rejected, so testing whether volume strengthens it is moot until a different structural claim is tried. |
