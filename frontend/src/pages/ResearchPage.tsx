import { AlertTriangle, ExternalLink, FlaskConical, Minus } from "lucide-react";
import type { ReactNode } from "react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  endpoints,
  operatorErrorMessage,
  runFactorSignificanceResearch,
  runSignalValidationResearch,
  runStrategyBacktestResearch,
  useApi,
} from "../api/client";
import { OperatorPageHeader } from "../components/OperatorPageHeader";
import { Panel, ResourceState, SectionHeading, StatusPill, Unavailable } from "../components/Ui";
import type {
  FactorSignificanceResult,
  FactorSignificanceRun,
  FactorSignificanceRunResponse,
  ResearchCatalogMetric,
  ResearchMetricCatalogResponse,
  SignalValidationRunResponse,
  StrategyBacktestRunResponse,
} from "../types";
import { formatNumber, formatScalar, formatTimestamp, NOT_AVAILABLE, toneForDirection } from "../utils/format";

// Sectioned by granularity first -- component, ensemble, strategy, desk --
// the same four-level taxonomy the metric catalog uses. Strategy is the
// secondary label inside each level, not the primary structure: a viewer's
// first question is "what am I looking at" (one factor? relationships
// between factors? a realized backtest?), and only then "which strategy."

const GRANULARITY_ORDER = ["component", "ensemble", "strategy", "desk"] as const;
const GRANULARITY_LABELS: Record<string, string> = {
  component: "Component — one factor alone",
  ensemble: "Ensemble — relationships among a strategy's own factors",
  strategy: "Strategy — one strategy's realized, combined output (fittable by an optimizer)",
  desk: "Desk — cross-strategy, whole portfolio",
};

export function ResearchPage() {
  return (
    <div className="workspace operator-page">
      <OperatorPageHeader
        title="Research"
        description="Real statistical evidence behind the desk's factors, sectioned by what's being tested -- one factor alone, relationships among a strategy's factors, a strategy's realized output, or the whole portfolio. Every number is either a real result from a real run or an honest 'not run yet'."
      />

      <GranularitySection level="component" description="Tests one factor by itself, in isolation from every other factor.">
        <FactorSignificanceSubsection />
      </GranularitySection>

      <GranularitySection level="ensemble" description="Tests relationships among a strategy's own factors -- correlation, redundancy, how many genuinely independent bets they add up to.">
        <SignalValidationSection
          strategyKey="macro_regime_composite"
          title="Macro regime factors"
          description="Number of factors != number of independent bets. The current exact-runtime audit covers 13 transformed macro contributions; production research should compare the contributions actually consumed by the score, not raw FRED levels."
        />
        <SignalValidationSection
          strategyKey="cross_sectional_momentum"
          title="Cross-sectional momentum factors"
          description="Same method applied to the momentum horizons: are they independent views, or mostly one restated several ways?"
        />
      </GranularitySection>

      <GranularitySection level="strategy" description="Tests one strategy's own realized, combined output -- CAGR, Sharpe, drawdown -- the tier an optimizer could actually fit.">
        <StrategyBacktestSection
          strategyKey="cross_sectional_momentum"
          title="Cross-sectional momentum"
          description="Current-version walk-forward: rank the universe with the registered production version, buy the top symbols equal-weighted, hold to the next rebalance, and chain exact-date returns into an equity curve."
        />
      </GranularitySection>

      <GranularitySection level="desk" description="Tests cross-strategy, whole-portfolio construction -- exposure limits, neutralization, concentration.">
        <Panel>
          <Unavailable title="Not built yet" detail="No multi-strategy portfolio layer exists yet to test." />
        </Panel>
      </GranularitySection>

      <div id="metric-catalog">
        <MetricCatalogSection />
      </div>
    </div>
  );
}

function GranularitySection({
  level,
  description,
  children,
}: {
  level: (typeof GRANULARITY_ORDER)[number];
  description: string;
  children: ReactNode;
}) {
  return (
    <section id={level} className="research-strategy-section">
      <div className="research-strategy-section__header">
        <h2>{GRANULARITY_LABELS[level]}</h2>
      </div>
      <p className="methodology-card__summary" style={{ marginBottom: 12 }}>{description}</p>
      {children}
    </section>
  );
}

function RegistryLink({ strategyKey }: { strategyKey: string }) {
  return (
    <Link className="button button--quiet" to={`/operations/strategies/${encodeURIComponent(strategyKey)}`}>
      Registry record <ExternalLink aria-hidden="true" size={13} />
    </Link>
  );
}

