import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { AdminProvider } from "../types";
import { formatTimestamp } from "../utils/format";
import { credentialVerificationStatus, lastVerificationContext, ProviderCard } from "./CredentialsPage";

describe("credential health presentation", () => {
  it("keeps an expired test visible without presenting it as current or healthy", () => {
    const provider: AdminProvider = {
      key: "fred",
      name: "FRED",
      credential: {
        configured: true,
        source: "keyring",
        managed: true,
        status: "expired",
        last_verified_at: "2026-08-10T00:00:00Z",
        verification_expires_at: "2026-08-17T00:00:00Z",
        verification_status: null,
        cooldown_seconds: 900,
        cooldown_remaining_seconds: 0,
        verification_ttl_seconds: 604800,
      },
      last_verification: {
        id: "verification-1",
        checked_at: "2026-08-10T00:00:00Z",
        expires_at: "2026-08-17T00:00:00Z",
        status: "healthy",
        message: "Provider responded successfully.",
        current: false,
        applies_to_credential: true,
        expired: true,
      },
    };

    const markup = renderToStaticMarkup(
      <ProviderCard
        provider={provider}
        busy={false}
        action={null}
        message={null}
        onSubmit={() => undefined}
        onVerify={() => undefined}
        onDelete={() => undefined}
      />,
    );

    expect(credentialVerificationStatus(provider.credential)).toBe("expired");
    expect(markup).toContain(">Expired</span>");
    expect(markup).not.toContain("credential-mark--healthy");
    expect(markup).toContain("Last tested");
    expect(markup).toContain("Valid until");
    expect(markup).toContain("Provider responded successfully.");
    expect(markup).toContain("health-validity window has expired");
  });

  it("labels a rotated credential's previous result as historical only", () => {
    const result = {
      current: false,
      applies_to_credential: false,
      expired: false,
      status: "healthy",
      checked_at: "2026-08-10T00:00:00Z",
    };
    expect(lastVerificationContext(result)).toContain("does not apply to the current credential");
  });

  it("presents a future-dated verification as a clock error, never healthy", () => {
    const provider: AdminProvider = {
      key: "fred",
      name: "FRED",
      credential: {
        configured: true,
        source: "keyring",
        managed: true,
        status: "invalid_clock",
        verification_status: null,
        verification_expires_at: null,
      },
      last_verification: {
        id: "future-verification",
        checked_at: "2026-08-25T12:00:00Z",
        expires_at: "2026-09-08T12:00:00Z",
        effective_expires_at: "2026-09-01T12:00:00Z",
        status: "healthy",
        current: false,
        applies_to_credential: true,
        expired: false,
        future_dated: true,
      },
    };

    const markup = renderToStaticMarkup(
      <ProviderCard
        provider={provider}
        busy={false}
        action={null}
        message={null}
        onSubmit={() => undefined}
        onVerify={() => undefined}
        onDelete={() => undefined}
      />,
    );

    expect(credentialVerificationStatus(provider.credential)).toBe("invalid_clock");
    expect(markup).toContain("status-pill--negative");
    expect(markup).toContain("Invalid Clock");
    expect(markup).toContain("outside the server clock tolerance");
    expect(markup).not.toContain("credential-mark--healthy");
  });

  it("uses the policy-capped expiry when describing current health", () => {
    const result = {
      current: true,
      applies_to_credential: true,
      expired: false,
      future_dated: false,
      status: "healthy",
      expires_at: "2026-09-08T12:00:00Z",
      effective_expires_at: "2026-09-01T12:00:00Z",
    };
    const context = lastVerificationContext(result);

    expect(context).toContain(formatTimestamp(result.effective_expires_at));
    expect(context).not.toContain(formatTimestamp(result.expires_at));
  });
});
