import {
  ArrowLeft,
  CalendarClock,
  ChartNoAxesCombined,
  Clock3,
  Gauge,
  History,
  Radar,
  RefreshCw,
  ShieldAlert,
} from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { endpoints, useApi } from "../api/client";
import { BacktestLedger } from "../components/BacktestLedger";
import { DataHealth } from "../components/DataHealth";
import { HierarchyTrace } from "../components/HierarchyTrace";
import { MetricsGrid } from "../components/MetricsGrid";
import { PositionCandidates } from "../components/PositionCandidates";
import { PriceChart } from "../components/PriceChart";
import { SnapshotBanner } from "../components/SnapshotBanner";
import {
  DetailList,
  Panel,
  ProvenanceStrip,
  ResourceState,
  SectionHeading,
  StatusPill,
  Unavailable,
} from "../components/Ui";
import type { MetricDatum, PriceBar, Recommendation, Snapshot, SymbolDetailResponse, SymbolEvent, SymbolSignal } from "../types";
import {
  formatCurrency,
  formatNumber,
  formatPercent,
  formatScalar,
  formatTimestamp,
  humanize,
  NOT_AVAILABLE,
} from "../utils/format";

export function SymbolPage() {
  const { symbol = "" } = useParams();
  const state = useApi<SymbolDetailResponse>(symbol ? endpoints.symbol(symbol) : null);
  const data = state.data;

  return (
    <div className="workspace symbol-page">
      <header className="workspace-header symbol-workspace-header">
        <div>
          <Link className="back-link" to="/symbols"><ArrowLeft aria-hidden="true" size={15} /> Symbol research</Link>
          <div className="symbol-title-line">
            <span className="symbol-monogram">{data?.symbol?.slice(0, 3) || symbol.slice(0, 3).toUpperCase()}</span>
            <div>
              <p className="eyebrow">Persisted symbol workspace</p>
              <h1>{data?.symbol || symbol.toUpperCase() || NOT_AVAILABLE}</h1>
              <p>{data?.name || (state.loading ? "Loading symbol identity…" : NOT_AVAILABLE)}</p>
            </div>
          </div>
        </div>
        <button className="button button--quiet" type="button" onClick={state.reload} disabled={state.loading}>
          <RefreshCw aria-hidden="true" size={15} /> Refresh symbol
        </button>
      </header>

      <ResourceState loading={state.loading} error={state.error} onRetry={state.reload} resource={`symbol ${symbol.toUpperCase()}`} />

      {data ? (
        <>
          {data.snapshot ? <SnapshotBanner snapshot={data.snapshot} /> : (
            <Unavailable title="Snapshot metadata not available" detail="The symbol response has no persisted snapshot identity." />
          )}

          <div className="symbol-overview-grid">
            <Panel className="symbol-identity-panel">
              <div className="identity-status-row">
                <StatusPill value={data.status} />
                <StatusPill value={data.freshness?.status} />
              </div>
              <p>{data.summary || NOT_AVAILABLE}</p>
              <dl className="identity-grid">
                <div><dt>Last database price</dt><dd>{formatCurrency(data.last_price, data.currency || "USD")}</dd></div>
                <div><dt>Price as of</dt><dd>{formatTimestamp(data.price_as_of)}</dd></div>
                <div><dt>Composite score</dt><dd>{formatNumber(data.composite_score)}</dd></div>
                <div><dt>Cross-section rank</dt><dd>{formatNumber(data.rank)}</dd></div>
                <div><dt>Asset type</dt><dd>{data.asset_type || NOT_AVAILABLE}</dd></div>
                <div><dt>Venue</dt><dd>{data.exchange || NOT_AVAILABLE}</dd></div>
              </dl>
              {data.freshness?.summary ? <p className="freshness-note"><Clock3 aria-hidden="true" size={14} />{data.freshness.summary}</p> : null}
              <ProvenanceStrip provenance={data.snapshot} sourceLabel="Symbol snapshot" compact />
            </Panel>

            <SymbolRecommendation recommendation={data.recommendation} snapshot={data.snapshot} />
          </div>

          <CurrentSignal signal={data.current_signal} />

          <Panel className="panel--chart">
            <SectionHeading
              eyebrow="Database market history"
              title={`${data.symbol} price and recorded events`}
              description="Recorded executions, signal observations, and price patterns use distinct annotations. Current proposals are never rendered as fills."
            />
            <PriceChart bars={data.bars} events={data.events} symbol={data.symbol} currency={data.currency} />
            <ProvenanceStrip provenance={latestBar(data.bars)} sourceLabel="Price-bar dataset" compact />
          </Panel>

          <Panel>
            <SectionHeading
              eyebrow="Full history, independent of chart timeframe"
              title="Backtest trade ledger"
              description="Every entry/exit round trip the server's MACD/RSI backtest logged, oldest first. The chart above only draws markers inside the selected timeframe; this table always shows the full history."
            />
            <BacktestLedger events={data.events} currency={data.currency} />
          </Panel>

          <Panel className="panel--trace">
            <SectionHeading
              eyebrow="State to instrument"
              title="Hierarchy trace"
              description="The stored trace lists selected DAG nodes in reading order. Incoming lineage on each card shows the actual edges, including parallel funding and exposure branches."
            />
            <HierarchyTrace trace={data.hierarchy_trace} />
            <ProvenanceStrip provenance={data.snapshot} sourceLabel="Symbol hierarchy snapshot" compact />
          </Panel>

          <Panel>
            <SectionHeading
              eyebrow="Research diagnostics"
              title="Return, IC, decay, and risk-adjusted evidence"
              description="Required diagnostics remain explicitly unavailable until the backend persists a calculated value."
            />
            <CoreDiagnostics metrics={data.metrics} />
            <MetricsGrid metrics={data.metrics} label="Symbol metrics" />
          </Panel>

          <Panel>
            <SectionHeading
              eyebrow="Current implementation review"
              title="Proposed structures"
              description="These are proposal records, never inferred fills or historical positions."
            />
            <PositionCandidates positions={data.position_candidates} title={`${data.symbol} proposals`} />
          </Panel>

          <Panel>
            <SectionHeading
              eyebrow="Audit trail"
              title="Recorded symbol events"
              description="Events are persisted observations. Their type and timestamps do not imply trade execution."
            />
            <EventLedger events={data.events} currency={data.currency} />
          </Panel>

          <Panel id="data-health">
            <SectionHeading
              eyebrow="Symbol provenance"
              title="Data sources and freshness"
              description="Live connectivity, timestamp availability, and coverage are shown independently."
            />
            <DataHealth sources={data.data_sources} snapshot={data.snapshot} />
          </Panel>
        </>
      ) : null}
    </div>
  );
}

