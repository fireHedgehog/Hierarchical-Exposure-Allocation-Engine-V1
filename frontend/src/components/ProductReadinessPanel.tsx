import { ArrowRight, ChevronDown } from "lucide-react";
import { Link } from "react-router-dom";
import type {
  ProductReadiness,
  ProductReadinessEvidence,
  ProductReadinessGate,
  ProductReadinessStatus,
} from "../types";
import { formatNumber, formatTimestamp, humanize, NOT_AVAILABLE } from "../utils/format";
import { Panel, SectionHeading, StatusPill, Unavailable } from "./Ui";

export function ProductReadinessPanel({ readiness }: { readiness?: ProductReadiness | null }) {
  if (!readiness) {
    return (
      <Panel className="operator-readiness-panel">
        <SectionHeading
          eyebrow="Evidence-gated product roadmap"
          title="Demo → real readiness"
          description="Product readiness is evaluated separately from pipeline implementation and run history."
        />
        <Unavailable
          title="Product readiness not available"
          detail="The operator overview has no persisted readiness contract. No product milestone can be treated as passed."
        />
      </Panel>
    );
  }

  const milestones = [...(readiness.milestones ?? [])].sort(compareReadinessOrder);
  const gates = [...(readiness.gates ?? [])].sort(compareReadinessOrder);
  const milestoneKeys = new Set(milestones.map((milestone) => milestone.key));
  const unassignedGates = gates.filter((gate) => !milestoneKeys.has(gate.milestone_key));
  const summary = readiness.summary;

  return (
    <Panel className="operator-readiness-panel">
      <SectionHeading
        eyebrow="Evidence-gated product roadmap"
        title="Demo → real readiness"
        description="These gates answer whether an output is backed by qualifying real evidence. Pipeline implementation and execution history remain separate below."
      />

      <div className="readiness-summary" aria-label="Product readiness counts">
        <ReadinessCount label="Milestones passed" value={summary.milestones_passed} total={summary.milestones_total} />
        <ReadinessCount label="Evidence gates passed" value={summary.gates_passed} total={summary.gates_total} />
        <article className="readiness-summary__current">
          <span>Current evidence gate</span>
          <strong>{summary.current_gate_key || NOT_AVAILABLE}</strong>
        </article>
      </div>

      <div className="readiness-current-action">
        <div>
          <span>Current action</span>
          <strong>{summary.current_action || "No current product-readiness action is recorded."}</strong>
        </div>
        <ReadinessRouteLink route={summary.target_route} label="Open next surface" />
      </div>

      {milestones.length ? (
        <ol className="readiness-milestone-list">
          {milestones.map((milestone, milestoneIndex) => {
            const milestoneGates = gates.filter((gate) => gate.milestone_key === milestone.key);
            const containsCurrentGate = milestoneGates.some((gate) => gate.key === summary.current_gate_key);
            return (
              <li className={`readiness-milestone readiness-milestone--${milestone.status}`} key={milestone.key}>
                <details open={containsCurrentGate}>
                  <summary className="readiness-milestone__header">
                    <span className="readiness-milestone__number" aria-hidden="true">
                      {String(milestoneIndex + 1).padStart(2, "0")}
                    </span>
                    <div>
                      <p className="eyebrow">Milestone · {milestone.key}</p>
                      <h3>{milestone.name || "Unnamed milestone"}</h3>
                      <p>{milestone.description || "No milestone description is recorded."}</p>
                    </div>
                    <div className="readiness-milestone__state">
                      <StatusPill value={milestone.status} tone={readinessTone(milestone.status)} />
                      <span>{formatNumber(milestone.gates_passed)} of {formatNumber(milestone.gates_total)} gates passed</span>
                    </div>
                    <ChevronDown className="readiness-milestone__chevron" aria-hidden="true" size={16} />
                  </summary>

                  {milestoneGates.length ? (
                    <ol className="readiness-gate-list">
                      {milestoneGates.map((gate) => (
                        <ReadinessGateCard
                          gate={gate}
                          current={gate.key === summary.current_gate_key}
                          key={gate.key}
                        />
                      ))}
                    </ol>
                  ) : (
                    <Unavailable
                      compact
                      title="Milestone gates not available"
                      detail="This milestone has no evidence-gate definitions; its state cannot be independently inspected here."
                    />
                  )}
                </details>
              </li>
            );
          })}
        </ol>
      ) : (
        <Unavailable
          title="Readiness milestones not available"
          detail="No ordered product milestones are returned. Counts alone do not establish readiness."
        />
      )}

      {unassignedGates.length ? (
        <section className="readiness-unassigned" aria-labelledby="unassigned-readiness-gates">
          <div>
            <h3 id="unassigned-readiness-gates">Unassigned evidence gates</h3>
            <p>These gates reference a milestone that is absent from the current contract, so they cannot be presented as completed roadmap steps.</p>
          </div>
          <ol className="readiness-gate-list">
            {unassignedGates.map((gate) => (
              <ReadinessGateCard gate={gate} current={gate.key === summary.current_gate_key} key={gate.key} />
            ))}
          </ol>
        </section>
      ) : null}
    </Panel>
  );
}

