import type { MatrixRow } from "../types";
import { isFiniteNumber } from "./format";

export interface Extent {
  min: number;
  max: number;
}

export function columnExtent(rows: MatrixRow[], key: string): Extent | null {
  const values = rows
    .map((row) => row.values[key])
    .filter((value): value is number => isFiniteNumber(value));
  if (!values.length) return null;
  return { min: Math.min(...values), max: Math.max(...values) };
}

export interface HeatCell {
  background: string;
  border: string;
  tone: "low" | "neutral" | "high" | "missing";
}

export function heatCell(value: number | null | undefined, extent: Extent | null): HeatCell {
  if (!isFiniteNumber(value) || !extent) {
    return {
      background: "rgba(255, 255, 255, 0.025)",
      border: "rgba(255, 255, 255, 0.07)",
      tone: "missing",
    };
  }

  const span = extent.max - extent.min;
  const normalized = span === 0 ? 0.5 : (value - extent.min) / span;
  if (normalized > 0.56) {
    const strength = (normalized - 0.5) * 2;
    return {
      background: `rgba(75, 143, 231, ${0.08 + strength * 0.26})`,
      border: `rgba(111, 169, 245, ${0.12 + strength * 0.34})`,
      tone: "high",
    };
  }
  if (normalized < 0.44) {
    const strength = (0.5 - normalized) * 2;
    return {
      background: `rgba(220, 151, 59, ${0.08 + strength * 0.24})`,
      border: `rgba(239, 177, 84, ${0.12 + strength * 0.32})`,
      tone: "low",
    };
  }
  return {
    background: "rgba(241, 185, 88, 0.12)",
    border: "rgba(241, 185, 88, 0.22)",
    tone: "neutral",
  };
}