function SymbolRecommendation({
  recommendation,
  snapshot,
}: {
  recommendation?: Recommendation | null;
  snapshot?: Snapshot | null;
}) {
  if (!recommendation) {
    return (
      <Panel className="symbol-recommendation">
        <Unavailable title="Symbol recommendation not available" detail="No recommendation record is attached to this symbol." />
      </Panel>
    );
  }
  return (
    <Panel className="symbol-recommendation">
      <div className="symbol-recommendation__topline">
        <div><Gauge aria-hidden="true" size={16} /><span>Latest persisted recommendation</span></div>
        <StatusPill value={recommendation.actionability || recommendation.status} />
      </div>
      <h2>{recommendation.posture ? humanize(recommendation.posture) : NOT_AVAILABLE}</h2>
      <p>{recommendation.summary || NOT_AVAILABLE}</p>
      <dl className="recommendation-allocation">
        <div><dt>Current</dt><dd>{formatPercent(recommendation.current_weight)}</dd></div>
        <div><dt>Target</dt><dd>{formatPercent(recommendation.target_weight)}</dd></div>
        <div className={directionClass(recommendation.delta_weight)}><dt>Delta</dt><dd>{formatPercent(recommendation.delta_weight)}</dd></div>
        <div><dt>Confidence</dt><dd>{formatPercent(recommendation.confidence)}</dd></div>
      </dl>
      <div className="recommendation-review">
        <CalendarClock aria-hidden="true" size={15} />
        <span>Review {formatTimestamp(recommendation.next_review_at)}</span>
      </div>
      <div className="recommendation-reasoning">
        <DetailList title="Rationale" items={recommendation.rationale} />
        <DetailList title="Invalidation" items={recommendation.invalidation} />
      </div>
      <ProvenanceStrip provenance={snapshot ? { ...snapshot, ...recommendation } : recommendation} sourceLabel={snapshot ? `Snapshot ${snapshot.id}` : "Recommendation record"} compact />
    </Panel>
  );
}