function ReadinessCount({ label, value, total }: { label: string; value: number; total: number }) {
  return (
    <article>
      <span>{label}</span>
      <strong>{formatNumber(value)} <small>of {formatNumber(total)}</small></strong>
    </article>
  );
}

function ReadinessGateCard({ gate, current }: { gate: ProductReadinessGate; current: boolean }) {
  const dependencies = gate.dependencies ?? [];
  const blockedBy = gate.blocked_by ?? [];
  const evidence = gate.evidence ?? [];
  return (
    <li className={`readiness-gate readiness-gate--${gate.status}`}>
      <div className="readiness-gate__header">
        <div>
          <span>{gate.layer ? humanize(gate.layer) : "Layer not recorded"}</span>
          <h4>{gate.name || "Unnamed evidence gate"}</h4>
        </div>
        <div>
          {current ? <span className="readiness-current-marker">Current gate</span> : null}
          <StatusPill value={gate.status} tone={readinessTone(gate.status)} />
        </div>
      </div>

      <p className="readiness-gate__description">{gate.description || "No gate description is recorded."}</p>

      <div className="readiness-gate__contract">
        <div>
          <span>Acceptance criterion</span>
          <p>{gate.acceptance_criterion || "No acceptance criterion is recorded; this gate cannot qualify."}</p>
        </div>
        <div>
          <span>Evaluator</span>
          <code>{gate.evaluator_key || NOT_AVAILABLE}</code>
        </div>
      </div>

      {dependencies.length || blockedBy.length || gate.status === "blocked" ? (
        <div className="readiness-dependencies">
          {dependencies.length ? (
            <div>
              <span>Dependencies</span>
              <ul>{dependencies.map((dependency) => <li key={dependency}><code>{dependency}</code></li>)}</ul>
            </div>
          ) : null}
          <div>
            <span>Blocked by</span>
            {blockedBy.length ? (
              <ul>{blockedBy.map((dependency) => <li key={dependency}><code>{dependency}</code></li>)}</ul>
            ) : (
              <p>{gate.status === "blocked" ? "Blocked dependency identifiers are not recorded." : "No blocked dependency is reported."}</p>
            )}
          </div>
        </div>
      ) : null}

      <section className="readiness-evidence" aria-label={`${gate.name || gate.key} evidence`}>
        <h5>Current evidence</h5>
        {evidence.length ? (
          <ul>
            {evidence.map((item, index) => (
              <ReadinessEvidenceItem evidence={item} key={`${item.kind}-${item.record_id || index}`} />
            ))}
          </ul>
        ) : (
          <Unavailable
            compact
            title="Evidence not recorded"
            detail="No qualifying, non-qualifying, or missing evidence record is attached to this gate."
          />
        )}
      </section>

      <div className="readiness-next-action">
        <div>
          <span>Next action</span>
          <strong>{gate.next_action || nextActionFallback(gate.status)}</strong>
        </div>
        <ReadinessRouteLink route={gate.target_route} label="Go to action" />
      </div>
    </li>
  );
}

function ReadinessEvidenceItem({ evidence }: { evidence: ProductReadinessEvidence }) {
  return (
    <li>
      <div className="readiness-evidence__title">
        <strong>{evidence.kind ? humanize(evidence.kind) : "Evidence kind not recorded"}</strong>
        <StatusPill value={evidence.status} tone={evidenceTone(evidence.status)} />
      </div>
      <p>{evidence.summary || "No evidence summary is recorded."}</p>
      <dl>
        <div><dt>Observed</dt><dd>{formatTimestamp(evidence.observed_at)}</dd></div>
        <div><dt>Record ID</dt><dd><code>{evidence.record_id || NOT_AVAILABLE}</code></dd></div>
      </dl>
    </li>
  );
}

function ReadinessRouteLink({ route, label }: { route?: string | null; label: string }) {
  if (!route) return <span className="readiness-route-unavailable">Target route not recorded</span>;
  if (!isInternalRoute(route)) return <span className="readiness-route-unavailable">Invalid target route</span>;
  return <Link className="button button--quiet readiness-route-link" to={route}>{label}<ArrowRight aria-hidden="true" size={14} /></Link>;
}

function compareReadinessOrder<T extends { sort_order: number; key: string }>(left: T, right: T): number {
  return left.sort_order - right.sort_order || left.key.localeCompare(right.key);
}

function isInternalRoute(route: string): boolean {
  return route.startsWith("/") && !route.startsWith("//");
}

function readinessTone(status: ProductReadinessStatus): "positive" | "negative" | "warning" | "info" {
  if (status === "passed") return "positive";
  if (status === "action_required") return "warning";
  if (status === "deferred") return "info";
  return "negative";
}

function evidenceTone(status: ProductReadinessEvidence["status"]): "positive" | "negative" {
  return status === "qualifying" ? "positive" : "negative";
}

function nextActionFallback(status: ProductReadinessStatus): string {
  if (status === "passed") return "No further action is recorded for this passed gate.";
  if (status === "deferred") return "No current action is recorded because this gate is deferred.";
  return "The next action is not recorded.";
}
