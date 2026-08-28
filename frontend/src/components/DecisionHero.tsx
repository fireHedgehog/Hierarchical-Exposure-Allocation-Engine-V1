import { ArrowRight, CalendarClock, Crosshair, Gauge, ShieldAlert, Sparkles } from "lucide-react";
import type { Recommendation, Snapshot } from "../types";
import { deltaBetween, formatPercent, formatTimestamp, NOT_AVAILABLE } from "../utils/format";
import { DetailList, ProvenanceStrip, StatusPill, Unavailable } from "./Ui";

export function DecisionHero({
  recommendation,
  snapshot,
}: {
  recommendation?: Recommendation | null;
  snapshot: Snapshot;
}) {
  if (!recommendation) {
    return (
      <div className="decision-hero decision-hero--empty">
        <Unavailable
          title="Today’s decision is not available"
          detail="This snapshot contains no persisted portfolio recommendation."
        />
      </div>
    );
  }

  const netDelta = resolveExposureDelta(
    recommendation.delta_net_exposure,
    recommendation.current_net_exposure,
    recommendation.target_net_exposure,
  );
  const grossDelta = resolveExposureDelta(
    recommendation.delta_gross_exposure,
    recommendation.current_gross_exposure,
    recommendation.target_gross_exposure,
  );
  const confidenceAvailable = typeof recommendation.confidence === "number" && Number.isFinite(recommendation.confidence);

  return (
    <div className="decision-hero">
      <div className="decision-hero__main">
        <div className="decision-hero__topline">
          <div>
            <Sparkles aria-hidden="true" size={15} />
            <span>Latest persisted portfolio decision</span>
          </div>
          {recommendation.status ? <StatusPill value={recommendation.status} /> : null}
        </div>
        <p className="eyebrow">Today’s posture</p>
        <h2>{recommendation.posture || NOT_AVAILABLE}</h2>
        <p className="decision-hero__summary">{recommendation.summary || NOT_AVAILABLE}</p>
        {recommendation.change_summary ? (
          <div className="change-summary">
            <Crosshair aria-hidden="true" size={17} />
            <span>{recommendation.change_summary}</span>
          </div>
        ) : null}

        <div className="exposure-board" aria-label="Current and target exposures">
          <ExposureLine
            label="Net exposure"
            current={recommendation.current_net_exposure}
            target={recommendation.target_net_exposure}
            delta={netDelta}
          />
          <ExposureLine
            label="Gross exposure"
            current={recommendation.current_gross_exposure}
            target={recommendation.target_gross_exposure}
            delta={grossDelta}
          />
        </div>
      </div>

      <aside className="decision-hero__aside">
        <div className="confidence-dial">
          <div
            className={`confidence-dial__graphic ${confidenceAvailable ? "" : "confidence-dial__graphic--unknown"}`.trim()}
            style={confidenceAvailable ? { "--confidence": recommendation.confidence } as React.CSSProperties : undefined}
            aria-label={confidenceAvailable ? `Six-month adverse frequency ${formatPercent(recommendation.confidence)}` : "Six-month adverse frequency unavailable"}
          >
            <span>
              <Gauge aria-hidden="true" size={18} />
              {formatPercent(recommendation.confidence)}
            </span>
          </div>
          <div>
            <strong>6M adverse frequency</strong>
            <span>Historical reference used by staging sizing.</span>
          </div>
        </div>

        <div className="review-time">
          <CalendarClock aria-hidden="true" size={17} />
          <div>
            <span>Next review</span>
            <strong>{formatTimestamp(recommendation.next_review_at)}</strong>
          </div>
        </div>

        <div className="decision-why">
          <DetailList title="Rationale" items={recommendation.rationale} />
          <div className="invalidation-block">
            <div>
              <ShieldAlert aria-hidden="true" size={16} />
              <h4>Invalidation</h4>
            </div>
            {recommendation.invalidation?.length ? (
              <ul>{recommendation.invalidation.map((item) => <li key={item}>{item}</li>)}</ul>
            ) : (
              <Unavailable compact />
            )}
          </div>
        </div>
        <ProvenanceStrip provenance={{ ...snapshot, ...recommendation }} sourceLabel={`Decision snapshot ${snapshot.id}`} compact />
      </aside>
    </div>
  );
}

export function resolveExposureDelta(
  persisted: number | null | undefined,
  current: number | null | undefined,
  target: number | null | undefined,
): number | null {
  return persisted !== undefined ? persisted : deltaBetween(current, target);
}

function ExposureLine({
  label,
  current,
  target,
  delta,
}: {
  label: string;
  current?: number | null;
  target?: number | null;
  delta?: number | null;
}) {
  const deltaDirection = delta === null || delta === undefined ? "unknown" : delta > 0 ? "up" : delta < 0 ? "down" : "flat";
  return (
    <div className="exposure-line">
      <strong>{label}</strong>
      <div>
        <span>
          <small>Current</small>
          <b>{formatPercent(current)}</b>
        </span>
        <ArrowRight aria-hidden="true" />
        <span className="exposure-target">
          <small>Target</small>
          <b>{formatPercent(target)}</b>
        </span>
        <span className={`exposure-delta direction-${deltaDirection}`}>
          <small>Delta</small>
          <b>{formatPercent(delta)}</b>
        </span>
      </div>
    </div>
  );
}
