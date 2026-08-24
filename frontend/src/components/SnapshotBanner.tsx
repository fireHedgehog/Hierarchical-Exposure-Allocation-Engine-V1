import { AlertTriangle, FlaskConical, Radio, ShieldCheck } from "lucide-react";
import type { Snapshot } from "../types";
import { formatTimestamp, humanize } from "../utils/format";
import { resolveSnapshotPresentation } from "../utils/snapshot";
import { StatusPill } from "./Ui";

export function SnapshotBanner({ snapshot }: { snapshot: Snapshot }) {
  const presentation = resolveSnapshotPresentation(snapshot);
  const {
    displayDataClassification,
    displayMode,
    hasMetadataIssue,
    isDemo,
    isSynthetic,
    isLive,
  } = presentation;

  return (
    <aside className={`snapshot-banner ${isDemo ? "snapshot-banner--demo" : isSynthetic ? "snapshot-banner--synthetic" : ""}`} aria-label="Dataset status">
      <div className="snapshot-banner__icon">
        {isDemo || isSynthetic ? <FlaskConical aria-hidden="true" /> : isLive ? <Radio aria-hidden="true" /> : <ShieldCheck aria-hidden="true" />}
      </div>
      <div className="snapshot-banner__copy">
        <div className="snapshot-banner__labels">
          <strong>
            {humanize(displayMode)}
            {displayDataClassification ? ` · ${humanize(displayDataClassification)} data` : ""}
          </strong>
          <StatusPill value={snapshot.status} />
          {displayDataClassification ? <StatusPill value={displayDataClassification} /> : null}
          {hasMetadataIssue ? <StatusPill value="metadata_issue" tone="negative" /> : null}
          <StatusPill value={isLive ? "live" : "not_live"} tone={isLive ? "positive" : "warning"} />
        </div>
        <p>
          Snapshot <code>{snapshot.id}</code> · as of {formatTimestamp(snapshot.as_of)}
        </p>
        {hasMetadataIssue ? (
          <p className="snapshot-banner__disclaimer">
            <AlertTriangle aria-hidden="true" size={14} /> Snapshot metadata is inconsistent or incomplete; this view is treating it as not live.
          </p>
        ) : null}
        {snapshot.disclaimer ? (
          <p className="snapshot-banner__disclaimer">
            <AlertTriangle aria-hidden="true" size={14} /> {snapshot.disclaimer}
          </p>
        ) : null}
      </div>
    </aside>
  );
}
