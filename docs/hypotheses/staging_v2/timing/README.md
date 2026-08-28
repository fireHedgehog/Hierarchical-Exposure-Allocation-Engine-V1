# Timing Research - Staging V2

Timing asks when to act on an already-selected candidate. Existing staging code
continues to run until a later translation is explicitly approved.

## Current study

| Study | Role | Status | Production use |
| --- | --- | --- | --- |
| H-TIME-S2-001 - Event and Signal Matrix | S2 | Initial design | None |

## H-TIME-S2-001 initial design

Hypothesis: a small set of predeclared price, volatility, and event states has a
stable relationship with the next path of an already-selected instrument.

| Loop axis | Initial values |
| --- | --- |
| Family | Time-series momentum; short-term reversal; gap down; large drop; Dow structure/risk state; VIX compression |
| Target family | Forward return; direction; realized volatility; adverse excursion; recovery or explosion event where applicable |
| Horizon | Family-specific, frozen before results |
| Instrument slice | Broad index; sector ETF; theme ETF; single name, kept separate |
| Validation | Episode de-duplication; time-ordered splits; cost-free relationship test first |

| Family | State/event | Target | Horizon | Slice | Episodes/N | Dev IC or delta | Test IC or delta | Effect rank | p | BH q | q rank | Stable | Verdict |
| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| _unrun_ | | | | | | | | | | | | | |

IC is used for continuous tests; event-rate delta is used for discrete tests.
They share one table but are never compared as if they were the same unit.

## Manual gates

1. Approve each family's event definition and horizon before running it.
2. Run only relationship tests in S2.
3. A signal with a real relationship may later get a separate S4 action rule.
4. Costs, turnover, liquidity, and full-path performance belong to S5; they are
   not smuggled into this matrix or used to change the running strategy.
