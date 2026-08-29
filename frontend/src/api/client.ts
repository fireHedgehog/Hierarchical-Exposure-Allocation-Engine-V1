import { useCallback, useEffect, useRef, useState } from "react";
import type { PipelineRun } from "../types";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

export const endpoints = {
  health: "/api/health",
  deskLatest: "/api/v1/desk/latest",
  crossSectionLatest: "/api/v1/cross-section/latest",
  crossSectionalRanking: "/api/v1/cross-sectional-ranking",
  symbols: "/api/v1/symbols",
  symbol: (symbol: string) => `/api/v1/symbols/${encodeURIComponent(symbol)}`,
  adminOverview: "/api/v1/admin/overview",
  adminProviders: "/api/v1/admin/providers",
  adminUniverse: "/api/v1/admin/universe",
  adminData: "/api/v1/admin/data",
  adminDataTestFetch: (symbol: string) => `/api/v1/admin/data/${encodeURIComponent(symbol)}/test-fetch`,
  adminLibraryFetch: "/api/v1/admin/library-fetch",
  adminResultsFilingCoverage: "/api/v1/admin/results-filings/coverage",
  adminResultsFilingFetch: "/api/v1/admin/results-filings/fetch",
  adminWatchlist: "/api/v1/admin/watchlist",
  adminWatchlistSymbol: (symbol: string) => `/api/v1/admin/watchlist/${encodeURIComponent(symbol)}`,
  adminPipeline: "/api/v1/admin/pipeline",
  adminPipelineRunStart: "/api/v1/admin/pipeline/runs/start",
  adminPipelineRunProgress: (progressRunId: string) => `/api/v1/admin/pipeline/runs/${encodeURIComponent(progressRunId)}/progress`,
  adminStrategies: "/api/v1/admin/strategies",
  adminStrategy: (key: string) => `/api/v1/admin/strategies/${safeAdminKey(key)}`,
  adminFactorSignificanceLatest: "/api/v1/admin/research/factor-significance/latest",
  adminSignalValidationLatest: (strategyKey: string) => `/api/v1/admin/research/signal-validation/latest?strategy_key=${safeAdminKey(strategyKey)}`,
  adminStrategyBacktestLatest: (strategyKey: string) => `/api/v1/admin/research/strategy-backtest/latest?strategy_key=${safeAdminKey(strategyKey)}`,
  adminResearchMetricCatalog: "/api/v1/admin/research/metric-catalog",
} as const;

export class ApiError extends Error {
  readonly status: number;
  readonly detail: string | null;
  readonly code: string | null;

  constructor(status: number, message: string, detail: string | null = null, code: string | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    this.code = code;
  }
}

export function operatorErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError && error.detail) return error.detail;
  if (error instanceof Error && error.message) return error.message;
  return fallback;
}

function errorDetail(payload: unknown): { message: string | null; code: string | null } {
  if (!payload || typeof payload !== "object") return { message: null, code: null };
  const record = payload as Record<string, unknown>;
  const rawDetail = record.detail ?? record.error;
  if (rawDetail && typeof rawDetail === "object") {
    const nested = rawDetail as Record<string, unknown>;
    return {
      message: typeof nested.message === "string" ? nested.message : null,
      code: typeof nested.code === "string" ? nested.code : null,
    };
  }
  const message = typeof rawDetail === "string" ? rawDetail : typeof record.message === "string" ? record.message : null;
  return { message, code: typeof record.code === "string" ? record.code : null };
}

export async function fetchJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "GET",
    headers: { Accept: "application/json" },
    signal,
  });

  let payload: unknown = null;
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    payload = await response.json();
  }

  if (!response.ok) {
    const detail = errorDetail(payload);
    const missingMessages: Record<string, string> = {
      symbol_not_found: "This symbol is absent from the latest persisted snapshot.",
      strategy_not_found: "This strategy is absent from the operator registry.",
      provider_not_found: "This provider is absent from the operator registry.",
      pipeline_not_found: "The operator pipeline is not registered.",
      snapshot_not_found: "No persisted snapshot is available.",
      route_not_found: "The requested API route does not exist.",
    };
    const message = response.status === 404
      ? (detail.code ? missingMessages[detail.code] : null) || "The requested resource is not available."
      : `The data service returned HTTP ${response.status}.`;
    throw new ApiError(response.status, message, detail.message, detail.code);
  }

  return payload as T;
}

