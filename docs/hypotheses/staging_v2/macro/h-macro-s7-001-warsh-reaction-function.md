# H-MACRO-S7-001 — Human Observation — Warsh Reaction Function

| Field | Value |
| --- | --- |
| Study ID | H-MACRO-S7-001 |
| Legacy ID | H-W01 |
| Decision layer | Macro |
| Study role | S7 — Human Observation |
| Status | Observing |
| Version | v2.0 |
| Registered | 2026-08-25 |
| Dataset | Dated FOMC, speech, and market-functioning event log |
| Input | Macro conditions, Treasury functioning, funding plumbing, and credit transmission |
| Target | Observed Fed response across rates, balance sheet, liquidity, and guidance |
| Production use | None |
| Does not claim | A calibrated chair classifier, market forecast, or trading signal |

## Hypothesis

A Warsh-led FOMC will tolerate a high yield or a falling asset price when markets
still function, but will respond when Treasury, funding, or credit transmission
shows genuine dysfunction. Market price pain and market dysfunction are separate
inputs.

The hypothesis is weakened by repeated easing or intervention caused by price
level alone, or by repeated non-response during observable market dysfunction.

## Observation contract

Record each checkpoint without inferring missing fields.

| Input group | Examples |
| --- | --- |
| Price | Nominal and real yields, breakevens, curve slope |
| Treasury functioning | Auction tail, bid-to-cover, dealer take-down, depth, fails, MOVE |
| Funding plumbing | SOFR-IORB spread, repo, SRF, discount window, reserves |
| Credit transmission | IG/HY spreads, mortgage and commercial-paper pricing, lending standards |
| Macro | Core PCE, inflation expectations, unemployment, claims, growth |

Keep four response dimensions separate:

| Response dimension | Values |
| --- | --- |
| Rate policy | Hike / Hold / Cut |
| Balance sheet | QE / Neutral / QT |
| Liquidity | None / Repo-SRF / Emergency facility |
| Guidance | Hawkish / Neutral / Dovish |

Market outcomes are optional observations, never inferred from the Fed response.

## Results

| Date | Event | Inputs observed | Fed response | Market outcome | Reading |
| --- | --- | --- | --- | --- | --- |
| Unconfirmed, approximately July 2026 | July 2026 FOMC | Core PCE above target; long yields elevated; no recorded functioning failure | Hold; liquidity none; guidance hawkish; balance sheet unknown | Unknown | One weak checkpoint consistent with tolerating a high yield level when functioning stress is absent. Exact meeting date and missing dimensions remain unconfirmed. |

## Honest conclusion

One partly unconfirmed checkpoint cannot establish a reaction function. It only
preserves the distinction between yield level and market dysfunction for future
observations.

## Translation decision

Keep as S7 Human Observation. Do not add it to the macro composite. Consider a
structured S2 study only after roughly 10-20 dated checkpoints make the response
categories usable.
