import {
  AlertTriangle,
  CheckCircle2,
  ExternalLink,
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
  useApi,
  verifyProvider,
  writeProviderCredential,
} from "../api/client";
import { OperatorPageHeader } from "../components/OperatorPageHeader";
import { Panel, ResourceState, SectionHeading, StatusPill, Unavailable } from "../components/Ui";
import type { AdminProvider, CredentialStatus, ProviderLastVerification, ProvidersResponse } from "../types";
import { formatNumber, formatTimestamp, humanize, NOT_AVAILABLE } from "../utils/format";

export function CredentialsPage() {
  const state = useApi<ProvidersResponse>(endpoints.adminProviders);
  const providers = state.data?.providers ?? [];
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

      {state.data ? (
        <Panel>
          <SectionHeading
            eyebrow={`${providers.length} registered providers`}
            title="Local access and smoke tests"
            description="Smoke-test cooldown and health validity are separate. An expired result remains visible as history, but cannot imply current provider health."
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
      </div>

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

function safeHttpsUrl(value: string | null | undefined): string | null {
  if (!value) return null;
  try {
    const parsed = new URL(value);
    return parsed.protocol === "https:" ? parsed.toString() : null;
  } catch {
    return null;
  }
}