function FactorSignificanceSubsection() {
  const state = useApi<FactorSignificanceRunResponse>(endpoints.adminFactorSignificanceLatest);
  const [running, setRunning] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const run = state.data?.run;

  const startRun = async () => {
    setRunning(true);
    setActionError(null);
    try {
      await runFactorSignificanceResearch<FactorSignificanceRunResponse>();
      state.reload();
    } catch (error) {
      setActionError(operatorErrorMessage(error, "The factor-significance research request failed."));
    } finally {
      setRunning(false);
    }
  };

  return (
    <Panel>
      <SectionHeading
        eyebrow="Macro regime factors"
        title="Factor significance"
        description="Real Pearson correlation and a real p-value between every macro factor and every staging symbol's forward return, corrected for multiple comparisons."
        action={(
          <div style={{ display: "flex", gap: 8 }}>
            <RegistryLink strategyKey="macro_regime_composite" />
            <button className="button operator-run-button" type="button" onClick={startRun} disabled={running}>
              <FlaskConical aria-hidden="true" size={16} /> {running ? "Running…" : "Run"}
            </button>
          </div>
        )}
      />
      {actionError ? <div className="operator-action-message operator-action-message--error" role="alert"><AlertTriangle aria-hidden="true" size={16} />{actionError}</div> : null}
      <ResourceState loading={state.loading} error={state.error} onRetry={state.reload} resource="factor-significance research run" />
      {run ? (
        <>
          <RunSummaryPanel run={run} />
          <ResultsPanel run={run} />
        </>
      ) : !state.loading && !state.error ? (
        <Unavailable compact title="No research run recorded yet" detail="Run significance research against the latest sealed dataset." />
      ) : null}
    </Panel>
  );
}

