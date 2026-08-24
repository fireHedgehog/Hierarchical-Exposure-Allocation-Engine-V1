import { ArrowDown, Braces, CircleDot, Filter, Gauge, GitBranch, Scale } from "lucide-react";
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
            <span>Confidence</span>
            <strong>{formatPercent(regime?.confidence)}</strong>
          </div>
        </div>

        <div className="regime-console__grid">
          <RegimeFilters filters={regime?.filters} />
          <RegimeWeights weights={regime?.weights} />
          <RegimeContributions contributions={regime?.contributions} />
        </div>
        <ProvenanceStrip provenance={regime} compact />
      </div>

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

function RegimeFilters({ filters }: { filters?: Regime["filters"] }) {
  return (
    <div className="regime-module">
      <div className="regime-module__title">
        <Filter aria-hidden="true" size={15} />
        <h4>Filters</h4>
      </div>
      {filters?.length ? (
        <div className="filter-stack">
          {filters.map((filter) => (
            <div className="filter-row" key={filter.name}>
              <div>
                <strong>{filter.name}</strong>
                {filter.explanation ? <small>{filter.explanation}</small> : null}
              </div>
              <span>{formatScalar(filter.value)}</span>
              <span className="filter-threshold">vs {formatScalar(filter.threshold)}</span>
              <StatusPill value={filter.status} tone={toneForStatus(filter.status)} />
              <details className="filter-provenance">
                <summary>Input provenance</summary>
                <dl>
                  <div><dt>Source</dt><dd>{filter.source_key || filter.source_name || NOT_AVAILABLE}</dd></div>
                  <div><dt>Observed</dt><dd>{formatTimestamp(filter.observed_at)}</dd></div>
                  <div><dt>Available</dt><dd>{formatTimestamp(filter.available_at)}</dd></div>
                  <div><dt>Ingested</dt><dd>{formatTimestamp(filter.ingested_at)}</dd></div>
                </dl>
              </details>
            </div>
          ))}
        </div>
      ) : (
        <Unavailable compact />
      )}
    </div>
  );
}

function RegimeWeights({ weights }: { weights?: Regime["weights"] }) {
  const maximum = Math.max(...(weights ?? []).map((item) => Math.abs(item.value ?? 0)), 0);
  return (
    <div className="regime-module">
      <div className="regime-module__title">
        <Scale aria-hidden="true" size={15} />
        <h4>Conditional weights</h4>
      </div>
      {weights?.length ? (
        <div className="weight-stack">
          {weights.map((weight) => {
            const width = maximum && isFiniteNumber(weight.value) ? (Math.abs(weight.value) / maximum) * 100 : 0;
            return (
              <div className="weight-row" key={weight.name}>
                <div>
                  <span>{weight.name}</span>
                  <b>{formatScalar(weight.value, weight.unit)}</b>
                </div>
                <span className="mini-bar" aria-hidden="true">
                  <i style={{ width: `${width}%` }} />
                </span>
              </div>
            );
          })}
        </div>
      ) : (
        <Unavailable compact />
      )}
    </div>
  );
}

function RegimeContributions({ contributions }: { contributions?: Regime["contributions"] }) {
  return (
    <div className="regime-module regime-module--wide">
      <div className="regime-module__title">
        <Braces aria-hidden="true" size={15} />
        <h4>Contributions</h4>
      </div>
      {contributions?.length ? (
        <div className="contribution-stack">
          {contributions.map((contribution) => (
            <details className="contribution-row" key={contribution.name}>
              <summary>
                <div>
                  <strong>{contribution.name}</strong>
                  <span>{contribution.explanation || NOT_AVAILABLE}</span>
                </div>
                <b className={`tone-${toneForDirection(contribution.direction)}`}>
                  {formatScalar(contribution.value, contribution.unit)}
                </b>
              </summary>
              {contribution.evidence?.length ? (
                <dl>
                  {contribution.evidence.map((evidence, index) => (
                    <div key={`${evidence.label}-${index}`}>
                      <dt>{evidence.label}</dt>
                      <dd>{formatScalar(evidence.value)}</dd>
                    </div>
                  ))}
                </dl>
              ) : (
                <Unavailable compact />
              )}
            </details>
          ))}
        </div>
      ) : (
        <Unavailable compact />
      )}
    </div>
  );
}
