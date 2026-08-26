# Warsh Fed reaction function (H-W01)

Status: observing
Version: v0.1
Registered: 2026-08-25

Not wired into any pipeline stage. This is a working paper, not a registered
strategy — see `docs/hypotheses/README.md` for why, and what "graduate" means.

## Thesis

Fed Chair Kevin Warsh's FOMC reacts primarily to deterioration in Treasury and
credit-market *functioning*, not to the absolute level of long-term yields. Market
price pain (a high yield, a falling equity index) is treated as distinct from
market dysfunction (a failed auction, repo stress, a break in credit transmission).
The Fed is hypothesized to tolerate the former and intervene on the latter, largely
independent of the yield level itself.

This would be falsified by a real episode where Warsh's FOMC eases or intervenes
in response to yield/price level alone, with no accompanying functioning-metric
deterioration — or conversely, tolerates a genuine functioning breakdown without
any response.

## Prior

Warsh's 2006-2011 Fed Governor record, used only as a Bayesian prior — the
financial system's structure, the Fed's balance sheet, and the fiscal backdrop
have all changed materially since then, so this is not a training set.

The prior itself shows a split, which is why this paper declares two independent
sub-functions rather than one blended reaction:

- **2008**: Warsh supported the Fed's unprecedented liquidity facilities once repo,
  commercial paper, and interbank funding markets showed genuine market-functioning
  failure.
- **2010**: discussing further asset purchases, he turned notably cautious, citing
  damage to market functioning, the risk of being seen as monetizing government
  debt, crowding out private buyers, and central-bank credibility — concerns that
  map closely onto the current environment (a large fiscal deficit, an elevated
  30-year yield, and a Treasury that would prefer lower yields).

Existing context: the desk's `macro_regime_composite` (8 hand-picked factors,
core PCE at weight 0.15) is itself an implicit reaction-function model, tuned for
a well-observed chair over years of data. There is no reason to assume those
weights transfer to a chair with ~3 months of tenure — this paper is a genuinely
separate hypothesis, not an edit to that assumption.

## Two independent sub-functions

Declared separately because the 2008 vs. 2010 record suggests they don't move
together:

1. **Monetary-policy reaction function** — the conventional rate-path/guidance
   response to macro conditions.
2. **Market-functioning reaction function** — the liquidity/balance-sheet response
   to Treasury and credit-market plumbing stress, hypothesized to dominate (1) when
   the two would otherwise conflict.

## What would count as a real checkpoint

Each FOMC meeting, Jackson Hole-style keynote, or market-stress episode is one
checkpoint. Every checkpoint is read against five observation-variable groups —
deliberately weighted differently than `macro_regime_composite`'s own priority
(funding plumbing and Treasury functioning are hypothesized to matter more to
intervention timing here than the macro group, the reverse of that composite's
weighting):

| Group | Variables |
| --- | --- |
| Price | 10Y nominal yield, 30Y nominal yield, 10Y TIPS real yield, 30Y TIPS real yield, breakeven inflation, curve slope |
| Treasury functioning | auction tail, bid-to-cover ratio, dealer take-down share, bid/ask spread, market depth, fails-to-deliver, MOVE index |
| Funding plumbing | SOFR-IORB spread, repo rate, SRF usage, discount window usage, reserve balances |
| Credit transmission | IG spread, HY spread, mortgage spread, bank lending standards, commercial paper pricing, private credit pricing |
| Macro | core PCE, inflation expectations, unemployment rate, initial claims, GDP/growth |

### Response ladder

Each checkpoint's reading is placed on this graduated ladder, not read as a single
hawkish/dovish scalar:

| Level | Meaning |
| --- | --- |
| R0 | Tolerate |
| R1 | Verbal intervention |
| R2 | Rate-path adjustment |
| R3 | SRF / repo / liquidity provision |
| R4 | Reserve-management Treasury bill purchases |
| R5 | Emergency credit facilities |
| R6 | Long-duration Treasury purchases / QE |

R3-R5 can expand the Fed balance sheet without implying monetary easing — the
Fed's own Monetary Policy Report already classifies current short-bill purchases
as reserve-management, not QE. Balance-sheet growth alone must never be labeled
`QE=true`.

### Speech text-factor keywords

For reading a keynote or statement's text directly:

| Signal | Keywords |
| --- | --- |
| Put probability down | price stability, market forces, fiscal responsibility, market participants, inflation credibility |
| Put probability up | market functioning, financial stability, credit transmission, liquidity, ample reserves, disorderly, balance-sheet flexibility |
| QE-branch probability up sharply | longer-term Treasury purchases, portfolio balance, duration, asset purchases |

Next scheduled checkpoint: Jackson Hole keynote, 2026-08-28 10:00 ET (Fed-confirmed).

## Promotion criteria

None claimed yet. This is a cold-start hypothesis with essentially zero real 2026
data — Warsh has held the chair for about three months and has deliberately
minimized forward guidance (in a July 2026 press conference he stated that the
market says it wants his reaction function but really wants his forecast/dot).
Real calibration requires roughly 10-20 observation checkpoints before this can
function as a regime classifier rather than a narrative. Only once that many real
checkpoints accumulate and the reading is consistent enough to state a real
conclusion does this graduate into a `strategies` row and real pipeline code —
per `docs/hypotheses/README.md`'s lifecycle.

## Observation log

| Date | Event | Sub-function | Reading | Note |
| --- | --- | --- | --- | --- |
| unconfirmed (~July 2026) | July 2026 FOMC | Monetary policy | Hawkish | Held rates 9-3 with core PCE still above the 2% target; the three dissenters wanted a hike, not a cut. Statement said the Committee "will deliver price stability." No easing guidance was given despite long-term yields already being elevated — the first real 2026 evidence that Warsh does not treat a high yield level, by itself, as a reason to ease. (User-reported, 2026-08-25 research session; exact meeting date not confirmed.) |
