import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchJson, operatorErrorMessage, runPipeline, selectResourceData, verifyProvider, writeProviderCredential } from "./client";

describe("FastAPI error envelopes", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("preserves nested symbol-not-found identity", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ detail: { code: "symbol_not_found", message: "Symbol OLD is absent." } }),
      { status: 404, headers: { "content-type": "application/json" } },
    )));

    await expect(fetchJson("/api/v1/symbols/OLD")).rejects.toMatchObject({
      code: "symbol_not_found",
      detail: "Symbol OLD is absent.",
      message: "This symbol is absent from the latest persisted snapshot.",
    });
  });

  it("uses a fixed credential route and explicit operator action", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ provider: { key: "fred" } }),
      { status: 200, headers: { "content-type": "application/json" } },
    ));
    vi.stubGlobal("fetch", fetchMock);

    await writeProviderCredential("fred", "transient-test-secret");

    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, request] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/admin/providers/fred/credential");
    expect(request.method).toBe("PUT");
    expect(request.headers).toMatchObject({ "X-Operator-Action": "credential.write" });
    expect(JSON.parse(String(request.body))).toEqual({ secret: "transient-test-secret" });
  });

  it("rejects an unsafe provider key before calling fetch", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    expect(() => verifyProvider("../fred")).toThrow("Invalid operator resource key");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("surfaces a sanitized operator recovery message", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ detail: { code: "credential_environment_managed", message: "Unset HEAE_FRED_API_KEY outside the app." } }),
      { status: 409, headers: { "content-type": "application/json" } },
    )));
    const error = await writeProviderCredential("fred", "transient-test-secret").catch((caught) => caught);
    expect(operatorErrorMessage(error, "Credential update failed.")).toBe("Unset HEAE_FRED_API_KEY outside the app.");
  });

  it("confirms dry-run pipeline actions through the fixed endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ run: { id: "run-1", dry_run: true } }),
      { status: 200, headers: { "content-type": "application/json" } },
    ));
    vi.stubGlobal("fetch", fetchMock);
    await runPipeline(true);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/admin/pipeline/runs",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({ "X-Operator-Action": "pipeline.run" }),
        body: JSON.stringify({ dry_run: true }),
      }),
    );
  });

  it("requests a provider-free stored-data recompute explicitly", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ run: { id: "run-stored", dry_run: false } }),
      { status: 200, headers: { "content-type": "application/json" } },
    ));
    vi.stubGlobal("fetch", fetchMock);

    await runPipeline(false, "instrument_engine", true);

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/admin/pipeline/runs",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          dry_run: false,
          stop_after: "instrument_engine",
          reuse_latest_dataset: true,
        }),
      }),
    );
  });

  it("never exposes a response under a different resource path", () => {
    const spy = { symbol: "SPY" };
    expect(selectResourceData({ path: "/api/v1/symbols/SPY", data: spy }, "/api/v1/symbols/SPY")).toBe(spy);
    expect(selectResourceData({ path: "/api/v1/symbols/SPY", data: spy }, "/api/v1/symbols/TLT")).toBeNull();
  });
});
