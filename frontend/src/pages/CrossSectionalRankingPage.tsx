import { useMemo, useState } from "react";
import { ArrowUpRight, ExternalLink, RefreshCw, Search } from "lucide-react";
import { Link } from "react-router-dom";
import { endpoints, useApi } from "../api/client";
import { Panel, ResourceState, SectionHeading, StatusPill } from "../components/Ui";
import type { CrossSectionalRankingResponse, CrossSectionalRankingRow } from "../types";
import { formatNumber, NOT_AVAILABLE } from "../utils/format";

type SortKey =
  | "leadership_persistence"
  | "rs_3m_percentile"
  | "candidate_weight"
  | "liquidity_rank"
  | "score"
  | "rs_3m"
  | "rs_6m"
  | "rs_12m"
  | "high_52w_distance"
  | "trend_distance"
  | "slope"
  | "median_dollar_volume_21d";
type Screen = "liquid" | "leaders" | "portfolio" | "aligned" | "all";

const evidenceUrl = "https://github.com/fireHedgehog/Hierarchical-Exposure-Allocation-Engine-V1/blob/main/docs/hypotheses/staging_v2/cross-sectional/h-xsec-s5-002-liquid-tail-implementation.md";
const movingAverageStudyUrl = "https://github.com/fireHedgehog/Hierarchical-Exposure-Allocation-Engine-V1/blob/main/docs/hypotheses/staging_v2/cross-sectional/h-xsec-s2-003-moving-average-state-transition.md";
const pct = (value: number | null) => value == null ? NOT_AVAILABLE : `${value >= 0 ? "+" : ""}${(value * 100).toFixed(1)}%`;
const plainPct = (value: number | null) => value == null ? NOT_AVAILABLE : `${value.toFixed(1)}%`;

export function screenMatches(row: CrossSectionalRankingRow, screen: Screen): boolean {
  if (screen === "liquid") return row.is_liquid_top100;
  if (screen === "leaders") return row.is_current_leader;
  if (screen === "portfolio") return (row.candidate_weight ?? 0) > 0;
  if (screen === "aligned") return row.above_all_mas;
  return true;
}

export function compareRows(a: CrossSectionalRankingRow, b: CrossSectionalRankingRow, sort: SortKey): number {
  if (sort === "liquidity_rank") {
    return (a.liquidity_rank ?? Infinity) - (b.liquidity_rank ?? Infinity) || a.symbol.localeCompare(b.symbol);
  }
  const primary = (b[sort] ?? -Infinity) - (a[sort] ?? -Infinity);
  if (primary) return primary;
  if (sort === "leadership_persistence") {
    const momentum = (b.rs_3m_percentile ?? -Infinity) - (a.rs_3m_percentile ?? -Infinity);
    if (momentum) return momentum;
  }
  return a.symbol.localeCompare(b.symbol);
}

function EvidenceBar({ value, tone = "positive" }: { value: number | null; tone?: "positive" | "warning" }) {
  const width = value == null ? 0 : Math.max(0, Math.min(100, value));
  return <div className="ranking-evidence"><span>{plainPct(value)}</span><div aria-hidden="true"><i className={`ranking-evidence__fill ranking-evidence__fill--${tone}`} style={{ width: `${width}%` }} /></div></div>;
}

function EvidenceStatus({ row }: { row: CrossSectionalRankingRow }) {
  if (row.is_current_leader) return <StatusPill value="Current leader" tone="positive" />;
  if ((row.candidate_weight ?? 0) > 0) return <StatusPill value="Active sleeve" tone="info" />;
  return <StatusPill value="Context" tone="neutral" />;
}

