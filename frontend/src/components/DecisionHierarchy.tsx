import { ArrowDown, Braces, ChevronDown, CircleDot, Gauge, GitBranch } from "lucide-react";
import type { DecisionEdge, DecisionGraph, DecisionNode, Regime } from "../types";
import {
  formatPercent,
  formatScalar,
  formatTimestamp,
  humanize,
  isFiniteNumber,
  NOT_AVAILABLE,
  toneForDirection,
  toneForStatus,
} from "../utils/format";
import { ProvenanceStrip, StatusPill, Unavailable } from "./Ui";

export function RegimeConsole({ regime }: { regime?: Regime | null }) {
  return (
    <div className="regime-console">
      <div className="regime-console__lead">
        <div className="regime-icon" aria-hidden="true">
          <Gauge />
        </div>
        <div>
          <p className="eyebrow">State modifier</p>
          <h3>{regime?.label || NOT_AVAILABLE}</h3>
          <p>{regime?.summary || "No persisted regime summary is available."}</p>
        </div>
        <div className="regime-confidence">
          <span>6M adverse frequency</span>
          <strong>{formatPercent(regime?.confidence)}</strong>
        </div>
      </div>

      <RegimePercentileGauge percentileRank={regime?.percentile_rank} />

      <RegimeFactorDetail
        filters={regime?.filters}
        weights={regime?.weights}
        contributions={regime?.contributions}
      />
      <ProvenanceStrip provenance={regime} compact />
    </div>
  );
}

// The zones are the runtime policy boundaries; the 0-100 position uses the
// exact 13-factor current-vintage reference distribution from S3-CV.
const GAUGE_STRESSED_CUTOFF = 33;
const GAUGE_CALM_CUTOFF = 67;

function RegimePercentileGauge({ percentileRank }: { percentileRank?: number | null }) {
  if (!isFiniteNumber(percentileRank)) {
    return null;
  }
  const clamped = Math.max(0, Math.min(100, percentileRank));
  const zoneLabel =
    clamped <= GAUGE_STRESSED_CUTOFF ? "Risk-off" : clamped >= GAUGE_CALM_CUTOFF ? "Risk-on" : "Balanced";

  return (
    <div className="regime-gauge">
      <p className="regime-gauge__title">Macro environment position</p>

      <div className="regime-gauge__pointer-row" style={{ "--gauge-position": `${clamped}%` } as React.CSSProperties}>
        <div className="regime-gauge__pointer">
          <strong>{clamped.toFixed(0)}</strong>
          <span>{zoneLabel}</span>
        </div>
      </div>

      <div className="regime-gauge__track" role="img" aria-label={`${clamped.toFixed(0)} of 100 on the macro environment scale, ${zoneLabel}`}>
        <div className="regime-gauge__zone regime-gauge__zone--off" style={{ width: `${GAUGE_STRESSED_CUTOFF}%` }} />
        <div
          className="regime-gauge__zone regime-gauge__zone--neutral"
          style={{ width: `${GAUGE_CALM_CUTOFF - GAUGE_STRESSED_CUTOFF}%` }}
        />
        <div className="regime-gauge__zone regime-gauge__zone--on" style={{ width: `${100 - GAUGE_CALM_CUTOFF}%` }} />
        <div className="regime-gauge__needle" style={{ left: `${clamped}%` }} />
      </div>

      <div className="regime-gauge__ticks">
        <span className="regime-gauge__tick" style={{ left: "0%" }}>0</span>
        <span className="regime-gauge__tick" style={{ left: `${GAUGE_STRESSED_CUTOFF}%` }}>{GAUGE_STRESSED_CUTOFF}</span>
        <span className="regime-gauge__tick" style={{ left: `${GAUGE_CALM_CUTOFF}%` }}>{GAUGE_CALM_CUTOFF}</span>
        <span className="regime-gauge__tick regime-gauge__tick--last" style={{ left: "100%" }}>100</span>
      </div>

      <div className="regime-gauge__zone-labels">
        <span>Risk-off</span>
        <span>Balanced</span>
        <span>Risk-on</span>
      </div>

      <p className="regime-gauge__readout">
        Today: <strong>{clamped.toFixed(0)}/100</strong> macro environment position ({zoneLabel}). Higher is more
        risk-on; lower is more risk-off.
      </p>
    </div>
  );
}

