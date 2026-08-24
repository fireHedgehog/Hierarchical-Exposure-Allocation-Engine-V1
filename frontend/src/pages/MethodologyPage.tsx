import { ArrowRight, BookMarked, Wrench } from "lucide-react";
import { Link } from "react-router-dom";
import { OperatorPageHeader } from "../components/OperatorPageHeader";
import { Panel, SectionHeading } from "../components/Ui";

interface FlowStep {
  label: string;
  formula: string;
}

interface Layer {
  key: string;
  name: string;
  codeReference: string;
  strategyKey?: string;
  summary: string;
  steps: FlowStep[];
  literature: string[] | null;
  naiveParameters: string | null;
}

const LAYERS: Layer[] = [
  {
    key: "macro_regime",
    name: "Macro regime composite (naive-v2)",
    codeReference: "backend/engine/regime/scoring_v2.py",
    strategyKey: "macro_regime_composite",
    summary: "8 real FRED series -> a single regime label and confidence. naive-v2 scores each factor's real surprise against its own trailing statistical expectation, not a fixed hand-picked target -- markets price the beat/miss, not the level.",
    steps: [
      { label: "Real observations", formula: "INDPRO, CPIAUCSL, PPIACO, PCEPILFE,\nPAYEMS, NFCI, VIXCLS, DGS10\n(full real history, not just latest)" },
      { label: "Trailing expectation", formula: "expected = trailing mean of the series'\nown last N real points\n(N: 6 monthly, 12 weekly, 60 daily)" },
      { label: "Surprise", formula: "surprise = latest - expected\n(YoY surprise for monthly series,\nlevel surprise for NFCI/VIXCLS/DGS10)" },
      { label: "Per-factor score", formula: "clamp(sign * surprise / scale, -1, 1)" },
      { label: "Weighted sum", formula: "composite = sum(w_i * contribution_i)\nw: growth .15, inflation .15, ppi .10,\npce .15, employment .10, liquidity .15,\nvolatility .10, rates .10" },
      { label: "Confidence", formula: "clamp(0.5 + composite / 2, 0.05, 0.95)" },
      { label: "Label", formula: "risk-on >= +0.15, risk-off <= -0.15,\nelse mixed" },
    ],
    literature: [
      "Andersen, T. G., Bollerslev, T., Diebold, F. X., & Vega, C. (2003). Micro effects of macro announcements: Real-time price discovery in foreign exchange. American Economic Review, 93(1), 38-62.",
      "Balduzzi, P., Elton, E. J., & Green, T. C. (2001). Economic news and bond prices: Evidence from the U.S. Treasury market. Journal of Financial and Quantitative Analysis, 36(4), 523-543.",
      "Krueger, J. T., & Kuttner, K. N. (1996). The Fed funds futures rate as a predictor of Federal Reserve policy. Journal of Futures Markets, 16(8), 865-879.",
      "Muth, J. F. (1961). Rational expectations and the theory of price movements. Econometrica, 29(3), 315-335.",
    ],
    naiveParameters: "All 8 weights are unchanged from naive-v1 and still hand-picked, not fit. The expectation windows (6/12/60 periods) and surprise scales are also hand-picked. Critically: the 'expectation' is a trailing statistical mean, not a real market consensus -- no free consensus/survey feed exists yet (Trading Economics is the planned paid source). Milestone 4 tests each factor's real significance (see Operations -> Research) before any weight is trusted. naive-v1 (level-vs-fixed-target) stays in the codebase, untouched, for reproducing any snapshot already sealed under it.",
  },
  {
    key: "cross_sectional_momentum",
    name: "Cross-sectional momentum (naive-v2)",
    codeReference: "backend/engine/factors/momentum_v2.py",
    strategyKey: "cross_sectional_momentum",
    summary: "Real prices -> a blended momentum score, ranked against peers, rescaled to conviction. naive-v2 derives the horizon blend weights from a real per-run significance test instead of a fixed hand-picked split.",
    steps: [
      { label: "Real closes", formula: "Yahoo daily bars, 10y history" },
      { label: "Horizon returns", formula: "r_1m, r_3m, r_6m =\n(close_t - close_t-n) / close_t-n" },
      { label: "Pooled IC test", formula: "for each horizon: pool (r_horizon, r_21d-forward)\nacross every staging symbol's own history;\nPearson r + p-value, Benjamini-Hochberg corrected" },
      { label: "Horizon weight", formula: "significant horizons: w proportional to |r|\nelse: equal weight (1/3) fallback;\nfinal vector normalized to sum to 1" },
      { label: "Weighted blend", formula: "blend = w_1m*r_1m + w_3m*r_3m + w_6m*r_6m\n(weights computed fresh every run)" },
      { label: "Cross-sectional z-score", formula: "z = (blend - mean(universe)) / stdev(universe)" },
      { label: "Squash", formula: "composite_score = clamp(z / 2, -1, 1)" },
      { label: "Rescale", formula: "conviction = clamp(composite_score * 5, -5, 5)" },
    ],
    literature: [
      "Jegadeesh, N., & Titman, S. (1993). Returns to buying winners and selling losers: Implications for stock market efficiency. The Journal of Finance, 48(1), 65-91.",
      "Pearson, K. (1895). Note on regression and inheritance in the case of two parents. Proceedings of the Royal Society of London, 58, 240-242.",
      "Benjamini, Y., & Hochberg, Y. (1995). Controlling the false discovery rate: A practical and powerful approach to multiple testing. Journal of the Royal Statistical Society, Series B, 57(1), 289-300.",
    ],
    naiveParameters: "The IC test itself is real and re-run every pipeline run against that run's own fetched history (see Operations -> Research for the same method applied to macro factors) -- but it is one narrow test, not the full Milestone 4 gate: no decorrelation across the three horizons and no fitted (vs. |r|-proportional or equal) weight has run yet. The z-score divisor (2) and x5 rescale are still hand-picked. naive-v1 (fixed 0.2/0.3/0.5) stays in the codebase, untouched, for reproducing any snapshot already sealed under it.",
  },
  {
    key: "single_name_timing",
    name: "MACD / RSI single-name timing",
    codeReference: "backend/engine/timing/backtest.py",
    strategyKey: "macd_rsi_single_name_timing",
    summary: "Real closes -> a real trade log (entry/exit dates, prices, reasons).",
    steps: [
      { label: "Real closes", formula: "Yahoo daily bars" },
      { label: "MACD", formula: "MACD = EMA(12) - EMA(26)\nsignal = EMA(9) of MACD" },
      { label: "RSI(14)", formula: "RSI = 100 - 100 / (1 + avg_gain/avg_loss)\n(Wilder smoothing)" },
      { label: "Entry rule", formula: "MACD crosses above signal" },
      { label: "Exit rule", formula: "MACD crosses below signal\nOR RSI >= 70" },
    ],
    literature: [
      "Appel, G. (2005). Technical analysis: Power tools for active investors. FT Press.",
      "Wilder, J. W. (1978). New concepts in technical trading systems. Trend Research.",
    ],
    naiveParameters: "MACD(12,26,9), RSI(14), and the 70 overbought threshold are the standard textbook defaults, not fit to this universe. The desk-level aggregate backtest currently loses to buy-and-hold on average -- an honest, expected result at this milestone.",
  },
  {
    key: "portfolio_construction",
    name: "Risk envelope allocation",
    codeReference: "backend/engine/allocation/envelope.py",
    strategyKey: "risk_envelope_allocation",
    summary: "Regime confidence -> one gross-exposure multiplier -> sleeve targets.",
    steps: [
      { label: "Regime confidence", formula: "real output of the regime composite" },
      { label: "Multiplier", formula: "clamp(confidence * 2, 0.5, 1.5)" },
      { label: "Target gross", formula: "current_gross * multiplier" },
      { label: "Sleeve targets", formula: "sum(per-symbol tilts) * multiplier,\ngrouped by category" },
    ],
    literature: null,
    naiveParameters: "The 0.5x-1.5x band and the confidence-to-multiplier scale (x2) are hand-picked. Every sleeve gets the same multiplier -- no covariance-aware or symbol-specific sizing yet.",
  },
  {
    key: "instrument_expression",
    name: "Conviction-scaled instrument selection",
    codeReference: "backend/engine/instruments/",
    strategyKey: "conviction_instrument_selection",
    summary: "Conviction -> a structure choice -> a real Black-Scholes price -> a bounded position size.",
    steps: [
      { label: "Conviction", formula: "clamp(composite_score * 5, -5, 5)" },
      { label: "Structure by |conviction|", formula: "<2.5 equity tilt\n2.5-3.4 credit spread\n3.5-4.4 debit spread\n>=4.5 LEAPS" },
      { label: "Black-Scholes-Merton price", formula: "real spot, 60d realized volatility,\nreal DGS10 rate as risk-free rate" },
      { label: "Position size", formula: "risk_budget = notional * risk_fraction\n* (|conviction| / 5)\nqty = floor(risk_budget / max_loss)" },
    ],
    literature: [
      "Black, F., & Scholes, M. (1973). The pricing of options and corporate liabilities. Journal of Political Economy, 81(3), 637-654.",
      "Merton, R. C. (1973). Theory of rational option pricing. The Bell Journal of Economics and Management Science, 4(1), 141-183.",
    ],
    naiveParameters: "The 2.5/3.5/4.5 structure breakpoints and each structure's fixed %-OTM strikes/DTE are hand-picked. Realized volatility stands in for market-implied volatility -- there is no free options-chain source, so every candidate is labeled theoretical-pricing-only.",
  },
  {
    key: "significance_research",
    name: "Factor significance research",
    codeReference: "backend/engine/research/",
    summary: "Milestone 4, step 1: does a factor's real change actually correlate with a symbol's real forward return?",
    steps: [
      { label: "Paired real samples", formula: "factor change_i, symbol forward_return_i\n(same date alignment, real data only)" },
      { label: "Correlation + p-value", formula: "r, p = scipy.stats.pearsonr(x, y)" },
      { label: "Multiple-comparisons correction", formula: "adjusted_p = Benjamini-Hochberg(all p-values)" },
      { label: "Significant?", formula: "significant = adjusted_p <= alpha (0.05)" },
    ],
    literature: [
      "Pearson, K. (1895). Note on regression and inheritance in the case of two parents. Proceedings of the Royal Society of London, 58, 240-242.",
      "Benjamini, Y., & Hochberg, Y. (1995). Controlling the false discovery rate: A practical and powerful approach to multiple testing. Journal of the Royal Statistical Society: Series B, 57(1), 289-300.",
    ],
    naiveParameters: null,
  },
];

