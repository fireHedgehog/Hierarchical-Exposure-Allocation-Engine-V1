import { BookMarked, CircleSlash } from "lucide-react";
import { Link } from "react-router-dom";
import { OperatorPageHeader } from "../components/OperatorPageHeader";
import { Panel, SectionHeading, StatusPill } from "../components/Ui";

interface Layer {
  key: string;
  name: string;
  implemented: boolean;
  codeReference: string | null;
  strategyKey?: string;
  summary: string;
  topParameter: string | null;
  literature: string[] | null;
  granularityNote: string | null;
}

// Deliberately thin: the top-level parameter and where the real
// implementation lives, not a hand-maintained step-by-step derivation.
// Deeper structural truth (versions, parameters_json, sub-components,
// diagnostics) lives in the database and renders live on each strategy's
// Registry record -- duplicating it here in static text is exactly what
// went stale before (this page still pointed at backtest.py after
// backtest_v2.py shipped). One line, one code reference, one link out.
const LAYERS: Layer[] = [
  {
    key: "macro_regime",
    name: "Macro regime composite",
    implemented: true,
    codeReference: "backend/engine/regime/scoring_v3.py",
    strategyKey: "macro_regime_composite",
    summary: "13 real FRED series -> a regime label and a real, calibrated confidence. Each factor scores as a real z-score against its own trailing history; factors are grouped into 3 real, evidence-based clusters (not weighted individually) so correlated factors can't outvote a smaller, independent group.",
    topParameter: "composite = mean(cluster_mean for cluster in {growth_inflation (6 factors), rate_level (3), market_stress (4)}). confidence = a real historical P(SPY drawdown >= 10% within 6mo), by which real tercile today's score falls into -- 34.5% stressed / 23.8% middle / 7.1% calm, out-of-sample validated 2004-2026. This is a risk-context read, not a timing signal -- it does not say when, and nothing here executes a trade.",
    literature: [
      "Andersen, Bollerslev, Diebold & Vega (2003). Micro effects of macro announcements. American Economic Review, 93(1), 38-62.",
      "Muth (1961). Rational expectations and the theory of price movements. Econometrica, 29(3), 315-335.",
    ],
    granularityNote: "A 4th real cluster (policy operations: Fed balance sheet, TGA, IORB/SOFR) is deliberately excluded -- its sign is genuinely ambiguous (balance-sheet expansion can mean either crisis liquidity injection or accommodative ease, context-dependent), a disclosed gap, not guessed. Liquidity and Guidance (from the separate Fed-reaction-function research track) aren't part of this composite at all. Full research arc: docs/hypotheses/macro-research/ in the repo.",
  },
  {
    key: "cross_sectional_momentum",
    name: "Cross-sectional momentum",
    implemented: true,
    codeReference: "backend/engine/factors/momentum_v3.py",
    strategyKey: "cross_sectional_momentum",
    summary: "Real prices -> a blended 1M/3M/6M/12-1 momentum score, ranked against peers. Horizon weights come from a real per-run significance test, not a fixed split.",
    topParameter: "blend = sum(w_h * r_h) for h in {1m,3m,6m,12m_skip1m}; w from pooled Pearson IC test, Benjamini-Hochberg corrected -- see Registry record.",
    literature: [
      "Jegadeesh & Titman (1993). Returns to buying winners and selling losers. The Journal of Finance, 48(1), 65-91.",
    ],
    granularityNote: "Momentum is currently the only registered cross-sectional signal. Sector/industry relative strength, value, quality, and low-volatility factors are not implemented.",
  },
  {
    key: "single_name_timing",
    name: "Single-name timing",
    implemented: true,
    codeReference: "backend/engine/timing/backtest_v3.py",
    strategyKey: "macd_rsi_single_name_timing",
    summary: "Real closes -> a real trade log. Split into two independently retireable components, not one fused function -- see the Registry record's Ensemble components panel for which are currently active.",
    topParameter: "entry: trailing 5-day return < -3% (short-term reversal). exit: RSI(14) >= 70 -- each condition owned by its own component (short_term_reversal_entry, rsi_overbought_exit). MACD's own entry trigger was retired (no real edge found, see docs/hypotheses/) and replaced by this cost-checked reversal rule.",
    literature: [
      "Jegadeesh (1990). Evidence of predictable behavior of security returns. The Journal of Finance, 45(3), 881-898.",
      "Wilder (1978). New concepts in technical trading systems. Trend Research.",
    ],
    granularityNote: null,
  },
  {
    key: "portfolio_construction",
    name: "Risk envelope allocation",
    implemented: true,
    codeReference: "backend/engine/allocation/envelope.py",
    strategyKey: "risk_envelope_allocation",
    summary: "Regime confidence -> one gross-exposure multiplier -> sleeve targets.",
    topParameter: "multiplier = clamp(confidence * 2, 0.5, 1.5); every sleeve gets the same multiplier -- no covariance-aware sizing yet.",
    literature: null,
    granularityNote: null,
  },
  {
    key: "instrument_expression",
    name: "Conviction-scaled instrument selection",
    implemented: true,
    codeReference: "backend/engine/instruments/",
    strategyKey: "conviction_instrument_selection",
    summary: "Conviction -> a structure choice -> a real Black-Scholes price -> a bounded position size.",
    topParameter: "structure by |conviction|: <2.5 equity tilt, 2.5-3.4 credit spread, 3.5-4.4 debit spread, >=4.5 LEAPS. Priced with real spot/realized-vol/DGS10 inputs.",
    literature: [
      "Black & Scholes (1973). The pricing of options and corporate liabilities. Journal of Political Economy, 81(3), 637-654.",
    ],
    granularityNote: null,
  },
  {
    key: "significance_research",
    name: "Factor significance research",
    implemented: true,
    codeReference: "backend/engine/research/",
    summary: "Milestone 4, step 1: does a factor's real change actually correlate with a symbol's real forward return? A validation tool, not a strategy itself.",
    topParameter: "r, p = pearsonr(x, y); adjusted_p = Benjamini-Hochberg(all p-values); significant = adjusted_p <= 0.05.",
    literature: [
      "Pearson (1895). Note on regression and inheritance. Proceedings of the Royal Society of London, 58, 240-242.",
      "Benjamini & Hochberg (1995). Controlling the false discovery rate. JRSS Series B, 57(1), 289-300.",
    ],
    granularityNote: null,
  },
  {
    key: "sentiment_text_mining",
    name: "Sentiment / text mining",
    implemented: false,
    codeReference: null,
    strategyKey: "sentiment_text_mining",
    summary: "Social/news-derived sentiment. Not started -- no free or paid text/social data source is connected (see roadmap.md).",
    topParameter: null,
    literature: null,
    granularityNote: "When work begins: define named sub-signal granularity first, matching the split already used for macro (8 factors) and timing (macd_crossover, rsi_overbought_exit) -- e.g. per-source or per-entity signals, each its own strategy_components row -- before writing one fused function.",
  },
  {
    key: "fundamental_analysis",
    name: "Fundamental analysis (EPS / earnings)",
    implemented: false,
    codeReference: null,
    strategyKey: "fundamental_analysis",
    summary: "Company fundamentals -- EPS, earnings surprises, estimate revisions. Not started -- Intrinio/Benzinga are planned providers, not yet registered or adapted (see roadmap.md).",
    topParameter: null,
    literature: null,
    granularityNote: "When work begins: define named sub-signal granularity first (e.g. EPS surprise, revenue surprise, estimate revision as separate strategy_components rows) before writing one fused function.",
  },
];

