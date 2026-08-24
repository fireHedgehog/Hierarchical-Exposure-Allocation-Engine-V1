import { AlertTriangle, CheckCircle2, Clock3, PlayCircle, RefreshCw, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { endpoints, operatorErrorMessage, runPipeline, useApi } from "../api/client";
import { OperatorPageHeader } from "../components/OperatorPageHeader";
import { Panel, ResourceState, SectionHeading, StatusPill, Unavailable } from "../components/Ui";
import type { AdminOverviewResponse, PipelineResponse, PipelineRun } from "../types";
import { formatNumber, formatTimestamp, NOT_AVAILABLE } from "../utils/format";

export function OperationsOverviewPage() {
  const overview = useApi<AdminOverviewResponse>(endpoints.adminOverview);
  const pipeline = useApi<PipelineResponse>(endpoints.adminPipeline);
  const [latestRun, setLatestRun] = useState<PipelineRun | null>(null);
  const [running, setRunning] = useState<"dry" | "full" | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const refresh = () => {
    overview.reload();
    pipeline.reload();
  };

  const startRun = async (dryRun: boolean) => {
    if (!dryRun && !window.confirm("Run every currently implemented stage? A successful run may publish a new immutable decision snapshot, but it will never place orders.")) return;
    setRunning(dryRun ? "dry" : "full");
    setActionError(null);
    try {
      const result = await runPipeline<{ run: PipelineRun }>(dryRun);
      setLatestRun(result.run);
      refresh();
    } catch (error) {
      setActionError(operatorErrorMessage(error, "The pipeline request failed."));
    } finally {
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
            {stage.status === "complete" || stage.status === "completed" ? <CheckCircle2 aria-hidden="true" size={15} /> : <Clock3 aria-hidden="true" size={15} />}
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