export function MethodologyPage() {
  return (
    <div className="workspace operator-page methodology-page">
      <OperatorPageHeader
        title="Methodology"
        description="How the engine actually computes its numbers, layer by layer -- a fast map of the real math, not the thousands of lines behind it. Read backend/engine-milestones.md for status and Operations -> Strategies for the live registry."
      />

      <Panel>
        <SectionHeading
          eyebrow="Staging, not production"
          title="What this page is and isn't"
          description={
            <>
              This is a proof-of-concept staging desk, not a production trading platform (see{" "}
              <Link to="/operations/strategies">Strategies</Link> for verification status per layer). Every step below
              is a real function over real data; the "Naive parameters" line on each card names exactly what's
              hand-picked rather than fit, so a future contributor knows precisely where to plug in a better
              activation, a different scaling function, or a fitted weight instead of guessing. Updated on request at
              milestones, not continuously or automatically — each update means re-reading the actual code and
              database fresh, not patching old text. Check git history/blame on this file for when it was last
              actually reviewed against the code; this page describes the system's current state, not its history.
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
          <code>{layer.codeReference}</code>
        </div>
        {layer.strategyKey ? (
          <Link className="button button--quiet" to={`/operations/strategies/${encodeURIComponent(layer.strategyKey)}`}>
            Registry record
          </Link>
        ) : null}
      </div>
      <p className="methodology-card__summary">{layer.summary}</p>

      <div className="methodology-flow" role="list" aria-label={`${layer.name} computation steps`}>
        {layer.steps.map((step, index) => (
          <div className="methodology-flow__step" role="listitem" key={step.label}>
            <div className="methodology-flow__box">
              <span>{step.label}</span>
              <code>{step.formula}</code>
            </div>
            {index < layer.steps.length - 1 ? <ArrowRight aria-hidden="true" size={16} className="methodology-flow__arrow" /> : null}
          </div>
        ))}
      </div>

      {layer.naiveParameters ? (
        <div className="methodology-card__note">
          <Wrench aria-hidden="true" size={14} />
          <span><strong>Naive parameters (future swap-out candidates):</strong> {layer.naiveParameters}</span>
        </div>
      ) : null}

      <div className="methodology-card__literature">
        <BookMarked aria-hidden="true" size={14} />
        {layer.literature ? (
          <ul>
            {layer.literature.map((citation) => (
              <li key={citation}>{citation}</li>
            ))}
          </ul>
        ) : (
          <span>No published literature basis -- a disclosed, naive, hand-built formula, not adapted from a specific source.</span>
        )}
      </div>
    </Panel>
  );
}
