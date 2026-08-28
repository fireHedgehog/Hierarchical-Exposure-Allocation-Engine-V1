import type { Scalar } from "../types";

export const NOT_AVAILABLE = "Not available";

export function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

export function formatNumber(
  value: number | null | undefined,
  options: Intl.NumberFormatOptions = {},
): string {
  if (!isFiniteNumber(value)) return NOT_AVAILABLE;
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: 2,
    ...options,
  }).format(value);
}

export function formatPercent(
  value: number | null | undefined,
  maximumFractionDigits = 1,
): string {
  if (!isFiniteNumber(value)) return NOT_AVAILABLE;
  return new Intl.NumberFormat("en-US", {
    style: "percent",
    maximumFractionDigits,
    signDisplay: "auto",
  }).format(value);
}

export function formatPercentPoints(
  value: number | null | undefined,
  maximumFractionDigits = 1,
): string {
  if (!isFiniteNumber(value)) return NOT_AVAILABLE;
  return `${new Intl.NumberFormat("en-US", {
    maximumFractionDigits,
    signDisplay: "auto",
  }).format(value)}%`;
}

export function formatCurrency(
  value: number | null | undefined,
  currency = "USD",
): string {
  if (!isFiniteNumber(value)) return NOT_AVAILABLE;
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    notation: Math.abs(value) >= 1_000_000 ? "compact" : "standard",
    maximumFractionDigits: Math.abs(value) >= 1_000 ? 1 : 2,
  }).format(value);
}

export function formatScalar(value: Scalar | undefined, unit?: string | null): string {
  if (value === null || value === undefined || value === "") return NOT_AVAILABLE;
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "string") return value;
  if (!Number.isFinite(value)) return NOT_AVAILABLE;
  const normalizedUnit = unit?.trim().toLowerCase();
  if (normalizedUnit === "%" || normalizedUnit === "percentage_points") return formatPercentPoints(value);
  if (
    normalizedUnit &&
    new Set([
      "fraction",
      "portfolio_weight",
      "net_exposure",
      "gross_exposure",
      "premium_budget",
      "annualized_fraction",
    ]).has(normalizedUnit)
  ) {
    return formatPercent(value);
  }
  if (normalizedUnit === "ratio") return formatNumber(value, { maximumFractionDigits: 3 });
  if (
    normalizedUnit &&
    new Set(["score", "score_0_to_1", "z_score", "index", "count"]).has(normalizedUnit)
  ) {
    return formatNumber(value, { maximumFractionDigits: 3 });
  }
  if (normalizedUnit === "usd" || normalizedUnit === "$" || normalizedUnit === "currency") return formatCurrency(value);
  return unit ? `${formatNumber(value)} ${unit}` : formatNumber(value);
}

// Every stored timestamp is UTC. Displaying it in the viewer's local zone
// (previously the browser default, e.g. NZST) makes cross-referencing with
// US market hours confusing regardless of where the app is opened from —
// shown in US Eastern time instead, the market's own convention, always.
const MARKET_TIME_ZONE = "America/New_York";

export function formatTimestamp(value: string | null | undefined): string {
  if (!value) return NOT_AVAILABLE;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZoneName: "short",
    timeZone: MARKET_TIME_ZONE,
  }).format(parsed);
}

export function formatDate(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return NOT_AVAILABLE;
  if (typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value)) {
    const [year, month, day] = value.split("-").map(Number);
    return new Intl.DateTimeFormat("en-US", { dateStyle: "medium", timeZone: "UTC" }).format(
      new Date(Date.UTC(year, month - 1, day)),
    );
  }
  const parsed = typeof value === "number" ? new Date(value * 1000) : new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return new Intl.DateTimeFormat("en-US", { dateStyle: "medium", timeZone: MARKET_TIME_ZONE }).format(parsed);
}

export function humanize(value: string | null | undefined): string {
  if (!value) return NOT_AVAILABLE;
  return value
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export type Tone = "positive" | "negative" | "warning" | "neutral" | "info";

export function toneForStatus(value: string | null | undefined): Tone {
  const status = normalizeToken(value);
  if (
    new Set([
      "blocked",
      "error",
      "failed",
      "failure",
      "stale",
      "unavailable",
      "disconnected",
      "not_connected",
      "invalid",
      "missing",
      "unhealthy",
      "invalid_credentials",
      "unreachable",
      "provider_error",
      "invalid_response",
      "invalid_clock",
      "expired",
      "verification_expired",
    ]).has(status)
  ) {
    return "negative";
  }
  if (
    new Set([
      "warning",
      "partial",
      "review",
      "review_only",
      "watch",
      "limited",
      "pending",
      "caution",
      "checking",
      "not_run",
      "not_available",
      "not_live",
      "unverified",
      "not_verified",
      "not_configured",
      "scaffolded",
      "completed_with_warnings",
      "rate_limited",
    ]).has(status)
  ) {
    return "warning";
  }
  if (
    new Set([
      "ready",
      "healthy",
      "complete",
      "completed",
      "pass",
      "available",
      "connected",
      "active",
      "configured",
      "current",
      "verified",
    ]).has(status)
  ) {
    return "positive";
  }
  if (
    new Set([
      "demo",
      "simulation",
      "synthetic",
      "info",
      "demo_not_live",
      "research",
      "paper",
      "simulation_ready",
      "synthetic_simulation_ready",
      "simulation_only",
      "synthetic_only",
      "simulation_candidate",
      "synthetic_fixture",
      "demo_fixture_loaded",
      "simulation_fixture_loaded",
      "manual_only",
      "dry_run",
      "full_run",
      "historical",
      "defined",
      "not_applicable",
      "skipped",
    ]).has(status)
  ) {
    return "info";
  }
  return "neutral";
}

/** Visual direction only; it deliberately does not imply health or validity. */
export function toneForDirection(value: string | null | undefined): Tone {
  const direction = normalizeToken(value);
  if (new Set(["positive", "up", "increase", "add", "long", "bull", "bullish", "supportive"]).has(direction)) {
    return "positive";
  }
  if (new Set(["negative", "down", "decrease", "reduce", "short", "bear", "bearish", "headwind"]).has(direction)) {
    return "negative";
  }
  if (new Set(["mixed", "flat", "neutral", "hold"]).has(direction)) return "warning";
  return "neutral";
}

function normalizeToken(value: string | null | undefined): string {
  return (value || "").trim().toLowerCase().replace(/[\s-]+/g, "_");
}

export function deltaBetween(
  current: number | null | undefined,
  target: number | null | undefined,
): number | null {
  if (!isFiniteNumber(current) || !isFiniteNumber(target)) return null;
  return target - current;
}
