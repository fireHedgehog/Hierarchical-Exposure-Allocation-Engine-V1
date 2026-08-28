# Dow Theory structure break as a risk-state signal (H-DOW02)

Status: concluded-confirmed
Version: v0.1
Registered: 2026-08-26

Not wired into any pipeline stage. Explicitly **not** a revival of
`dow-theory-trend-structure.md` (H-DOW01a, concluded-rejected, stays
rejected) — that paper tested `structure → E[r_{t+1}]` and found no
positive edge, in fact the opposite. This is a genuinely different claim:
`structure → forward realized volatility`, a risk-state question, not a
return-direction one. Prompted directly by external review (a parallel,
code-blind conversation the user ran alongside this session) correctly
pointing out that this project had only ever tested the mean-return shape
of a hypothesis, never the volatility/risk shape — real, valid
methodological gap, checked here rather than assumed.

## Thesis

A broken swing structure (a Lower High or Lower Low, per H-DOW01a's same
mechanical fractal definition) predicts higher forward realized volatility
than an intact structure — independent of whether it predicts higher or
lower forward *return*, which H-DOW01a already answered separately. A
structural break plausibly signals genuine uncertainty/disagreement about
price, which should show up as volatility whether the subsequent move is
up or down.

This would be falsified by a real test showing no significant difference,
or the opposite direction, in forward realized volatility between an
intact and a broken structure.

## Prior

No single canonical paper the way the return-direction factors had one;
this is a standard, real practice in institutional systematic
research — testing a state variable against multiple downstream
distributional properties (volatility, tail risk, dispersion), not just
conditional mean — rather than a specific published anomaly. Consistent
with, though not proof of, real trend-following literature's broader
point (Moskowitz, Ooi & Pedersen 2012; Hurst, Ooi & Pedersen's extension
to roughly a century of cross-asset data) that trend-related signals carry
real information on diversified, multi-asset-class instruments — this
project's staging universe is neither diversified across asset classes
nor long/short, a real, disclosed limitation of what this specific test
can and cannot speak to.

## What would count as a real checkpoint

A continuous, statistically testable claim: the same point-in-time
intact/broken structure indicator as H-DOW01a, paired with real forward
realized volatility (standard deviation of daily returns over the
forward window, not the return itself) instead of forward return.
Computed via `backend/research_lab/dow_theory_risk_state.py` (read-only
against the sealed dataset, never the production DB), reusing the exact
swing-detection code already proven in H-DOW01a's script.

## Promotion criteria

Real, significant relationship between structure state and forward
volatility. If confirmed, this signal is a candidate for a risk-state /
sizing role (`strategy_components.roles_json`, already proven for
role-tagging in 0.13), not the alpha/timing ensemble — a structurally
different consumer than a confirmed return-direction factor would be,
decided from the evidence once it exists, not assumed in advance.

## Observation log

| Date | Checkpoint | Reading | Note |
| --- | --- | --- | --- |
| 2026-08-26 | Real IC test, structure state vs. forward 21-day realized volatility (daily stdev), `research_lab/dow_theory_risk_state.py` against dataset `real-macro-d9a319bd-09e0-443b-93b3-2e6ec70f4170`, stride=5, identical swing detector to H-DOW01a | **Confirmed.** r=-0.039 (adjusted p=0.0001, n=10,219: 3,945 intact, 6,274 broken) — negative, meaning broken structure predicts *higher* forward volatility. Mean forward realized vol: intact structure 1.17%, broken structure 1.24%. | Real, modest in magnitude but genuinely different from H-DOW01a's rejected return-direction result — the same underlying state variable, tested against a different downstream property, gives a different, real answer. First clean confirmation this session of the risk-state reframing (external review's correct point): a signal can fail as `factor → E[r]` and still succeed as `factor → risk`. Candidate for a sizing/risk-state role (`strategy_components.roles_json`), not the alpha/timing ensemble, if this survives further scrutiny — not decided here, just the honest category it would belong to. |
| 2026-08-26 | Rerun on the real 2004-2026 dataset (post-0.38 extension, now including 2008), same script, same swing detector | **Confirmed, replicated and slightly strengthened.** r=-0.044 (adjusted p<0.0001, n=21,480: 8,026 intact, 13,454 broken) -- was r=-0.039 on 2016-26. Mean forward realized vol: intact 1.16%, broken 1.24% -- same direction, similar magnitude. | The confirmation holds up on the longer window including 2008 -- real evidence this risk-state signal isn't specific to one bull decade, strengthening the case for it as a genuine sizing candidate (H-VOLSCALE01's inconclusive integration test used this same longer dataset already). |
