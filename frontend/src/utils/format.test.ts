import { describe, expect, it } from "vitest";
import {
  deltaBetween,
  formatNumber,
  formatPercent,
  formatScalar,
  NOT_AVAILABLE,
  toneForDirection,
  toneForStatus,
  formatTimestamp,
} from "./format";
import { columnExtent, heatCell } from "./matrix";

describe("honest value formatting", () => {
  it("keeps zero distinct from unavailable", () => {
    expect(formatNumber(0)).toBe("0");
    expect(formatNumber(null)).toBe(NOT_AVAILABLE);
    expect(formatScalar(false)).toBe("No");
    expect(formatScalar(null)).toBe(NOT_AVAILABLE);
  });

  it("formats a valid timestamp without an incompatible Intl option set", () => {
    expect(formatTimestamp("2026-08-21T20:00:00Z")).not.toBe(NOT_AVAILABLE);
    expect(formatTimestamp("2026-08-21T20:00:00Z")).toContain("2026");
  });

  it("formats exposure ratios and derives deltas only from complete values", () => {
    expect(formatPercent(0.125)).toBe("12.5%");
    expect(deltaBetween(0.2, 0.3)).toBeCloseTo(0.1);
    expect(deltaBetween(null, 0.3)).toBeNull();
  });

  it("formats ratio-valued database units as percentages", () => {
    expect(formatScalar(0.3, "fraction")).toBe("30%");
    expect(formatScalar(0.125, "portfolio_weight")).toBe("12.5%");
    expect(formatScalar(0.1, "annualized_fraction")).toBe("10%");
    expect(formatScalar(0.3, "score")).toBe("0.3");
    expect(formatScalar(-0.15, "z_score")).toBe("-0.15");
  });

  it("keeps data health separate from trade direction", () => {
    expect(toneForStatus("unavailable")).toBe("negative");
    expect(toneForStatus("available")).toBe("positive");
    expect(toneForStatus("short")).toBe("neutral");
    expect(toneForStatus("reduce")).toBe("neutral");
    expect(toneForStatus("simulation_only")).toBe("info");
    expect(toneForStatus("synthetic_only")).toBe("info");
    expect(toneForStatus("unreachable")).toBe("negative");
    expect(toneForStatus("provider_error")).toBe("negative");
    expect(toneForStatus("invalid_response")).toBe("negative");
    expect(toneForStatus("invalid_clock")).toBe("negative");
    expect(toneForStatus("expired")).toBe("negative");
    expect(toneForDirection("short")).toBe("negative");
    expect(toneForDirection("reduce")).toBe("negative");
  });
});

describe("cross-sectional matrix scaling", () => {
  const rows = [
    { symbol: "A", values: { score: -1 } },
    { symbol: "B", values: { score: null } },
    { symbol: "C", values: { score: 2 } },
  ];

  it("ignores missing values when calculating the column range", () => {
    expect(columnExtent(rows, "score")).toEqual({ min: -1, max: 2 });
  });

  it("gives missing cells a distinct state", () => {
    expect(heatCell(null, { min: -1, max: 2 }).tone).toBe("missing");
    expect(heatCell(-1, { min: -1, max: 2 }).tone).toBe("low");
    expect(heatCell(2, { min: -1, max: 2 }).tone).toBe("high");
  });
});
