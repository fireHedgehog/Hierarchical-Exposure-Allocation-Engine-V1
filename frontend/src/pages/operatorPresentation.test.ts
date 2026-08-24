import { describe, expect, it } from "vitest";
import { invalidInventoryStatus } from "./DataManagementPage";
import { statusForOverviewMetric } from "./OperationsOverviewPage";

describe("operator count presentation", () => {
  it("does not present an empty registered universe as ready or active", () => {
    expect(statusForOverviewMetric("healthy", 0, 0)).toBe("not_configured");
    expect(statusForOverviewMetric("ready", 0, 0)).toBe("not_configured");
    expect(statusForOverviewMetric("active", 0, 0)).toBe("not_configured");
    expect(statusForOverviewMetric("active", 0, 3)).toBe("unavailable");
  });

  it("preserves positive and partial ratio semantics", () => {
    expect(statusForOverviewMetric("healthy", 2, 2)).toBe("healthy");
    expect(statusForOverviewMetric("ready", 2, 3)).toBe("partial");
    expect(statusForOverviewMetric("configured", 0, 2)).toBe("missing");
  });

  it("distinguishes invalid, clean, empty, and unsupported inventory counts", () => {
    expect(invalidInventoryStatus(2, true)).toBe("invalid");
    expect(invalidInventoryStatus(0, true)).toBe("healthy");
    expect(invalidInventoryStatus(0, false)).toBe("not_configured");
    expect(invalidInventoryStatus(undefined, true)).toBe("unavailable");
  });
});
