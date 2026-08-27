# Warsh Fed reaction function (H-W01)

Status: observing
Version: v0.1
Registered: 2026-08-25

Not wired into any pipeline stage. Uses the 3-layer input/response/outcome
structure defined in [`macro-research/README.md`](README.md) — this paper
supplies the input-signal groups and is the first to apply the decomposed
response table.

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
checkpoint, read through the 3-layer structure ([framework](README.md)).

### Layer 1 — input signals

Deliberately weighted differently than `macro_regime_composite`'s own
priority (funding plumbing and Treasury functioning are hypothesized to
matter more to intervention timing here than the macro group, the reverse of
that composite's weighting):

| Group | Variables |
| --- | --- |
| Price | 10Y/30Y nominal yield, 10Y/30Y TIPS real yield, breakeven inflation, curve slope |
| Treasury functioning | auction tail, bid-to-cover ratio, dealer take-down share, bid/ask spread, market depth, fails-to-deliver, MOVE index |
| Funding plumbing | SOFR-IORB spread, repo rate, SRF usage, discount window usage, reserve balances |
| Credit transmission | IG spread, HY spread, mortgage spread, bank lending standards, commercial paper pricing, private credit pricing |
| Macro | core PCE, inflation expectations, unemployment rate, initial claims, GDP/growth |

### Layer 2 — Fed response (independent dimensions, not one scalar)

| Dimension | Outcomes |
| --- | --- |
| Rate policy | Hike / Hold / Cut |
| Balance sheet | QE / Neutral / QT |
| Liquidity | None / Repo-SRF / Emergency facility |
| Guidance | Hawkish / Neutral / Dovish |

Balance sheet ≠ Liquidity: reserve-management bill purchases can expand the
balance sheet without being QE — the Fed's own Monetary Policy Report already
draws this distinction. Never collapse the two into one `QE=true` flag.

### Layer 3 — market outcome (kept separate from layer 2)

| Dimension | Outcomes |
| --- | --- |
| Equity | Risk-on / Neutral / Risk-off |
| Duration | Bull / Neutral / Bear |
| Credit | Tightening / Neutral / Easing |
| USD | Strong / Neutral / Weak |
| Volatility | Expansion / Neutral / Compression |

A cut doesn't automatically mean layer 3 = risk-on (a panic cut can coincide
with equities still falling) — recorded independently, never inferred from
layer 2.

### Speech text-factor keywords

For reading a keynote or statement's text directly:

| Signal | Keywords |
| --- | --- |
| Put probability down | price stability, market forces, fiscal responsibility, market participants, inflation credibility |
| Put probability up | market functioning, financial stability, credit transmission, liquidity, ample reserves, disorderly, balance-sheet flexibility |
| QE-branch probability up sharply | longer-term Treasury purchases, portfolio balance, duration, asset purchases |

Next scheduled checkpoint: Jackson Hole keynote, 2026-08-28 10:00 ET (Fed-confirmed).

`asset-selection-research/gold-reaction-function.md` (H-SECT06) registered
2026-08-27, one day ahead of this keynote, watching the same real event
from `GLD`'s side (fiscal-dominance/debasement pricing vs. this paper's
Fed reaction function) — worth cross-checking both after the keynote lands.

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

Columns match layer 2's dimensions, plus layer 3 where known; `?` where not
yet recorded — never force-filled.

| Date | Event | Rate | Balance sheet | Liquidity | Guidance | Layer 3 | Note |
| --- | --- | --- | --- | --- | --- | --- | --- |
| unconfirmed (~July 2026) | July 2026 FOMC | Hold | ? | None | Hawkish | ? | Held rates 9-3 with core PCE still above the 2% target; the three dissenters wanted a hike, not a cut. Statement said the Committee "will deliver price stability." No easing guidance despite long-term yields already elevated — the first real 2026 evidence Warsh does not treat a high yield level, by itself, as a reason to ease. Balance-sheet stance and market outcome not recorded at the time; left `?` rather than reconstructed after the fact. (User-reported, 2026-08-25 session; exact meeting date not confirmed.) |