function SignalValidationSection({
  strategyKey,
  title,
  description,
}: {
  strategyKey: "macro_regime_composite" | "cross_sectional_momentum";
  title: string;
  description: string;
}) {
  const state = useApi<SignalValidationRunResponse>(endpoints.adminSignalValidationLatest(strategyKey));
  const [running, setRunning] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const run = state.data?.run;

  const startRun = async () => {
    setRunning(true);
    setActionError(null);
    try {
      await runSignalValidationResearch<SignalValidationRunResponse>(strategyKey);
      state.reload();
    } catch (error) {
      setActionError(operatorErrorMessage(error, "The signal-validation research request failed."));
    } finally {
      setRunning(false);
    }
  };

  return (
    <Panel>
      <SectionHeading
        eyebrow={title}
        title="Diversification"
        description={description}
        action={(
          <div style={{ display: "flex", gap: 8 }}>
            <RegistryLink strategyKey={strategyKey} />
            <button className="button operator-run-button" type="button" onClick={startRun} disabled={running}>
              <FlaskConical aria-hidden="true" size={16} /> {running ? "Running…" : "Run"}
            </button>
          </div>
        )}
      />
      {actionError ? <div className="operator-action-message operator-action-message--error" role="alert"><AlertTriangle aria-hidden="true" size={16} />{actionError}</div> : null}
      {run ? (
        <>
          <dl className="strategy-identity-grid">
            <div><dt>Effective number of bets</dt><dd><strong>{run.effective_number_of_bets != null ? run.effective_number_of_bets.toFixed(2) : NOT_AVAILABLE}</strong> of {run.factor_count ?? NOT_AVAILABLE} factors</dd></div>
            <div><dt>Run at</dt><dd>{formatTimestamp(run.started_at)}</dd></div>
            <div><dt>Dataset snapshot</dt><dd><code>{run.dataset_snapshot_id || NOT_AVAILABLE}</code></dd></div>
          </dl>
          <p className="methodology-card__summary">{run.summary}</p>
          {run.factor_correlations?.length ? (
            <div className="operator-table-scroll">
              <table className="operator-table">
                <thead>
                  <tr><th>Factor A</th><th>Factor B</th><th>Correlation</th><th>Flag</th></tr>
                </thead>
                <tbody>
                  {run.factor_correlations.map((pair) => (
                    <tr key={`${pair.key_a}-${pair.key_b}`} className={correlationRowClass(pair.correlation)}>
                      <td><code>{pair.key_a}</code></td>
                      <td><code>{pair.key_b}</code></td>
                      <td>{pair.correlation.toFixed(3)}</td>
                      <td>{pair.flagged_redundant ? <StatusPill value="redundant" tone="negative" /> : <StatusPill value="ok" tone="positive" />}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </>
      ) : !state.loading ? (
        <Unavailable compact title="No signal-validation run recorded yet" detail="Run it against the latest sealed dataset." />
      ) : null}
    </Panel>
  );
}

function correlationRowClass(correlation: number): string {
  const magnitude = Math.abs(correlation);
  if (magnitude >= 0.7) return "factor-significance-row--negative";
  if (magnitude >= 0.3) return "factor-significance-row--caution";
  return "factor-significance-row--significant";
}

function StrategyBacktestSection({
  strategyKey,
  title,
  description,
}: {
  strategyKey: "cross_sectional_momentum";
  title: string;
  description: string;
}) {
  const state = useApi<StrategyBacktestRunResponse>(endpoints.adminStrategyBacktestLatest(strategyKey));
  const [running, setRunning] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const run = state.data?.run;

  const startRun = async () => {
    setRunning(true);
    setActionError(null);
    try {
      await runStrategyBacktestResearch<StrategyBacktestRunResponse>(strategyKey);
      state.reload();
    } catch (error) {
      setActionError(operatorErrorMessage(error, "The strategy-backtest research request failed."));
    } finally {
      setRunning(false);
    }
  };

  return (
    <Panel>
      <SectionHeading
        eyebrow={title}
        title="Walk-forward backtest"
        description={description}
        action={(
          <div style={{ display: "flex", gap: 8 }}>
            <RegistryLink strategyKey={strategyKey} />
            <button className="button operator-run-button" type="button" onClick={startRun} disabled={running}>
              <FlaskConical aria-hidden="true" size={16} /> {running ? "Running…" : "Run"}
            </button>
          </div>
        )}
      />
      {actionError ? <div className="operator-action-message operator-action-message--error" role="alert"><AlertTriangle aria-hidden="true" size={16} />{actionError}</div> : null}
      {run ? (
        <>
          {run.invalidated_reason ? <div className="operator-action-message operator-action-message--error" role="alert"><AlertTriangle aria-hidden="true" size={16} />Invalidated evidence: {run.invalidated_reason}</div> : null}
          <dl className="strategy-identity-grid">
            <div><dt>CAGR</dt><dd><strong>{formatScalar(run.cagr, "fraction")}</strong></dd></div>
            <div><dt>Sharpe ratio</dt><dd>{formatScalar(run.sharpe_ratio, "ratio")}</dd></div>
            <div><dt>Max drawdown</dt><dd>{formatScalar(run.max_drawdown, "fraction")}</dd></div>
            <div><dt>Calmar ratio</dt><dd>{formatScalar(run.calmar_ratio, "ratio")}</dd></div>
            <div><dt>Annualized volatility</dt><dd>{formatScalar(run.annualized_volatility, "fraction")}</dd></div>
            <div><dt>Turnover per rebalance</dt><dd>{formatScalar(run.portfolio_turnover, "fraction")}</dd></div>
            <div><dt>Run at</dt><dd>{formatTimestamp(run.started_at)}</dd></div>
            <div><dt>Dataset snapshot</dt><dd><code>{run.dataset_snapshot_id || NOT_AVAILABLE}</code></dd></div>
          </dl>
          <p className="methodology-card__summary">{run.summary}</p>
        </>
      ) : !state.loading ? (
        <Unavailable compact title="No strategy-backtest run recorded yet" detail="Run it against the latest sealed dataset." />
      ) : null}
    </Panel>
  );
}

function MetricCatalogSection() {
  const state = useApi<ResearchMetricCatalogResponse>(endpoints.adminResearchMetricCatalog);
  const metrics = state.data?.metrics ?? [];
  const byLevel = useMemo(() => groupByGranularity(metrics), [metrics]);

  return (
    <Panel>
      <SectionHeading
        eyebrow="Reference — every metric this program can compute"
        title="Research metric catalog"
        description="Same level order as the sections above. A metric having no data yet is an honest 'not run', not an oversight — not every factor needs every check, and null is allowed."
      />
      <ResourceState loading={state.loading} error={state.error} onRetry={state.reload} resource="metric catalog" />
      {GRANULARITY_ORDER.map((level) => {
        const levelMetrics = byLevel[level];
        if (!levelMetrics?.length) return null;
        const byCategory = groupByCategory(levelMetrics);
        return (
          <div key={level} style={{ marginBottom: 16 }}>
            <h3 style={{ margin: "0 0 8px", fontFamily: "Georgia, 'Times New Roman', serif", fontSize: 14, fontWeight: 500 }}>
              {GRANULARITY_LABELS[level] || level}
            </h3>
            {Object.entries(byCategory).map(([category, categoryMetrics]) => (
              <div key={category} className="methodology-card__note methodology-card__note--null" style={{ display: "block", marginBottom: 10 }}>
                <strong style={{ display: "block", marginBottom: 6, textTransform: "capitalize" }}>{category.replace(/_/g, " ")}</strong>
                <div className="operator-table-scroll">
                  <table className="operator-table">
                    <thead><tr><th>Metric</th><th>Unit</th><th>Status</th></tr></thead>
                    <tbody>
                      {categoryMetrics.map((metric) => (
                        <tr key={metric.metric_key} title={metric.description}>
                          <td>{metric.label}</td>
                          <td>{metric.unit || NOT_AVAILABLE}</td>
                          <td>{metric.has_data ? <StatusPill value="data available" tone="positive" /> : <Minus aria-hidden="true" size={14} className="strategy-no-spec" />}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ))}
          </div>
        );
      })}
    </Panel>
  );
}

function groupByGranularity(metrics: ResearchCatalogMetric[]): Record<string, ResearchCatalogMetric[]> {
  const grouped: Record<string, ResearchCatalogMetric[]> = {};
  for (const metric of metrics) {
    (grouped[metric.granularity] ||= []).push(metric);
  }
  return grouped;
}

function groupByCategory(metrics: ResearchCatalogMetric[]): Record<string, ResearchCatalogMetric[]> {
  const grouped: Record<string, ResearchCatalogMetric[]> = {};
  for (const metric of metrics) {
    (grouped[metric.category] ||= []).push(metric);
  }
  return grouped;
}

function RunSummaryPanel({ run }: { run: FactorSignificanceRun }) {
  return (
    <dl className="strategy-identity-grid">
      <div><dt>Method</dt><dd>{run.method} · {run.correction_method}</dd></div>
      <div><dt>Forward horizon</dt><dd>{run.forward_horizon_days} trading days</dd></div>
      <div><dt>Alpha</dt><dd>{run.alpha}</dd></div>
      <div><dt>Min samples</dt><dd>{formatNumber(run.min_samples)}</dd></div>
      <div><dt>Factors × symbols</dt><dd>{run.factor_count} × {run.symbol_count}</dd></div>
      <div><dt>Pairs tested</dt><dd>{formatNumber(run.test_count)} / {formatNumber(run.factor_count * run.symbol_count)}</dd></div>
      <div><dt>Significant after correction</dt><dd>{formatNumber(run.significant_count)}</dd></div>
      <div><dt>Run at</dt><dd>{formatTimestamp(run.started_at)}</dd></div>
      <div><dt>Dataset snapshot</dt><dd><code>{run.dataset_snapshot_id || NOT_AVAILABLE}</code></dd></div>
    </dl>
  );
}

function ResultsPanel({ run }: { run: FactorSignificanceRun }) {
  const results = run.results ?? [];
  const sorted = useMemo(() => sortResults(results), [results]);

  if (!results.length) {
    return <Unavailable compact title="No pair results are persisted for this run" />;
  }

  return (
    <>
      <p className="methodology-card__summary">{run.summary}</p>
      <div className="operator-table-scroll">
        <table className="operator-table factor-significance-table">
          <thead>
            <tr>
              <th>Factor</th>
              <th>Symbol</th>
              <th>Samples</th>
              <th>Correlation</th>
              <th>p-value</th>
              <th>Adjusted p-value</th>
              <th>Direction</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((result) => (
              <tr key={`${result.factor_key}-${result.symbol}`} className={result.significant ? "factor-significance-row--significant" : ""}>
                <td><code>{result.factor_key}</code></td>
                <td><code>{result.symbol}</code></td>
                <td>{formatNumber(result.sample_size)}</td>
                <td>{result.correlation !== null && result.correlation !== undefined ? result.correlation.toFixed(3) : NOT_AVAILABLE}</td>
                <td>{formatPValue(result.p_value)}</td>
                <td>{formatPValue(result.adjusted_p_value)}</td>
                <td><StatusPill value={directionLabel(result)} tone={toneForDirection(result.significant ? result.direction : "neutral")} /></td>
                <td><StatusPill value={result.status} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function sortResults(results: FactorSignificanceResult[]): FactorSignificanceResult[] {
  return [...results].sort((a, b) => {
    if (a.significant !== b.significant) return a.significant ? -1 : 1;
    const aAbs = Math.abs(a.correlation ?? 0);
    const bAbs = Math.abs(b.correlation ?? 0);
    if (aAbs !== bAbs) return bAbs - aAbs;
    return a.factor_key.localeCompare(b.factor_key) || a.symbol.localeCompare(b.symbol);
  });
}

function directionLabel(result: FactorSignificanceResult): string {
  if (result.status === "insufficient_data") return "insufficient_data";
  if (!result.significant) return "not_significant";
  return result.direction;
}

function formatPValue(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return NOT_AVAILABLE;
  if (value < 0.0001) return "< 0.0001";
  return value.toFixed(4);
}
