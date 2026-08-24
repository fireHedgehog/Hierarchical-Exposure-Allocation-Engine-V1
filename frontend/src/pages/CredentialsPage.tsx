import {
  AlertTriangle,
  CheckCircle2,
  ExternalLink,
  FlaskConical,
  Factory,
  KeyRound,
  RefreshCw,
  ShieldCheck,
  TestTube2,
  Trash2,
} from "lucide-react";
import type { FormEvent } from "react";
import { useState } from "react";
import {
  deleteProviderCredential,
  endpoints,
  operatorErrorMessage,
  setEngineMode,
  useApi,
  verifyProvider,
  writeProviderCredential,
} from "../api/client";
import { OperatorPageHeader } from "../components/OperatorPageHeader";
import { Panel, ResourceState, SectionHeading, StatusPill, Unavailable } from "../components/Ui";
import type {
  AdminProvider,
  CredentialStatus,
  EngineMode,
  ProviderLastVerification,
  ProviderRoadmap,
  ProviderRoadmapAccount,
  ProvidersResponse,
  UniverseResponse,
} from "../types";
import { formatNumber, formatTimestamp, humanize, NOT_AVAILABLE } from "../utils/format";

export function CredentialsPage() {
  const state = useApi<ProvidersResponse>(endpoints.adminProviders);
  const providers = state.data?.providers ?? [];
  const roadmap = state.data?.roadmap;
  const [activeAction, setActiveAction] = useState<string | null>(null);
  const [message, setMessage] = useState<{ provider: string; kind: "success" | "error"; text: string } | null>(null);

  const writeCredential = async (event: FormEvent<HTMLFormElement>, provider: AdminProvider) => {
    event.preventDefault();
    const form = event.currentTarget;
    const submitted = new FormData(form).get("secret");
    if (typeof submitted !== "string" || !submitted.trim()) {
      setMessage({ provider: provider.key, kind: "error", text: "Enter a credential before submitting." });
      return;
    }
    setActiveAction(`${provider.key}:write`);
    setMessage(null);
    try {
      await writeProviderCredential<unknown>(provider.key, submitted.trim());
      form.reset();
      setMessage({ provider: provider.key, kind: "success", text: "Credential stored by the backend. Run a smoke test when ready." });
      state.reload();
    } catch (error) {
      form.reset();
      setMessage({ provider: provider.key, kind: "error", text: operatorErrorMessage(error, "Credential update failed.") });
    } finally {
      setActiveAction(null);
    }
  };

  const smokeTest = async (provider: AdminProvider) => {
    setActiveAction(`${provider.key}:verify`);
    setMessage(null);
    try {
      await verifyProvider<unknown>(provider.key);
      setMessage({ provider: provider.key, kind: "success", text: "Smoke test completed. The persisted verification state is refreshing." });
      state.reload();
    } catch (error) {
      setMessage({ provider: provider.key, kind: "error", text: operatorErrorMessage(error, "Provider verification failed.") });
    } finally {
      setActiveAction(null);
    }
  };

  const removeCredential = async (provider: AdminProvider) => {
    if (!window.confirm(`Remove the locally managed ${provider.name} credential?`)) return;
    setActiveAction(`${provider.key}:delete`);
    setMessage(null);
    try {
      await deleteProviderCredential<unknown>(provider.key);
      setMessage({ provider: provider.key, kind: "success", text: "Locally managed credential removed." });
      state.reload();
    } catch (error) {
      setMessage({ provider: provider.key, kind: "error", text: operatorErrorMessage(error, "Credential removal failed.") });
    } finally {
      setActiveAction(null);
    }
  };

  return (
    <div className="workspace operator-page">
      <OperatorPageHeader
        title="Credentials"
        description="Configure local provider access without placing API keys in Git, SQLite, frontend state, or browser storage."
        action={(
          <button className="button button--quiet" type="button" onClick={state.reload} disabled={state.loading}>
            <RefreshCw aria-hidden="true" size={15} /> Refresh providers
          </button>
        )}
      />
      <ResourceState loading={state.loading} error={state.error} onRetry={state.reload} resource="provider registry" />

      <EngineModePanel engineMode={state.data?.engine_mode ?? null} onChanged={state.reload} />
      <StagingUniversePanel />

      {roadmap ? <ProviderRoadmapPanel roadmap={roadmap} /> : null}

      {state.data ? (
        <Panel>
          <SectionHeading
            eyebrow={`${providers.length} supported provider ${providers.length === 1 ? "account" : "accounts"}`}
            title="Actionable credentials and smoke tests"
            description="Only providers with an implemented verifier appear here. Smoke-test cooldown and health validity are separate; historical results never imply current provider health."
          />
          {providers.length ? (
            <div className="credential-grid">
              {providers.map((provider) => (
                <ProviderCard
                  key={provider.key}
                  provider={provider}
                  busy={activeAction?.startsWith(`${provider.key}:`) === true}
                  action={activeAction?.split(":")[1] || null}
                  message={message?.provider === provider.key ? message : null}
                  onSubmit={writeCredential}
                  onVerify={smokeTest}
                  onDelete={removeCredential}
                />
              ))}
            </div>
          ) : <Unavailable title="No providers registered" detail="The backend has no provider configuration records." />}
        </Panel>
      ) : null}
    </div>
  );
}

