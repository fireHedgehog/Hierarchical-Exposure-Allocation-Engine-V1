import { Ban, Boxes, CheckCircle2, ExternalLink, ShieldAlert } from "lucide-react";
import { Link } from "react-router-dom";
import type { PositionCandidate, PositionLeg } from "../types";
import {
  formatCurrency,
  formatNumber,
  formatPercent,
  humanize,
  NOT_AVAILABLE,
} from "../utils/format";
import { ConvictionBadge, ProvenanceStrip, StatusPill, Unavailable } from "./Ui";

export function PositionCandidates({
  positions,
  title = "Proposed position expressions",
}: {
  positions?: PositionCandidate[] | null;
  title?: string;
}) {
  if (!positions?.length) {
    return (
      <Unavailable
        title="Position proposals not available"
        detail="The persisted snapshot contains no proposed position expressions."
      />
    );
  }

  return (
    <div className="position-list">
      <div className="position-list__notice">
        <Boxes aria-hidden="true" size={16} />
        <span>{title}</span>
        <em>Proposal record · not an order</em>
      </div>
      {positions.map((position) => (
        <PositionCard position={position} key={position.id} />
      ))}
    </div>
  );
}

function PositionCard({ position }: { position: PositionCandidate }) {
  const unresolvedBlockers = position.blockers?.filter(
    (blocker) => typeof blocker === "string" || blocker.resolved !== true,
  ) ?? [];
  const ready = isPositionReady(position);
  const blocked = !ready;
  const completenessLabel = position.input_completeness_scope === "synthetic_simulation_inputs"
    ? "Simulation inputs complete"
    : position.input_completeness_scope === "live_market_data"
      ? "Live market data complete"
      : "Inputs complete";
  return (
    <article className={`position-card ${blocked ? "position-card--blocked" : ""}`}>
      <div className="position-card__identity">
        <div className="position-symbol">
          <Link to={`/symbols/${encodeURIComponent(position.symbol)}`}>
            {position.symbol} <ExternalLink aria-hidden="true" size={13} />
          </Link>
          <span>{position.name || NOT_AVAILABLE}</span>
        </div>
        <div className="position-card__pills">
          <ConvictionBadge value={position.conviction} />
          <StatusPill value={position.side} />
          <StatusPill value={position.structure_type} />
          <StatusPill value={position.actionability || position.status} />
        </div>
      </div>

      <div className="position-card__basis">
        Allocation basis: <strong>{humanize(position.allocation_basis)}</strong>
      </div>
      <div className="position-card__allocation">
        <AllocationDatum label="Current" value={position.current_weight} />
        <span className="allocation-arrow" aria-hidden="true">→</span>
        <AllocationDatum label="Target" value={position.target_weight} emphasis />
        <AllocationDatum label="Delta" value={position.delta_weight} delta />
      </div>

      <div className="position-card__risk">
        <div>
          <span>Confidence</span>
          <strong>{formatPercent(position.confidence)}</strong>
        </div>
        <div>
          <span>Maximum loss</span>
          <strong>{formatCurrency(position.max_loss)}</strong>
        </div>
        <div>
          <span>Maximum profit</span>
          <strong>{formatCurrency(position.max_profit)}</strong>
        </div>
        <div>
          <span>Net debit / credit</span>
          <strong>{formatCurrency(position.net_debit_credit ?? position.net_debit ?? position.net_credit)}</strong>
        </div>
        <div>
          <span>Cost estimate</span>
          <strong>{formatCurrency(position.cost_estimate)}</strong>
        </div>
        <div>
          <span>Breakeven low</span>
          <strong>{formatCurrency(position.breakeven_low)}</strong>
        </div>
        <div>
          <span>Breakeven high</span>
          <strong>{formatCurrency(position.breakeven_high)}</strong>
        </div>
        <div>
          <span>Horizon</span>
          <strong>{position.horizon || NOT_AVAILABLE}</strong>
        </div>
      </div>

      <div className={`actionability ${blocked ? "actionability--blocked" : "actionability--ready"}`}>
        {blocked ? <Ban aria-hidden="true" /> : <CheckCircle2 aria-hidden="true" />}
        <div>
          <strong>{blocked ? "Not actionable from this snapshot" : humanize(position.actionability || position.status || "actionability_not_specified")}</strong>
          <span>
            {completenessLabel}: {position.market_data_complete === null || position.market_data_complete === undefined ? NOT_AVAILABLE : position.market_data_complete ? "Yes" : "No"}
          </span>
        </div>
      </div>

      {unresolvedBlockers.length ? (
        <div className="blocker-list">
          <ShieldAlert aria-hidden="true" size={16} />
          <div>
            <strong>Blockers</strong>
            <ul>
              {unresolvedBlockers.map((blocker, index) => (
                <li key={typeof blocker === "string" ? blocker : blocker.key || `${blocker.label}-${index}`}>
                  <strong>{typeof blocker === "string" ? blocker : blocker.label}</strong>
                  {typeof blocker !== "string" && blocker.detail ? <span>{blocker.detail}</span> : null}
                </li>
              ))}
            </ul>
          </div>
        </div>
      ) : null}

      <details className="position-details">
        <summary>Structure, rationale, and risk</summary>
        <div className="position-details__grid">
          <div>
            <h4>Legs</h4>
            {position.legs?.length ? <LegTable legs={position.legs} /> : <Unavailable compact />}
          </div>
          <TextList title="Rationale" values={position.rationale} />
          <TextList title="Known risks" values={position.risks} />
          <div>
            <h4>Local Greeks</h4>
            <dl className="greeks-grid">
              {(["delta", "gamma", "vega", "theta", "rho"] as const).map((greek) => (
                <div key={greek}>
                  <dt>{humanize(greek)}</dt>
                  <dd>{formatGreek(position.greeks?.[greek])}</dd>
                </div>
              ))}
            </dl>
          </div>
        </div>
      </details>
      <ProvenanceStrip provenance={position} sourceLabel="Position proposal" compact />
    </article>
  );
}

