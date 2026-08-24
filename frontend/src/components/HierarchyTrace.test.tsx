import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { HierarchyTraceItem } from "../types";
import { HierarchyTrace } from "./HierarchyTrace";

describe("HierarchyTrace", () => {
  it("renders actual incoming DAG lineage without implying list adjacency is a chain", () => {
    const trace: HierarchyTraceItem[] = [
      { level: "desk", node_id: "desk", label: "Desk allocation", incoming_edges: [] },
      {
        level: "exposure",
        node_id: "duration",
        label: "Long-duration Treasuries",
        parent_node_id: "defensive_family",
        parent_label: "Defensive diversifiers",
        incoming_edges: [{
          from_node_id: "defensive_family",
          from_label: "Defensive diversifiers",
          relation: "expresses_as",
          weight: 0.1,
        }],
      },
      {
        level: "funding_family",
        node_id: "convex_family",
        label: "Convex overlays",
        parent_node_id: "risk_budget",
        parent_label: "Risk budget",
        incoming_edges: [{
          from_node_id: "risk_budget",
          from_label: "Risk budget",
          relation: "reserves_for",
          weight: 0.08,
        }],
      },
      {
        level: "instrument",
        node_id: "tlt_spread",
        label: "TLT call spread simulation",
        parent_node_id: "duration",
        parent_label: "Long-duration Treasuries",
        incoming_edges: [
          {
            from_node_id: "duration",
            from_label: "Long-duration Treasuries",
            relation: "candidate_instrument",
            weight: 1,
          },
          {
            from_node_id: "convex_family",
            from_label: "Convex overlays",
            relation: "funds_defined_risk_overlay",
            weight: 0.5,
          },
        ],
      },
    ];

    const markup = renderToStaticMarkup(<HierarchyTrace trace={trace} />);

    expect(markup).toContain("adjacent cards are not implied to be parent and child");
    expect(markup).toContain("Long-duration Treasuries");
    expect(markup).toContain("Convex overlays");
    expect(markup).toContain("Funds Defined Risk Overlay");
    expect(markup).toContain("Edge weight 50%");
    expect(markup).not.toContain("trace-arrow");
  });
});
