import { AlertTriangle, FlaskConical, Minus, RefreshCw } from "lucide-react";
import { useMemo, useState } from "react";
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
  SignalValidationRun,
  SignalValidationRunResponse,
} from "../types";
import { formatNumber, formatTimestamp, NOT_AVAILABLE, toneForDirection } from "../utils/format";

export function FactorSignificancePage() {
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
    <div className="workspace operator-page">
      <OperatorPageHeader
        title="Factor significance"
        description="Milestone 4, step 1 (docs/engine-milestones.md): real Pearson correlation and a real p-value between every macro factor and every staging symbol's forward return, corrected for multiple comparisons. Staging-tier proof of concept — the full validation program (PCA/decorrelation, decay, fitted weights) is not run here."
        action={(
          <button className="button operator-run-button" type="button" onClick={startRun} disabled={running}>
            <FlaskConical aria-hidden="true" size={16} /> {running ? "Running…" : "Run significance research"}
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
        <Unavailable
          title="No research run recorded yet"
          detail="Run significance research against the latest sealed dataset to populate this page."
        />
      ) : null}

      <SignalValidationSection
        strategyKey="macro_regime_composite"
        title="Macro factors — diversification"
        description="Number of factors != number of independent bets. PCA on the 8 macro factors' real pairwise correlation matrix, over the same sealed dataset."
      />
      <SignalValidationSection
        strategyKey="cross_sectional_momentum"
        title="Momentum horizons — diversification"
        description="Same method applied to the 1M/3M/6M momentum horizons: are they three independent views, or mostly one restated three ways?"
      />

      <MetricCatalogSection />
    </div>
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
        eyebrow="Signal validation — effective number of bets"
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

function MetricCatalogSection() {
  const state = useApi<ResearchMetricCatalogResponse>(endpoints.adminResearchMetricCatalog);
  const metrics = state.data?.metrics ?? [];
  const grouped = useMemo(() => groupByCategory(metrics), [metrics]);

  return (
    <Panel>
      <SectionHeading
        eyebrow="The full taxonomy"
        title="Research metric catalog"
        description="Every metric this project's research program can compute, enumerated up front. A metric having no data yet is an honest 'not run', not an oversight — not every factor needs every check, and null is allowed."
      />
      <ResourceState loading={state.loading} error={state.error} onRetry={state.reload} resource="metric catalog" />
      {Object.entries(grouped).map(([category, categoryMetrics]) => (
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
    </Panel>
  );
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
    <Panel>
      <SectionHeading
        eyebrow={`${run.method} · ${run.correction_method}`}
        title="Latest run"
        description={run.summary}
      />
      <dl className="strategy-identity-grid">
        <div><dt>Forward horizon</dt><dd>{run.forward_horizon_days} trading days</dd></div>
        <div><dt>Alpha</dt><dd>{run.alpha}</dd></div>
        <div><dt>Min samples</dt><dd>{formatNumber(run.min_samples)}</dd></div>
        <div><dt>Factors × symbols</dt><dd>{run.factor_count} × {run.symbol_count}</dd></div>
        <div><dt>Pairs tested</dt><dd>{formatNumber(run.test_count)} / {formatNumber(run.factor_count * run.symbol_count)}</dd></div>
        <div><dt>Significant after correction</dt><dd>{formatNumber(run.significant_count)}</dd></div>
        <div><dt>Run at</dt><dd>{formatTimestamp(run.started_at)}</dd></div>
        <div><dt>Dataset snapshot</dt><dd><code>{run.dataset_snapshot_id || NOT_AVAILABLE}</code></dd></div>
      </dl>
    </Panel>
  );
}

function ResultsPanel({ run }: { run: FactorSignificanceRun }) {
  const results = run.results ?? [];
  const sorted = useMemo(() => sortResults(results), [results]);

  if (!results.length) {
    return <Unavailable title="No pair results are persisted for this run" />;
  }

  return (
    <Panel>
      <SectionHeading
        eyebrow="Every (factor, symbol) pair"
        title="Correlation and significance"
        description="A pair without 'significant' is not confirmed to have zero effect — it means the real data available so far cannot distinguish it from noise at this run's alpha. Direction is reported only for significant pairs, never inferred from a non-significant correlation sign."
      />
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
    </Panel>
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
