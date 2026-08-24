import { describe, expect, it } from "vitest";
import type { SymbolEvent } from "../types";
import { buildVolumeSeriesData, classifyChartEvent } from "./PriceChart";

function event(type: string): SymbolEvent {
  return { time: "2026-08-20T20:00:00Z", type, label: type };
}

describe("chart event semantics", () => {
  it("uses conservative heuristics only for legacy events without a status", () => {
    expect(classifyChartEvent(event("signal_entry"))).toBe("signal");
    expect(classifyChartEvent(event("execution_entry"))).toBe("entry");
    expect(classifyChartEvent(event("backtest_exit"))).toBe("exit");
    expect(classifyChartEvent(event("weight_review"))).toBe("excluded");
  });

  it("never renders proposed or cancelled events as executions", () => {
    expect(classifyChartEvent({ ...event("execution_entry"), status: "proposed" })).toBe("excluded");
    expect(classifyChartEvent({ ...event("backtest_exit"), status: "cancelled" })).toBe("excluded");
    expect(classifyChartEvent({ ...event("signal_entry"), status: "proposed" })).toBe("excluded");
  });

  it("renders persisted executions as entries or exits regardless of the type prefix", () => {
    expect(classifyChartEvent({ ...event("signal_entry"), status: "executed" })).toBe("entry");
    expect(classifyChartEvent({ ...event("pattern_exit"), status: "executed" })).toBe("exit");
  });

  it("keeps explicit signal and annotation states non-executing", () => {
    expect(classifyChartEvent({ ...event("signal_entry"), status: "signal_state" })).toBe("signal");
    expect(classifyChartEvent({ ...event("signal_entry"), status: "annotation" })).toBe("signal");
    expect(classifyChartEvent({ ...event("pattern_higher_high"), status: "annotation" })).toBe("pattern");
    expect(classifyChartEvent({ ...event("execution_entry"), status: "annotation" })).toBe("excluded");
    expect(classifyChartEvent({ ...event("execution_entry"), status: "future_state" })).toBe("excluded");
  });
});

describe("chart volume semantics", () => {
  it("keeps missing volume as whitespace while preserving measured zero", () => {
    const data = buildVolumeSeriesData([
      { time: "2026-08-20", open: 100, close: 101, volume: null },
      { time: "2026-08-21", open: 101, close: 102, volume: 0 },
      { time: "2026-08-22", open: 102, close: 101, volume: Number.NaN },
      { time: "2026-08-23", open: 101, close: 103, volume: 250 },
    ]);

    expect(data[0]).toEqual({ time: "2026-08-20" });
    expect(data[1]).toMatchObject({ time: "2026-08-21", value: 0 });
    expect(data[2]).toEqual({ time: "2026-08-22" });
    expect(data[3]).toMatchObject({ time: "2026-08-23", value: 250 });
  });
});
