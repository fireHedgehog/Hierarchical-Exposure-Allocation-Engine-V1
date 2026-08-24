import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { AdminProvider, EngineMode, ProviderRoadmap } from "../types";
import { formatTimestamp } from "../utils/format";
import {
  credentialVerificationStatus,
  EngineModePanel,
  formatCredentialDuration,
  lastVerificationContext,
  ProviderCard,
  ProviderRoadmapPanel,
} from "./CredentialsPage";

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
        verification_ttl_seconds: 31_536_000,
        verification_policy_refresh_required: true,
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
    expect(markup).toContain("1 year");
    expect(markup).toContain("older, shorter policy");
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

  it("presents the one-year policy in operator language", () => {
    expect(formatCredentialDuration(31_536_000)).toBe("1 year");
    expect(formatCredentialDuration(900)).toBe("15 minutes");
  });

  it("separates what is needed now from the three future provider accounts", () => {
    const roadmap: ProviderRoadmap = {
      summary: {
        planned_accounts: 4,
        supported_accounts: 1,
        verified_accounts: 1,
        registrations_needed_now: 0,
        verifications_needed_now: 0,
        future_accounts_planned: 3,
        capabilities_total: 5,
        capabilities_ingestion_ready: 0,
      },
      next_action: "No additional registration is needed for the first regime slice.",
      accounts: [
        {
          key: "fred",
          operator_provider_key: "fred",
          name: "FRED / ALFRED",
          category: "macro",
          role: "Macro actuals and vintages",
          integration_status: "verification_ready",
          access_status: "healthy",
          required_for_first_slice: true,
          registration_available: true,
          guidance: "This is the only account requested now.",
          licensing_note: "Keep raw responses local.",
          capabilities: [{ key: "macro_actuals_vintages", role: "primary" }],
        },
        {
          key: "intrinio",
          name: "Intrinio",
          category: "market and options",
          role: "Market and options foundation",
          integration_status: "planned",
          access_status: "not_available",
          required_for_first_slice: false,
          registration_available: false,
          guidance: "Do not purchase until its adapter exists.",
          licensing_note: "Confirm licensing.",
          capabilities: [{ key: "equity_market_history", role: "primary" }],
        },
      ],
      capabilities: [
        {
          key: "macro_actuals_vintages",
          name: "Macro actuals and vintages",
          requirement_level: "required_now",
          integration_status: "verification_ready",
          ingestion_ready: false,
          providers: [{ key: "fred", name: "FRED / ALFRED" }],
          unlocks: ["regime_filter"],
        },
      ],
    };

    const markup = renderToStaticMarkup(<ProviderRoadmapPanel roadmap={roadmap} />);

    expect(markup).toContain("Full-desk accounts later");
    expect(markup).toContain("No additional registration is needed");
    expect(markup).toContain("Intrinio");
    expect(markup).toContain("Register Later");
    expect(markup).toContain("Stored-data health is a separate gate");
    expect(markup).not.toContain('type="password"');
  });
});

describe("engine operating mode panel", () => {
  it("defaults to presenting pilot mode when no engine_mode is returned yet", () => {
    const markup = renderToStaticMarkup(<EngineModePanel engineMode={null} onChanged={() => undefined} />);
    expect(markup).toContain("Pilot");
    expect(markup).toContain("paid-tier provider");
  });

  it("presents production mode distinctly from pilot", () => {
    const engineMode: EngineMode = {
      mode: "production",
      updated_at: "2026-08-24T12:00:00Z",
      updated_reason: "Paid providers connected.",
    };
    const markup = renderToStaticMarkup(<EngineModePanel engineMode={engineMode} onChanged={() => undefined} />);
    expect(markup).toContain("Production");
    expect(markup).toContain(formatTimestamp(engineMode.updated_at));
  });
});
