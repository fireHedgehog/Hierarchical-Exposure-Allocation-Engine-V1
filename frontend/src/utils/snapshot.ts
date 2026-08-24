import type { Snapshot } from "../types";

export interface SnapshotPresentation {
  displayMode: string;
  displayDataClassification: string | null;
  isDemo: boolean;
  isSynthetic: boolean;
  isLive: boolean;
  hasMetadataIssue: boolean;
}

function normalizeToken(value: string | null | undefined): string {
  return value?.trim().toLowerCase() ?? "";
}

/**
 * Resolve safety-sensitive snapshot labels from all redundant provenance fields.
 *
 * Demo or synthetic evidence wins over a live flag, but those concepts remain
 * distinct. A live presentation additionally requires an explicit non-demo flag
 * and a known, non-synthetic classification so incomplete claims fail closed.
 */
export function resolveSnapshotPresentation(snapshot: Snapshot): SnapshotPresentation {
  const mode = normalizeToken(snapshot.mode);
  const dataClassification = normalizeToken(snapshot.data_classification);
  const modeSaysDemo = mode === "demo";
  const classificationSaysSynthetic = dataClassification === "synthetic";
  const flagSaysDemo = snapshot.is_demo === true;
  const isDemo = flagSaysDemo || modeSaysDemo;
  const isSynthetic = classificationSaysSynthetic;
  const requestedLive = snapshot.is_live === true;
  const hasCompleteNonDemoMetadata = snapshot.is_demo === false && dataClassification.length > 0;

  const explicitDemoFlagDisagrees = snapshot.is_demo === false && modeSaysDemo;
  const liveModeDisagrees = mode === "live"
    && (!requestedLive || isDemo || isSynthetic);
  const unsafeLiveClaim = requestedLive
    && (isDemo || isSynthetic || !hasCompleteNonDemoMetadata);
  const hasMetadataIssue = explicitDemoFlagDisagrees
    || liveModeDisagrees
    || unsafeLiveClaim;

  return {
    displayMode: isDemo ? "demo" : snapshot.mode,
    displayDataClassification: snapshot.data_classification ?? null,
    isDemo,
    isSynthetic,
    isLive: requestedLive && !isDemo && !isSynthetic && hasCompleteNonDemoMetadata && !hasMetadataIssue,
    hasMetadataIssue,
  };
}

export function snapshotRunState(presentation: SnapshotPresentation): string {
  if (presentation.isDemo && presentation.isSynthetic) return "Demo · synthetic · not live";
  if (presentation.isDemo) return "Demo · not live";
  if (presentation.isSynthetic) return "Synthetic data · not live";
  if (presentation.isLive) return "Live data";
  if (presentation.hasMetadataIssue) return "Not live · metadata issue";
  return "Not live";
}
