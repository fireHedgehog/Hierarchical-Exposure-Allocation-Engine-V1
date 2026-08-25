import { AlertTriangle, ExternalLink, FlaskConical, Minus } from "lucide-react";
import type { ReactNode } from "react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  endpoints,
  operatorErrorMessage,
  runFactorSignificanceResearch,
  runSignalValidationResearch,
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
} from "../types";
import { formatNumber, formatTimestamp, NOT_AVAILABLE, toneForDirection } from "../utils/format";

// One section per strategy family, grouped by what the research is ABOUT --
// not by which statistical method produced it. Each section links to that
// strategy's Registry record, and the Registry record links back (see
// StrategyDetailPage's "View research" action) -- a real click-through both
// directions, not two pages that happen to describe the same thing.

export function ResearchPage() {
  return (
    <div className="workspace operator-page">
      <OperatorPageHeader
        title="Research"
        description="Real statistical evidence behind the desk's factors, one section per strategy. Every number here is either a real result from a real run or an honest 'not run yet' -- never a placeholder."
      />

      <StrategyResearchSection strategyKey="macro_regime_composite" anchorId="macro-regime" title="Macro regime factors">
        <FactorSignificanceSubsection />
        <SignalValidationSection
          strategyKey="macro_regime_composite"
          title="Diversification"
          description="Number of factors != number of independent bets. PCA on the 8 macro factors' real pairwise correlation matrix, over the same sealed dataset."
        />
      </StrategyResearchSection>

      <StrategyResearchSection strategyKey="cross_sectional_momentum" anchorId="cross-sectional-momentum" title="Cross-sectional momentum factors">
        <SignalValidationSection
          strategyKey="cross_sectional_momentum"
          title="Diversification"
          description="Are the momentum horizons independent views, or mostly one restated several ways? Same method as macro, applied to this strategy's own components."
        />
      </StrategyResearchSection>

      <div id="metric-catalog">
        <MetricCatalogSection />
      </div>
    </div>
  );
}

function StrategyResearchSection({
  strategyKey,
  anchorId,
  title,
  children,
}: {
  strategyKey: string;
  anchorId: string;
  title: string;
  children: ReactNode;
}) {
  return (
    <section id={anchorId} className="research-strategy-section">
      <div className="research-strategy-section__header">
        <h2>{title}</h2>
        <Link className="button button--quiet" to={`/operations/strategies/${encodeURIComponent(strategyKey)}`}>
          Registry record <ExternalLink aria-hidden="true" size={13} />
        </Link>
      </div>
      {children}
    </section>
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
        eyebrow="Component level — one factor vs. one symbol's forward return"
        title="Factor significance"
        description="Real Pearson correlation and a real p-value between every macro factor and every staging symbol's forward return, corrected for multiple comparisons."
        action={(
          <button className="button operator-run-button" type="button" onClick={startRun} disabled={running}>
            <FlaskConical aria-hidden="true" size={16} /> {running ? "Running…" : "Run"}
          </button>
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
        eyebrow="Ensemble level — relationships among this strategy's own factors"
        title={title}
        description={description}
        action={(
          <button className="button operator-run-button" type="button" onClick={startRun} disabled={running}>
            <FlaskConical aria-hidden="true" size={16} /> {running ? "Running…" : "Run"}
          </button>
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

const GRANULARITY_ORDER = ["component", "ensemble", "strategy", "desk"] as const;
const GRANULARITY_LABELS: Record<string, string> = {
  component: "Component — one factor alone",
  ensemble: "Ensemble — relationships among a strategy's own factors",
  strategy: "Strategy — one strategy's realized, combined output (fittable by an optimizer)",
  desk: "Desk — cross-strategy, whole portfolio",
};

function MetricCatalogSection() {
  const state = useApi<ResearchMetricCatalogResponse>(endpoints.adminResearchMetricCatalog);
  const metrics = state.data?.metrics ?? [];
  const byLevel = useMemo(() => groupByGranularity(metrics), [metrics]);

  return (
    <Panel>
      <SectionHeading
        eyebrow="Every strategy, the full taxonomy, by level"
        title="Research metric catalog"
        description="Metric granularity matches factor granularity: component metrics evaluate one factor alone, ensemble metrics evaluate relationships among a strategy's own factors, strategy metrics evaluate one strategy's realized output, desk metrics evaluate cross-strategy portfolio construction. A metric having no data yet is an honest 'not run', not an oversight."
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
