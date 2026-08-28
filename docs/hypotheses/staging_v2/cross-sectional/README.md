# Cross-Sectional Research - Staging V2

This type asks where an existing risk budget should be expressed relative to a
declared peer group. The larger disposable Stage 2 dataset is research-only; its
symbols do not enter the live desk universe.

## Current studies

| Study | Role | Status | Production use |
| --- | --- | --- | --- |
| [Gold Reaction Function](h-xsec-s7-001-gold-reaction-function.md) | S7 | Observing | None |
| H-XSEC-S2-001 - Broad-Universe Factor Matrix | S2 | Design; wait for fetch completion | None |

## H-XSEC-S2-001 initial design

Hypothesis: some candidate characteristics have a stable relationship with
later relative performance across a declared peer universe. One loop replaces a
separate paper for every factor, target, and horizon.

| Loop axis | Initial values |
| --- | --- |
| Signal family | Cross-sectional momentum; low volatility; MAX effect; relative strength; dispersion; beta-adjusted and regime-conditioned variants |
| Target family | Forward relative return; rank persistence; forward volatility; maximum adverse excursion |
| Horizon | 1W; 1M; 3M; 6M; 12M where data supports it |
| Universe slice | Broad market; sector; thematic membership; asset sleeve |
| Validation | Time-ordered splits; symbol coverage and membership limitations shown |

Parameters and universe slices are frozen before reading results. A variant is a
new row in the loop, not a new document.

| Family | Signal | Target | Horizon | Universe | N | Dev IC | Test IC | IC rank | Effect | p | BH q | q rank | Sign stable | Verdict |
| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| _unrun_ | | | | | | | | | | | | | | |

## Manual gates

1. Wait for the current Stage 2 fetch to finish and audit actual coverage.
2. Approve the peer universes, factor definitions, horizons, and split.
3. Run the approved matrix once.
4. Review ranked results manually; do not promote the lowest p-value.
5. Open S3, S4, or S5 only for a result selected for a different question.
