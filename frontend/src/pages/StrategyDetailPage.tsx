import { ArrowLeft, ExternalLink, FileCheck2, Fingerprint, History, RefreshCw } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { endpoints, useApi } from "../api/client";
import { OperatorPageHeader } from "../components/OperatorPageHeader";
import { Panel, ResourceState, SectionHeading, StatusPill, Unavailable } from "../components/Ui";
import type { ResearchArtifact, StrategyDetail, StrategyDetailResponse, StrategyVersion } from "../types";
import { formatScalar, formatTimestamp, NOT_AVAILABLE } from "../utils/format";

export function StrategyDetailPage() {
  const { key = "" } = useParams();
  const endpoint = strategyEndpoint(key);
  const state = useApi<StrategyDetailResponse>(endpoint);
  const strategy = state.data?.strategy;
  const currentVersion = resolveCurrentStrategyVersion(strategy);
  const currentDecay = currentVersion?.diagnostics?.find((diagnostic) => diagnostic.metric_key === "decay_rate");

  return (
    <div className="workspace operator-page strategy-detail-page">
      <Link className="back-link" to="/operations/strategies"><ArrowLeft aria-hidden="true" size={15} /> Strategy registry</Link>
      <OperatorPageHeader
        title={strategy?.name || "Strategy record"}
        description={strategy?.summary || "Loading the persisted lifecycle and evidence record."}
        action={(
          <button className="button button--quiet" type="button" onClick={state.reload} disabled={state.loading || !endpoint}>
            <RefreshCw aria-hidden="true" size={15} /> Refresh strategy
          </button>
        )}
      />
      {!endpoint ? <div className="resource-state resource-state--error" role="alert">Invalid strategy key.</div> : null}
      <ResourceState loading={state.loading} error={state.error} onRetry={state.reload} resource="strategy record" />

      {strategy ? (
        <>
          <Panel className="strategy-identity-panel">
            <div className="strategy-identity-topline">
              <div><p className="eyebrow">{strategy.family || "Strategy"}</p><code>{strategy.key}</code></div>
              <div><StatusPill value={strategy.status} /><StatusPill value={strategy.version ? `version_${strategy.version}` : null} /></div>
            </div>
            <p>{strategy.summary || NOT_AVAILABLE}</p>
            <dl className="strategy-identity-grid">
              <div><dt>Added to universe</dt><dd>{formatTimestamp(strategy.added_at)}</dd></div>
              <div><dt>Retired</dt><dd>{formatTimestamp(strategy.retired_at)}</dd></div>
              <div><dt>Retirement reason</dt><dd>{strategy.retirement_reason || NOT_AVAILABLE}</dd></div>
              <div><dt>Current decay</dt><dd>{currentDecay ? formatScalar(currentDecay.value, currentDecay.unit) : NOT_AVAILABLE}</dd></div>
            </dl>
            <PublicSpec url={strategy.public_spec_url} />
          </Panel>

          <CurrentStrategyDiagnostics version={currentVersion} />

          <Panel>
            <SectionHeading eyebrow="Change control" title="Version and lifecycle history" description="Keep the record compact: what changed, why it changed, and when it became active or retired." />
            {strategy.versions?.length ? (
              <div className="strategy-version-list">
                {strategy.versions.map((version) => (
                  <article key={version.version}>
                    <span className="operator-icon"><History aria-hidden="true" size={15} /></span>
                    <div>
                      <div>
                        <strong>Version {version.version}</strong>
                        <StatusPill value={version.version === strategy.version ? "current" : "historical"} />
                        <StatusPill value={version.verification_status || "registered_only"} />
                      </div>
                      <p>{version.change_summary || "No version change summary is persisted."}</p>
                      {version.thesis ? <small>Thesis: {version.thesis}</small> : null}
                      {version.expected_edge ? <small>Expected edge: {version.expected_edge}</small> : null}
                      <small>Created {formatTimestamp(version.created_at)} · Promoted {formatTimestamp(version.promoted_at)} · Next review {formatTimestamp(version.next_review_at)}</small>
                    </div>
                    <CodeReference value={version.code_reference} />
                  </article>
                ))}
              </div>
            ) : <Unavailable title="Version history not available" />}
            {strategy.lifecycle?.length ? (
              <div className="strategy-lifecycle-list">
                {strategy.lifecycle.map((event, index) => (
                  <article key={event.event_id || `${event.occurred_at}-${index}`}>
                    <History aria-hidden="true" size={14} />
                    <div><strong>{event.from_status ? `${event.from_status} → ${event.to_status || NOT_AVAILABLE}` : event.to_status || NOT_AVAILABLE}</strong><p>{event.reason || "No lifecycle reason is persisted."}</p><small>{formatTimestamp(event.occurred_at)} · version {event.strategy_version || NOT_AVAILABLE}</small></div>
                  </article>
                ))}
              </div>
            ) : <Unavailable compact title="Lifecycle events not available" />}
          </Panel>

          <Panel>
            <SectionHeading eyebrow="Reproducible research" title="Runs and immutable artifacts" description="Database records drive the app. Optional reports explain a run and carry fingerprints; they are not runtime configuration." />
            {strategy.research_runs?.length ? (
              <div className="research-run-list">
                {strategy.research_runs.map((run) => (
                  <article key={run.id}>
                    <div className="research-run-header"><div><FileCheck2 aria-hidden="true" size={16} /><strong>{run.id}</strong></div><StatusPill value={run.status} /></div>
                    <p>{run.summary || "No research summary is persisted."}</p>
                    <small>Version {run.strategy_version || NOT_AVAILABLE} · {formatTimestamp(run.started_at)} → {formatTimestamp(run.finished_at)}</small>
                    <ArtifactList artifacts={run.artifacts} />
                  </article>
                ))}
              </div>
            ) : <Unavailable title="Research runs not available" detail="No reproducible result artifact has been registered yet." />}
          </Panel>
        </>
      ) : null}
    </div>
  );
}