export function MethodologyPage() {
  const implementedCount = LAYERS.filter((layer) => layer.implemented).length;
  return (
    <div className="workspace operator-page methodology-page">
      <OperatorPageHeader
        title="Methodology"
        description={`Every named desk, top to bottom -- ${implementedCount} of ${LAYERS.length} real, the rest explicitly null. A fast map, not a derivation: each card names its top-level parameter and where the real implementation lives; deeper structural detail (versions, sub-components, diagnostics) lives in the database -- see the Registry record link on each card.`}
      />

      <Panel>
        <SectionHeading
          eyebrow="Staging, not production"
          title="What this page is and isn't"
          description={
            <>
              This is a proof-of-concept staging desk, not a production trading platform. Every implemented card is a
              real function over real data; the top-level parameter line names exactly what's hand-picked so a future
              contributor knows where to plug in a better weight without guessing. Updated on request at milestones,
              not automatically -- check git history/blame on this file for when it was last actually reviewed
              against the code. See <Link to="/operations/strategies">Strategies</Link> for the live, DB-driven
              registry this page only summarizes.
            </>
          }
        />
      </Panel>

      <div className="methodology-grid">
        {LAYERS.map((layer) => (
          <LayerCard key={layer.key} layer={layer} />
        ))}
      </div>
    </div>
  );
}

function LayerCard({ layer }: { layer: Layer }) {
  return (
    <Panel className="methodology-card">
      <div className="methodology-card__header">
        <div>
          <h3>{layer.name}</h3>
          {layer.codeReference ? <code>{layer.codeReference}</code> : <span className="strategy-no-spec">No implementation yet</span>}
        </div>
        <div className="methodology-card__header-right">
          <StatusPill value={layer.implemented ? "implemented" : "not_implemented"} />
          {layer.strategyKey ? (
            <Link className="button button--quiet" to={`/operations/strategies/${encodeURIComponent(layer.strategyKey)}`}>
              Registry record
            </Link>
          ) : null}
        </div>
      </div>
      <p className="methodology-card__summary">{layer.summary}</p>

      {layer.topParameter ? (
        <div className="methodology-card__note">
          <code>{layer.topParameter}</code>
        </div>
      ) : null}

      {layer.granularityNote ? (
        <div className="methodology-card__note methodology-card__note--null">
          <CircleSlash aria-hidden="true" size={14} />
          <span>{layer.granularityNote}</span>
        </div>
      ) : null}

      {layer.literature ? (
        <div className="methodology-card__literature">
          <BookMarked aria-hidden="true" size={14} />
          <ul>
            {layer.literature.map((citation) => (
              <li key={citation}>{citation}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </Panel>
  );
}