type OperatorAction =
  | "credential.write"
  | "credential.delete"
  | "provider.verify"
  | "pipeline.run"
  | "engine_mode.write"
  | "research.run_factor_significance"
  | "research.run_signal_validation"
  | "research.run_strategy_backtest";
type OperatorMethod = "POST" | "PUT" | "DELETE";

interface OperatorRequest {
  method: OperatorMethod;
  action: OperatorAction;
  body?: Record<string, unknown>;
}

async function operatorJson<T>(path: string, request: OperatorRequest): Promise<T> {
  assertOperatorPath(path, request.method, request.action);
  const response = await fetch(path, {
    method: request.method,
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "X-Operator-Action": request.action,
    },
    body: request.body === undefined ? undefined : JSON.stringify(request.body),
  });

  let payload: unknown = null;
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) payload = await response.json();
  if (!response.ok) {
    const detail = errorDetail(payload);
    throw new ApiError(
      response.status,
      `Operator action failed with HTTP ${response.status}.`,
      detail.message,
      detail.code,
    );
  }
  return payload as T;
}

export function writeProviderCredential<T>(providerKey: string, secret: string): Promise<T> {
  const path = `/api/v1/admin/providers/${safeAdminKey(providerKey)}/credential`;
  return operatorJson<T>(path, { method: "PUT", action: "credential.write", body: { secret } });
}

export function deleteProviderCredential<T>(providerKey: string): Promise<T> {
  const path = `/api/v1/admin/providers/${safeAdminKey(providerKey)}/credential`;
  return operatorJson<T>(path, { method: "DELETE", action: "credential.delete" });
}

export function verifyProvider<T>(providerKey: string): Promise<T> {
  const path = `/api/v1/admin/providers/${safeAdminKey(providerKey)}/verify`;
  return operatorJson<T>(path, { method: "POST", action: "provider.verify", body: {} });
}

export type PipelineStageKey =
  | "fetch_data" | "validate_data" | "regime_filter"
  | "factor_engine" | "allocation_engine" | "instrument_engine";

export function runPipeline<T>(dryRun = true, stopAfter?: PipelineStageKey, reuseLatestDataset = false): Promise<T> {
  return operatorJson<T>("/api/v1/admin/pipeline/runs", {
    method: "POST",
    action: "pipeline.run",
    body: {
      dry_run: dryRun,
      ...(stopAfter ? { stop_after: stopAfter } : {}),
      ...(reuseLatestDataset ? { reuse_latest_dataset: true } : {}),
    },
  });
}

/** Starts a real run in the background and returns immediately with an id
 * to poll -- real, direct user request for live progress instead of one
 * opaque blocking request. Poll endpoints.adminPipelineRunProgress(id). */
export function startBackgroundPipelineRun<T>(dryRun = true, stopAfter?: PipelineStageKey, reuseLatestDataset = false): Promise<T> {
  return operatorJson<T>("/api/v1/admin/pipeline/runs/start", {
    method: "POST",
    action: "pipeline.run",
    body: {
      dry_run: dryRun,
      ...(stopAfter ? { stop_after: stopAfter } : {}),
      ...(reuseLatestDataset ? { reuse_latest_dataset: true } : {}),
    },
  });
}

export interface PipelineRunProgress {
  run_id: string;
  stage: PipelineStageKey | null;
  stage_index: number;
  total_stages: number;
  item_progress: { done: number; total: number; current: string | null } | null;
  finished: boolean;
  error: string | null;
  result: { run: PipelineRun } | null;
}

export function setEngineMode<T>(mode: "pilot" | "production", reason?: string): Promise<T> {
  return operatorJson<T>("/api/v1/admin/engine-mode", {
    method: "PUT",
    action: "engine_mode.write",
    body: reason ? { mode, reason } : { mode },
  });
}

export function runFactorSignificanceResearch<T>(): Promise<T> {
  return operatorJson<T>("/api/v1/admin/research/factor-significance/runs", {
    method: "POST",
    action: "research.run_factor_significance",
    body: {},
  });
}

export function runSignalValidationResearch<T>(strategyKey: "macro_regime_composite" | "cross_sectional_momentum"): Promise<T> {
  return operatorJson<T>("/api/v1/admin/research/signal-validation/runs", {
    method: "POST",
    action: "research.run_signal_validation",
    body: { strategy_key: strategyKey },
  });
}

