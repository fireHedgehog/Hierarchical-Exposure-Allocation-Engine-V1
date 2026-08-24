import { describe, expect, it } from "vitest";
import { computeEma, computeMacd, computeRsi } from "./indicators";

describe("computeRsi", () => {
  it("is null until seeded", () => {
    const closes = Array.from({ length: 10 }, (_, i) => 100 + i);
    const rsi = computeRsi(closes, 14);
    expect(rsi.every((value) => value === null)).toBe(true);
  });

  it("approaches 100 for a pure uptrend and 0 for a pure downtrend", () => {
    const up = Array.from({ length: 30 }, (_, i) => 100 + i);
    expect(computeRsi(up, 14).at(-1)).toBe(100);

    const down = Array.from({ length: 30 }, (_, i) => 130 - i);
    expect(computeRsi(down, 14).at(-1)).toBe(0);
  });
});

describe("computeEma / computeMacd", () => {
  it("seeds EMA with a simple average then smooths", () => {
    const ema = computeEma([10, 11, 12, 13, 14], 3);
    expect(ema[0]).toBeNull();
    expect(ema[1]).toBeNull();
    expect(ema[2]).toBeCloseTo((10 + 11 + 12) / 3);
    expect(ema[3]).not.toBeNull();
  });

  it("produces aligned macd/signal/histogram arrays with a positive MACD in a steady uptrend", () => {
    const closes = Array.from({ length: 40 }, (_, i) => 100 + i * 0.5);
    const { macdLine, signalLine, histogram } = computeMacd(closes);
    expect(macdLine).toHaveLength(closes.length);
    expect(signalLine).toHaveLength(closes.length);
    expect(histogram).toHaveLength(closes.length);
    expect(macdLine[24]).toBeNull();
    expect(macdLine[25]).not.toBeNull();
    expect(macdLine.at(-1)).toBeGreaterThan(0);
  });
});
