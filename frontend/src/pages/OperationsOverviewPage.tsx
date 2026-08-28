import { AlertTriangle, CheckCircle2, Clock3, Download, LineChart, Loader2, PlayCircle, RefreshCw, ShieldCheck } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import {
  endpoints, operatorErrorMessage, runPipeline, startBackgroundPipelineRun,
  type PipelineRunProgress, type PipelineStageKey, useApi,
} from "../api/client";
import { OperatorPageHeader } from "../components/OperatorPageHeader";
import { ProductReadinessPanel } from "../components/ProductReadinessPanel";
import { Panel, ResourceState, SectionHeading, StatusPill, Unavailable } from "../components/Ui";
import type { AdminOverviewResponse, PipelineResponse, PipelineRun } from "../types";
import { formatNumber, formatTimestamp, NOT_AVAILABLE } from "../utils/format";

const STAGE_LABELS: Record<PipelineStageKey, string> = {
  fetch_data: "Fetching real data",
  validate_data: "Validating",
  regime_filter: "Scoring regime",
  factor_engine: "Ranking symbols",
  allocation_engine: "Sizing allocation",
  instrument_engine: "Proposing instruments",
};

export function OperationsOverviewPage() {
  const overview = useApi<AdminOverviewResponse>(endpoints.adminOverview);
  const pipeline = useApi<PipelineResponse>(endpoints.adminPipeline);
  const [latestRun, setLatestRun] = useState<PipelineRun | null>(null);
  const [running, setRunning] = useState<"dry" | "full" | "stored" | PipelineStageKey | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [liveProgress, setLiveProgress] = useState<PipelineRunProgress | null>(null);
  const pollTimer = useRef<number | null>(null);

  const refresh = () => {
    overview.reload();
    pipeline.reload();
  };

  const stopPolling = () => {
    if (pollTimer.current !== null) {
      window.clearInterval(pollTimer.current);
      pollTimer.current = null;
    }
  };

  useEffect(() => stopPolling, []);

  const startRun = async (dryRun: boolean, stopAfter?: PipelineStageKey, reuseLatestDataset = false) => {
    if (!dryRun && !stopAfter && !window.confirm("Run every currently implemented stage? A successful run may publish a new immutable decision snapshot, but it will never place orders.")) return;
    setRunning(reuseLatestDataset ? "stored" : stopAfter ?? (dryRun ? "dry" : "full"));
    setActionError(null);
    setLiveProgress(null);

    // Dry runs are fast (no real fetch) -- the simple, synchronous call is
    // enough. Real runs use the background+poll path for live progress.
    if (dryRun) {
      try {
        const result = await runPipeline<{ run: PipelineRun }>(true, undefined, reuseLatestDataset);
        setLatestRun(result.run);
        refresh();
      } catch (error) {
        setActionError(operatorErrorMessage(error, "The pipeline request failed."));
      } finally {
        setRunning(null);
      }
      return;
    }

    try {
      const { progress_run_id: progressRunId } = await startBackgroundPipelineRun<{ progress_run_id: string }>(false, stopAfter, reuseLatestDataset);
      pollTimer.current = window.setInterval(async () => {
        try {
          const response = await fetch(endpoints.adminPipelineRunProgress(progressRunId));
          if (!response.ok) throw new Error(`HTTP ${response.status}`);
          const progress: PipelineRunProgress = await response.json();
          setLiveProgress(progress);
          if (progress.finished) {
            stopPolling();
            setRunning(null);
            if (progress.error) {
              setActionError(progress.error);
            } else if (progress.result) {
              setLatestRun(progress.result.run);
              refresh();
            }
          }
        } catch (error) {
          stopPolling();
          setRunning(null);
          setActionError(operatorErrorMessage(error, "Lost contact with the running pipeline."));
        }
      }, 700);
    } catch (error) {
      setActionError(operatorErrorMessage(error, "The pipeline request failed to start."));
      setRunning(null);
    }
  };

  const data = overview.data;
  const definition = pipeline.data?.definition || data?.pipeline.definition;
  const run = latestRun || pipeline.data?.latest_run || data?.pipeline.latest_run;

  return (
    <div className="workspace operator-page">
      <OperatorPageHeader
        title="Run pipeline"
        description="Inspect prerequisites and advance the persisted workflow deliberately. Automation remains disabled until every stage is trustworthy."
        action={(
          <button className="button button--quiet" type="button" onClick={refresh} disabled={overview.loading || pipeline.loading}>
            <RefreshCw aria-hidden="true" size={15} /> Refresh operations
          </button>
        )}
      />

      {liveProgress && !liveProgress.finished ? <LivePipelineProgress progress={liveProgress} /> : null}

      <ResourceState loading={overview.loading} error={overview.error} onRetry={overview.reload} resource="operator overview" />

      {data ? (
        <>
          <div className="operator-notice">
            <ShieldCheck aria-hidden="true" size={18} />
            <div>
              <strong>Manual control is intentional</strong>
              <p>Scheduling is off. This draft records a dry-run history and exposes unimplemented stages without manufacturing outputs.</p>
            </div>
            <StatusPill value={data.manual_only ? "manual_only" : "automation_enabled"} />
          </div>

          <div className="operator-stat-grid">
            <OverviewMetric label="Healthy providers" value={data.providers.healthy} denominator={data.providers.total} status={statusForOverviewMetric("healthy", data.providers.healthy, data.providers.total)} />
            <OverviewMetric label="Configured keys" value={data.providers.configured} denominator={data.providers.total} status={statusForOverviewMetric("configured", data.providers.configured, data.providers.total)} />
            <OverviewMetric label="Ready datasets" value={data.data.ready} denominator={data.data.assets} status={statusForOverviewMetric("ready", data.data.ready, data.data.assets)} />
            <OverviewMetric label="Active strategies" value={data.strategies.active} denominator={data.strategies.total} status={statusForOverviewMetric("active", data.strategies.active, data.strategies.total)} />
          </div>
        </>
      ) : null}

      <ResourceState loading={pipeline.loading && !data} error={pipeline.error} onRetry={pipeline.reload} resource="pipeline definition" />

      {definition ? (
        <Panel className="operator-pipeline-panel">
          <SectionHeading
            eyebrow={`${definition.key} · ${definition.version || NOT_AVAILABLE}`}
            title={definition.name}
            description={definition.description || "No pipeline description is persisted."}
            action={(
              <div className="operator-run-actions">
                <button className="button button--quiet" type="button" onClick={() => startRun(true)} disabled={running !== null}>
                  <ShieldCheck aria-hidden="true" size={15} /> {running === "dry" ? "Checking…" : "Dry preflight"}
                </button>
                <button
                  className="button button--quiet"
                  type="button"
                  onClick={() => startRun(false, "fetch_data")}
                  disabled={running !== null}
                  title="Runs only the fetch stage -- refreshes real data without recomputing regime, ranking, or allocation."
                >
                  <Download aria-hidden="true" size={15} /> {running === "fetch_data" ? "Fetching…" : "Fetch data only"}
                </button>
                <button
                  className="button button--quiet"
                  type="button"
                  onClick={() => startRun(false, "instrument_engine", true)}
                  disabled={running !== null}
                  title="Reuses the newest sealed dataset with no FRED/Yahoo request. Recomputes a complete local decision snapshot so the macro reading updates without removing other desk features."
                >
                  <LineChart aria-hidden="true" size={15} /> {running === "stored" ? "Recomputing…" : "Macro · stored data"}
                </button>
                <button className="button operator-run-button" type="button" onClick={() => startRun(false)} disabled={running !== null}>
                  <PlayCircle aria-hidden="true" size={16} /> {running === "full" ? "Starting…" : "Run available stages"}
                </button>
              </div>
            )}
          />
          {actionError ? <div className="operator-action-message operator-action-message--error" role="alert"><AlertTriangle aria-hidden="true" size={16} />{actionError}</div> : null}
          <ol className="pipeline-stage-list">
            {(definition.stages ?? []).map((stage, index) => {
              const status = stage.implementation_status || "unknown";
              return (
                <li key={stage.key}>
                  <span className="pipeline-stage-number">{String(index + 1).padStart(2, "0")}</span>
                  <div>
                    <div className="pipeline-stage-title"><strong>{stage.label}</strong><StatusPill value={status} /></div>
                    <p>{stage.description || "No stage description is persisted."}</p>
                    <code>{stage.key}{stage.required_provider_keys?.length ? ` · requires ${stage.required_provider_keys.join(", ")}` : ""}</code>
                  </div>
                </li>
              );
            })}
          </ol>
          {!definition.stages?.length ? <Unavailable title="Pipeline stages not available" detail="The definition has no persisted stages." /> : null}
        </Panel>
      ) : null}

      <Panel>
        <SectionHeading
          eyebrow="Persisted execution record"
          title="Latest manual run"
          description="A run record is operational history, not proof that market data or model output is valid."
        />
        {run ? <PipelineRunCard run={run} /> : <Unavailable title="No pipeline run recorded" detail="Start a dry run when you are ready to verify the staged workflow." />}
      </Panel>

      {data ? <ProductReadinessPanel readiness={data.readiness} /> : null}
    </div>
  );
}

