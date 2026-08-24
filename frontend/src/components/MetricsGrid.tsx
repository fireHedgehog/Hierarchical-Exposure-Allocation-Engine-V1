import { Activity, CircleHelp } from "lucide-react";
import type { BacktestSummary, MetricDatum } from "../types";
import { formatScalar, NOT_AVAILABLE } from "../utils/format";
import { ProvenanceStrip, StatusPill, Unavailable } from "./Ui";

export function MetricsGrid({
  metrics,
  backtest,
  label = "Evaluation metrics",
}: {
  metrics?: MetricDatum[] | null;
  backtest?: BacktestSummary | null;
  label?: string;
}) {
  const deskMetrics = metrics ?? [];
  const backtestMetrics = backtest?.metrics ?? [];

  if (!deskMetrics.length && !backtest) {
    return <Unavailable title={`${label} not available`} detail="No persisted evaluation metrics were returned." />;
  }

  return (
    <div className="metrics-block">
      {backtest ? (
        <div className="backtest-context">
          <div>
            <Activity aria-hidden="true" size={17} />
            <span>Evaluation context</span>
          </div>
          <strong>{backtest.title || backtest.label || NOT_AVAILABLE}</strong>
          <StatusPill value={backtest.status} />
          <p>{backtest.summary || NOT_AVAILABLE}</p>
          {backtest.methodology ? <small>{backtest.methodology}</small> : null}
          <ProvenanceStrip provenance={backtest} compact />
        </div>
      ) : null}

      {deskMetrics.length ? <MetricGroup title={backtest ? "Desk metrics" : label} metrics={deskMetrics} /> : null}
      {backtestMetrics.length ? (
        <MetricGroup title="Backtest metrics" metrics={backtestMetrics} />
      ) : backtest ? (
        <Unavailable compact title="Backtest metrics not available" detail="The evaluation context has no persisted metric rows." />
      ) : null}
    </div>
  );
}

function MetricGroup({ title, metrics }: { title: string; metrics: MetricDatum[] }) {
  return (
    <section className="metrics-group" aria-label={title}>
      <p className="metrics-group__label">{title}</p>
      <div className="metrics-grid">
        {metrics.map((metric) => (
          <article className="metric-card" key={metric.key}>
            <div className="metric-card__topline">
              <span>{metric.label}</span>
              {metric.description ? (
                <span className="metric-help" title={metric.description} aria-label={metric.description}>
                  <CircleHelp aria-hidden="true" size={14} />
                </span>
              ) : null}
            </div>
            <strong>{metric.display_value || formatScalar(metric.value, metric.unit)}</strong>
            <div className="metric-card__footer">
              <span>{metric.period || NOT_AVAILABLE}</span>
              <StatusPill value={metric.status} />
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