export function runStrategyBacktestResearch<T>(strategyKey: "cross_sectional_momentum"): Promise<T> {
  return operatorJson<T>("/api/v1/admin/research/strategy-backtest/runs", {
    method: "POST",
    action: "research.run_strategy_backtest",
    body: { strategy_key: strategyKey },
  });
}

// Lighter than operatorJson: the watchlist is a personal, reversible,
// day-to-day preference (direct_loopback_guard only on the backend, no
// operator-action header required) -- not a capital/credential-affecting
// action, so it doesn't belong in the operatorJson allowlist above.
async function watchlistJson<T>(symbol: string, method: "POST" | "DELETE"): Promise<T> {
  const response = await fetch(endpoints.adminWatchlistSymbol(symbol), {
    method,
    headers: { Accept: "application/json" },
  });
  let payload: unknown = null;
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) payload = await response.json();
  if (!response.ok) {
    const detail = errorDetail(payload);
    throw new ApiError(response.status, `Watchlist update failed with HTTP ${response.status}.`, detail.message, detail.code);
  }
  return payload as T;
}

export function addToWatchlist<T>(symbol: string): Promise<T> {
  return watchlistJson<T>(symbol, "POST");
}

export function removeFromWatchlist<T>(symbol: string): Promise<T> {
  return watchlistJson<T>(symbol, "DELETE");
}

function safeAdminKey(value: string): string {
  const key = value.trim();
  if (!/^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/.test(key)) {
    throw new Error("Invalid operator resource key.");
  }
  return encodeURIComponent(key);
}

function assertOperatorPath(path: string, method: OperatorMethod, action: OperatorAction): void {
  const providerCredential = /^\/api\/v1\/admin\/providers\/[A-Za-z0-9._-]+\/credential$/;
  const providerVerify = /^\/api\/v1\/admin\/providers\/[A-Za-z0-9._-]+\/verify$/;
  const allowed =
    (providerCredential.test(path) && method === "PUT" && action === "credential.write") ||
    (providerCredential.test(path) && method === "DELETE" && action === "credential.delete") ||
    (providerVerify.test(path) && method === "POST" && action === "provider.verify") ||
    (path === "/api/v1/admin/pipeline/runs" && method === "POST" && action === "pipeline.run") ||
    (path === "/api/v1/admin/pipeline/runs/start" && method === "POST" && action === "pipeline.run") ||
    (path === "/api/v1/admin/engine-mode" && method === "PUT" && action === "engine_mode.write") ||
    (path === "/api/v1/admin/research/factor-significance/runs" && method === "POST" && action === "research.run_factor_significance");
  if (!allowed) throw new Error("Blocked unsafe operator request.");
}

interface ApiState<T> {
  data: T | null;
  error: Error | null;
  loading: boolean;
  reload: () => void;
}

interface ResolvedResource<T> {
  path: string;
  data: T;
}

export function selectResourceData<T>(resource: ResolvedResource<T> | null, path: string | null): T | null {
  return resource?.path === path ? resource.data : null;
}

export function useApi<T>(path: string | null): ApiState<T> {
  const [resource, setResource] = useState<ResolvedResource<T> | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(Boolean(path));
  const [revision, setRevision] = useState(0);
  const requestId = useRef(0);

  const reload = useCallback(() => setRevision((value) => value + 1), []);

  useEffect(() => {
    if (!path) {
      setResource(null);
      setError(null);
      setLoading(false);
      return;
    }

    const controller = new AbortController();
    const currentRequest = ++requestId.current;
    setLoading(true);
    setError(null);

    fetchJson<T>(path, controller.signal)
      .then((result) => {
        if (requestId.current !== currentRequest) return;
        setResource({ path, data: result });
      })
      .catch((caught: unknown) => {
        if (controller.signal.aborted || requestId.current !== currentRequest) return;
        setResource(null);
        setError(caught instanceof Error ? caught : new Error("Unknown API error"));
      })
      .finally(() => {
        if (requestId.current === currentRequest) setLoading(false);
      });

    return () => controller.abort();
  }, [path, revision]);

  const data = selectResourceData(resource, path);
  const changingResource = Boolean(path && resource && resource.path !== path);
  return { data, error, loading: loading || changingResource, reload };
}