export function resolveCurrentStrategyVersion(strategy?: StrategyDetail | null): StrategyVersion | undefined {
  if (!strategy?.version) return undefined;
  return strategy.versions?.find((version) => version.version === strategy.version);
}

export function CurrentStrategyDiagnostics({ version }: { version?: StrategyVersion }) {
  return (
    <Panel>
      <SectionHeading eyebrow="Measured evidence" title="Current diagnostics" description="A null metric remains unavailable; lifecycle status is never inferred from a missing value." />
      {version?.diagnostics?.length ? (
        <div className="strategy-diagnostic-grid">
          {version.diagnostics.map((diagnostic) => (
            <article key={diagnostic.metric_key}>
              <div><span>{diagnostic.label || diagnostic.metric_key}</span><StatusPill value={diagnostic.status} /></div>
              <strong>{formatScalar(diagnostic.value, diagnostic.unit)}</strong>
              <p>{diagnostic.description || "No diagnostic description is persisted."}</p>
              <small>{diagnostic.window_label || "Window unavailable"} · as of {formatTimestamp(diagnostic.as_of)}</small>
            </article>
          ))}
        </div>
      ) : <Unavailable title="Diagnostics not available" detail="No calculated diagnostics are attached to the explicitly selected current strategy version." />}
    </Panel>
  );
}

function PublicSpec({ url, compact = false }: { url?: string | null; compact?: boolean }) {
  const safe = safeHttpsUrl(url);
  if (!safe) return compact ? <span className="strategy-no-spec">No public spec</span> : <div className="strategy-public-spec"><span>Public specification</span><strong>{NOT_AVAILABLE}</strong></div>;
  return <a className={compact ? "button button--quiet" : "strategy-public-spec strategy-public-spec--linked"} href={safe} target="_blank" rel="noopener noreferrer"><span>Public specification</span><strong>Open versioned source <ExternalLink aria-hidden="true" size={13} /></strong></a>;
}

function CodeReference({ value }: { value?: string | null }) {
  const safe = safeHttpsUrl(value);
  if (safe) return <a className="button button--quiet" href={safe} target="_blank" rel="noopener noreferrer">Code reference <ExternalLink aria-hidden="true" size={13} /></a>;
  return <code className="strategy-code-reference">{value || NOT_AVAILABLE}</code>;
}

function ArtifactList({ artifacts }: { artifacts?: ResearchArtifact[] | null }) {
  if (!artifacts?.length) return <Unavailable compact title="No artifacts registered" />;
  return (
    <div className="artifact-list">
      {artifacts.map((artifact, index) => (
        <div key={artifact.artifact_key || artifact.sha256 || `${artifact.relative_path}-${index}`}>
          <Fingerprint aria-hidden="true" size={14} />
          <div><strong>{artifact.artifact_key || artifact.relative_path || "Research artifact"}</strong><span>{artifact.media_type || NOT_AVAILABLE} · {formatTimestamp(artifact.created_at)} · {artifact.curated ? "curated" : "generated"}</span><code>{artifact.sha256 || NOT_AVAILABLE}</code></div>
        </div>
      ))}
    </div>
  );
}

function strategyEndpoint(key: string): string | null {
  if (!/^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/.test(key)) return null;
  return endpoints.adminStrategy(key);
}

function safeHttpsUrl(value: string | null | undefined): string | null {
  if (!value) return null;
  try {
    const parsed = new URL(value);
    return parsed.protocol === "https:" ? parsed.toString() : null;
  } catch {
    return null;
  }
}
