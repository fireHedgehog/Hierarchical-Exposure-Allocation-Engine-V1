import type { ReactNode } from "react";
import { AlertCircle, ChevronRight, Database, RefreshCw } from "lucide-react";
import type { Provenance } from "../types";
import { ApiError } from "../api/client";
import { formatTimestamp, humanize, NOT_AVAILABLE, toneForStatus, type Tone } from "../utils/format";

export function StatusPill({ value, tone }: { value?: string | null; tone?: Tone }) {
  const label = value ? humanize(value) : NOT_AVAILABLE;
  return <span className={`status-pill status-pill--${tone ?? toneForStatus(value)}`}>{label}</span>;
}

/** The -5..+5 conviction scale (conviction_from_composite): equity tilt at
 * |1.0-2.4|, credit spread at |2.5-3.4|, debit spread at |3.5-4.4|, LEAPS at
 * |4.5-5.0|. Shown as a real number, not just its consequence. */
export function ConvictionBadge({ value }: { value?: number | null }) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return <span className="conviction-badge conviction-badge--neutral">{NOT_AVAILABLE}</span>;
  }
  const tone = value > 0.05 ? "positive" : value < -0.05 ? "negative" : "neutral";
  return (
    <span className={`conviction-badge conviction-badge--${tone}`} title="Conviction, -5 (max bearish) to +5 (max bullish)">
      {value > 0 ? "+" : ""}{value.toFixed(1)}
    </span>
  );
}

export function SectionHeading({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow?: string;
  title: string;
  description?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="section-heading">
      <div>
        {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
        <h2>{title}</h2>
        {description ? <div className="section-description">{description}</div> : null}
      </div>
      {action ? <div className="section-action">{action}</div> : null}
    </div>
  );
}

export function Panel({
  children,
  className = "",
  id,
}: {
  children: ReactNode;
  className?: string;
  id?: string;
}) {
  return (
    <section className={`panel ${className}`.trim()} id={id}>
      {children}
    </section>
  );
}

export function Unavailable({
  title = NOT_AVAILABLE,
  detail,
  compact = false,
}: {
  title?: string;
  detail?: string;
  compact?: boolean;
}) {
  return (
    <div className={`unavailable ${compact ? "unavailable--compact" : ""}`}>
      <Database aria-hidden="true" size={compact ? 16 : 22} />
      <div>
        <strong>{title}</strong>
        {detail ? <p>{detail}</p> : null}
      </div>
    </div>
  );
}

export function ResourceState({
  loading,
  error,
  onRetry,
  resource = "data",
}: {
  loading: boolean;
  error: Error | null;
  onRetry?: () => void;
  resource?: string;
}) {
  if (loading) {
    return (
      <div className="resource-state" role="status" aria-live="polite">
        <span className="loading-mark" aria-hidden="true" />
        <div>
          <strong>Loading {resource}</strong>
          <p>Reading the latest persisted state.</p>
        </div>
      </div>
    );
  }

  if (!error) return null;
  const missingIdentity = error instanceof ApiError && new Set(["symbol_not_found", "strategy_not_found", "provider_not_found"]).has(error.code || "");
  const isMissingSymbol = error instanceof ApiError && error.code === "symbol_not_found";
  const isEmpty = error instanceof ApiError && error.status === 404 && (!error.code || error.code === "snapshot_not_found");
  return (
    <div className={`resource-state resource-state--${isEmpty ? "empty" : "error"}`} role="alert">
      <AlertCircle aria-hidden="true" size={22} />
      <div className="resource-state__copy">
        <strong>{isEmpty ? `No ${resource} snapshot` : isMissingSymbol ? "Symbol absent from current snapshot" : missingIdentity ? `${resource} not found` : `Unable to load ${resource}`}</strong>
        <p>
          {isEmpty
            ? "The database has no persisted snapshot for this surface. Demo data must be seeded explicitly."
            : error.message}
        </p>
        {error instanceof ApiError && error.detail ? <small>{error.detail}</small> : null}
      </div>
      {onRetry ? (
        <button className="button button--quiet" type="button" onClick={onRetry}>
          <RefreshCw aria-hidden="true" size={15} />
          Retry
        </button>
      ) : null}
    </div>
  );
}

export function ProvenanceStrip({
  provenance,
  sourceLabel,
  compact = false,
}: {
  provenance?: Provenance | null;
  sourceLabel?: string | null;
  compact?: boolean;
}) {
  const items = [
    { label: "Observed", value: provenance?.observed_at || provenance?.as_of },
    { label: "Available", value: provenance?.available_at },
    { label: "Ingested", value: provenance?.ingested_at },
  ];

  return (
    <div className={`provenance ${compact ? "provenance--compact" : ""}`} aria-label="Data provenance">
      <div className="provenance__source">
        <Database aria-hidden="true" size={14} />
        <span>{sourceLabel || provenance?.source_name || "Persisted database"}</span>
      </div>
      <div className="provenance__times">
        {items.map((item) => (
          <span key={item.label}>
            <b>{item.label}</b> {formatTimestamp(item.value)}
          </span>
        ))}
      </div>
    </div>
  );
}

export function DetailList({ title, items }: { title: string; items?: string[] | null }) {
  if (!items?.length) {
    return <Unavailable title={`${title}: ${NOT_AVAILABLE}`} compact />;
  }
  return (
    <div className="detail-list">
      <h4>{title}</h4>
      <ul>
        {items.map((item, index) => (
          <li key={`${item}-${index}`}>
            <ChevronRight aria-hidden="true" size={14} />
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
