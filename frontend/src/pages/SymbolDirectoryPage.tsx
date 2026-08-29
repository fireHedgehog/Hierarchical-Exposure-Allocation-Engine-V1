import { useState, type MouseEvent } from "react";
import { ArrowUpRight, RefreshCw, SearchX, Star } from "lucide-react";
import { Link } from "react-router-dom";
import { addToWatchlist, endpoints, removeFromWatchlist, useApi } from "../api/client";
import { SnapshotBanner } from "../components/SnapshotBanner";
import { Panel, ResourceState, SectionHeading, StatusPill } from "../components/Ui";
import type { SymbolsResponse } from "../types";
import { formatCurrency, formatNumber, formatTimestamp, NOT_AVAILABLE } from "../utils/format";

export function SymbolDirectoryPage() {
  const [showAll, setShowAll] = useState(false);
  const state = useApi<SymbolsResponse>(showAll ? `${endpoints.symbols}?scope=all` : endpoints.symbols);
  const symbols = state.data?.symbols ?? [];

  const [pendingSymbol, setPendingSymbol] = useState<string | null>(null);
  async function toggleWatchlist(event: MouseEvent, symbol: string, currentlyWatched: boolean) {
    event.preventDefault();
    event.stopPropagation();
    setPendingSymbol(symbol);
    try {
      if (currentlyWatched) await removeFromWatchlist(symbol);
      else await addToWatchlist(symbol);
      state.reload();
    } finally {
      setPendingSymbol(null);
    }
  }

  return (
    <div className="workspace symbols-page">
      <header className="workspace-header">
        <div>
          <p className="eyebrow">Research workspace</p>
          <h1>Timing</h1>
          <p>Symbol-level timing research and persisted lineage. Placeholder methods are not guaranteed to validate or produce trading edge.</p>
        </div>
        <div className="workspace-header__actions">
          <button className="button button--quiet" type="button" onClick={() => setShowAll((value) => !value)}>
            {showAll ? "Watchlist only" : "Show full data library"}
          </button>
          <button className="button button--quiet" type="button" onClick={state.reload} disabled={state.loading}>
            <RefreshCw aria-hidden="true" size={15} /> Refresh universe
          </button>
        </div>
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
            title={showAll ? "Full data library" : "Watchlist"}
            description={state.data?.snapshot ? `As of ${formatTimestamp(state.data.snapshot.as_of)}` : "Snapshot metadata is not available."}
          />
          <div className="symbol-grid">
            {symbols.map((symbol) => {
              const watched = Boolean(symbol.watchlist);
              return (
              <Link className="symbol-card" to={`/symbols/${encodeURIComponent(symbol.symbol)}`} key={symbol.symbol}>
                <button
                  type="button"
                  className={`watchlist-star symbol-card__star ${watched ? "watchlist-star--active" : ""}`}
                  onClick={(event) => toggleWatchlist(event, symbol.symbol, watched)}
                  disabled={pendingSymbol === symbol.symbol}
                  title={watched ? "Remove from watchlist" : "Add to watchlist"}
                  aria-label={watched ? `Remove ${symbol.symbol} from watchlist` : `Add ${symbol.symbol} to watchlist`}
                >
                  <Star aria-hidden="true" size={13} fill={watched ? "currentColor" : "none"} />
                </button>
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
              );
            })}
          </div>
        </Panel>
      ) : null}
    </div>
  );
}