export function CrossSectionalRankingPage() {
  const state = useApi<CrossSectionalRankingResponse>(endpoints.crossSectionalRanking);
  const [screen, setScreen] = useState<Screen>("liquid");
  const [sort, setSort] = useState<SortKey>("leadership_persistence");
  const [query, setQuery] = useState("");
  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    return [...(state.data?.rows ?? [])]
      .filter((row) => screenMatches(row, screen))
      .filter((row) => !q || row.symbol.toLowerCase().includes(q) || row.name.toLowerCase().includes(q))
      .sort((a, b) => compareRows(a, b, sort));
  }, [state.data, screen, sort, query]);
  const reversalRows = useMemo(() => [...(state.data?.rows ?? [])]
    .filter((row) => row.is_reversal_watch)
    .sort((a, b) => Math.max(b.reversal_5d_percentile ?? -Infinity, b.sector_relative_reversal_percentile ?? -Infinity)
      - Math.max(a.reversal_5d_percentile ?? -Infinity, a.sector_relative_reversal_percentile ?? -Infinity)), [state.data]);
  const formationCount = state.data?.leadership_formation_count ?? 0;

  return <div className="workspace ranking-page">
    <header className="workspace-header"><div><p className="eyebrow">Research workspace</p><h1>Cross-sectional ranking</h1><p>Research translation of Stage 2 evidence. It describes current leadership and technical context; it is not registered alpha or a trading recommendation.</p></div><button className="button button--quiet" type="button" onClick={state.reload} disabled={state.loading}><RefreshCw size={15} /> Refresh ranking</button></header>
    <ResourceState loading={state.loading} error={state.error} onRetry={state.reload} resource="cross-sectional ranking" />
    {state.data ? <>
      <div className="ranking-summary">
        <div><span>Liquid evidence pool</span><strong>{state.data.liquid_top100_count}</strong></div>
        <div><span>Current 3M leaders</span><strong>{state.data.current_leader_count}</strong></div>
        <div><span>Active 13-week sleeves</span><strong>{state.data.active_sleeve_count}</strong></div>
        <div><span>Latest price date</span><strong>{state.data.latest_price_date || NOT_AVAILABLE}</strong></div>
        <div><span>Weekly formations</span><strong>{state.data.leadership_formation_count}</strong></div>
        <div><span>Model status</span><StatusPill value="Research only" tone="warning" /></div>
      </div>

      <Panel><SectionHeading eyebrow="Evidence-informed translation" title="Liquid 3M leadership and persistence" description="The liquid Top-100 is selected by trailing 21-session dollar volume with a $5 raw-price floor. Current leaders are the top decile of exact-date 3M excess return versus SPY. Persistence asks how often a name entered the last 13 weekly leader sleeves; candidate weight is the natural average of those equal-weight sleeves, not an authorized allocation." />
        <div className="ranking-controls"><label><Search size={13} /><input aria-label="Search ranking" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Symbol or company" /></label><select aria-label="Screen" value={screen} onChange={(event) => setScreen(event.target.value as Screen)}><option value="liquid">Liquid Top-100</option><option value="leaders">Current leaders</option><option value="portfolio">Active 13-week sleeves</option><option value="aligned">Above all MAs</option><option value="all">All eligible</option></select><select aria-label="Sort ranking" value={sort} onChange={(event) => setSort(event.target.value as SortKey)}><option value="leadership_persistence">Leadership persistence</option><option value="rs_3m_percentile">Current 3M percentile</option><option value="candidate_weight">Candidate weight</option><option value="liquidity_rank">Liquidity rank</option><option value="score">Technical context score</option><option value="rs_3m">3m vs SPY</option><option value="rs_6m">6m vs SPY</option><option value="rs_12m">12m vs SPY</option><option value="high_52w_distance">52w high proximity</option><option value="trend_distance">MA distance</option><option value="slope">MA slope</option><option value="median_dollar_volume_21d">Dollar volume</option></select></div>
        <div className="operator-table-scroll"><table className="operator-table ranking-table"><thead><tr><th>Rank</th><th>Symbol</th><th>Evidence</th><th>3M percentile</th><th>13W persistence</th><th>Candidate weight</th><th>Liquidity</th><th>3m vs SPY</th><th>Technical context</th><th>6m vs SPY</th><th>12m vs SPY</th><th>52w high</th><th>MA distance</th><th>MA slope</th><th>Structure</th></tr></thead><tbody>{rows.slice(0, 100).map((row, index) => <tr key={row.symbol}><td>{index + 1}</td><td><Link to={`/symbols/${encodeURIComponent(row.symbol)}`}><strong>{row.symbol}</strong> <ArrowUpRight size={11} /></Link><small>{row.name}</small></td><td><EvidenceStatus row={row} /></td><td><EvidenceBar value={row.rs_3m_percentile} /></td><td><EvidenceBar value={row.leadership_persistence == null ? null : row.leadership_persistence * 100} /><small className="ranking-cell-note">{row.leadership_appearances_13w ?? NOT_AVAILABLE}/{formationCount}</small></td><td>{pct(row.candidate_weight)}</td><td>{row.liquidity_rank == null ? NOT_AVAILABLE : `#${row.liquidity_rank}`}</td><td>{pct(row.rs_3m)}</td><td><strong>{formatNumber(row.technical_context_score, 1)}</strong></td><td>{pct(row.rs_6m)}</td><td>{pct(row.rs_12m)}</td><td>{pct(row.high_52w_distance)}</td><td>{pct(row.trend_distance)}</td><td>{pct(row.slope)}</td><td><StatusPill value={row.ordered_mas ? "Ordered" : row.above_all_mas ? "Above all" : "Mixed"} /></td></tr>)}</tbody></table></div>{rows.length > 100 ? <p className="ranking-footnote">Showing the first 100 of {rows.length}; search or change the screen or sort to inspect another name.</p> : null}
      </Panel>

      <Panel><SectionHeading eyebrow={`${state.data.reversal_watch_count} current observations`} title="Short-term rebound watch — execution fragile" description="A separate observation list for the most negative 5-session returns, both raw and relative to a sufficiently populated sector. It receives no momentum weight. The experiment rotated roughly 85–87% per week and failed the stricter cost gate, so this is a watchlist, not an allocation sleeve." />
        <div className="operator-table-scroll"><table className="operator-table ranking-reversal-table"><thead><tr><th>Symbol</th><th>5D return</th><th>Loss percentile</th><th>Sector-relative 5D</th><th>Sector loss percentile</th><th>Boundary</th></tr></thead><tbody>{reversalRows.map((row) => <tr key={row.symbol}><td><Link to={`/symbols/${encodeURIComponent(row.symbol)}`}><strong>{row.symbol}</strong> <ArrowUpRight size={11} /></Link></td><td>{pct(row.return_5d)}</td><td><EvidenceBar value={row.reversal_5d_percentile} tone="warning" /></td><td>{pct(row.sector_relative_return_5d)}</td><td><EvidenceBar value={row.sector_relative_reversal_percentile} tone="warning" /></td><td><StatusPill value="No weight" tone="warning" /></td></tr>)}</tbody></table></div>
      </Panel>

      <Panel><SectionHeading eyebrow="Preserved product contract" title="Technical context, not validated alpha" description="The original composite remains available in the table and sort controls. It blends percentile ranks of 3m/6m/12m excess return versus SPY (25/25/15%), 52-week-high proximity (15%), four-MA distance (10%), and MA slope (10%). Its failed transition forecast is disclosed rather than hidden." /><div className="ranking-links"><a href={evidenceUrl} target="_blank" rel="noreferrer">Implementation evidence <ExternalLink size={12} /></a><a href={movingAverageStudyUrl} target="_blank" rel="noreferrer">Failed MA transition study <ExternalLink size={12} /></a><a href="https://onlinelibrary.wiley.com/doi/full/10.1111/j.1540-6261.2004.00695.x" target="_blank" rel="noreferrer">52-week high literature <ExternalLink size={12} /></a><a href="https://www.aqr.com/Insights/Research/Journal-Article/Trends-Everywhere" target="_blank" rel="noreferrer">Trend-following reference <ExternalLink size={12} /></a></div></Panel>

      <Panel><SectionHeading eyebrow="Read-only source inventory" title="Research data selection" description="No duplicate ranking table is created. This view selects the disposable universe, identity, membership, and price layers and calculates the latest ranking in memory; Refresh never fetches a provider." /><div className="operator-table-scroll"><table className="operator-table ranking-source-table"><thead><tr><th>Role</th><th>Table</th><th>Selection</th></tr></thead><tbody>{state.data.sources.map((source) => <tr key={source.role}><td>{source.role}</td><td><code>{source.table}</code></td><td>{source.selection}</td></tr>)}</tbody></table></div></Panel>
    </> : null}
  </div>;
}
