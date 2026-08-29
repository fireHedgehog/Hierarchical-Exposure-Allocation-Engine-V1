import { useMemo, useState } from "react";
import { ArrowUpRight, ExternalLink, RefreshCw, Search } from "lucide-react";
import { Link } from "react-router-dom";
import { endpoints, useApi } from "../api/client";
import { Panel, ResourceState, SectionHeading, StatusPill } from "../components/Ui";
import type { CrossSectionalRankingResponse } from "../types";
import { formatNumber, NOT_AVAILABLE } from "../utils/format";

type SortKey = "score" | "rs_3m" | "rs_6m" | "rs_12m" | "high_52w_distance" | "trend_distance" | "slope" | "median_dollar_volume_21d";
const studyUrl = "https://github.com/fireHedgehog/Hierarchical-Exposure-Allocation-Engine-V1/blob/main/docs/hypotheses/staging_v2/cross-sectional/h-xsec-s2-003-moving-average-state-transition.md";
const pct = (value: number | null) => value == null ? NOT_AVAILABLE : `${value >= 0 ? "+" : ""}${(value * 100).toFixed(1)}%`;

export function CrossSectionalRankingPage() {
  const state = useApi<CrossSectionalRankingResponse>(endpoints.crossSectionalRanking);
  const [screen, setScreen] = useState<"aligned" | "all">("aligned");
  const [sort, setSort] = useState<SortKey>("score");
  const [query, setQuery] = useState("");
  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    return [...(state.data?.rows ?? [])].filter((row) => screen === "all" || row.above_all_mas)
      .filter((row) => !q || row.symbol.toLowerCase().includes(q) || row.name.toLowerCase().includes(q))
      .sort((a, b) => (b[sort] ?? -Infinity) - (a[sort] ?? -Infinity));
  }, [state.data, screen, sort, query]);
  return <div className="workspace ranking-page">
    <header className="workspace-header"><div><p className="eyebrow">Research workspace</p><h1>Cross-sectional ranking</h1><p>Descriptive research version. It ranks the disposable Stage 2 universe; it is not validated alpha, a registered strategy, or a trading recommendation.</p></div><button className="button button--quiet" type="button" onClick={state.reload} disabled={state.loading}><RefreshCw size={15} /> Refresh ranking</button></header>
    <ResourceState loading={state.loading} error={state.error} onRetry={state.reload} resource="cross-sectional ranking" />
    {state.data ? <>
      <div className="ranking-summary"><div><span>Stage 2 members</span><strong>{state.data.member_count}</strong></div><div><span>Eligible histories</span><strong>{state.data.eligible_count}</strong></div><div><span>Latest price date</span><strong>{state.data.latest_price_date || NOT_AVAILABLE}</strong></div><div><span>Model status</span><StatusPill value="Research only" tone="warning" /></div></div>
      <Panel><SectionHeading eyebrow="Read-only source inventory" title="Research data selection" description="No duplicate ranking table is created. This view selects four database layers and calculates the latest ranking in memory." /><div className="operator-table-scroll"><table className="operator-table ranking-source-table"><thead><tr><th>Role</th><th>Table</th><th>Selection</th></tr></thead><tbody>{state.data.sources.map((source) => <tr key={source.role}><td>{source.role}</td><td><code>{source.table}</code></td><td>{source.selection}</td></tr>)}</tbody></table></div></Panel>
      <Panel><SectionHeading eyebrow={`${rows.length} displayed names`} title="Momentum and trend rank" description="Default screen requires price above SMA 20/50/100/200. Score blends percentile ranks: 3m/6m/12m excess return vs SPY (25/25/15%), 52-week-high proximity (15%), four-MA distance (10%), and MA slope (10%)." />
        <div className="ranking-controls"><label><Search size={13} /><input aria-label="Search ranking" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Symbol or company" /></label><select aria-label="Screen" value={screen} onChange={(e) => setScreen(e.target.value as "aligned" | "all")}><option value="aligned">Above all MAs</option><option value="all">All eligible</option></select><select aria-label="Sort ranking" value={sort} onChange={(e) => setSort(e.target.value as SortKey)}><option value="score">Composite score</option><option value="rs_3m">3m vs SPY</option><option value="rs_6m">6m vs SPY</option><option value="rs_12m">12m vs SPY</option><option value="high_52w_distance">52w high proximity</option><option value="trend_distance">MA distance</option><option value="slope">MA slope</option><option value="median_dollar_volume_21d">Dollar volume</option></select></div>
        <div className="operator-table-scroll"><table className="operator-table ranking-table"><thead><tr><th>Rank</th><th>Symbol</th><th>Score</th><th>3m vs SPY</th><th>6m vs SPY</th><th>12m vs SPY</th><th>52w high</th><th>MA distance</th><th>MA slope</th><th>Structure</th></tr></thead><tbody>{rows.slice(0, 100).map((row, index) => <tr key={row.symbol}><td>{index + 1}</td><td><Link to={`/symbols/${encodeURIComponent(row.symbol)}`}><strong>{row.symbol}</strong> <ArrowUpRight size={11} /></Link><small>{row.name}</small></td><td><strong>{formatNumber(row.score, 1)}</strong></td><td>{pct(row.rs_3m)}</td><td>{pct(row.rs_6m)}</td><td>{pct(row.rs_12m)}</td><td>{pct(row.high_52w_distance)}</td><td>{pct(row.trend_distance)}</td><td>{pct(row.slope)}</td><td><StatusPill value={row.ordered_mas ? "Ordered" : row.above_all_mas ? "Above all" : "Mixed"} /></td></tr>)}</tbody></table></div>{rows.length > 100 ? <p className="ranking-footnote">Showing the first 100 of {rows.length}; search or change the sort to inspect another name.</p> : null}
      </Panel>
      <Panel><SectionHeading eyebrow="Honest boundary" title="Why this exists despite a failed experiment" description="Development found no validated forward-return edge for its tested moving-average transitions. A failed forecast does not prevent a transparent descriptive ranking; it prevents us from calling it a proven strategy." /><div className="ranking-links"><a href={studyUrl} target="_blank" rel="noreferrer">Failed internal study <ExternalLink size={12} /></a><a href="https://onlinelibrary.wiley.com/doi/full/10.1111/j.1540-6261.2004.00695.x" target="_blank" rel="noreferrer">52-week high literature <ExternalLink size={12} /></a><a href="https://www.aqr.com/Insights/Research/Journal-Article/Trends-Everywhere" target="_blank" rel="noreferrer">Trend-following reference <ExternalLink size={12} /></a></div></Panel>
    </> : null}
  </div>;
}
