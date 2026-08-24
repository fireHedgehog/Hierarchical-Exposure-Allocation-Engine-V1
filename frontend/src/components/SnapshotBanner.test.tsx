import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { Snapshot } from "../types";
import { resolveSnapshotPresentation, snapshotRunState } from "../utils/snapshot";
import { SnapshotBanner } from "./SnapshotBanner";

const baseSnapshot: Snapshot = {
  id: "snapshot-honesty-fixture",
  as_of: "2026-08-24T00:00:00Z",
  status: "available",
  mode: "live",
  data_classification: "real",
  is_live: true,
  is_demo: false,
};

describe("SnapshotBanner", () => {
  it("lets an explicit demo flag override contradictory live metadata", () => {
    const snapshot = { ...baseSnapshot, is_demo: true };
    const presentation = resolveSnapshotPresentation(snapshot);
    const markup = renderToStaticMarkup(<SnapshotBanner snapshot={snapshot} />);

    expect(presentation).toMatchObject({
      displayMode: "demo",
      displayDataClassification: "real",
      isDemo: true,
      isSynthetic: false,
      isLive: false,
      hasMetadataIssue: true,
    });
    expect(snapshotRunState(presentation)).toBe("Demo · not live");
    expect(markup).toContain("snapshot-banner snapshot-banner--demo");
    expect(markup).toContain("Demo · Real data");
    expect(markup).toContain("Metadata Issue");
    expect(markup).toContain("Not Live");
    expect(markup).toContain("this view is treating it as not live");
    expect(markup).not.toContain(">Live</span>");
  });

  it("suppresses a live claim when another demo marker contradicts it", () => {
    const snapshot: Snapshot = {
      ...baseSnapshot,
      mode: "demo",
      data_classification: "synthetic",
      is_demo: false,
    };
    const presentation = resolveSnapshotPresentation(snapshot);
    const markup = renderToStaticMarkup(<SnapshotBanner snapshot={snapshot} />);

    expect(presentation.isDemo).toBe(true);
    expect(presentation.isSynthetic).toBe(true);
    expect(presentation.isLive).toBe(false);
    expect(presentation.hasMetadataIssue).toBe(true);
    expect(markup).toContain("Demo · Synthetic data");
    expect(markup).toContain("Not Live");
    expect(markup).not.toContain(">Live</span>");
  });

  it("fails closed when a claimed-live payload omits the demo safety flag", () => {
    const snapshot: Snapshot = { ...baseSnapshot, is_demo: undefined };
    const presentation = resolveSnapshotPresentation(snapshot);

    expect(presentation.isDemo).toBe(false);
    expect(presentation.isSynthetic).toBe(false);
    expect(presentation.isLive).toBe(false);
    expect(presentation.hasMetadataIssue).toBe(true);
    expect(snapshotRunState(presentation)).toBe("Not live · metadata issue");
  });

  it("preserves the live presentation for complete, internally consistent metadata", () => {
    const presentation = resolveSnapshotPresentation(baseSnapshot);
    const markup = renderToStaticMarkup(<SnapshotBanner snapshot={baseSnapshot} />);

    expect(presentation).toMatchObject({
      displayMode: "live",
      displayDataClassification: "real",
      isDemo: false,
      isSynthetic: false,
      isLive: true,
      hasMetadataIssue: false,
    });
    expect(snapshotRunState(presentation)).toBe("Live data");
    expect(markup).toContain("Live · Real data");
    expect(markup).toContain(">Live</span>");
    expect(markup).not.toContain("Metadata Issue");
    expect(markup).not.toContain("Not Live");
  });

  it("keeps a synthetic simulation distinct from a demo", () => {
    const snapshot: Snapshot = {
      ...baseSnapshot,
      mode: "simulation",
      data_classification: "synthetic",
      is_live: false,
      is_demo: false,
    };
    const presentation = resolveSnapshotPresentation(snapshot);
    const markup = renderToStaticMarkup(<SnapshotBanner snapshot={snapshot} />);

    expect(presentation).toMatchObject({
      displayMode: "simulation",
      displayDataClassification: "synthetic",
      isDemo: false,
      isSynthetic: true,
      isLive: false,
      hasMetadataIssue: false,
    });
    expect(snapshotRunState(presentation)).toBe("Synthetic data · not live");
    expect(markup).toContain("snapshot-banner snapshot-banner--synthetic");
    expect(markup).toContain("Simulation · Synthetic data");
    expect(markup).not.toContain("Metadata Issue");
  });
});
