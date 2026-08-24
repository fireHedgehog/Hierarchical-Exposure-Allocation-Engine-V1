import { CheckCircle2, Clock3, DatabaseZap, TriangleAlert } from "lucide-react";
import type { DataSource, Snapshot } from "../types";
import { formatNumber, formatPercent, formatTimestamp, humanize, NOT_AVAILABLE, toneForStatus } from "../utils/format";
import { ProvenanceStrip, StatusPill, Unavailable } from "./Ui";

export function DataHealth({
  sources,
  snapshot,
}: {
  sources?: DataSource[] | null;
  snapshot?: Snapshot | null;
}) {
  if (!sources?.length) {
    return (
      <Unavailable
        title="Data-source health not available"
        detail="No persisted source-health records were returned for this snapshot."
      />
    );
  }

  return (
    <div className="data-health">
      <div className="data-health__summary">
        <DatabaseZap aria-hidden="true" />
        <div>
          <strong>{sources.length} registered source{sources.length === 1 ? "" : "s"}</strong>
          <span>Freshness and missingness are evaluated independently.</span>
        </div>
        <StatusPill value={snapshot?.status} />
      </div>

      <div className="source-grid">
        {sources.map((source, index) => {
          const sourceTone = toneForStatus(source.status);
          const healthy = sourceTone === "positive" || sourceTone === "info";
          return (
            <article className="source-card" key={source.id || `${source.name}-${index}`}>
              <div className="source-card__header">
                <span className={`source-card__icon source-card__icon--${sourceTone}`}>
                  {healthy ? <CheckCircle2 aria-hidden="true" /> : <TriangleAlert aria-hidden="true" />}
                </span>
                <div>
                  <h3>{source.name}</h3>
                  <p>{source.dataset || (source.category ? humanize(source.category) : NOT_AVAILABLE)}</p>
                </div>
                <StatusPill value={source.status} />
              </div>
              <dl>
                <div>
                  <dt>Freshness</dt>
                  <dd>{source.freshness || NOT_AVAILABLE}</dd>
                </div>
                <div>
                  <dt>Coverage</dt>
                  <dd>{typeof source.coverage === "number" ? formatPercent(source.coverage) : source.coverage || NOT_AVAILABLE}</dd>
                </div>
                <div>
                  <dt>Missingness</dt>
                  <dd>{formatPercent(source.missingness)}</dd>
                </div>
                <div>
                  <dt><Clock3 aria-hidden="true" size={13} /> Ingested</dt>
                  <dd>{formatTimestamp(source.ingested_at)}</dd>
                </div>
              </dl>
              <div className="source-card__latency">
                <span>Live source</span>
                <b>{source.is_live === null || source.is_live === undefined ? NOT_AVAILABLE : source.is_live ? "Yes" : "No"}</b>
                <span>Ingest latency</span>
                <b>{source.latency_seconds === null || source.latency_seconds === undefined ? NOT_AVAILABLE : `${formatNumber(source.latency_seconds)} sec`}</b>
              </div>
              {source.detail ? <p className="source-card__detail">{source.detail}</p> : null}
              <ProvenanceStrip provenance={source} compact />
            </article>
          );
        })}
      </div>
    </div>
  );
}