const READY_POSITION_STATES = new Set([
  "ready",
  "actionable",
  "simulation_ready",
  "synthetic_simulation_ready",
]);

const BLOCKING_POSITION_STATES = new Set([
  "blocked",
  "unavailable",
  "not_available",
  "review",
  "review_only",
  "not_ready",
  "not_actionable",
  "missing",
  "incomplete",
  "invalid",
  "disabled",
]);

export function isPositionReady(position: PositionCandidate): boolean {
  if (position.market_data_complete !== true) return false;

  const hasRequiredBlocker = position.blockers?.some((blocker) => {
    if (typeof blocker === "string") return true;
    return blocker.resolved !== true && blocker.required !== false;
  }) ?? false;
  if (hasRequiredBlocker) return false;

  const states = [position.actionability, position.status]
    .filter((state): state is string => typeof state === "string" && state.trim().length > 0)
    .map((state) => state.trim().toLowerCase().replace(/[\s-]+/g, "_"));
  if (states.some((state) => BLOCKING_POSITION_STATES.has(state))) return false;
  return states.some((state) => READY_POSITION_STATES.has(state));
}

function formatGreek(value: number | { value: number | null; unit?: string | null } | null | undefined): string {
  if (value && typeof value === "object") {
    const formatted = formatNumber(value.value, { maximumFractionDigits: 4 });
    return value.unit && formatted !== NOT_AVAILABLE ? `${formatted} ${humanize(value.unit)}` : formatted;
  }
  return formatNumber(value, { maximumFractionDigits: 4 });
}

function AllocationDatum({
  label,
  value,
  emphasis = false,
  delta = false,
}: {
  label: string;
  value?: number | null;
  emphasis?: boolean;
  delta?: boolean;
}) {
  return (
    <div className={`${emphasis ? "allocation-datum--emphasis" : ""} ${delta ? "allocation-datum--delta" : ""}`.trim()}>
      <span>{label}</span>
      <strong>{formatPercent(value)}</strong>
    </div>
  );
}

function LegTable({ legs }: { legs: PositionLeg[] }) {
  return (
    <div className="leg-list">
      {legs.map((leg, index) => (
        <div key={`${leg.instrument || leg.symbol || "leg"}-${index}`}>
          <StatusPill value={leg.action || leg.side} />
          <strong>{leg.instrument || leg.symbol || NOT_AVAILABLE}</strong>
          <span>{leg.instrument_type ? humanize(leg.instrument_type) : NOT_AVAILABLE}</span>
          <span>Type {leg.option_type ? humanize(leg.option_type) : NOT_AVAILABLE}</span>
          <span>Qty {formatNumber(leg.quantity)}</span>
          {leg.strike !== null && leg.strike !== undefined ? <span>Strike {formatCurrency(leg.strike)}</span> : null}
          <span>Expiry {leg.expiry || leg.expiration || NOT_AVAILABLE}</span>
          <span>DTE {formatNumber(leg.dte)}</span>
          <span>Bid {formatCurrency(leg.bid)}</span>
          <span>Ask {formatCurrency(leg.ask)}</span>
          <span>Mid {formatCurrency(leg.mid)}</span>
          <span>Multiplier {formatNumber(leg.multiplier)}</span>
          <span>OI {formatNumber(leg.open_interest)}</span>
          <span>Volume {formatNumber(leg.volume)}</span>
          <span>IV {formatPercent(leg.implied_volatility)}</span>
          <span>Δ {formatNumber(leg.delta, { maximumFractionDigits: 4 })}</span>
          <span>Γ {formatNumber(leg.gamma, { maximumFractionDigits: 4 })}</span>
          <span>Θ {formatNumber(leg.theta, { maximumFractionDigits: 4 })}</span>
          <span>Vega {formatNumber(leg.vega, { maximumFractionDigits: 4 })}</span>
        </div>
      ))}
    </div>
  );
}

function TextList({ title, values }: { title: string; values?: string[] | null }) {
  return (
    <div>
      <h4>{title}</h4>
      {values?.length ? <ul className="plain-list">{values.map((value) => <li key={value}>{value}</li>)}</ul> : <Unavailable compact />}
    </div>
  );
}
