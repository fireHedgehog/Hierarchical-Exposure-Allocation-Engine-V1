import { ArrowUpRight, BookOpenCheck, ExternalLink, RefreshCw } from "lucide-react";
import { Link } from "react-router-dom";
import { endpoints, useApi } from "../api/client";
import { OperatorPageHeader } from "../components/OperatorPageHeader";
import { Panel, ResourceState, SectionHeading, StatusPill, Unavailable } from "../components/Ui";
import type { StrategiesResponse, StrategySummary } from "../types";
import { formatScalar, formatTimestamp, NOT_AVAILABLE } from "../utils/format";

export function StrategyRegistryPage() {
  const state = useApi<StrategiesResponse>(endpoints.adminStrategies);
  const strategies = state.data?.strategies ?? [];

  return (
    <div className="workspace operator-page">
      <OperatorPageHeader
        title="Strategy registry"
        description="Track strategy identity, version, decay evidence, and lifecycle without turning Markdown files into runtime state."
        action={(
          <button className="button button--quiet" type="button" onClick={state.reload} disabled={state.loading}>
            <RefreshCw aria-hidden="true" size={15} /> Refresh registry
          </button>
        )}
      />
      <ResourceState loading={state.loading} error={state.error} onRetry={state.reload} resource="strategy registry" />

      {state.data ? (
        <>
          <div className="operator-stat-grid">
            <RegistryMetric label="Registered" value={state.data.summary.total} status="defined" />
            <RegistryMetric label="Active" value={state.data.summary.active} status="active" />
            <RegistryMetric label="Watching" value={state.data.summary.watching} status="watch" />
            <RegistryMetric label="Retired" value={state.data.summary.retired} status="retired" />
          </div>
          <Panel>
            <SectionHeading
              eyebrow="Database lifecycle records"
              title="Strategies and factors"
              description="Operational status lives in the database. A public specification may explain a version, but cannot silently change the running system."
            />
            {strategies.length ? (
              <div className="strategy-registry-grid">
                {strategies.map((strategy) => <StrategyCard key={strategy.key} strategy={strategy} />)}
              </div>
            ) : <Unavailable title="No strategies registered" detail="The strategy registry is empty; no runtime strategy is inferred from documents." />}
          </Panel>
        </>
      ) : null}
    </div>
  );
}

function RegistryMetric({ label, value, status }: { label: string; value: number; status: string }) {
  return <article className="operator-stat"><div><span>{label}</span><StatusPill value={status} /></div><strong>{value}</strong></article>;
}

function StrategyCard({ strategy }: { strategy: StrategySummary }) {
  const specUrl = safeHttpsUrl(strategy.public_spec_url);
  return (
    <article className="strategy-card">
      <div className="strategy-card-header">
        <span className="operator-icon"><BookOpenCheck aria-hidden="true" size={16} /></span>
        <div><span>{strategy.family || NOT_AVAILABLE}</span><h3>{strategy.name}</h3><code>{strategy.key}</code></div>
        <div className="strategy-card-header-pills">
          <StatusPill value={strategy.status} />
          <StatusPill value={strategy.verification_status || "registered_only"} />
        </div>
      </div>
      <p>{strategy.summary || "No database summary is available."}</p>
      <dl className="strategy-card-metrics">
        <div><dt>Version</dt><dd>{strategy.version || NOT_AVAILABLE}</dd></div>
        <div><dt>Function</dt><dd><code>{strategy.code_reference || NOT_AVAILABLE}</code></dd></div>
        <div><dt>Last checked</dt><dd>{formatTimestamp(strategy.last_checked_at)}</dd></div>
        <div><dt>Next review</dt><dd>{formatTimestamp(strategy.next_review_at)}</dd></div>
        <div><dt>Decay</dt><dd>{strategy.decay ? formatScalar(strategy.decay.value, strategy.decay.unit) : NOT_AVAILABLE}</dd></div>
        <div><dt>Decay status</dt><dd><StatusPill value={strategy.decay?.status} /></dd></div>
        <div><dt>Added</dt><dd>{formatTimestamp(strategy.added_at)}</dd></div>
        <div><dt>Retired</dt><dd>{formatTimestamp(strategy.retired_at)}</dd></div>
      </dl>
      <div className="strategy-card-actions">
        <Link className="button" to={`/operations/strategies/${encodeURIComponent(strategy.key)}`}>Open record <ArrowUpRight aria-hidden="true" size={14} /></Link>
        {specUrl ? <a className="button button--quiet" href={specUrl} target="_blank" rel="noopener noreferrer">Public spec <ExternalLink aria-hidden="true" size={13} /></a> : <span className="strategy-no-spec">No public spec URL</span>}
      </div>
    </article>
  );
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