export function EngineModePanel({
  engineMode,
  onChanged,
}: {
  engineMode: EngineMode | null;
  onChanged: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ kind: "success" | "error"; text: string } | null>(null);
  const mode = engineMode?.mode ?? "pilot";

  const switchTo = async (next: "pilot" | "production") => {
    if (next === mode || busy) return;
    setBusy(true);
    setMessage(null);
    try {
      await setEngineMode<unknown>(next);
      setMessage({
        kind: "success",
        text: next === "pilot"
          ? "Switched to pilot mode. Only free-data-tier providers may run engine stages."
          : "Switched to production mode. Stages requiring paid-tier providers are no longer blocked by mode alone.",
      });
      onChanged();
    } catch (error) {
      setMessage({ kind: "error", text: operatorErrorMessage(error, "Could not change the engine operating mode.") });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Panel className="engine-mode-panel">
      <SectionHeading
        eyebrow="Engine operating mode"
        title="Pilot vs. production"
        description="A real, gated choice — not a label. Pilot mode blocks any engine stage that requires a paid-tier provider, even if that provider happens to be configured. Every snapshot a run produces is stamped with the mode that was active when it ran, so outputs stay honestly attributable. Switching to production does not remove the free staging symbols below — it only lifts the block on paid-tier stages. Without Intrinio/Benzinga/Trading Economics keys configured, production mode still only has the free-tier universe to work with."
      />
      <div className="engine-mode-current">
        <span>Current mode</span>
        <StatusPill value={mode} tone={mode === "pilot" ? "info" : "positive"} />
        {engineMode?.updated_at ? <small>Since {formatTimestamp(engineMode.updated_at)}</small> : null}
      </div>
      <div className="engine-mode-actions">
        <button
          className={`button button--quiet ${mode === "pilot" ? "engine-mode-actions__button--active" : ""}`}
          type="button"
          aria-pressed={mode === "pilot"}
          disabled={busy}
          onClick={() => switchTo("pilot")}
        >
          <FlaskConical aria-hidden="true" size={15} /> Pilot — free data only{mode === "pilot" ? " (current)" : ""}
        </button>
        <button
          className={`button button--quiet ${mode === "production" ? "engine-mode-actions__button--active" : ""}`}
          type="button"
          aria-pressed={mode === "production"}
          disabled={busy}
          onClick={() => switchTo("production")}
        >
          <Factory aria-hidden="true" size={15} /> Production — full provider stack{mode === "production" ? " (current)" : ""}
        </button>
      </div>
      {message ? (
        <div className={`operator-action-message operator-action-message--${message.kind}`} role="status">
          {message.kind === "success" ? <CheckCircle2 aria-hidden="true" size={15} /> : <AlertTriangle aria-hidden="true" size={15} />}
          {message.text}
        </div>
      ) : null}
    </Panel>
  );
}

export function StagingUniversePanel() {
  const state = useApi<UniverseResponse>(endpoints.adminUniverse);
  const summary = state.data?.summary;
  const categories = summary ? Object.entries(summary.by_category).sort(([a], [b]) => a.localeCompare(b)) : [];

  return (
    <Panel className="staging-universe-panel">
      <SectionHeading
        eyebrow="Free-tier staging universe"
        title="Default symbols — no paid key required"
        description="Seeded automatically from the database schema on every fresh clone (never hard-coded in frontend or strategy code). This is what pilot mode has to work with; production mode does not remove it, but without paid-tier keys configured, production mode still only has this list."
      />
      {summary ? (
        <div className="provider-roadmap-summary" aria-label="Staging universe summary">
          <RoadmapMetric label="Active symbols" value={`${summary.active}/${summary.total}`} detail="Seeded by schema.sql, not hard-coded in the app" />
          {categories.map(([category, count]) => (
            <RoadmapMetric key={category} label={humanize(category)} value={String(count)} detail="free tier" />
          ))}
        </div>
      ) : (
        <Unavailable compact title="Universe not available" detail="No staging symbol catalog was returned." />
      )}
    </Panel>
  );
}

export function ProviderRoadmapPanel({ roadmap }: { roadmap: ProviderRoadmap }) {
  const summary = roadmap.summary;
  const accounts = roadmap.accounts ?? [];
  const capabilities = roadmap.capabilities ?? [];

  return (
    <Panel className="provider-roadmap-panel">
      <SectionHeading
        eyebrow="Data onboarding plan"
        title="What the desk needs—and when"
        description="The first regime slice and the complete desk have different requirements. Planned accounts are visible here, but key entry stays disabled until a tested adapter exists."
      />

      <div className="provider-roadmap-summary" aria-label="Provider readiness summary">
        <RoadmapMetric
          label="Supported access verified"
          value={`${summary.verified_accounts}/${summary.supported_accounts}`}
          detail="Credential adapters available now"
        />
        <RoadmapMetric
          label="Register now"
          value={String(summary.registrations_needed_now)}
          detail={summary.verifications_needed_now ? `${summary.verifications_needed_now} stored key needs verification or policy refresh` : "No extra account for the first slice"}
        />
        <RoadmapMetric
          label="Full-desk accounts later"
          value={String(summary.future_accounts_planned)}
          detail={`${summary.planned_accounts} accounts in the researched plan`}
        />
        <RoadmapMetric
          label="Ingestion adapters ready"
          value={`${summary.capabilities_ingestion_ready}/${summary.capabilities_total}`}
          detail="Stored-data health is a separate gate"
        />
      </div>

      <div className="provider-next-action">
        <ShieldCheck aria-hidden="true" size={17} />
        <div><strong>Next action</strong><p>{roadmap.next_action || "No next action is recorded."}</p></div>
      </div>

      <div className="provider-plan-grid">
        {accounts.map((account) => <ProviderPlanCard key={account.key} account={account} />)}
      </div>

      <div className="capability-roadmap">
        <div className="capability-roadmap-heading">
          <div><strong>Data capability roadmap</strong><span>{capabilities.length} distinct requirements; provider accounts may cover more than one.</span></div>
          <StatusPill value="database_driven" tone="info" />
        </div>
        <div className="capability-roadmap-list">
          {capabilities.map((capability) => (
            <article key={capability.key}>
              <div className="capability-roadmap-title">
                <div><strong>{capability.name}</strong><code>{capability.key}</code></div>
                <div><StatusPill value={capability.requirement_level} /><StatusPill value={capability.integration_status} /></div>
              </div>
              <p>{capability.description}</p>
              <dl>
                <div><dt>Planned sources</dt><dd>{capability.providers?.map((provider) => provider.name).filter(Boolean).join(" + ") || NOT_AVAILABLE}</dd></div>
                <div><dt>Unlocks</dt><dd>{capability.unlocks?.map(humanize).join(", ") || NOT_AVAILABLE}</dd></div>
              </dl>
            </article>
          ))}
        </div>
      </div>
    </Panel>
  );
}

function RoadmapMetric({ label, value, detail }: { label: string; value: string; detail: string }) {
  return <div><span>{label}</span><strong>{value}</strong><small>{detail}</small></div>;
}

function ProviderPlanCard({ account }: { account: ProviderRoadmapAccount }) {
  const documentationUrl = safeHttpsUrl(account.documentation_url);
  const signupUrl = safeHttpsUrl(account.signup_url);
  const pricingUrl = safeHttpsUrl(account.pricing_url);
  const termsUrl = safeHttpsUrl(account.terms_url);
  const capabilities = account.capabilities ?? [];

  return (
    <article className={`provider-plan-card ${account.required_for_first_slice ? "provider-plan-card--now" : ""}`}>
      <div className="provider-plan-card-header">
        <div><span>{humanize(account.category)}</span><h3>{account.name}</h3></div>
        <div>
          <StatusPill value={account.integration_status} />
          <StatusPill value={account.registration_available ? account.access_status : "register_later"} tone={account.registration_available ? undefined : "info"} />
        </div>
      </div>
      <p className="provider-plan-role">{account.role}</p>
      <div className="credential-capabilities">
        {capabilities.map((capability) => <span key={capability.key}>{humanize(capability.key)}</span>)}
      </div>
      <p className="provider-plan-guidance"><strong>{account.required_for_first_slice ? "Needed now" : "Full desk later"}</strong>{account.guidance}</p>
      <small>{account.licensing_note}</small>
      <div className="provider-plan-links">
        {signupUrl ? <a href={signupUrl} target="_blank" rel="noopener noreferrer">{account.registration_available ? "Manage account" : "Provider access"} <ExternalLink aria-hidden="true" size={11} /></a> : null}
        {documentationUrl ? <a href={documentationUrl} target="_blank" rel="noopener noreferrer">API docs <ExternalLink aria-hidden="true" size={11} /></a> : null}
        {pricingUrl ? <a href={pricingUrl} target="_blank" rel="noopener noreferrer">Pricing <ExternalLink aria-hidden="true" size={11} /></a> : null}
        {termsUrl ? <a href={termsUrl} target="_blank" rel="noopener noreferrer">Terms <ExternalLink aria-hidden="true" size={11} /></a> : null}
      </div>
    </article>
  );
}

export function ProviderCard({
  provider,
  busy,
  action,
  message,
  onSubmit,
  onVerify,
  onDelete,
}: {
  provider: AdminProvider;
  busy: boolean;
  action: string | null;
  message: { kind: "success" | "error"; text: string } | null;
  onSubmit: (event: FormEvent<HTMLFormElement>, provider: AdminProvider) => void;
  onVerify: (provider: AdminProvider) => void;
  onDelete: (provider: AdminProvider) => void;
}) {
  const credential = provider.credential;
  const configured = credential.configured;
  const verificationStatus = credentialVerificationStatus(credential);
  const healthy = verificationStatus === "healthy" && credential.status === "verified";
  const manageable = !configured || credential.managed === true || credential.source === "keyring";
  const cooldown = credential.cooldown_remaining_seconds ?? 0;
  const documentationUrl = safeHttpsUrl(provider.documentation_url);
  const signupUrl = safeHttpsUrl(provider.signup_url);
  const termsUrl = safeHttpsUrl(provider.terms_url);
  const lastVerification = provider.last_verification;

  return (
    <article className="credential-card">
      <div className="credential-card-header">
        <span className={`credential-mark ${healthy ? "credential-mark--healthy" : configured ? "credential-mark--unverified" : ""}`}>
          {healthy ? <CheckCircle2 aria-hidden="true" size={18} /> : <KeyRound aria-hidden="true" size={18} />}
        </span>
        <div>
          <div className="credential-title-line"><h3>{provider.name}</h3>{provider.required ? <StatusPill value="required" /> : <StatusPill value="optional" />}</div>
          <p>{humanize(provider.category || "data provider")} · <code>{provider.key}</code></p>
        </div>
        <StatusPill value={configured ? "configured" : "not_configured"} />
      </div>

      <div className="credential-health">
        <div><span>Verification</span><StatusPill value={verificationStatus} /></div>
        <div><span>Secret source</span><strong>{credential.source ? humanize(credential.source) : NOT_AVAILABLE}</strong></div>
        <div><span>Last tested</span><strong>{formatTimestamp(lastVerification?.checked_at || credential.last_verified_at)}</strong></div>
        <div><span>Valid until</span><strong>{formatTimestamp(credential.verification_expires_at)}</strong></div>
        <div><span>Health policy</span><strong>{formatCredentialDuration(credential.verification_ttl_seconds)}</strong></div>
        <div><span>Repeat-test cooldown</span><strong>{formatCredentialDuration(credential.cooldown_seconds)}</strong></div>
      </div>

      {credential.verification_policy_refresh_required ? (
        <div className="credential-policy-refresh" role="status">
          <AlertTriangle aria-hidden="true" size={15} />
          <span>This result was recorded under an older, shorter policy. Run one fresh smoke test to establish the current one-year window; the historical record remains unchanged.</span>
        </div>
      ) : null}

      {provider.capabilities?.length ? (
        <div className="credential-capabilities">{provider.capabilities.map((capability) => <span key={capability}>{humanize(capability)}</span>)}</div>
      ) : null}

      <div className="credential-instructions">
        <ShieldCheck aria-hidden="true" size={15} />
        <div>
          <strong>How to obtain access</strong>
          <p>{provider.instructions || "Provider instructions are not available."}</p>
          <div className="credential-official-links">
            {signupUrl ? <a href={signupUrl} target="_blank" rel="noopener noreferrer">Create or manage API key <ExternalLink aria-hidden="true" size={12} /></a> : null}
            {documentationUrl ? <a href={documentationUrl} target="_blank" rel="noopener noreferrer">Official API documentation <ExternalLink aria-hidden="true" size={12} /></a> : null}
            {termsUrl ? <a href={termsUrl} target="_blank" rel="noopener noreferrer">Provider terms <ExternalLink aria-hidden="true" size={12} /></a> : null}
          </div>
          {provider.attribution_notice ? <small className="credential-attribution">{provider.attribution_notice}</small> : null}
        </div>
      </div>

      {manageable ? (
        <form className="credential-form" onSubmit={(event) => onSubmit(event, provider)} autoComplete="off">
          <label htmlFor={`credential-${provider.key}`}>{configured ? "Rotate local key" : "Enter local key"}</label>
          <div>
            <input
              id={`credential-${provider.key}`}
              name="secret"
              type="password"
              autoComplete="off"
              spellCheck={false}
              disabled={busy}
              placeholder="Submitted once; never displayed"
              aria-describedby={`credential-note-${provider.key}`}
            />
            <button className="button" type="submit" disabled={busy}>{action === "write" ? "Saving…" : configured ? "Rotate" : "Save key"}</button>
          </div>
          <small id={`credential-note-${provider.key}`}>This app does not persist the submitted value in frontend state or browser storage. The backend stores supported secrets in the operating-system keyring.</small>
        </form>
      ) : (
        <div className="credential-env-notice"><AlertTriangle aria-hidden="true" size={15} /><span>This key comes from the server environment. Change it outside the app, then restart the service.</span></div>
      )}

      <div className="credential-actions">
        <button className="button button--quiet" type="button" disabled={busy || !configured || cooldown > 0} onClick={() => onVerify(provider)}>
          <TestTube2 aria-hidden="true" size={15} /> {action === "verify" ? "Testing…" : "Smoke test"}
        </button>
        {manageable && configured ? (
          <button className="button button--danger" type="button" disabled={busy} onClick={() => onDelete(provider)}>
            <Trash2 aria-hidden="true" size={14} /> Remove
          </button>
        ) : null}
        {cooldown > 0 ? <span>Test available in {formatNumber(cooldown)}s</span> : null}
      </div>

      {lastVerification ? (
        <p className="credential-verification-detail">
          Latest recorded test ({humanize(lastVerification.status)}): {lastVerification.message || "No test detail was recorded."}
          <span>{lastVerificationContext(lastVerification)}</span>
        </p>
      ) : null}
      {message ? <div className={`operator-action-message operator-action-message--${message.kind}`} role="status">{message.kind === "success" ? <CheckCircle2 aria-hidden="true" size={15} /> : <AlertTriangle aria-hidden="true" size={15} />}{message.text}</div> : null}
    </article>
  );
}

export function credentialVerificationStatus(credential: CredentialStatus): string {
  if (credential.status === "invalid_clock") return "invalid_clock";
  if (credential.status === "expired") return "expired";
  if (credential.verification_status) return credential.verification_status;
  if (!credential.configured) return "not_configured";
  if (credential.status === "unhealthy") return "unhealthy";
  return "unverified";
}

export function lastVerificationContext(verification: ProviderLastVerification): string {
  if (verification.future_dated) {
    return "This test timestamp is outside the server clock tolerance and cannot establish current health. Correct the clock, then run a new smoke test.";
  }
  if (!verification.applies_to_credential) {
    return "This test does not apply to the current credential and is historical only.";
  }
  if (verification.expired) {
    return "This test applied to the current credential, but its health-validity window has expired.";
  }
  if (!verification.current) {
    return "This result is historical and is not current provider health.";
  }
  return `Current for this credential until ${formatTimestamp(verification.effective_expires_at || verification.expires_at)}.`;
}

export function formatCredentialDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || !Number.isFinite(seconds)) return NOT_AVAILABLE;
  if (seconds === 31_536_000) return "1 year";
  if (seconds % 86_400 === 0) return `${formatNumber(seconds / 86_400)} days`;
  if (seconds % 3_600 === 0) return `${formatNumber(seconds / 3_600)} hours`;
  if (seconds % 60 === 0) return `${formatNumber(seconds / 60)} minutes`;
  return `${formatNumber(seconds)} seconds`;
}

function safeHttpsUrl(value: string | null | undefined): string | null {
  if (!value) return null;
  try {
    const parsed = new URL(value);
    return parsed.protocol === "https:" ? parsed.toString() : null;
  } catch {
    return null;
  }
}
