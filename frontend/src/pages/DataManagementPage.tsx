import { ArrowUpRight, Database, RefreshCw } from "lucide-react";
import { Link } from "react-router-dom";
import { endpoints, useApi } from "../api/client";
import { OperatorPageHeader } from "../components/OperatorPageHeader";
import { Panel, ResourceState, SectionHeading, StatusPill, Unavailable } from "../components/Ui";
import type { AdminDataAsset, AdminDataResponse, AdminSymbolData } from "../types";
import { formatDate, formatNumber, formatTimestamp, NOT_AVAILABLE } from "../utils/format";

export function DataManagementPage() {
  const state = useApi<AdminDataResponse>(endpoints.adminData);
  const assets = state.data?.assets ?? [];
  const symbols = state.data?.symbols ?? [];
  const summary = state.data?.summary;
  const hasInventory = Boolean(summary && (summary.assets > 0 || symbols.length > 0));

  return (
    <div className="workspace operator-page">
      <OperatorPageHeader
        title="Data management"
        description="See exactly what is present locally, how old it is, and which inputs are still missing before any model is trusted."
        action={(
          <button className="button button--quiet" type="button" onClick={state.reload} disabled={state.loading}>
            <RefreshCw aria-hidden="true" size={15} /> Refresh inventory
          </button>
        )}
      />
      <ResourceState loading={state.loading} error={state.error} onRetry={state.reload} resource="data inventory" />

      {state.data ? (
        <>
          <div className="operator-stat-grid operator-stat-grid--data">
            <DataMetric label="Tracked assets" value={state.data.summary.assets} status={hasInventory ? "defined" : "not_configured"} />
            <DataMetric label="Ready" value={state.data.summary.ready} status={!hasInventory ? "unavailable" : state.data.summary.ready ? "ready" : "unavailable"} />
            <DataMetric label="Stale" value={state.data.summary.stale} status={!hasInventory ? "unavailable" : state.data.summary.stale ? "stale" : "healthy"} />
            <DataMetric label="Missing" value={state.data.summary.missing} status={!hasInventory ? "unavailable" : state.data.summary.missing ? "missing" : "healthy"} />
            <DataMetric
              label="Invalid inventory"
              value={state.data.summary.invalid}
              status={invalidInventoryStatus(state.data.summary.invalid, hasInventory)}
            />
          </div>

          <Panel>
            <SectionHeading
              eyebrow={`Inventory as of ${formatTimestamp(state.data.as_of)}`}
              title="Local dataset inventory"
              description="Row counts, observation time, fetch time, and freshness are independent. A successful fetch does not make an old observation current."
            />
            {assets.length ? <DataInventoryTable assets={assets} /> : (
              <Unavailable title="No managed datasets" detail="The database contains no data-asset inventory records." />
            )}
          </Panel>

          <Panel>
            <SectionHeading
              eyebrow={`${symbols.length} symbols with persisted bar inventory`}
              title="Symbol bar coverage"
              description="Counts and timestamps come from the managed dataset inventory. Open the symbol workspace to inspect the actual bars and annotations."
            />
            {symbols.length ? <SymbolDataTable symbols={symbols} /> : (
              <Unavailable title="Symbol bar inventory not available" detail="No per-symbol bar summary is persisted for the current dataset." />
            )}
          </Panel>
        </>
      ) : null}
    </div>
  );
}

function SymbolDataTable({ symbols }: { symbols: AdminSymbolData[] }) {
  return (
    <div className="operator-table-scroll">
      <table className="operator-table symbol-data-table">
        <thead><tr><th>Symbol</th><th>Bars</th><th>Coverage</th><th>Last observation</th><th>Last fetch</th><th>Freshness</th></tr></thead>
        <tbody>
          {symbols.map((item) => (
            <tr key={item.symbol}>
              <td><Link className="symbol-data-link" to={`/symbols/${encodeURIComponent(item.symbol)}`}><span><strong>{item.symbol}</strong><small>{item.name || NOT_AVAILABLE}</small></span><ArrowUpRight aria-hidden="true" size={14} /></Link></td>
              <td data-label="Bars"><strong className="mono-value">{formatNumber(item.row_count)}</strong></td>
              <td data-label="Coverage"><span className="table-stack"><b>{formatDate(item.period_start)}</b><small>to {formatDate(item.period_end)}</small></span></td>
              <td data-label="Last observation"><span className="table-stack"><b>{formatTimestamp(item.last_observation_at)}</b><small>{item.dataset_snapshot_id || NOT_AVAILABLE}</small></span></td>
              <td data-label="Last fetch"><span className="table-stack"><b>{formatTimestamp(item.last_fetched_at)}</b><small>{item.classification || NOT_AVAILABLE}</small></span></td>
              <td data-label="Freshness"><div className="table-status-stack"><StatusPill value={item.freshness} /><StatusPill value={item.status} /></div></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function invalidInventoryStatus(value: number | null | undefined, hasInventory: boolean): string {
  if (value === null || value === undefined) return "unavailable";
  if (value > 0) return "invalid";
  return hasInventory ? "healthy" : "not_configured";
}

function DataMetric({ label, value, status }: { label: string; value: number | null | undefined; status: string }) {
  return (
    <article className="operator-stat">
      <div><span>{label}</span><StatusPill value={status} /></div>
      <strong>{formatNumber(value)}</strong>
    </article>
  );
}

function DataInventoryTable({ assets }: { assets: AdminDataAsset[] }) {
  return (
    <div className="operator-table-scroll">
      <table className="operator-table data-inventory-table">
        <thead>
          <tr>
            <th>Dataset</th>
            <th>Rows</th>
            <th>Coverage</th>
            <th>Last observation</th>
            <th>Last fetch</th>
            <th>Freshness</th>
          </tr>
        </thead>
        <tbody>
          {assets.map((asset) => (
            <tr key={asset.key}>
              <td>
                <div className="data-asset-name">
                  <span className="operator-icon"><Database aria-hidden="true" size={14} /></span>
                  <div>
                    <strong>{asset.symbol ? `${asset.symbol} · ${asset.label}` : asset.label}</strong>
                    <small>{asset.kind || NOT_AVAILABLE} · {asset.frequency || NOT_AVAILABLE} · {asset.provider_key || NOT_AVAILABLE}</small>
                    {asset.detail ? <p>{asset.detail}</p> : null}
                  </div>
                </div>
              </td>
              <td data-label="Rows"><strong className="mono-value">{formatNumber(asset.row_count)}</strong></td>
              <td data-label="Coverage"><span className="table-stack"><b>{formatDate(asset.period_start)}</b><small>to {formatDate(asset.period_end)}</small></span></td>
              <td data-label="Last observation"><span className="table-stack"><b>{formatTimestamp(asset.last_observation_at)}</b><small>Age {formatAge(asset.age_seconds)} · limit {formatAge(asset.max_age_seconds)}</small></span></td>
              <td data-label="Last fetch"><span className="table-stack"><b>{formatTimestamp(asset.last_fetched_at)}</b><small>{asset.classification || NOT_AVAILABLE}</small></span></td>
              <td data-label="Freshness"><div className="table-status-stack"><StatusPill value={asset.freshness} /><StatusPill value={asset.status} /></div></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function formatAge(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || !Number.isFinite(seconds)) return NOT_AVAILABLE;
  if (seconds < 3600) return `${Math.round(seconds / 60)} min`;
  if (seconds < 86400) return `${Math.round(seconds / 3600)} hr`;
  return `${Math.round(seconds / 86400)} days`;
}