export function DecisionHierarchy({
  regime,
  graph,
}: {
  regime?: Regime | null;
  graph?: DecisionGraph | null;
}) {
  const nodes = graph?.nodes ?? [];
  const grouped = groupByLayer(nodes);

  return (
    <div className="hierarchy-layout">
      <RegimeConsole regime={regime} />

      {grouped.length ? (
        <div className="hierarchy-flow" aria-label="Top-down allocation hierarchy">
          {grouped.map(([layer, layerNodes], layerIndex) => (
            <div className="hierarchy-stage" key={layer}>
              <div className="hierarchy-stage__label">
                <span>{String(layerIndex + 1).padStart(2, "0")}</span>
                <div>
                  <small>Decision layer</small>
                  <h3>{humanize(layer)}</h3>
                </div>
              </div>
              <div className="hierarchy-stage__nodes">
                {layerNodes.map((node) => (
                  <HierarchyNode
                    node={node}
                    incoming={incomingEdges(node, graph?.edges ?? [])}
                    nodeLabels={new Map(nodes.map((item) => [item.id, item.label]))}
                    key={node.id}
                  />
                ))}
              </div>
              {layerIndex < grouped.length - 1 ? (
                <div className="hierarchy-connector" aria-hidden="true">
                  <span />
                  <ArrowDown />
                </div>
              ) : null}
            </div>
          ))}
        </div>
      ) : (
        <Unavailable
          title="Decision hierarchy not available"
          detail="No persisted decision nodes were returned for this snapshot."
        />
      )}

      {graph?.observations?.length ? (
        <div className="hierarchy-observations">
          <div className="hierarchy-observations__title">
            <GitBranch aria-hidden="true" size={17} />
            <h3>Engine observations</h3>
          </div>
          <ul>
            {graph.observations.map((observation, index) => (
              <li key={observation.id || `${observation.label}-${index}`}>
                <div>
                  <strong>{observation.label}</strong>
                  <StatusPill value={observation.status} />
                </div>
                <span>{formatScalar(observation.value, observation.unit)}</span>
                {observation.detail ? <p>{observation.detail}</p> : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

function groupByLayer(nodes: DecisionNode[]): [string, DecisionNode[]][] {
  const groups = new Map<string, DecisionNode[]>();
  for (const node of nodes) {
    const key = node.layer || node.type || "unspecified_layer";
    const existing = groups.get(key) ?? [];
    existing.push(node);
    groups.set(key, existing);
  }
  return Array.from(groups.entries());
}

function incomingEdges(node: DecisionNode, edges: DecisionEdge[]): DecisionEdge[] {
  const linked = edges.filter((edge) => (edge.target ?? edge.to) === node.id);
  if (!linked.length && node.parent_id) {
    return [{ source: node.parent_id, target: node.id, relation: "parent" }];
  }
  return linked;
}

function HierarchyNode({
  node,
  incoming,
  nodeLabels,
}: {
  node: DecisionNode;
  incoming: DecisionEdge[];
  nodeLabels: Map<string, string>;
}) {
  const hasEvidence = Boolean(node.evidence?.length || node.description || node.summary);
  return (
    <article className="hierarchy-node">
      {incoming.length ? (
        <div className="node-lineage" aria-label="Incoming decision links">
          {incoming.map((edge, index) => (
            <div className="node-lineage__edge" key={edge.id || `${edge.source ?? edge.from}-${edge.target ?? edge.to}-${index}`}>
              <span className="node-lineage__branch" aria-hidden="true" />
              <div>
                <small>From</small>
                <strong>{nodeLabels.get(edge.source ?? edge.from ?? "") || edge.source || edge.from || NOT_AVAILABLE}</strong>
              </div>
              <div>
                <small>Relation</small>
                <strong>{humanize(edge.relation || edge.label)}</strong>
              </div>
              <div>
                <small>Edge weight</small>
                <strong>{formatPercent(edge.weight)}</strong>
              </div>
              {edge.rationale ? <p>{edge.rationale}</p> : null}
            </div>
          ))}
        </div>
      ) : (
        <div className="node-lineage node-lineage--root">Root decision</div>
      )}
      <div className="hierarchy-node__topline">
        <div>
          <CircleDot aria-hidden="true" size={14} />
          <span>{node.id}</span>
        </div>
        <StatusPill value={node.status} />
      </div>
      <h4>{node.label}</h4>
      {node.confidence !== null && node.confidence !== undefined ? (
        <div className="hierarchy-node__confidence">
          <span>Confidence</span>
          <strong>{formatPercent(node.confidence)}</strong>
        </div>
      ) : null}

      <dl className="triplet-grid">
        <div>
          <dt>Current</dt>
          <dd>{formatScalar(node.current_value, node.value_unit)}</dd>
        </div>
        <div>
          <dt>Target</dt>
          <dd>{formatScalar(node.target_value, node.value_unit)}</dd>
        </div>
        <div className={isFiniteNumber(node.delta_value) ? `direction-${node.delta_value > 0 ? "up" : node.delta_value < 0 ? "down" : "flat"}` : ""}>
          <dt>Delta</dt>
          <dd>{formatScalar(node.delta_value, node.value_unit)}</dd>
        </div>
      </dl>

      <div className="node-attribution">
        <span>
          Contribution <b>{formatPercent(node.contribution)}</b>
        </span>
      </div>

      {node.constraints?.length ? (
        <div className="constraint-list">
          <span>Binding context</span>
          {node.constraints.map((constraint) => (
            <em key={constraint}>{constraint}</em>
          ))}
        </div>
      ) : null}

      {hasEvidence ? (
        <details className="evidence-disclosure">
          <summary>Evidence and interpretation</summary>
          {node.description || node.summary ? <p>{node.description || node.summary}</p> : null}
          {node.evidence?.length ? (
            <dl>
              {node.evidence.map((evidence, index) => (
                <div key={`${evidence.label}-${index}`}>
                  <dt>{evidence.label}</dt>
                  <dd>
                    <b>{formatScalar(evidence.value)}</b>
                    {evidence.detail ? <span>{evidence.detail}</span> : null}
                    {evidence.source ? <small>Source: {evidence.source}</small> : null}
                  </dd>
                </div>
              ))}
            </dl>
          ) : null}
        </details>
      ) : null}
    </article>
  );
}

function RegimeFactorDetail({
  filters,
  weights,
  contributions,
}: {
  filters?: Regime["filters"];
  weights?: Regime["weights"];
  contributions?: Regime["contributions"];
}) {
  const weightByKey = new Map((weights ?? []).map((item) => [item.key || item.name, item]));
  const contributionByKey = new Map((contributions ?? []).map((item) => [item.key || item.name, item]));
  const rows = filters ?? [];

  if (!rows.length) {
    return (
      <div className="regime-factor-detail">
        <Unavailable compact />
      </div>
    );
  }

  return (
    <details className="regime-factor-detail">
      <summary>
        <Braces aria-hidden="true" size={14} />
        <span>Factor detail ({rows.length})</span>
        <ChevronDown aria-hidden="true" size={14} className="regime-factor-detail__chevron" />
      </summary>
      <div className="regime-factor-table-wrap">
        <table className="regime-factor-table">
          <thead>
            <tr>
              <th scope="col">Factor</th>
              <th scope="col">Current</th>
              <th scope="col">Trailing basis</th>
              <th scope="col">Weight</th>
              <th scope="col">Direction</th>
              <th scope="col" aria-label="More" />
            </tr>
          </thead>
          <tbody>
            {rows.map((filter) => {
              const factorKey = filter.key || filter.name;
              const weight = weightByKey.get(factorKey);
              const contribution = contributionByKey.get(factorKey);
              const hasDetail = Boolean(filter.explanation || contribution?.explanation || contribution?.evidence?.length);
              return (
                <tr key={filter.name}>
                  <td>
                    <strong>{filter.name}</strong>
                    <StatusPill value={filter.status} tone={toneForStatus(filter.status)} />
                  </td>
                  <td>{formatScalar(filter.value)}</td>
                  <td>{formatScalar(filter.threshold)}</td>
                  <td>{formatScalar(weight?.value, weight?.unit)}</td>
                  <td className={`tone-${toneForDirection(contribution?.direction)}`}>
                    {contribution?.direction ? humanize(contribution.direction) : NOT_AVAILABLE}
                  </td>
                  <td>
                    {hasDetail ? (
                      <details className="regime-factor-row-detail">
                        <summary>More</summary>
                        {filter.explanation ? <p>{filter.explanation}</p> : null}
                        {contribution?.explanation ? <p>{contribution.explanation}</p> : null}
                        {contribution?.evidence?.length ? (
                          <dl>
                            {contribution.evidence.map((evidence, index) => (
                              <div key={`${evidence.label}-${index}`}>
                                <dt>{evidence.label}</dt>
                                <dd>{formatScalar(evidence.value)}</dd>
                              </div>
                            ))}
                          </dl>
                        ) : null}
                        <dl>
                          <div><dt>Source</dt><dd>{filter.source_key || filter.source_name || NOT_AVAILABLE}</dd></div>
                          <div><dt>Observed</dt><dd>{formatTimestamp(filter.observed_at)}</dd></div>
                          <div><dt>Available</dt><dd>{formatTimestamp(filter.available_at)}</dd></div>
                        </dl>
                      </details>
                    ) : null}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </details>
  );
}
