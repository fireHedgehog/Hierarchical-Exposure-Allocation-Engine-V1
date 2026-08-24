import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import type { ProductReadiness, ProductReadinessGate } from "../types";
import { ProductReadinessPanel } from "./ProductReadinessPanel";

const macroGate: ProductReadinessGate = {
  key: "real_macro_dataset",
  milestone_key: "real_regime",
  name: "Real macro dataset",
  layer: "data",
  description: "Require a sealed real macro dataset before publishing a regime.",
  status: "action_required",
  acceptance_criterion: "A sealed real dataset contains validated FRED/ALFRED vintage observations.",
  evaluator_key: "real_macro_dataset_v1",
  next_action: "Run the first real macro ingestion and validation slice.",
  target_route: "/operations/data",
  sort_order: 10,
  dependencies: ["fred_access"],
  blocked_by: [],
  evidence: [
    {
      kind: "dataset_snapshot",
      record_id: "demo-market-2026-08-21-v3",
      status: "non_qualifying",
      observed_at: "2026-08-21T20:00:00Z",
      summary: "The latest sealed dataset is explicitly synthetic.",
    },
  ],
};

function renderPanel(readiness?: ProductReadiness | null): string {
  return renderToStaticMarkup(
    <MemoryRouter initialEntries={["/operations"]}>
      <ProductReadinessPanel readiness={readiness} />
    </MemoryRouter>,
  );
}

describe("demo to real readiness presentation", () => {
  it("orders milestones and gates while exposing criteria, evidence, blockers, and actions", () => {
    const readiness: ProductReadiness = {
      summary: {
        milestones_total: 2,
        milestones_passed: 0,
        gates_total: 3,
        gates_passed: 1,
        current_gate_key: "real_macro_dataset",
        current_action: "Create the first qualifying real dataset.",
        target_route: "/operations/data",
      },
      milestones: [
        {
          key: "single_stock_discovery",
          name: "Single-stock discovery",
          description: "Rank point-in-time eligible stocks.",
          status: "blocked",
          sort_order: 20,
          gates_total: 1,
          gates_passed: 0,
          current_gate_key: null,
        },
        {
          key: "real_regime",
          name: "Real regime",
          description: "Replace the synthetic macro state with sealed real evidence.",
          status: "action_required",
          sort_order: 10,
          gates_total: 2,
          gates_passed: 1,
          current_gate_key: "real_macro_dataset",
        },
      ],
      gates: [
        {
          key: "stock_universe",
          milestone_key: "single_stock_discovery",
          name: "Point-in-time stock universe",
          layer: "universe",
          description: "Preserve historical eligibility and exclusions.",
          status: "blocked",
          acceptance_criterion: "A versioned universe evaluation retains included and excluded securities.",
          evaluator_key: "stock_universe_v1",
          next_action: "Connect the security-master adapter.",
          target_route: "/operations/credentials",
          sort_order: 10,
          dependencies: ["real_macro_dataset", "market_reference_adapter"],
          blocked_by: ["market_reference_adapter"],
          evidence: [],
        },
        macroGate,
        {
          key: "fred_access",
          milestone_key: "real_regime",
          name: "FRED access",
          layer: "provider_access",
          description: "Verify the configured FRED key.",
          status: "passed",
          acceptance_criterion: "The current FRED credential has a qualifying healthy verification.",
          evaluator_key: "fred_access_v1",
          next_action: "Proceed to real ingestion.",
          target_route: "/operations/credentials",
          sort_order: 5,
          dependencies: [],
          blocked_by: [],
          evidence: [{ kind: "provider_verification", record_id: "verify-42", status: "qualifying", observed_at: "2026-08-24T01:00:00Z", summary: "FRED access is healthy." }],
        },
      ],
    };

    const markup = renderPanel(readiness);

    expect(markup).toContain("Demo → real readiness");
    expect(markup.indexOf("Real regime")).toBeLessThan(markup.indexOf("Single-stock discovery"));
    expect(markup.indexOf("FRED access")).toBeLessThan(markup.indexOf("Real macro dataset"));
    expect(markup).toContain("A sealed real dataset contains validated FRED/ALFRED vintage observations.");
    expect(markup).toContain("demo-market-2026-08-21-v3");
    expect(markup).toContain("Non Qualifying");
    expect(markup).toContain("market_reference_adapter");
    expect(markup).toContain('href="/operations/data"');
    expect(markup).toContain("Current gate");
    expect(markup.match(/<details open=""/g)).toHaveLength(1);
    expect(markup).not.toContain("progressbar");
    expect(markup).not.toContain("%");
  });

  it("does not infer readiness when the API contract is absent or contains no milestones", () => {
    const absent = renderPanel(null);
    expect(absent).toContain("Product readiness not available");
    expect(absent).toContain("No product milestone can be treated as passed");

    const empty = renderPanel({
      summary: {
        milestones_total: 0,
        milestones_passed: 0,
        gates_total: 0,
        gates_passed: 0,
        current_gate_key: null,
        current_action: null,
        target_route: null,
      },
      milestones: [],
      gates: [],
    });
    expect(empty).toContain("Readiness milestones not available");
    expect(empty).toContain("Counts alone do not establish readiness");
    expect(empty).toContain("No current product-readiness action is recorded");
  });

  it("keeps a deferred gate and missing evidence visibly non-passed", () => {
    const readiness: ProductReadiness = {
      summary: {
        milestones_total: 1,
        milestones_passed: 0,
        gates_total: 1,
        gates_passed: 0,
        current_gate_key: null,
        current_action: null,
        target_route: null,
      },
      milestones: [{
        key: "options_expression",
        name: "Options expression",
        description: "Compare defined-risk structures after the underlying target exists.",
        status: "deferred",
        sort_order: 10,
        gates_total: 1,
        gates_passed: 0,
        current_gate_key: null,
      }],
      gates: [{
        key: "validated_option_chain",
        milestone_key: "options_expression",
        name: "Validated option chain",
        layer: "instrument_expression",
        description: "Require timestamped contracts, quotes, liquidity, volatility, and Greeks.",
        status: "deferred",
        acceptance_criterion: "A sealed option-chain dataset passes completeness and liquidity validation.",
        evaluator_key: "validated_option_chain_v1",
        next_action: "",
        target_route: "",
        sort_order: 10,
        dependencies: ["underlying_target"],
        blocked_by: [],
        evidence: [],
      }],
    };

    const markup = renderPanel(readiness);
    expect(markup).toContain("Deferred");
    expect(markup).toContain("Evidence not recorded");
    expect(markup).toContain("No current action is recorded because this gate is deferred");
    expect(markup).toContain("Target route not recorded");
    expect(markup).not.toContain("Passed</span>");
  });
});
