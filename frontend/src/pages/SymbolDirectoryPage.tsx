import { ArrowUpRight, RefreshCw, SearchX } from "lucide-react";
import { Link } from "react-router-dom";
import { endpoints, useApi } from "../api/client";
import { SnapshotBanner } from "../components/SnapshotBanner";
import { Panel, ResourceState, SectionHeading, StatusPill } from "../components/Ui";
import type { SymbolsResponse } from "../types";
import { formatCurrency, formatNumber, formatTimestamp, NOT_AVAILABLE } from "../utils/format";

export function SymbolDirectoryPage() {
  const state = useApi<SymbolsResponse>(endpoints.symbols);
  const symbols = state.data?.symbols ?? [];

  return (
    <div className="workspace symbols-page">
      <header className="workspace-header">
        <div>
          <p className="eyebrow">Research universe</p>
          <h1>Symbol research</h1>
          <p>Open a security’s persisted decision lineage, bars, events, metrics, and proposed structures.</p>
        </div>
        <button className="button button--quiet" type="button" onClick={state.reload} disabled={state.loading}>
          <RefreshCw aria-hidden="true" size={15} /> Refresh universe
        </button>
      </header>

      <ResourceState loading={state.loading} error={state.error} onRetry={state.reload} resource="symbol universe" />
      {state.data?.snapshot ? <SnapshotBanner snapshot={state.data.snapshot} /> : null}

      {state.data && !symbols.length ? (
        <div className="universe-empty">
          <SearchX aria-hidden="true" />
          <div>
            <h2>No persisted symbols</h2>
            <p>The database is reachable, but its latest symbol universe is empty. No demo rows are inserted automatically.</p>
          </div>
        </div>
      ) : null}

      {symbols.length ? (
        <Panel>
          <SectionHeading
            eyebrow={`${symbols.length} persisted securities`}
            title="Latest snapshot universe"
            description={state.data?.snapshot ? `As of ${formatTimestamp(state.data.snapshot.as_of)}` : "Snapshot metadata is not available."}
          />
          <div className="symbol-grid">
            {symbols.map((symbol) => (
              <Link className="symbol-card" to={`/symbols/${encodeURIComponent(symbol.symbol)}`} key={symbol.symbol}>
                <div className="symbol-card__topline">
                  <div>
                    <strong>{symbol.symbol}</strong>
                    <span>{symbol.asset_type || NOT_AVAILABLE}</span>
                  </div>
                  <ArrowUpRight aria-hidden="true" size={18} />
                </div>
                <h2>{symbol.name || NOT_AVAILABLE}</h2>
                <p>{symbol.summary || symbol.sector || NOT_AVAILABLE}</p>
                <dl>
                  <div><dt>Last database price</dt><dd>{formatCurrency(symbol.last_price, symbol.currency || "USD")}</dd></div>
                  <div><dt>Composite</dt><dd>{formatNumber(symbol.composite_score)}</dd></div>
                  <div><dt>Rank</dt><dd>{formatNumber(symbol.rank)}</dd></div>
                  <div><dt>Proposals</dt><dd>{formatNumber(symbol.candidate_count)}</dd></div>
                </dl>
                <div className="symbol-card__footer">
                  <StatusPill value={symbol.status} />
                  <span>Price as of {formatTimestamp(symbol.price_as_of)}</span>
                </div>
              </Link>
            ))}
          </div>
        </Panel>
      ) : null}
    </div>
  );
}
