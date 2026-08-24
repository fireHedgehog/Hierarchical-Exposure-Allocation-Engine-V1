import { RefreshCw } from "lucide-react";
import { endpoints, useApi } from "../api/client";
import { CrossSectionMatrix } from "../components/CrossSectionMatrix";
import { DataHealth } from "../components/DataHealth";
import { DecisionHero } from "../components/DecisionHero";
import { DecisionHierarchy } from "../components/DecisionHierarchy";
import { MetricsGrid } from "../components/MetricsGrid";
import { PhilosophyPanel } from "../components/PhilosophyPanel";
import { PositionCandidates } from "../components/PositionCandidates";
import { SnapshotBanner } from "../components/SnapshotBanner";
import { Panel, ResourceState, SectionHeading } from "../components/Ui";
import type { CrossSectionResponse, DeskResponse } from "../types";
import { formatTimestamp } from "../utils/format";

export function DeskPage() {
  const desk = useApi<DeskResponse>(endpoints.deskLatest);
  const crossSection = useApi<CrossSectionResponse>(endpoints.crossSectionLatest);

  const refresh = () => {
    desk.reload();
    crossSection.reload();
  };

  return (
    <div className="workspace desk-page">
      <header className="workspace-header">
        <div>
          <p className="eyebrow">Latest database state</p>
          <h1>Today’s decision</h1>
          <p>
            A top-down trace from the persisted state hypothesis to bounded portfolio and
            instrument proposals.
          </p>
        </div>
        <button className="button button--quiet" type="button" onClick={refresh} disabled={desk.loading || crossSection.loading}>
          <RefreshCw aria-hidden="true" size={15} />
          Refresh snapshot
        </button>
      </header>

      <ResourceState loading={desk.loading} error={desk.error} onRetry={desk.reload} resource="desk" />

      {desk.data ? (
        <>
          <SnapshotBanner snapshot={desk.data.snapshot} />
          <section className="decision-surface" aria-labelledby="today-decision-title">
            <div className="surface-kicker">
              <span>Decision surface</span>
              <span>As of {formatTimestamp(desk.data.snapshot.as_of)}</span>
            </div>
            <h2 className="sr-only" id="today-decision-title">Latest persisted portfolio decision</h2>
            <DecisionHero recommendation={desk.data.recommendation} snapshot={desk.data.snapshot} />
          </section>

          <Panel>
            <SectionHeading
              eyebrow="Implementation review"
              title="Proposed position expressions"
              description="Candidates remain decision-support records. Incomplete market evidence is visible and blocks actionability."
            />
            <PositionCandidates positions={desk.data.position_candidates} />
          </Panel>

          <Panel id="hierarchy" className="panel--hierarchy">
            <SectionHeading
              eyebrow="Allocation engine"
              title="Decision hierarchy"
              description="Every allocation is shown with its incoming lineage, current and target state, contribution, and constraints."
            />
            <DecisionHierarchy regime={desk.data.regime} graph={desk.data.decision_graph} />
          </Panel>

          <Panel className="panel--matrix">
            <SectionHeading
              eyebrow="One layer up"
              title="Cross-sectional evidence"
              description="Relative factor measurements inform instrument selection; color encodes raw rank within each column, not investment merit."
            />
            <ResourceState
              loading={crossSection.loading}
              error={crossSection.error}
              onRetry={crossSection.reload}
              resource="cross-sectional"
            />
            {crossSection.data ? <CrossSectionMatrix data={crossSection.data} /> : null}
          </Panel>

          <Panel>
            <SectionHeading
              eyebrow="Research state"
              title="Evaluation and backtest"
              description="Zeros are retained as zeros; uncalculated fields remain unavailable."
            />
            <MetricsGrid metrics={desk.data.metrics} backtest={desk.data.backtest} />
          </Panel>

          <Panel id="data-health">
            <SectionHeading
              eyebrow="Operational evidence"
              title="Data health and provenance"
              description="Coverage, freshness, and source timestamps are separate from model confidence."
            />
            <DataHealth sources={desk.data.data_sources} snapshot={desk.data.snapshot} />
          </Panel>

          <Panel className="panel--philosophy">
            <SectionHeading
              eyebrow="Database-sourced identity"
              title="Operating philosophy"
              description="The system identity is stored with the snapshot rather than embedded as a frontend conclusion."
            />
            <PhilosophyPanel philosophy={desk.data.philosophy} snapshot={desk.data.snapshot} />
          </Panel>
        </>
      ) : null}
    </div>
  );
}
