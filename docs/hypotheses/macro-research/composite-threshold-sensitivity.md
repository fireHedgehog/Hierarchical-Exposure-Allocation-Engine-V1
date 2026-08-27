# Composite threshold sensitivity

Status: observing
Version: v0.1
Registered: 2026-08-27

Is H-MACRO09's finding sensitive to the hand-picked -10% drawdown
threshold and tercile split, or does it hold across nearby reasonable
choices? Full 2004-2026 pooled data — a robustness check on the design,
not a fresh claim. `research_lab/composite_threshold_sensitivity.py`.

## Results

| Window | Split | -8% | -10% | -12% | -15% |
| --- | --- | --- | --- | --- | --- |
| 3mo | Tercile | +25.9pp, p=0.0001 | +22.4pp, p=0.0001 | +11.8pp, p=0.023 | +8.2pp, p=0.057 (ns) |
| 3mo | Quartile | +28.6pp, p=0.0002 | +25.4pp, p=0.0003 | +12.7pp, p=0.044 | +7.9pp, p=0.164 (ns) |
| 6mo | Tercile | +33.3pp, p<0.0001 | +27.4pp, p<0.0001 | +23.8pp, p=0.0001 | +14.3pp, p=0.007 |
| 6mo | Quartile | +38.1pp, p<0.0001 | +31.7pp, p<0.0001 | +28.6pp, p=0.0001 | +19.0pp, p=0.002 |

## Reading this

Robust. 14 of 16 combinations significant; both non-significant cells are
the same real, expected edge case (-15% at 3 months — a rare tail event at
the shortest window, small hit counts, not a sign the design is fragile).
**6-month window is clean across every threshold and split tested.**

## Recommendation for production wiring

Use the 6-month window as primary (universally robust); disclose the 3mo/
-15% cell honestly rather than drop it silently. -10%/tercile (the
original choice) sits comfortably mid-range, not cherry-picked from the
strongest cell.

## Observation log

| Date | Checkpoint | Reading |
| --- | --- | --- |
| 2026-08-27 | 4 thresholds × 2 splits × 2 windows, full pooled 2004-2026 | See Results table above. |
