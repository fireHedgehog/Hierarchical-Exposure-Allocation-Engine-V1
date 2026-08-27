# Changelog

This log records material changes to the product thesis, interaction design, data semantics, application, and operating model. Detailed run results and strategy lifecycle events belong in the database.

## Unreleased

### Research — H-MACRO03: equity outcome predictors, direct test of "bad news is good news"

- New `research_lab/equity_outcome_predictors.py`: real, pooled continuous IC, each of 24 layer-1 indicators vs. SPY's own forward 1m/3m return. 17/24 significant, full 2004-2026 history for most.
- Direct test of a real, user-proposed mechanism (stress → policy intervention → rally): VIX confirms it cleanly (higher fear → higher forward return, r=+0.129 at 3m, full history) and breakevens confirm the other half (lower T10YIE → higher return, r=-0.154). NFCI does not fit the same story — negatively correlated, the naive direction, opposite of VIX — disclosed as a real, unresolved nuance rather than smoothed over.
- Second real pattern: INDPRO negative (strong growth → lower forward return, a "good news is bad news"/hawkish-Fed story) while CPI/PCE are positive — flagged for a redundancy pass, not force-explained.

### Research — H-MACRO02: balance-sheet predictors, continuous IC not discrete events

- New `research_lab/balance_sheet_predictors.py`: unlike Rate's discrete FOMC steps, balance sheet is a continuous stock — a naive weekly-direction "event" would mostly capture routine operational noise, the exact QE/reserve-management conflation the framework flags. Tests each indicator's level against `WALCL`'s own forward 13-week % change instead, real Pearson + Benjamini-Hochberg.
- Real result: 10 of 23 significant (richer than Rate's 4/22) — rate-level and credit-tightening signals predict forward contraction, NFCI's stress signal predicts forward expansion. Two credit-spread results real but confined entirely to the 2023-2025 QT window, flagged as possibly regime-specific.
- The continuous framing gave even the shortest-history series (credit spreads n=36, SOFR n=106) enough samples to clear the floor — no "not done" rows this time, illustrating that test shape matters as much as data availability.

### Research — H-MACRO01: first indicator-vs-Rate-decision table, real ground truth derived from data

- New `research_lab/rate_decision_predictors.py`: real hike/cut events derived directly from `DFEDTAR`/`DFEDTARU`/`DFEDTARL` level changes (2004-2026, no hand-curated FOMC calendar — holds deliberately not classified, disclosed as a real v1 limitation). Tests all 22 other layer-1 indicators via Pearson + Benjamini-Hochberg.
- Real result: 4 of 22 significant — NFCI, VIXCLS, T10YIE, T5YIE (all market-based/forward-looking; none of the slower macro releases individually predicted direction). `BAMLH0A0HYM2`/`BAMLC0A0CM` correctly landed "not done — only 6 real events in their 3-year window," exactly the honest-gap case this format was designed to surface.
- 3 more free FRED series added to production (`DFEDTAR`, `DFEDTARU`, `DFEDTARL`) for this ground truth; caught and fixed a real `None`-handling gap in `fetch_data.py`/`validate_data.py` for DFEDTAR's permanent discontinuation before it broke anything downstream.

### Engine — 14 new free FRED series fetched into production, live-verified

- `SERIES_METADATA` (`common.py`) extended from 8 to 22 series — `fred_observations` is already series-agnostic, so no schema change. Every candidate verified live against the real FRED API before being wired in (a wrong ID hard-fails the whole fetch stage).
- Real, live pipeline run: 50,196 FRED observations across 22 series (was 13,793/8). One real freshness-threshold miss caught and corrected: GDPC1's freshest print was 147 days old, not ≤120 as guessed — bumped to 160 based on the real observed value, same pattern as PCEPILFE's earlier correction.
- Real, disclosed data-quality finding: `BAMLH0A0HYM2`/`BAMLC0A0CM` (HY/IG OAS spreads) only have ~3 years of real point-in-time vintage history in this project's pinned-`realtime_start` fetch, even though their current/non-vintage display goes back further — a genuine ALFRED vintage-archive limit on these vendor-licensed series, verified directly against the API, not a bug.
- `macro_regime_composite` untouched — these 14 are fetched and available, not yet used by the live composite, per the explicit freeze.

### Research — macro research subfolder + 3-layer framework

- New `docs/hypotheses/macro-research/`: user-designed 3-layer structure (input signal / Fed response, decomposed into independent Rate-Balance sheet-Liquidity-Guidance dimensions / market outcome, kept separate from the response layer) replacing "does X predict QE/hike/risk-on" single-scalar questions. Per-indicator research card template; redundancy/incremental-value check reuses the existing `signal_validation.py` effective-number-of-bets machinery already proven on the 8 macro factors.
- `warsh-reaction-function.md` (H-W01) moved into the subfolder and restructured onto this framework: its old R0-R6 response ladder replaced by the 4-dimension table; a new market-outcome layer added; the existing July 2026 FOMC observation re-tagged, `?` left honest where not recorded rather than reconstructed.
- **`macro_regime_composite` stays frozen at naive-v2** until this program produces real, quantified evidence — explicit, non-negotiable, per direct instruction.

### Research — two informal claims run and rejected (H-GAPFILL01, H-CRASHREV01)

- `research_lab/gap_down_fill.py`: SPY/QQQ gap-down fill rate is high in absolute terms (72-93%) but *lower* than the unconditional baseline (~99.9%) at every spec, both symbols — the opposite of the claim. Rejected.
- `research_lab/large_drop_reversion.py`: after a real SPY >=3% single-day drop, close-based recovery is significantly *slower* than baseline at every window (5/10/20d); the loose intraday-high check is ~ceiling for both conditional and baseline, uninformative. Rejected; not a contradiction of the already-confirmed H-STREV01 (a much weaker, differently-specified claim).
- Data caveat disclosed in both: SPY's free-tier daily `open` rarely differs from the prior close in this data source, understating true overnight gaps (doesn't change either result's direction).

### Research — thematic beta selection process preregistered (H-BETA01)

- New `docs/hypotheses/thematic-beta-selection-process.md`: not a new price/volume anomaly (every prior paper in the folder already covers single-name ground) — a decision-process hypothesis, prompted directly by the user's own trading history (thematic-beta riding, not stock-picking) and their own stated bottleneck: "I cannot always rely on the market story then believe it will be long term beta, that is purely luck."
- Split into 6 minimum ingredients per this project's single-ingredient discipline: price leadership, leadership duration, breadth confirmation, and a leader-specific deterioration signal are all real and buildable now from the existing 2004-2026 staging dataset with no new data; fundamental/positioning confirmation is named as a real, honest gap (no data provider exists yet); theme identification itself is inherently qualitative and real-time, tracked (not statistically tested) via a new R0-R10 theme-lifecycle ladder, the same shape as `warsh-reaction-function.md`'s response ladder.
- Three companion papers named and queued, not yet built (H-BETA02 leadership-duration distribution, H-BETA03 breadth-confirmation value, H-BETA04 leader-specific deterioration signal reusing H-DOW02's validated detector) — the fast-accumulating half of this program, answerable now against real historical data rather than waiting on new real-time episodes.
- Observation log seeded with one real, retrospective, explicitly pre-process entry (AI infrastructure capex, R1) — logged honestly as the prior that motivated the paper, not evidence the process works.

### Engine — 12-1 momentum promoted into the live cross-sectional blend as naive-v3

- `12m_skip1m` (Jegadeesh & Titman 1993 "12-1" momentum) flipped `draft` → `active` and wired into the live IC-weighted blend as a 4th horizon — a registration decision on already-standing evidence (0.16: diversifying, ENB 1.74→2.11; 0.26: real significant predictor, r=+0.067), not a new research run.
- New `backend/engine/factors/momentum_v3.py`: same significance-weighted blend mechanism as `momentum_v2.py`, generalized to 4 horizons with a per-horizon `skip_days` (21 for 12m_skip1m — the real 12-1 signal point is one month before the decision date, not the latest close). `cross_sectional_backtest.py` and `factor_engine.py` both repointed at v3 so "the real production ranking" stays an honest claim. 7 new tests. 168/168 backend tests passing.
- Live-verified on a fresh real pipeline run: `factor_dimensions` shows the new horizon actually computed — `momentum_12m_skip1m`, 21,409 real paired samples, r=+0.059, significant, weight 0.31.

### Engine — short-term reversal entry engineered and wired in as naive-v3

- New `backend/engine/timing/backtest_v3.py`: real entry when trailing 5-day return drops below -3% (disclosed, hand-picked, not fit), exit unchanged (RSI(14) >= 70). Same result shape and honest-failure behavior as `backtest_v2.py` — retiring either component degrades gracefully (open positions stay open, or `no_entry_signal_active`), never crashes or fabricates a rule. 5 new tests.
- `macd_rsi_single_name_timing` promoted to `naive-v3`: `short_term_reversal_entry` flipped `draft` → `active` with a real `code_reference` (was `NULL`); `rsi_overbought_exit` carried forward active. `factor_engine.py` repointed at the new version and function; 8 stale MACD-referencing messages corrected. 161/161 backend tests passing.
- Live-verified on a fresh real pipeline run: `factor_engine` logged 872 real entries across 22 symbols — the exact inverse of the prior milestone's proven zero-trade `no_entry_signal_active` state, now firing for the real reason a real entry trigger exists again. `symbol_events` couldn't be spot-checked against this specific run — `publish_snapshot` remains scaffolded and unconnected (pre-existing, unrelated), so no new snapshot was published; the stage's own message is the live proof here.

### Engine — MACD entry retired, short-term reversal registered as its draft replacement

- `macd_crossover`'s status flipped to `retired` (fresh-clone-safe UPDATE, effective on the existing dev DB with no reset) — a real event study found no edge (0.29). It was the only registered entry trigger, so the pipeline now honestly reports `no_entry_signal_active` and zero trades — live-verified on a real pipeline run.
- New `short_term_reversal_entry` component registered as `draft`, `code_reference=NULL` — real, cost-checked evidence exists (H-STREV01/H-STREV02) but the entry rule itself hasn't been engineered or wired in yet. `verification_status` stays `registered_only`, not `verified` — research evidence and a production-ready rule are different bars.
- Two new lifecycle events record both changes with real reasons. 156/156 backend tests passing.

### Research — short-term reversal's cost/turnover robustness: real, cost-sensitive

- New H-STREV02 (`short-term-reversal-cost-robustness.md`): a real, tradable weekly walk-forward strategy on H-STREV01's confirmed signal (buy the 5 biggest trailing-5-day losers, hold a week), gross vs. net at four disclosed real cost assumptions (5/10/25/50bps), scaled by actually-measured turnover (mean 148.7%/period).
- Real result: gross Sharpe 1.15; net Sharpe 0.96 at 5bps, 0.77 at 10bps, 0.21 at 25bps, -0.73 at 50bps — the edge survives cost levels plausible for this liquid universe, fully destroyed by 50bps. Recorded `concluded-confirmed (cost-sensitive)` rather than a forced binary call. Caveat disclosed: this covers ~2018-2026 (shortest-symbol-constrained by XLC), not the full 2004-2026 window.

### Engine — momentum sign bug fixed

- `compute_horizon_weights` weighted each horizon by `abs(correlation)` only, discarding sign — flagged since 0.26, now fixed. A significantly reversal-shaped horizon now gets a real negative weight, applied as a final signed step on top of the unchanged magnitude normalization; every other horizon keeps the existing naive positive-momentum default.
- New dedicated test proves both halves: the horizon gets a real negative weight, and a symbol with a strong recent gain on that reversal-shaped horizon scores less bullish than a flat one, not more. 156/156 backend tests passing.
- Live-verified honestly: the freshest real pipeline pull right now shows none of the 3 live-blend horizons clearing significance (expected — live market data is non-stationary; a rerun minutes earlier did find 1m/3m significant). The fix is real and unit-proven regardless of what any single live snapshot shows.

### Research — 2004-2026 rerun: one strengthened, two replicated, one weakened

- Reran the four price/vol hypotheses with real `research_lab` scripts against the real 2004-2026 dataset (now including 2008): time-series momentum weakened (2 of 5 horizons still significant, was 5 of 5); Dow Theory trend-structure and risk-state both replicated cleanly at similar magnitude; short-term mean reversion strengthened and now holds at 2 weeks too (was 1 week only) — the strongest, most durable result this session.
- Each paper's observation log got a new dated entry with real numbers, never overwriting prior checkpoints. A temporary tracking table lived in `docs/hypotheses/README.md` for the duration and was deleted once done, per standing instruction that only this file accumulates — other docs stay snapshots, `git log` is the history.
- Four items deliberately not rerun (production-factor audits, not research_lab scripts): the still-unfixed momentum sign bug, the draft 12-1 promotion decision, the MACD-entry retirement decision, and RSI/MACD-exit monitoring — named here so they aren't lost, deferred as product decisions.

### Research — hypothesis index gains a dataset column and real-finding recap

- `docs/hypotheses/README.md`'s index: new `Dataset` column (`2016+` vs. `2004+`) flagging that 8 of this session's 11 hypothesis tests predate the 2004 data extension and one (H-VOLSCALE01) doesn't — not apples-to-apples. Checkpoint-count column replaced with a one-line real-finding summary per paper, for self-serve recap as the hypothesis count grows.
- Named, queued: re-running the 8 pre-extension hypotheses against the real 2004-2026 data (now including 2008) — the highest-value next step, testing whether the session's repeated "disruption beats order" pattern is durable or a bull-decade artifact, before broadening to new candidate factors.

### Research — vol-scaling integration test: honest, inconclusive, attribution-checked

- New H-VOLSCALE01 (`vol-scaled-cross-sectional-momentum.md`), preregistered before running: real vol-scaled vs. constant-exposure comparison on `cross_sectional_momentum`'s already-validated strategy backtest (not `macd_rsi_single_name_timing`, whose entry has no proven edge — external review's correction).
- Against the naive 100%-exposure baseline, the vol-scaled version looked like a clean win (max drawdown -25.9% → -19.9%, Sharpe flat). An attribution check (constant 77.2% exposure, zero timing) produced nearly identical numbers — most of the improvement is just being less invested on average, not the timing mechanism. Recorded `concluded-inconclusive` (new status) rather than forced into confirmed/rejected.

### Engine — staging universe now fetched from a fixed 2004-12-01 anchor

- New `STAGING_UNIVERSE_START_DATE = "2004-12-01"` (GLD's real, empirically-verified launch day) replaces the rolling 10-year `PRICE_FETCH_RANGE` for the staging price fetch. Every symbol aligns to the same real calendar window (a controlled cross-asset comparison, e.g. gold vs. an equity index across 2008) instead of each reaching back as far as its own history allows; dot-com coverage is deliberately traded away since GLD didn't exist yet, 2008 is kept.
- Real discovery made while implementing: Yahoo's `range=max` silently degrades `interval=1d` to a coarser real resolution over multi-decade spans (verified: 262 bars instead of the real 5,467). `fetch_daily_bars()` gained a `start_date` parameter using explicit `period1`/`period2` to get genuine daily granularity; `range_` still works for relative-window callers.
- `FRED_OBSERVATION_WINDOW_DAYS` extended to match (7,950 days). Live-verified: a real pipeline run now fetches 113,026 real daily bars (was 55,950) and 13,793 real FRED observations (was 6,330); GLD/SPY/QQQ/IGV align to 2004-12-01, while XLC (real 2018 listing) correctly keeps its own later start date.

### Research — `proportion_significance()`: the statistical primitive for probability-shaped hypotheses

- New, real, hypothesis-agnostic addition to `backend/engine/research/significance.py`: a real Fisher's exact test between two groups' hit-rates — answers "is P(event) actually different between two states," which `pearson_significance` cannot. Chosen over a naive two-proportion z-test for validity on small/imbalanced samples. 5 new tests, 155/155 passing.

### Research — risk-state reframing validated: a rejected signal confirmed as a real volatility signal

- New H-DOW02 (`dow-theory-risk-state.md`), prompted by external review naming a real gap: every price/volume hypothesis this session was tested only as `factor → E[r]`, never against volatility/risk. Not a revival of the rejected H-DOW01a (return-direction) — a genuinely different claim, same structure-state indicator against forward realized volatility instead.
- New `research_lab/dow_theory_risk_state.py`. Confirmed: r=-0.039 (adjusted p=0.0001, n=10,219) — broken structure predicts higher forward volatility (1.24% vs. 1.17% mean daily stdev). First clean demonstration this session that a signal can fail as a return predictor and succeed as a risk-state one. Four more analogous sub-hypotheses proposed and queued, not built all at once.

### Frontend — chart volume promoted to its own pane; a real hover tooltip

- `PriceChart.tsx`: volume moved from a bottom-of-price-pane overlay into its own real pane (price, volume, RSI, MACD, in order). New crosshair-driven hover tooltip: OHLC, real volume, and close × volume as an honestly-labeled turnover *approximation* (no float data exists for a real figure). Built with `textContent`, not `innerHTML`. `tsc`, 52 frontend tests, and the build all clean; could not visually confirm in a browser — no automation tool available in this environment, disclosed rather than assumed.

### Research — orthogonality check on the "four independent tests" claim; partly wrong, corrected

- New `research_lab/orthogonality_check.py`: real pairwise correlation across all five price/vol signals tested this session, triggered by the user's own suspicion that the Dow Theory test might just be re-measuring the same recent-drawdown condition as the other rejections.
- Result: `low_vol_63d` and `max_return_21d` are r=+0.78 — genuinely the same bet, not independent. But `dow_structure_intact` and `ts_momentum_12m` correlate weakly with everything else; effective number of bets across all 5 = 3.84. Corrected claim: not four independent tests, not one test four times — roughly four real, mostly-independent signals with one genuinely redundant pair. Both affected papers updated rather than left overstated.

### Research — Dow Theory swing structure rejected; four-for-four on the same signature

- New `research_lab/dow_theory_trend_structure.py`: a mechanical, non-discretionary fractal swing detector (real OHLC, point-in-time confirmed, no look-ahead) tests whether an intact Higher-High/Higher-Low structure predicts higher forward returns than a broken one. Split from volume confirmation (a separate, later hypothesis) per single-ingredient discipline.
- Rejected, opposite direction: r=-0.039 (adjusted p=0.0001, n=10,219); mean forward return during intact structure (+1.19%) was lower than during broken structure (+1.71%).
- Fourth independently-specified rejection this session with the identical directional signature (low-volatility anomaly, time-series momentum, MAX effect, now this) — four unrelated mechanisms converging the same way, named as this session's strongest real finding, still kept entirely in `docs/hypotheses/` per the developer's letter.

### Research — MAX effect rejected; a third test lands on the same regime signature

- New `research_lab/max_effect.py`: real IC test, trailing max single-day return vs. forward return — a deliberately orthogonal candidate (tail/skewness, not trend or variance). Rejected: r=-0.18 (adjusted p<0.0001, n=10,283), opposite of the predicted direction.
- Third rejection this session with the identical directional signature (calm/low-extreme underperforms, volatile/extreme outperforms) — real evidence about this window's character, named as a pattern, not treated as proof or quietly adapted into the staging pipeline.

### Research — short-term mean reversion confirmed, the first non-rejected factor this session

- New `research_lab/short_term_mean_reversion.py`: a fresh test at Jegadeesh (1990)'s original window (trailing ~1 week), not reused from the two rejected papers' reversal-shaped side effects — avoids hypothesizing after the results were known, disclosed explicitly in the new paper.
- Real result: confirmed at the 1-week forward window (r=-0.0204, adjusted p=0.0020, n=26,044); not significant at 2 weeks (r=+0.0042, p=0.50) — the effect resolves within about a week, empirically locating the "time limit" boundary rather than just asserting one exists.

### Research — low-volatility anomaly run; a real 12-1 check on the reversal finding

- Low-volatility anomaly run against real data: also rejected (r=-0.19, adjusted p<0.0001; calmest third's forward return +0.62% vs. +2.73% for the most volatile third) — likely the same underlying mechanism as time-series momentum's rejection (drawdowns getting bought aggressively in this window's bull market), not an unrelated fluke. Scope caveat recorded: only raw return tested, not the more precise risk-adjusted form of the academic claim.
- User raised a real methodological point: short-term reversal and medium-term continuation are separately time-windowed effects in the literature (Jegadeesh 1990; Jegadeesh & Titman 1993's 12-1 spec) — tested, not assumed. A proper 12-1 (skip-month) version of time-series momentum still rejected (r=-0.028, adjusted p=0.0066), smaller in magnitude but still real and negative.

### Research — first full hypothesis cycle; two new literature-backed candidates preregistered

- Two candidates preregistered under `docs/hypotheses/`: time-series momentum (Moskowitz, Ooi & Pedersen 2012) as a timing-layer challenger to MACD; low-volatility anomaly (Ang, Hodrick, Xing & Zhang 2006; Frazzini & Pedersen 2014) as a cross-sectional addition. Added `preregistered` as a real status distinct from `observing`.
- New `backend/research_lab/time_series_momentum.py`: real IC test across 4 horizons against the sealed dataset, read-only. Result recorded honestly: all 4 horizons significant but negative — the opposite of the predicted direction — moved to `concluded-rejected` (on this universe/window) with a stated, unproven mechanism rather than discarded or softened.

### Research — timing-signal event-study IC test; MACD entry shows no real edge

- `run_timing_signal_significance_research()` tests macd_rsi_single_name_timing's two components as real event studies (0/1 event indicator vs. real 21-day forward return, pooled across every symbol's full history) — the third and final "3 category" gap (macro, name selection, timing), closing out after 0.25/0.26 covered the other two.
- Live-verified: RSI-overbought is a real, validated exit signal (r=-0.015, adjusted p=0.0012, 4,583 real event days). MACD bullish crossover — the strategy's only registered entry trigger — shows no real edge (r=+0.002, p=0.66) over this universe/decade. Flagged, not silently patched.

### Frontend — "Run pipeline" button was buried below a full-page report

- `OperationsOverviewPage.tsx` reordered: the pipeline run panel (`Dry preflight`/`Run available stages`) and latest-run record now render right after the top stat grid; the evidence-gated roadmap (`ProductReadinessPanel`, a long five-milestone report) moved to the bottom. A page titled "Run pipeline" now leads with the ability to run it. User-caught by trying to actually use the page, not by reading the code.

### Engine — real per-symbol current timing signal (regime + cross-sectional + timing, connected)

- New `symbol_events` row per symbol per snapshot (`event_type='timing_signal'`, `event_status='signal_state'`), derived from the MACD/RSI backtest's own trade log — no new table, no new backend field. One of three honest states: holding (open, no exit trigger since entry), flat (closed, no new entry trigger since), or no signal yet.
- Closes a real gap: the cross-sectional signal (relative sector/name strength) and the timing signal (is now the right entry/exit moment) were both computed but never shown together — `factor_engine.py`'s own code comment already said as much. Zero frontend changes needed — the existing generic event-render path picks up the new type automatically.
- Live-verified with real data: IGV and XLE both really did exit on RSI-overbought recently and are flat with no new entry signal; SMH reads cross-sectionally bullish (rank 5 of 22) while its timing state is flat (MACD just crossed bearish) — a real "strong sector, wrong entry moment" read.

### Research — momentum horizon forward-return IC test; a real sign bug found, not yet fixed

- `run_momentum_significance_research()` tests each of cross_sectional_momentum's 4 candidate horizons (1m/3m/6m/12m_skip1m) for real Pearson IC and Rank IC against forward returns — the gap 0.16 explicitly left open. Reuses the exact pooled pairing and Benjamini-Hochberg correction already proven in the live `compute_horizon_weights`; does not touch the live blend itself.
- Live-verified: 1m and 3m are real, significant short-term **reversal** (negative IC), not momentum; 12m_skip1m is real, significant momentum (positive IC); 6m is not significant — the textbook Jegadeesh & Titman (1993) shape.
- **Found, not fixed**: the live blend weights each horizon by `abs(correlation)` only, discarding sign — so a positive 1-month return is currently scored bullish by the live ranking when the data says that direction is bearish. Flagged for a deliberate decision rather than silently patched.

### Research — macro composite's own regime score gets a real forward-return IC test

- `_macro_composite_score_series()` builds the real, point-in-time composite regime score (the same `compute_regime_v2` blend that drives the live regime label) as a real time series, then folds it into the existing 8-factor significance batch as a 9th tested series — no new table, same Pearson/Benjamini-Hochberg correction pool. Closes the gap named in 0.20: every individual macro factor's forward-return correlation had been tested, never the blended composite itself.
- Live-verified against a fresh real pipeline run: 102 real composite-score points (2018-01 to 2026-07) tested against all 22 staging symbols — none of the 22 correlations survive correction (|r| ≤ 0.13), an honest null result, while the pre-existing NFCI-vs-XLV finding (r=+0.18, adjusted p=0.007) reproduced unchanged.

### Infrastructure — `backend/research_lab/` scratch-code convention; hypotheses folder in the nav

- New `backend/research_lab/`: throwaway, no-quality-bar scripts for testing a hypothesis, governed by two rules — never imported by production code, never writes to the database. Reuse is one-way: a script here may import the real utilities in `backend/engine/research/`, never the reverse.
- Side nav gained a "Research hypotheses" link to the GitHub-rendered `docs/hypotheses/` folder, instead of building an in-app Markdown renderer.

### Research — hypotheses start as Markdown working papers, not DB rows

- Retracted `research_observations` and the `warsh_reaction_function` DB registration (both new in this same Unreleased section, never shipped) after recognizing the underlying problem directly: `research_observations.signal_direction` was a hawkish/dovish/neutral/inconclusive `CHECK` constraint, a shape specific to a Fed-policy hypothesis — a price-action or fundamentals hypothesis needs a genuinely different data shape, so committing to one SQL schema at the pre-conclusion research stage is premature structure.
- New `docs/hypotheses/` folder: a hypothesis now starts as a versioned Markdown working paper (thesis, prior, checkpoint definition, promotion criteria, an inline observation log), not a database row. It graduates into a real `strategies` row and real SQL only once it reaches a real conclusion — at which point its schema is designed from the evidence in hand, not guessed at registration time. Reusable, hypothesis-agnostic stats utilities (`backend/engine/research/significance.py`, `signal_validation.py`) remain available for use during the paper stage itself, from an ad-hoc script, without touching the database.
- First hypothesis under the new pattern: `docs/hypotheses/warsh-reaction-function.md` (H-W01) — Fed Chair Kevin Warsh's FOMC reacts primarily to Treasury/credit-market *functioning*, not the absolute yield level; two independent sub-functions (monetary policy; market functioning), the same content previously drafted as DB rows, now as a working paper with one real observation (July 2026 FOMC, hawkish) logged inline.

### Frontend — display-name correction, `macd_rsi_single_name_timing`

- Renamed the user-facing name from "MACD/RSI single-name timing" to "Single-name timing" — a name tied to today's specific components reads as wrong the moment one is retired or a new one registered. `strategy_key` stays untouched (same separation already applied to `security_id` vs. ticker); only the display label changed, via an `UPDATE` alongside the seed row so existing databases pick it up too, not just fresh clones.

### Engine — strategy-level backtest, the "strategy" granularity tier's first real content

- New `backend/engine/factors/cross_sectional_backtest.py`: a real, naive-v1 walk-forward backtest for `cross_sectional_momentum` — at each rebalance date, rank the universe with the real production ranking function (point-in-time, recomputed from only history available then), buy the top N equal-weighted, hold, chain into a real equity curve against a real equal-weight benchmark. `POST /api/v1/admin/research/strategy-backtest/runs`, live-verified: 85 real rebalance periods, naive momentum beats its benchmark (+338.0% vs. +196.0%, CAGR +23.2%, Sharpe 1.22) — an honest, unvalidated result (no costs, no out-of-sample split, hand-picked parameters), not a claim of a working strategy. `STRATEGY_BACKTEST_FAMILIES` explicitly excludes `macro_regime_composite` — a classifier isn't traded, so there's no "strategy" tier for it, matching the desk's own reasoning.

### Frontend — hash-link scroll bug, missing factor_count, granularity-first regroup

- User caught two real bugs by clicking the link a prior fix added: (1) `#anchor` navigation didn't scroll anywhere — React Router doesn't replicate a browser's native jump-to-`#id` behavior on client-side navigation — leaving the momentum link landing on the macro section with no visual cue anything was wrong. Fixed globally in `AppShell.tsx`, not per-page. (2) the read-back endpoint for a signal-validation run was missing `factor_count`, showing "Not available." Fixed by deriving it from the stored correlation pairs.
- User follow-up: the Research page's strategy-first grouping ("Macro regime factors" / "Cross-sectional momentum factors" sections) buried the more important question — what granularity level is this. Regrouped to lead with level (Component / Ensemble / Strategy / Desk, matching the metric catalog's own order), strategy as the secondary label; explicit placeholder sections for the still-unbuilt Strategy and Desk levels state the gap instead of omitting it.

### Frontend — Research page reorganized

- User-identified the Research page had become five unrelated things (macro significance, macro diversification, momentum diversification, the 71-metric catalog) stacked under a page still titled "Factor significance," with no click-through to or from the Strategy registry. Renamed `FactorSignificancePage.tsx` → `ResearchPage.tsx` (route unchanged), restructured into one section per strategy family with a "Registry record" link out of each; Strategy detail page gained a matching "View research" link and per-run "View full result" links. Also named honestly, not fixed: no whole-strategy backtest exists yet for `cross_sectional_momentum` (the composite ranking has never been traded into a real equity curve) — the real reason all 40 `strategy`-level catalog metrics are still dashes, not a UI gap.

### Engine — metric granularity axis

- New `research_metric_catalog.granularity` column (`component` / `ensemble` / `strategy` / `desk`), independent from `category`: WHAT LEVEL of the strategy hierarchy a metric evaluates, mapped onto the existing `strategy_components` → ensemble math → strategy backtest → desk-portfolio schema. User-identified gap: the 71-metric catalog had flattened single-factor metrics (IC), cross-factor metrics (correlation, effective number of bets), and realized-return metrics (Sharpe, CAGR — the tier an optimizer could fit) into one undifferentiated list. All 71 rows re-tagged; the Research page's catalog panel now groups by level first, then category.

### Engine — first research-loop smoke test

- Added Jegadeesh & Titman's (1993) original "12-1" momentum (12-month return, most recent month skipped) as a real `strategy_components` candidate (`status='draft'`) under `cross_sectional_momentum`, proving the whole research loop end to end with a genuine literature-classic factor: ~10 lines in one existing extraction function, zero schema/endpoint/UI changes, DB insert and API read-path both verified directly. Correlates 0.68 with 6M, 0.44 with 3M, only 0.08 with 1M, not flagged redundant — effective number of bets rose from 1.74 to 2.11 once included, a genuine, honest, diversifying result.

### Engine — research-evidence layer (signal validation / effective number of bets)

- New `research_metric_catalog` (71 entries) enumerates the full quant-research taxonomy across 6 categories — data integrity, signal validation, backtest performance, robustness/statistical validation, trading reality, portfolio/risk — each tagged with which strategy families it structurally applies to. New EAV `research_run_metrics` holds only what a real research run actually computed; an uncomputed catalog entry renders as an honest dash, not an implied gap. `research_runs` extended with `component_key`, `superseded_by_run_id`, and `invalidated_reason` for correcting a research mistake without deleting sealed history (schema-ready; no endpoint uses the latter two yet).
- New `backend/engine/research/signal_validation.py`: Rank IC, IC-series mean/std/ICIR, pairwise correlation matrix, effective number of bets (PCA/inverse-Herfindahl), and redundancy flagging — pure, standalone-tested functions, 11 new tests.
- `POST /api/v1/admin/research/signal-validation/runs` wires real, point-in-time-aligned extraction for macro's 8 factors and momentum's 3 horizons. First live run: macro's 8 factors → effective number of bets 2.43 (CPI/core-PCE/PPI flagged redundant at r=0.92-0.998); momentum's 3 horizons → ENB 1.74 (3M/6M redundant at r=0.75). Real numbers validating the "10 factors, PCA, ENB ≈ 2" framing this milestone was built to prove.
- Research page (Operations → Research) gets a diversification panel per factor family and a full metric-catalog reference table.
- Unrelated bug found and fixed while proving this live: `fetch_data`'s FRED realtime pin used UTC "today," which can run a day ahead of FRED's own server clock right after UTC midnight, causing a reproducible HTTP 400. Fixed with a 1-day safety margin.

### Engine — strategy registry backfill

- Registered the 5 real engine algorithms (macro regime composite, cross-sectional momentum, MACD/RSI single-name timing, risk envelope allocation, conviction-scaled instrument selection) in the `strategies`/`strategy_versions` registry that has existed since Edition V1 but was never populated. Each carries real parameters, a `naive-v1` version, a `verification_status` flag (`registered_only` until Milestone 4's statistical gate passes), a `next_review_at` date, and honestly-NULL decay/capacity diagnostics. Seeded in schema.sql, not code or documentation prose — queryable via the existing Strategy registry pages with no new UI.

### Engine — Milestone 4 statistical validation, first slice

- Added `backend/engine/research/`: real Pearson correlation + p-value (scipy) between every macro factor and every staging symbol's forward return, with a hand-rolled, tested Benjamini-Hochberg correction for the resulting multiple-comparisons problem. Run on demand against a sealed dataset (new `POST /api/v1/admin/research/factor-significance/runs`), persisted to new `factor_significance_runs`/`factor_significance_results` tables — deliberately kept separate from the Milestone-3 manual pipeline.
- Extended `fetch_data`'s FRED observation window from 400 days to 10 years (`FRED_OBSERVATION_WINDOW_DAYS`) after the first significance run showed the 5 monthly macro series had too few observations to test at all. With the full window, all 176 (factor, symbol) pairs are testable; exactly one survives correction (NFCI vs. XLV, r=+0.18, adjusted p=0.0059, n=516). The earlier 400-day run's one "significant" result (NFCI vs. XLP on 51 samples) disappeared with more data — evidence for, not against, why this validation step exists before any weight gets fit.
- **Macro research 2**: promoted `macro_regime_composite` naive-v1 -> naive-v2 (`backend/engine/regime/scoring_v2.py`). Real markets price a macro release's surprise against an already-priced-in expectation, not its raw level (Andersen, Bollerslev, Diebold & Vega, 2003; Balduzzi, Elton & Green, 2001) — the same logic behind CME FedWatch-style policy-rate expectations (Krueger & Kuttner, 1996). No free consensus/survey feed exists yet, so the honest, disclosed proxy is a trailing statistical mean of each series' own history (an adaptive-expectations stand-in, Muth 1961), not a market consensus. Same weights and aggregation as naive-v1; only the per-factor scoring formula changed. naive-v1 stays in the codebase untouched for reproducing already-sealed snapshots. New `strategy_versions` row (not a rewrite) records the promotion with real citations.
- **Modular swap-safety proof**: `cross_sectional_momentum` promoted naive-v1 -> naive-v2 (`backend/engine/factors/momentum_v2.py`) to demonstrate that one engine algorithm can be revised and isolation-tested standalone, then swapped into `factor_engine.py` as a one-line change, without breaking the pipeline or any existing test — the pluggable-strategy contract every engine module already follows (self-contained file, standalone test, no shared mutable state). The statistical content is real but secondary: v1's fixed 1M/3M/6M blend weights (0.2/0.3/0.5) are replaced by weights from a real Pearson/Benjamini-Hochberg significance test against pooled forward returns, run fresh every pipeline run. First live run (10y real Yahoo data, 2026-08-25): 1M not significant (r=+0.010, adjusted p=0.284), 3M and 6M significant (r=+0.053/+0.078, p<0.001, n>10,000 pairs each) — consistent with the published momentum literature (Jegadeesh & Titman, 1993), though this pass is coding-agent depth, not a literature review or research-team-grade validation. Equal-weight fallback keeps the score visible if nothing clears correction. v1's code stays untouched and importable; new `strategy_versions` row records the promotion.
- **Sub-strategy granularity, first slice**: new `strategy_components` table registers named, independently versioned, independently retireable sub-signals inside a strategy — the granularity gap identified after 0.12's swap-safety proof (a top-level strategy could already be swapped safely; its internal sub-signals could not be, individually). Supports two component types from day one — `computed` (a real function, value comes from the engine each run) and `manual_override` (a human-set standing value with no data source, e.g. a normally-neutral geopolitical/war-risk override settable to an extreme like -100, with a full audit trail) — though only `computed` components exist yet. `macd_rsi_single_name_timing` promoted naive-v1 -> naive-v2 (`backend/engine/timing/backtest_v2.py`), splitting into `macd_crossover` (entry+exit) and `rsi_overbought_exit` (exit only), combined by a role-tagged signal ensemble rather than macro's null-tolerant weighted average — the two are not peers in a sum, they play different roles in a sequential rule, and forcing one aggregation shape onto both would be wrong, not simpler. Live-proved against real data: retiring `rsi_overbought_exit` (a DB flag flip) degrades gracefully, changing QQQ's backtest return while every pipeline stage still completes; retiring `macd_crossover` too — removing the only registered entry trigger — produces an explicit `no_entry_signal_active` status with zero trades and a plain-language reason, never a crash or a fabricated rule. `get_strategy()` and the Strategy detail page now surface components end-to-end.
- Added a Methodology page (Operations → Methodology), later thinned: one card per named desk — top-level parameter, code reference, and real APA7 citations where a technique comes from published literature (Jegadeesh & Titman 1993, Appel 2005, Wilder 1978, Black & Scholes 1973, Pearson 1895, Benjamini & Hochberg 1995) — with a step-by-step formula walkthrough per layer dropped after it went stale (it still named the retired `backtest.py` after `backtest_v2.py` shipped) and duplicated content that now lives correctly in the DB-driven strategy registry instead. Every named desk is listed, real or explicitly null: the 5 implemented layers plus 2 new `draft` placeholders with no implementation yet (sentiment/text mining, fundamental/EPS analysis — see roadmap.md), each carrying a granularity note for what to define before writing code. An in-app page, not a Markdown file, updated on request at milestones rather than continuously.
- Persisted the -5..+5 `conviction` score (`conviction_from_composite()`) onto `cross_section_rows` and `position_candidates` — it was driving structure selection (equity tilt vs. credit/debit spread vs. LEAPS) this whole time but was computed and discarded, never actually visible. Now shown as a real number on the Today page's Cross-sectional evidence matrix and each Proposed position expression card.
- Added an Operations → Research page presenting every (factor, symbol) pair honestly (significant highlighted, non-significant explicitly labeled rather than implying zero effect), and widened `strategy_versions.verification_status` to a full honest vocabulary (`registered_only`, `verified`, `not_significant`, `collinear`, `decayed`, `outdated`) — none of them disable the underlying naive-v1 function, which keeps running regardless. The Strategy registry list page now shows `code_reference`, `verification_status`, `next_review_at`, and a real `last_checked_at`; running significance research now auto-writes a real diagnostic onto `macro_regime_composite` without overclaiming the composite itself is verified.

### Product design and privacy

- Removed the external shared-conversation reference from the archived Edition V1; the project-owned edition now stands on its own as the design record.
- Clarified the broad-first decision path: sleeve allocation, point-in-time universe, cross-sectional discovery, independent single-name timing, portfolio target, and downstream instrument expression.
- Recorded DIA and IBIT only as configurable universe candidates with distinct sleeve and overlap controls, not as recommendations or hard-coded seed additions.
- Separated underlying research references from effective-dated execution instruments: BTC may inform a digital-asset target, while IBIT can be evaluated only during its actual availability and must never receive fabricated pre-listing history or trades.
- Added a concise capability roadmap that states each demo-to-real gap, its completion evidence, and the application surface it unlocks.
- Added an Operations readiness map whose ordered gates, dependencies, acceptance criteria, evidence, and next action come from the database; current state is derived from canonical records, and synthetic fixtures cannot qualify.

### Operations and data readiness

- Added a database-driven onboarding roadmap that distinguishes four planned provider accounts from five data-capability groups and shows the registration timing, official links, licensing cautions, and next action in the Credentials UI.
- Established the current provider plan: FRED/ALFRED for the first regime slice, followed later by Intrinio, Benzinga, and Trading Economics for the complete desk. Planned providers cannot accept credentials before their adapters exist.
- Changed FRED smoke-test health validity from seven days to 365 days while retaining the separate 15-minute repeat-call cooldown and immutable historical verification records.
- Kept provider access distinct from adapter integration and operational data: a healthy FRED key does not imply that ingestion is implemented or a dataset is ready.

### Engine — free-data pilot mode, all six compute stages real

- Implemented real `fetch_data`, `validate_data`, `regime_filter`, `factor_engine`, `allocation_engine`, and `instrument_engine` pipeline stages. Only `publish_snapshot` remains scaffolded. Every value traces to a fetched observation or a function over one; nothing is a hand-typed placeholder.
- Added a database-driven staging symbol table (TLT, IEF, SPY, QQQ, DIA, GLD, BTC-USD, all 11 sector SPDRs, AAPL, NVDA, SMH, IGV — 21 tradeable symbols plus the 8 FRED macro series), auto-seeded on every fresh clone so the free-data pilot runs with zero configuration.
- `regime_filter`: 8-factor macro model (growth, inflation, PPI, core PCE, employment, liquidity, volatility, rates) against live FRED/ALFRED data.
- `factor_engine`: real cross-sectional momentum ranking (blended 1M/3M/6M z-score, Yahoo 10-year price history) and an independent, real per-symbol MACD(12,26,9)/RSI(14) backtest with a full trade log, Sharpe ratio, win rate, and max drawdown — plus a desk-level equal-weighted aggregate across every backtested symbol.
- `allocation_engine`: a real risk envelope — regime confidence scales gross exposure, cross-sectional composites roll up into sleeve targets — persisted as a real decision graph (desk → risk envelope → sleeves).
- `instrument_engine`: a full -5..+5 conviction scale mapped to concrete instrument expressions (equity tilt, credit spread, debit spread, LEAPS long call/put), priced with a real Black-Scholes engine fed by real spot price, real realized volatility, and the real 10-year Treasury rate. Every options candidate is honestly labeled theoretical-pricing-only (no free options-chain quotes exist) and carries a required, unresolved blocker so it cannot pass as executable.
- Added a real, gated engine operating mode (pilot/production; Operations → Credentials): pilot blocks any stage requiring a paid-tier provider and stamps every snapshot it produces with the active mode.
- Moved the staging position-sizing default ($1M notional, 2% max risk per position) from a Python constant into a seeded `staging_budget_config` database row, matching the `staging_symbols` pattern — a fresh clone and every running instance see the same inspectable, editable default instead of one buried in source.
- Frontend: chart timeframe selector (1M/3M/6M/1Y/5Y/10Y/Max) with RSI and MACD panes alongside volume, a full backtest trade ledger table (independent of the chart's selected timeframe — the chart only draws markers inside the visible window; the table always shows full history), and market-time (US Eastern) timestamp display everywhere.
- See [docs/engine-milestones.md](docs/engine-milestones.md) for current status and [docs/editions/edition-v2.md](docs/editions/edition-v2.md) for the updated design record.

The next planned product slice is the point-in-time security master and versioned universe (roadmap phase 2), and a decision on `publish_snapshot`.

## 0.1.0 — Initial edition — 2026-08-24

Status: first substantive application edition; not tagged or released. The preserved design baseline is [Edition V1](docs/editions/edition-v1.md).

### Product and design

- Defined a hierarchical trade desk that converts macro regime evidence into risk budget, cross-sectional allocation, symbol expression, and portfolio constraints.
- Made the decision path inspectable from the Today desk down to symbol signals, events, chart context, metrics, and position candidates.
- Separated research evidence, simulation readiness, and any future live-execution gate instead of treating a persuasive strategy narrative as approval.
- Placed lower-frequency controls under Operations so daily decision surfaces remain primary.
- Established a manual-first operating model: observe and reproduce every stage before introducing scheduling.
- Adopted lightweight institutional discipline through explicit strategy revisions, evidence, promotion, monitoring, and retirement without turning documents into the runtime product.

### Application

- Added database-driven desk, hierarchy, cross-sectional, data-health, symbol research, and strategy lifecycle views.
- Added explicit current signal state and distinct signal, pattern, and execution markers on symbol charts.
- Added an honest empty state and an opt-in synthetic demonstration dataset with both simulation-ready and blocked examples.
- Added a lower-frequency Operations area for provider readiness, data inventory, manual pipeline runs, and strategy/research records.

### Data and operations

- Added point-in-time dataset snapshots, decision provenance, stable identifiers, honest null handling, and immutable sealed demo snapshots.
- Added operating-system keychain credential storage, read-only environment fallback, and a cached FRED v2 health check; secret values never enter the application database.
- Added database-indexed research runs and fingerprinted artifact manifests. Generated reports are optional exports, while database records remain canonical.
- Added concise architecture, operations, strategy lifecycle, reproducibility, and project-checkpoint documentation.

### Correctness and security

- Excluded runtime databases, provider secrets, local configuration, raw data, caches, and bulk artifacts from version control.
- Restricted operator APIs to loopback; mutations additionally validate the local origin and an action-specific request header.
- Sanitized provider failures before display and prevented credential values from being returned, logged, or persisted in SQLite.
- Made verification health fail closed after rotation, expiry, restart-sensitive environment changes, or invalid future timestamps.
- Required published desk snapshots to reference sealed datasets with consistent live, demonstration, and classification provenance.
