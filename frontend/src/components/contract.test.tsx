import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import type { BacktestSummary, CrossSectionResponse, DecisionGraph, MetricDatum, Philosophy, PositionCandidate, Recommendation, Regime, Snapshot } from "../types";
import { CrossSectionMatrix } from "./CrossSectionMatrix";
import { DecisionHero, resolveExposureDelta } from "./DecisionHero";
import { DecisionHierarchy } from "./DecisionHierarchy";
import { MetricsGrid } from "./MetricsGrid";
import { PhilosophyPanel } from "./PhilosophyPanel";
import { isPositionReady, PositionCandidates } from "./PositionCandidates";
import { ProvenanceStrip } from "./Ui";

const snapshot: Snapshot = {
  id: "fixture-1",
  as_of: "2026-08-21T20:00:00Z",
  status: "demo_not_live",
  mode: "demo",
  data_classification: "synthetic",
  is_live: false,
};

describe("canonical backend contract rendering", () => {
  it("renders philosophy sections and structured DAG observations", () => {
    const philosophy: Philosophy = {
      sections: [{ key: "uncertainty", title: "Uncertainty remains visible", body: "Missing stays null.", principle: "Unknown is not zero." }],
    };
    const regime: Regime = {
      label: "Mixed",
      filters: [{ name: "Breadth", value: 0.5, threshold: 0.55, status: "caution", source_key: "fixture", available_at: snapshot.as_of }],
    };
    const graph: DecisionGraph = {
      nodes: [
        { id: "desk", type: "desk", label: "Desk", summary: "Root", current_value: 0.6, target_value: 0.55, value_unit: "net_exposure" },
        { id: "risk", parent_id: "desk", type: "risk_budget", label: "Risk budget", summary: "Bounded", current_value: 0.75, target_value: 0.7, value_unit: "gross_exposure" },
      ],
      edges: [{ id: "desk-risk", from: "desk", to: "risk", relation: "bounded_by", weight: 0.3, rationale: "Confidence caps risk." }],
      observations: [{ id: "obs", node_id: "risk", label: "Live option chain", value: null, status: "unavailable", detail: "Not connected." }],
    };
    const markup = renderToStaticMarkup(
      <>
        <PhilosophyPanel philosophy={philosophy} snapshot={snapshot} />
        <DecisionHierarchy regime={regime} graph={graph} />
      </>,
    );
    expect(markup).toContain("Uncertainty remains visible");
    expect(markup).toContain("Bounded By");
    expect(markup).toContain("Confidence caps risk.");
    expect(markup).toContain("Live option chain");
    expect(markup).toContain("Not available");
  });

  it("joins regime weights to factors by stable key instead of display name", () => {
    const regime: Regime = {
      label: "Mixed",
      filters: [{ key: "employment", name: "Employment growth", value: 0, threshold: 0, status: "pass" }],
      weights: [{ key: "employment", name: "Employment", value: 1 / 18, unit: "fraction" }],
      contributions: [{ key: "employment", name: "Employment growth", value: 0.2, direction: "positive" }],
    };

    const markup = renderToStaticMarkup(<DecisionHierarchy regime={regime} graph={{ nodes: [], edges: [] }} />);

    expect(markup).toContain("Employment growth");
    expect(markup).toContain("5.6%");
    expect(markup).toContain("Positive");
  });

  it("renders object blockers, nested greeks, and matrix provenance", () => {
    const position: PositionCandidate = {
      id: "spread",
      symbol: "IWM",
      allocation_basis: "premium_budget",
      input_completeness_scope: "live_market_data",
      market_data_complete: false,
      blockers: [{ key: "chain", label: "Live chain", detail: "Required", resolved: false }],
      greeks: { delta: { value: null, unit: "per_contract" } },
      legs: [{ action: "buy", symbol: "IWM", instrument_type: "option", option_type: "call", bid: null }],
    };
    const matrix: CrossSectionResponse = {
      snapshot,
      dimensions: { columns: [{ key: "quality", label: "Quality", unit: "score_0_to_1", weight: 0.2 }] },
      rows: [{ symbol: "IWM", values: { quality: 0.4 }, quality: { quality: "available" }, provenance: { quality: { source_key: "fixture", available_at: snapshot.as_of } } }],
      legend: [{ legend_key: "higher", label: "Higher score" }],
    };
    const markup = renderToStaticMarkup(
      <MemoryRouter>
        <PositionCandidates positions={[position]} />
        <CrossSectionMatrix data={matrix} />
      </MemoryRouter>,
    );
    expect(markup).toContain("Live chain");
    expect(markup).toContain("Allocation basis:");
    expect(markup).toContain("Premium Budget");
    expect(markup).toContain("Live market data complete: No");
    expect(markup).toContain("Type Call");
    expect(markup).toContain("Weight 20%");
    expect(markup).toContain("fixture");
    expect(markup).toContain("Higher score");
  });

  it("fails position readiness closed for unknown completeness and blocking states", () => {
    const position: PositionCandidate = {
      id: "unknown-inputs",
      symbol: "SPY",
      actionability: "blocked",
      market_data_complete: null,
      blockers: [],
    };
    const markup = renderToStaticMarkup(
      <MemoryRouter>
        <PositionCandidates positions={[position]} />
      </MemoryRouter>,
    );

    expect(isPositionReady(position)).toBe(false);
    expect(isPositionReady({ ...position, market_data_complete: true, actionability: "review_only" })).toBe(false);
    expect(isPositionReady({ ...position, market_data_complete: true, actionability: "unavailable" })).toBe(false);
    expect(isPositionReady({ ...position, market_data_complete: true, actionability: "simulation_ready", status: "blocked" })).toBe(false);
    expect(markup).toContain("position-card position-card--blocked");
    expect(markup).toContain("actionability actionability--blocked");
    expect(markup).toContain("Not actionable from this snapshot");
    expect(markup).toContain("Inputs complete: Not available");
    expect(markup).not.toContain("actionability--ready");
  });

  it("keeps optional unresolved blockers visible without suppressing explicit simulation readiness", () => {
    const position: PositionCandidate = {
      id: "simulation",
      symbol: "TLT",
      actionability: "simulation_ready",
      status: "synthetic_simulation_ready",
      market_data_complete: true,
      blockers: [{ key: "approval", label: "Optional review", required: false, resolved: false }],
    };
    const markup = renderToStaticMarkup(
      <MemoryRouter>
        <PositionCandidates positions={[position]} />
      </MemoryRouter>,
    );

    expect(isPositionReady(position)).toBe(true);
    expect(markup).toContain("actionability actionability--ready");
    expect(markup).toContain("Optional review");
  });

  it("renders desk and backtest metrics as distinct persisted groups", () => {
    const metrics: MetricDatum[] = [
      { key: "net_exposure", label: "Net exposure", value: 0.55, unit: "fraction", status: "available" },
    ];
    const backtest: BacktestSummary = {
      title: "Point-in-time evaluation",
      status: "not_run",
      metrics: [{ key: "sharpe", label: "Sharpe ratio", value: null, status: "unavailable" }],
    };
    const markup = renderToStaticMarkup(<MetricsGrid metrics={metrics} backtest={backtest} />);
    expect(markup).toContain("Desk metrics");
    expect(markup).toContain("Net exposure");
    expect(markup).toContain("Backtest metrics");
    expect(markup).toContain("Sharpe ratio");
    expect(markup).toContain("Not available");
  });

  it("keeps unknown confidence unmeasured and prefers persisted exposure deltas", () => {
    const recommendation: Recommendation = {
      posture: "Measured",
      confidence: null,
      current_net_exposure: 0.1,
      target_net_exposure: 0.8,
      delta_net_exposure: 0.02,
      current_gross_exposure: 0.2,
      target_gross_exposure: 0.9,
      delta_gross_exposure: 0,
    };
    const markup = renderToStaticMarkup(<DecisionHero recommendation={recommendation} snapshot={snapshot} />);

    expect(markup).toContain("confidence-dial__graphic--unknown");
    expect(markup).toContain("Six-month adverse frequency unavailable");
    expect(markup).not.toContain("--confidence:");
    expect(markup).toContain('<span class="exposure-delta direction-up"><small>Delta</small><b>2%</b></span>');
    expect(markup).toContain('<span class="exposure-delta direction-flat"><small>Delta</small><b>0%</b></span>');
    expect(markup).not.toContain("<small>Delta</small><b>70%</b>");
    expect(resolveExposureDelta(undefined, 0.1, 0.8)).toBeCloseTo(0.7);
    expect(resolveExposureDelta(null, 0.1, 0.8)).toBeNull();
    expect(resolveExposureDelta(0, 0.1, 0.8)).toBe(0);
  });

  it("does not substitute record creation time for unknown market-data provenance", () => {
    const markup = renderToStaticMarkup(
      <ProvenanceStrip provenance={{ as_of: snapshot.as_of, created_at: "2099-12-31T23:59:59Z" }} />,
    );

    expect(markup).toContain("<b>Observed</b>");
    expect(markup).toContain("<b>Available</b> Not available");
    expect(markup).toContain("<b>Ingested</b> Not available");
    expect(markup).not.toContain("2099");
  });
});