export type OverviewMetricKind = "healthy" | "configured" | "ready" | "active";

export function statusForOverviewMetric(kind: OverviewMetricKind, value: number, denominator: number): string {
  if (denominator <= 0) return "not_configured";
  if (value <= 0) return kind === "configured" ? "missing" : "unavailable";
  if (kind === "active") return "active";
  if (value < denominator) return "partial";
  return kind;
}

function OverviewMetric({ label, value, denominator, status }: { label: string; value: number; denominator: number; status: string }) {
  return (
    <article className="operator-stat">
      <div><span>{label}</span><StatusPill value={status} /></div>
      <strong>{formatNumber(value)}<small> / {formatNumber(denominator)}</small></strong>
    </article>
  );
}

function LivePipelineProgress({ progress }: { progress: PipelineRunProgress }) {
  const stageLabel = progress.stage ? STAGE_LABELS[progress.stage] || progress.stage : "Starting…";
  const item = progress.item_progress;
  const itemPercent = item && item.total > 0 ? Math.round((item.done / item.total) * 100) : null;
  return (
    <div className="live-pipeline-progress">
      <div className="live-pipeline-progress__header">
        <Loader2 aria-hidden="true" size={16} className="live-pipeline-progress__spinner" />
        <strong>Stage {progress.stage_index} of {progress.total_stages}: {stageLabel}</strong>
      </div>
      <div className="live-pipeline-progress__bar">
        <div className="live-pipeline-progress__bar-fill" style={{ width: `${(progress.stage_index / progress.total_stages) * 100}%` }} />
      </div>
      {item ? (
        <div className="live-pipeline-progress__item">
          <span>{item.done} / {item.total}{item.current ? ` — ${item.current}` : ""}</span>
          <div className="live-pipeline-progress__bar live-pipeline-progress__bar--item">
            <div className="live-pipeline-progress__bar-fill" style={{ width: `${itemPercent ?? 0}%` }} />
          </div>
        </div>
      ) : null}
    </div>
  );
}

