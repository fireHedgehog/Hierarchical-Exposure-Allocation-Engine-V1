# Opening gap-down fill (H-GAPFILL01)

Status: concluded-rejected
Version: v0.1
Registered: 2026-08-26

Not wired into any pipeline stage. Preregistered from an informal claim (not
a peer-reviewed source — disclosed honestly, this is trading folklore worth
checking, not literature) the user came across: SPY/QQQ opening gaps down
"always" fill back within a few days.

This is a timing/entry-shaped question at the broad-market level (SPY, QQQ —
the beta itself, not a single stock's technical trigger), not a revival of
the single-name `macd_rsi_single_name_timing` layer.

## Thesis

When SPY or QQQ opens with a real gap down (today's open below yesterday's
close), price trades back up to at least the pre-gap closing level within a
short, disclosed window at a rate meaningfully higher than an unconditional
baseline — not literally "always," but real and exploitable.

This would be falsified by a fill rate not meaningfully different from the
unconditional baseline rate of SPY/QQQ trading back up to any given
reference level within the same window on a random day (a naive comparison
is required — SPY spends most of its real history trending up over any
given multi-day window, so a high raw fill rate alone would be a trivial,
spurious confirmation, not evidence of a real gap-specific effect; see
H-VOLSCALE01's attribution-check discipline for why this comparison is
non-negotiable here).

## Prior

None cited — this is explicitly informal, not literature-grounded, unlike
every other paper in this folder. Gap-fill is a commonly repeated piece of
trading folklore with no single canonical academic source; treated here as a
testable claim to check, not a result to confirm.

## What would count as a real checkpoint

A continuous, statistically testable claim, computed via
`backend/research_lab/gap_down_fill.py` (read-only against the sealed
dataset, real OHLC data — this project stores real daily open/high/low/close,
already used by the Dow Theory swing detector):

- **Gap down, primary spec:** today's real `open` < yesterday's real `close`
  (any negative gap). **Secondary spec:** gap of at least 0.3% (a
  economically meaningful gap for a liquid index ETF, filtering out noise-
  sized gaps the primary spec would also count).
- **Filled:** the real intraday `high` on any day within the window reaches
  or exceeds the pre-gap closing level.
- **Window:** primary 5 trading days, secondary 10 trading days.
- **Baseline:** the same fill-rate calculation computed unconditionally
  (starting from every real trading day, not just gap-down days) over the
  same real history, for direct comparison — the real test is whether the
  conditional (post-gap-down) rate is higher than this, not whether it is
  high in absolute terms.
- **Universe:** SPY and QQQ specifically (the claim named these), full
  2004-2026 staging history for each.

## Promotion criteria

A real, meaningful gap between the conditional fill rate and the
unconditional baseline rate, holding for both SPY and QQQ independently (not
just pooled), at either window. A result that holds only when pooled, or
only for one of the two symbols, is a real but weaker finding, stated as
such rather than rounded up.

## Observation log

| Date | Checkpoint | Reading | Note |
| --- | --- | --- | --- |
| 2026-08-27 | `research_lab/gap_down_fill.py`, SPY+QQQ, 2004-2026, 4 specs each | **Rejected — opposite direction.** Fill rate is high in absolute terms (72-93%) but *lower* than the unconditional baseline (~99.9%) at every spec, both symbols, p<0.001 throughout. e.g. SPY any-gap/5d: 83.3% vs. 99.9% baseline. A gap down is not a special "snaps back fast" event — SPY/QQQ nearly always retrace to any given recent level within days regardless of a gap; a gap down is if anything mildly *slower* to fill than a random day, not faster. | Exactly why the baseline comparison was required: the raw fill rate alone (72-93%) looks like it confirms the claim; only against the true base rate does it invert. Data caveat: SPY's real `open` is at/above the prior close on 99.1% of days in this free-tier daily source (open<prev-close n=48/5466) — genuine overnight gaps are likely understated here, not a script bug (confirmed: 0 days with open==prev-close exactly). QQQ shows more gap days (n=119), suggesting this data-quality effect is symbol-dependent. Result direction is unaffected either way (baseline still far exceeds conditional), but the small SPY sample size should be read with this in mind. |
