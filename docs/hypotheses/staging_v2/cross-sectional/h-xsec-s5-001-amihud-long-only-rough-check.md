# H-XSEC-S5-001 - Amihud Long-Only Rough Check

| Field | Value |
| --- | --- |
| Status | Rough candidate gate passed; not production-authorized |
| Type | Trading implementation |
| Category | Cross-sectional |
| Parent evidence | [H-XSEC-S2-002](h-xsec-s2-002-price-volume-factor-screen.md) |
| Code | `backend/research_lab/amihud_long_only_rough_check.py` |
| Production authority | None |

## Question

Does the sector-neutral Amihud discovery relationship remain visible in a very
simple long-only portfolio after turnover and explicit cost assumptions, and is
the implied position size obviously unusable?

This is a rough candidate check, not an attempt to revive an old factor as a
production strategy. It does not tune a signal and it does not register one.

## Frozen translation

- Rank the same 21-session Amihud measure used by H-XSEC-S2-002 within each of
  the 11 sector cohorts at each month-end.
- Hold the highest-illiquidity 20% of each usable sector with equal sector
  weights and equal name weights inside sectors.
- Average two or three overlapping monthly sleeves, approximating the confirmed
  42/63-session discovery horizons without choosing individual exit dates.
- Form the signal at the month-end close and rebalance at the following trading
  session's adjusted close. Same-close fills are forbidden.
- Compare with a sector-equal portfolio of all names passing the same screen and
  with SPY.
- Primary raw-close and median 21-session dollar-volume screen: `$2` and `$1m`.
  `$5m` and `$10m` floors are sensitivity checks, not tuning choices.
- Measure one-way target-weight turnover. Apply `0/5/10/25/50 bps` per unit of
  turnover as declared scenarios; these are assumptions, not observed slippage.
- Estimate capacity as the most restrictive position at 1% of median daily
  dollar volume. No arbitrary account-size pass line is imposed.
- Holdout starts `2023-07-01`, unchanged from the parent screen.

## Candidate gate

The rough implementation candidate passes only if annualized excess over the
matched sector-equal portfolio is positive in both the full sample and holdout,
and remains positive in holdout at the conservative 25 bps scenario. A pass
still authorizes only further research. Missing spread/quote data remains an
explicit implementation gap.

## Result

The candidate gate passed. That means the relationship is worth keeping on the
research watchlist; it does **not** mean observed trading friction, historical
membership, or a production implementation has passed.

The primary three-sleeve translation produced:

| Fold | Periods | Avg. names | Gross ann. | Sector-EW ann. | Gross excess | One-way turnover / month | Net excess at 25 bps | Net excess at 50 bps | 1% ADV capacity p10 / median |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Full | 246 | 120.6 | +22.47% | +15.12% | +7.35% | 7.23% | +7.09% | +6.83% | $0.5m / $1.5m |
| Holdout | 38 | 140.3 | +27.21% | +20.49% | +6.72% | 8.57% | +6.40% | +6.08% | $2.9m / $10.6m |

The two-sleeve translation reached the same rough conclusion (`+7.17%` full
and `+6.44%` holdout gross annualized excess; `9.98%` and `12.16%` monthly
one-way turnover). Raising the median-dollar-volume floor also did not remove
the three-sleeve gross result:

| ADV floor | Full excess | Holdout excess | Full capacity p10 / median | Holdout capacity p10 / median |
| ---: | ---: | ---: | --- | --- |
| $1m | +7.35% | +6.72% | $0.5m / $1.5m | $2.9m / $10.6m |
| $5m | +7.10% | +6.62% | $2.3m / $3.6m | $6.9m / $11.0m |
| $10m | +7.13% | +6.61% | $4.3m / $6.3m | $7.7m / $11.0m |

## Honest gate ledger

| Check | Status | Reading |
| --- | --- | --- |
| Parent IC/spread discovery | Pass | Positive in full, validation, and holdout in H-XSEC-S2-002. |
| Executable signal timing | Pass | Signal at month-end close; first permitted fill is next-session adjusted close. |
| Long-only gross result | Pass | Positive versus the matched sector-equal universe in full and holdout. |
| Assumed cost stress | Pass | Positive at 25 and 50 bps per unit of measured turnover. These are scenarios, not quotes. |
| Turnover | Measured; no gate | Three-sleeve mean one-way monthly turnover is 7.23% full / 8.57% holdout. No arbitrary threshold was invented. |
| Dollar-volume sensitivity | Pass | The gross relationship remains at the $5m and $10m floors. |
| Capacity | Watch | The historical 1% ADV p10 is only $0.5m at the primary floor; recent capacity is larger. Capacity depends on account size. |
| Bid/ask spread and market impact | Not tested | No historical quote data. Assumed bps must not be relabeled as measured slippage. |
| Historical universe | Not tested | Current-vintage survivor-conditioned sample remains a discovery limitation. |
| Production registration | Not authorized | No strategy, component, schema, runtime, or UI change. |

The unusually large backtest return is a reason for skepticism, not a reason to
promote. Keep Amihud as an old but live candidate until real friction and a
cleaner forward sample justify another decision.
