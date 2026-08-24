import { AlertTriangle, FlaskConical, RefreshCw } from "lucide-react";
import { useMemo, useState } from "react";
import { endpoints, operatorErrorMessage, runFactorSignificanceResearch, useApi } from "../api/client";
import { OperatorPageHeader } from "../components/OperatorPageHeader";
import { Panel, ResourceState, SectionHeading, StatusPill, Unavailable } from "../components/Ui";
import type { FactorSignificanceResult, FactorSignificanceRun, FactorSignificanceRunResponse } from "../types";
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
    </div>
  );
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
