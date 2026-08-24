import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { StrategyDetail } from "../types";
import { CurrentStrategyDiagnostics, resolveCurrentStrategyVersion } from "./StrategyDetailPage";

const draftVersion = {
  version: "0.2.0-draft",
  diagnostics: [{ metric_key: "decay_rate", label: "Decay rate", value: 0.12, unit: "fraction" }],
};

function strategy(version: string | null): StrategyDetail {
  return {
    key: "state_conditioned_exposure",
    name: "State-conditioned exposure",
    version,
    versions: [draftVersion],
  };
}

describe("strategy current-version presentation", () => {
  it.each([
    ["missing", strategy(null)],
    ["dangling", strategy("9.9.9-missing")],
  ])("does not present a draft as current when the reference is %s", (_case, record) => {
    const current = resolveCurrentStrategyVersion(record);
    const markup = renderToStaticMarkup(<CurrentStrategyDiagnostics version={current} />);

    expect(current).toBeUndefined();
    expect(markup).toContain("Diagnostics not available");
    expect(markup).not.toContain("Decay rate");
  });

  it("uses diagnostics only when the current-version reference matches explicitly", () => {
    const current = resolveCurrentStrategyVersion(strategy("0.2.0-draft"));
    const markup = renderToStaticMarkup(<CurrentStrategyDiagnostics version={current} />);

    expect(current?.version).toBe("0.2.0-draft");
    expect(markup).toContain("Decay rate");
  });
});
