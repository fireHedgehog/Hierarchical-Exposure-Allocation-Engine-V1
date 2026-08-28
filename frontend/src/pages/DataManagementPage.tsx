import { useEffect, useState, type ReactNode } from "react";
import { ArrowUpDown, ArrowUpRight, Database, Download, RefreshCw, Search, Star, X } from "lucide-react";
import { Link } from "react-router-dom";
import { addToWatchlist, endpoints, removeFromWatchlist, useApi } from "../api/client";
import { OperatorPageHeader } from "../components/OperatorPageHeader";
import { Panel, ResourceState, SectionHeading, StatusPill, Unavailable } from "../components/Ui";
import type { AdminDataAsset, AdminDataResponse, AdminSymbolData } from "../types";
import { formatDate, formatNumber, formatTimestamp, NOT_AVAILABLE } from "../utils/format";

type SortOrder = "asc" | "desc";
type Health = "all" | "unhealthy";

interface TestFetchResult {
  ok: boolean;
  detail: string;
}

interface LibraryFetchResult {
  dataset_snapshot_id: string;
  fetched: { symbol: string; bar_count: number }[];
  failed: { symbol: string; error: string }[];
  remaining: number;
}

/** Shared query state (search/sort/health/page) for one compact symbol
 * table instance. Two independent instances back the watchlist and the
 * full data library -- separate tables, separate state, per the real
 * distinction between "what I watch today" and "what's fetched." */
function useSymbolTableQuery(scope: "watchlist" | "all") {
  const [queryInput, setQueryInput] = useState("");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [health, setHealth] = useState<Health>("all");
  const [sort, setSort] = useState("symbol");
  const [order, setOrder] = useState<SortOrder>("asc");

  useEffect(() => {
    const timer = window.setTimeout(() => setQuery(queryInput.trim()), 300);
    return () => window.clearTimeout(timer);
  }, [queryInput]);

  useEffect(() => {
    setPage(1);
  }, [query, health, sort, order]);

  const params = new URLSearchParams();
  params.set("scope", scope);
  if (query) params.set("q", query);
  if (page > 1) params.set("page", String(page));
  if (health !== "all") params.set("health", health);
  if (sort !== "symbol") params.set("sort", sort);
  if (order !== "asc") params.set("order", order);

  const state = useApi<AdminDataResponse>(`${endpoints.adminData}?${params.toString()}`);

  function toggleSort(column: string) {
    if (sort === column) setOrder((value) => (value === "asc" ? "desc" : "asc"));
    else {
      setSort(column);
      setOrder("asc");
    }
  }

  return { state, queryInput, setQueryInput, query, page, setPage, health, setHealth, sort, order, toggleSort };
}