function PipelineRunCard({ run }: { run: PipelineRun }) {
  return (
    <div className="pipeline-run-card">
      <div className="pipeline-run-header">
        <div>
          <span className="operator-icon"><Clock3 aria-hidden="true" size={17} /></span>
          <div><strong>{run.id}</strong><small>Requested {formatTimestamp(run.requested_at || run.started_at)}</small></div>
        </div>
        <div className="pipeline-run-pills"><StatusPill value={run.status} /><StatusPill value={run.dry_run ? "dry_run" : "full_run"} /></div>
      </div>
      {run.summary ? <p>{run.summary}</p> : null}
      <div className="pipeline-run-stages">
        {(run.stages ?? []).map((stage, index) => (
          <article key={`${stage.key}-${index}`}>
            {stage.status === "complete" || stage.status === "completed" ? (
              <CheckCircle2 aria-hidden="true" size={15} />
            ) : stage.status === "completed_with_warnings" ? (
              <AlertTriangle aria-hidden="true" size={15} className="pipeline-stage-warning-icon" />
            ) : (
              <Clock3 aria-hidden="true" size={15} />
            )}
            <div>
              <strong>{stage.key}</strong>
              <span>{stage.message || "No stage output was recorded."}</span>
              {stage.error_code ? <code>{stage.error_code}</code> : null}
              <small>{formatTimestamp(stage.finished_at || stage.started_at)}</small>
            </div>
            <StatusPill value={stage.status} />
          </article>
        ))}
      </div>
      {!run.stages?.length ? <Unavailable compact title="Stage history not available" /> : null}
      <div className="pipeline-run-footer"><span>Finished</span><strong>{formatTimestamp(run.finished_at)}</strong></div>
    </div>
  );
}