function CurrentSignal({ signal }: { signal?: SymbolSignal | null }) {
  const hasSignal = Boolean(signal && signal.status !== "none");
  return (
    <Panel className={`current-signal-panel ${hasSignal ? "current-signal-panel--present" : ""}`}>
      <div className="current-signal-header">
        <div>
          <span className="operator-icon"><Radar aria-hidden="true" size={17} /></span>
          <div><p className="eyebrow">Signal state · separate from allocation</p><h2>Current signal</h2></div>
        </div>
        <StatusPill value={signal?.status || "unavailable"} />
      </div>
      {signal ? (
        <div className="current-signal-body">
          <div className="current-signal-callout">
            <strong>{signal.status === "none" ? "None" : signal.label || humanize(signal.status)}</strong>
            <span>{signal.rationale || (signal.status === "none" ? "No active signal is persisted for this symbol." : "No signal rationale is persisted.")}</span>
          </div>
          <dl>
            <div><dt>Direction</dt><dd>{signal.direction ? humanize(signal.direction) : NOT_AVAILABLE}</dd></div>
            <div><dt>Strength</dt><dd>{formatPercent(signal.strength)}</dd></div>
            <div><dt>Source node</dt><dd>{signal.source_node_id || NOT_AVAILABLE}</dd></div>
            <div><dt>Observed</dt><dd>{formatTimestamp(signal.observed_at)}</dd></div>
          </dl>
          <ProvenanceStrip provenance={signal} compact />
        </div>
      ) : <Unavailable title="Current signal unavailable" detail="No signal-state record is attached to this symbol. This does not imply a neutral signal." compact />}
    </Panel>
  );
}

function CoreDiagnostics({ metrics }: { metrics?: MetricDatum[] | null }) {
  const definitions = [
    { label: "Return", aliases: ["total_return", "return", "cagr", "annualized_return"] },
    { label: "Information coefficient", aliases: ["information_coefficient", "ic", "mean_ic"] },
    { label: "Signal decay", aliases: ["signal_decay", "decay", "decay_half_life"] },
    { label: "Sharpe ratio", aliases: ["sharpe", "sharpe_ratio"] },
  ];
  return (
    <div className="core-diagnostics">
      {definitions.map((definition) => {
        const metric = metrics?.find((item) => definition.aliases.includes(item.key.toLowerCase()));
        return (
          <article key={definition.label}>
            <div><ChartNoAxesCombined aria-hidden="true" size={15} /><span>{definition.label}</span></div>
            <strong>{metric ? metric.display_value || formatScalar(metric.value, metric.unit) : NOT_AVAILABLE}</strong>
            <small>{metric?.description || "No calculated database value is present."}</small>
            {metric?.status ? <StatusPill value={metric.status} /> : null}
          </article>
        );
      })}
    </div>
  );
}

function EventLedger({ events, currency }: { events?: SymbolEvent[] | null; currency?: string | null }) {
  if (!events?.length) {
    return <Unavailable title="Recorded events not available" detail="No event rows are persisted for this symbol." />;
  }
  return (
    <div className="event-ledger">
      {events.map((event, index) => (
        <article key={event.id || `${event.time}-${event.type}-${index}`}>
          <div className="event-ledger__rail"><History aria-hidden="true" size={15} /><span /></div>
          <div className="event-ledger__body">
            <div className="event-ledger__topline">
              <div><h3>{event.label}</h3><StatusPill value={event.type} />{event.status ? <StatusPill value={event.status} /> : null}</div>
              <time>{formatTimestamp(String(event.time))}</time>
            </div>
            <p>{event.detail || NOT_AVAILABLE}</p>
            <div className="event-ledger__meta">
              <span>Recorded price <b>{formatCurrency(event.price, currency || "USD")}</b></span>
              <span>Source <b>{event.source_key || NOT_AVAILABLE}</b></span>
            </div>
            <ProvenanceStrip provenance={event} compact />
          </div>
        </article>
      ))}
    </div>
  );
}

function directionClass(value: number | null | undefined): string {
  if (value === null || value === undefined) return "";
  return `direction-${value > 0 ? "up" : value < 0 ? "down" : "flat"}`;
}

function latestBar(bars: SymbolDetailResponse["bars"]): PriceBar | null {
  return bars?.length ? bars[bars.length - 1] : null;
}