export function DataManagementPage() {
  const watchlistTable = useSymbolTableQuery("watchlist");
  const libraryTable = useSymbolTableQuery("all");

  const assets = watchlistTable.state.data?.assets ?? [];
  const summary = watchlistTable.state.data?.summary;
  const hasInventory = Boolean(summary && (summary.assets > 0 || (watchlistTable.state.data?.symbols?.length ?? 0) > 0));

  const [pendingSymbol, setPendingSymbol] = useState<string | null>(null);
  async function toggleWatchlist(symbol: string, currentlyWatched: boolean) {
    setPendingSymbol(symbol);
    try {
      if (currentlyWatched) await removeFromWatchlist(symbol);
      else await addToWatchlist(symbol);
      watchlistTable.state.reload();
      libraryTable.state.reload();
    } finally {
      setPendingSymbol(null);
    }
  }

  const [testFetchResults, setTestFetchResults] = useState<Record<string, TestFetchResult>>({});
  const [testFetchPending, setTestFetchPending] = useState<string | null>(null);
  async function testFetch(symbol: string) {
    setTestFetchPending(symbol);
    setTestFetchResults((prev) => {
      const next = { ...prev };
      delete next[symbol];
      return next;
    });
    try {
      const response = await fetch(endpoints.adminDataTestFetch(symbol), { method: "POST" });
      const payload = await response.json();
      const detail = payload.ok
        ? `${payload.bar_count} bars, ${payload.period_start} → ${payload.period_end}`
        : payload.error || "Fetch failed.";
      setTestFetchResults((prev) => ({ ...prev, [symbol]: { ok: Boolean(payload.ok), detail } }));
    } catch {
      setTestFetchResults((prev) => ({ ...prev, [symbol]: { ok: false, detail: "Request failed." } }));
    } finally {
      setTestFetchPending(null);
    }
  }

  const [libraryFetchPending, setLibraryFetchPending] = useState(false);
  const [libraryFetchResult, setLibraryFetchResult] = useState<LibraryFetchResult | null>(null);
  const [libraryFetchError, setLibraryFetchError] = useState<string | null>(null);
  async function fetchLibraryBatch() {
    setLibraryFetchPending(true);
    setLibraryFetchError(null);
    try {
      const response = await fetch(endpoints.adminLibraryFetch, { method: "POST" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const payload: LibraryFetchResult = await response.json();
      setLibraryFetchResult(payload);
      libraryTable.state.reload();
    } catch {
      setLibraryFetchError("Request failed.");
    } finally {
      setLibraryFetchPending(false);
    }
  }

  return (
    <div className="workspace operator-page">
      <OperatorPageHeader
        title="Data management"
        description="See exactly what is present locally, how old it is, and which inputs are still missing before any model is trusted."
        action={(
          <div className="workspace-header__actions">
            <button
              className="button button--quiet"
              type="button"
              onClick={fetchLibraryBatch}
              disabled={libraryFetchPending}
              title="Fetches real price history for the extended data library (staging_symbols.fetch_only=1) -- admin work, never touches the live Today-desk product's active symbols or dataset. Resumable: click again for the next batch."
            >
              <Download aria-hidden="true" size={15} /> {libraryFetchPending ? "Fetching…" : "Fetch data library"}
            </button>
            <button
              className="button button--quiet"
              type="button"
              onClick={() => {
                watchlistTable.state.reload();
                libraryTable.state.reload();
              }}
              disabled={watchlistTable.state.loading || libraryTable.state.loading}
            >
              <RefreshCw aria-hidden="true" size={15} /> Refresh inventory
            </button>
          </div>
        )}
      />
      {libraryFetchError ? (
        <div className="library-fetch-banner library-fetch-banner--error">{libraryFetchError}</div>
      ) : null}
      {libraryFetchResult ? (
        <div className="library-fetch-banner">
          <strong>Library fetch batch:</strong>{" "}
          {libraryFetchResult.fetched.length} fetched, {libraryFetchResult.failed.length} failed, {libraryFetchResult.remaining} remaining.
          {libraryFetchResult.failed.length ? (
            <span className="library-fetch-banner__failed">
              {" "}Failed: {libraryFetchResult.failed.map((item) => `${item.symbol} (${item.error})`).join(", ")}
            </span>
          ) : null}
        </div>
      ) : null}
      <ResourceState loading={watchlistTable.state.loading} error={watchlistTable.state.error} onRetry={watchlistTable.state.reload} resource="data inventory" />

      {watchlistTable.state.data ? (
        <>
          <div className="operator-stat-grid operator-stat-grid--data">
            <DataMetric label="Tracked assets" value={summary?.assets} status={hasInventory ? "defined" : "not_configured"} />
            <DataMetric label="Ready" value={summary?.ready} status={!hasInventory ? "unavailable" : summary?.ready ? "ready" : "unavailable"} />
            <DataMetric label="Stale" value={summary?.stale} status={!hasInventory ? "unavailable" : summary?.stale ? "stale" : "healthy"} />
            <DataMetric label="Missing" value={summary?.missing} status={!hasInventory ? "unavailable" : summary?.missing ? "missing" : "healthy"} />
            <DataMetric label="Invalid inventory" value={summary?.invalid} status={invalidInventoryStatus(summary?.invalid, hasInventory)} />
          </div>

          <Panel>
            <SectionHeading
              eyebrow={`Inventory as of ${formatTimestamp(watchlistTable.state.data.as_of)}`}
              title="Local dataset inventory"
              description="Row counts, observation time, fetch time, and freshness are independent. A successful fetch does not make an old observation current."
            />
            {assets.length ? <DataInventoryTable assets={assets} /> : (
              <Unavailable title="No managed datasets" detail="The database contains no data-asset inventory records." />
            )}
          </Panel>

          <SymbolTablePanel
            title="Watchlist"
            table={watchlistTable}
            emptyLabel="watchlist"
            renderAction={(item) => (
              <button
                type="button"
                className="watchlist-star watchlist-star--active"
                onClick={() => toggleWatchlist(item.symbol, true)}
                disabled={pendingSymbol === item.symbol}
                title="Remove from watchlist"
                aria-label={`Remove ${item.symbol} from watchlist`}
              >
                <X aria-hidden="true" size={13} />
              </button>
            )}
          />

          <SymbolTablePanel
            title="Full data library"
            table={libraryTable}
            emptyLabel="data library"
            showHealthFilter
            renderAction={(item) => {
              const watched = Boolean(item.watchlist);
              const result = testFetchResults[item.symbol];
              return (
                <div className="symbol-row-actions">
                  <button
                    type="button"
                    className="button button--tiny"
                    onClick={() => testFetch(item.symbol)}
                    disabled={testFetchPending === item.symbol}
                    title="Live diagnostic fetch -- does not write to the database"
                  >
                    <Download aria-hidden="true" size={12} /> Test fetch
                  </button>
                  <button
                    type="button"
                    className={`watchlist-star ${watched ? "watchlist-star--active" : ""}`}
                    onClick={() => toggleWatchlist(item.symbol, watched)}
                    disabled={pendingSymbol === item.symbol}
                    title={watched ? "Remove from watchlist" : "Add to watchlist"}
                    aria-label={watched ? `Remove ${item.symbol} from watchlist` : `Add ${item.symbol} to watchlist`}
                  >
                    <Star aria-hidden="true" size={13} fill={watched ? "currentColor" : "none"} />
                  </button>
                  {result ? (
                    <small className={result.ok ? "test-fetch-result test-fetch-result--ok" : "test-fetch-result test-fetch-result--error"}>
                      {result.detail}
                    </small>
                  ) : null}
                </div>
              );
            }}
          />
        </>
      ) : null}
    </div>
  );
}

type SymbolTableQuery = ReturnType<typeof useSymbolTableQuery>;

function SymbolTablePanel({
  title,
  table,
  emptyLabel,
  renderAction,
  showHealthFilter = false,
}: {
  title: string;
  table: SymbolTableQuery;
  emptyLabel: string;
  renderAction: (item: AdminSymbolData) => ReactNode;
  showHealthFilter?: boolean;
}) {
  const symbols = table.state.data?.symbols ?? [];
  const search = table.state.data?.symbol_search;

  return (
    <Panel>
      <SectionHeading
        eyebrow={search ? `${search.total} symbols` : `${symbols.length} symbols`}
        title={title}
        description="Counts and timestamps come from the managed dataset inventory. Open the symbol workspace to inspect the actual bars and annotations."
      />
      <div className="symbol-table-controls">
        <div className="symbol-search-bar">
          <Search aria-hidden="true" size={14} />
          <input
            type="text"
            placeholder="Find a symbol by ticker or name…"
            value={table.queryInput}
            onChange={(event) => table.setQueryInput(event.target.value)}
          />
        </div>
        {showHealthFilter ? (
          <button
            type="button"
            className={`button button--tiny ${table.health === "unhealthy" ? "button--tiny-active" : ""}`}
            onClick={() => table.setHealth(table.health === "unhealthy" ? "all" : "unhealthy")}
          >
            {table.health === "unhealthy" ? "Showing unhealthy only" : "Show unhealthy only"}
          </button>
        ) : null}
      </div>
      {symbols.length ? (
        <>
          <CompactSymbolTable symbols={symbols} sort={table.sort} order={table.order} onSort={table.toggleSort} renderAction={renderAction} />
          {search && search.total_pages > 1 ? (
            <div className="symbol-search-pagination">
              <button className="button button--quiet" type="button" onClick={() => table.setPage((value) => Math.max(1, value - 1))} disabled={search.page <= 1}>
                Previous
              </button>
              <span>Page {search.page} of {search.total_pages}</span>
              <button className="button button--quiet" type="button" onClick={() => table.setPage((value) => Math.min(search.total_pages, value + 1))} disabled={search.page >= search.total_pages}>
                Next
              </button>
            </div>
          ) : null}
        </>
      ) : (
        <Unavailable
          title={table.query ? "No symbols match that search" : `Nothing in the ${emptyLabel} yet`}
          detail={table.query ? `Nothing matches "${table.query}".` : table.health === "unhealthy" ? "No unhealthy symbols right now." : `The ${emptyLabel} is empty.`}
        />
      )}
    </Panel>
  );
}

const SORT_COLUMNS: { key: string; label: string }[] = [
  { key: "symbol", label: "Symbol" },
  { key: "category", label: "Type" },
  { key: "row_count", label: "Bars" },
  { key: "period_start", label: "From" },
  { key: "period_end", label: "To" },
  { key: "last_observation_at", label: "Last observation" },
  { key: "last_fetched_at", label: "Last fetch" },
  { key: "status", label: "Health" },
];

function CompactSymbolTable({
  symbols,
  sort,
  order,
  onSort,
  renderAction,
}: {
  symbols: AdminSymbolData[];
  sort: string;
  order: SortOrder;
  onSort: (column: string) => void;
  renderAction: (item: AdminSymbolData) => ReactNode;
}) {
  return (
    <div className="operator-table-scroll">
      <table className="operator-table symbol-data-table symbol-data-table--compact">
        <thead>
          <tr>
            {SORT_COLUMNS.map((column) => (
              <th key={column.key}>
                <button type="button" className="symbol-table-sort" onClick={() => onSort(column.key)}>
                  {column.label}
                  {sort === column.key ? <ArrowUpDown aria-hidden="true" size={10} className={order === "desc" ? "symbol-table-sort__icon--desc" : undefined} /> : null}
                </button>
              </th>
            ))}
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {symbols.map((item) => (
            <tr key={item.symbol}>
              <td>
                <Link className="symbol-compact-link" to={`/symbols/${encodeURIComponent(item.symbol)}`}>
                  {item.symbol} <ArrowUpRight aria-hidden="true" size={11} />
                </Link>
              </td>
              <td>{formatCategory(item.category)}</td>
              <td className="mono-value">{formatNumber(item.row_count)}</td>
              <td className="mono-value">{formatDate(item.period_start)}</td>
              <td className="mono-value">{formatDate(item.period_end)}</td>
              <td className="mono-value">{formatTimestamp(item.last_observation_at)}</td>
              <td className="mono-value">{formatTimestamp(item.last_fetched_at)}</td>
              <td><StatusPill value={item.status} /></td>
              <td>{renderAction(item)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function formatCategory(category: string | null | undefined): string {
  if (!category) return NOT_AVAILABLE;
  return category.replace(/_/g, " ");
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
