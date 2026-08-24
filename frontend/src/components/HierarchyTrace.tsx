import { CircleDotDashed, Fingerprint } from "lucide-react";
import type { HierarchyTraceIncoming, HierarchyTraceItem } from "../types";
import { formatPercent, formatScalar, humanize, NOT_AVAILABLE } from "../utils/format";
import { Unavailable } from "./Ui";

export function HierarchyTrace({ trace }: { trace?: HierarchyTraceItem[] | null }) {
  if (!trace?.length) {
    return (
      <Unavailable
        title="Hierarchy trace not available"
        detail="This symbol has no persisted state-to-instrument trace."
      />
    );
  }

  return (
    <div className="trace-flow" aria-label="Symbol hierarchy trace">
      <div className="trace-flow__header">
        <div className="trace-flow__origin">
          <Fingerprint aria-hidden="true" />
          <span>Selected DAG nodes</span>
        </div>
        <p>Cards are ordered for reading. Incoming lineage shows the stored graph edges; adjacent cards are not implied to be parent and child.</p>
      </div>
      {trace.map((item, index) => (
        <div className="trace-step-wrap" key={item.id || item.node_id || `${item.level || item.layer}-${index}`}>
          <article className="trace-step">
            <div className="trace-step__layer">
              <span>DAG</span>
              <small>{item.level || item.layer || NOT_AVAILABLE}</small>
            </div>
            <div className="trace-step__body">
              <div>
                <CircleDotDashed aria-hidden="true" size={15} />
                <h3>{item.label}</h3>
              </div>
              {item.node_id ? <code className="trace-node-id">{item.node_id}</code> : null}
              {item.value !== null && item.value !== undefined ? <strong>{formatScalar(item.value)}</strong> : null}
              {item.explanation ? <p>{item.explanation}</p> : null}
              <dl className="trace-allocation-grid">
                <div><dt>Current</dt><dd>{formatScalar(item.current_value, item.value_unit)}</dd></div>
                <div><dt>Target</dt><dd>{formatScalar(item.target_value, item.value_unit)}</dd></div>
                <div className={item.delta_value === null || item.delta_value === undefined ? "" : `direction-${item.delta_value > 0 ? "up" : item.delta_value < 0 ? "down" : "flat"}`}>
                  <dt>Delta</dt><dd>{formatScalar(item.delta_value, item.value_unit)}</dd>
                </div>
                <div><dt>Contribution</dt><dd>{formatPercent(item.contribution)}</dd></div>
              </dl>
              <TraceLineage item={item} />
              {item.constraints?.length ? (
                <div className="constraint-list">
                  <span>Constraints</span>
                  {item.constraints.map((constraint) => <em key={constraint}>{constraint}</em>)}
                </div>
              ) : null}
              {item.evidence?.length ? (
                <details className="evidence-disclosure">
                  <summary>Evidence</summary>
                  <dl>
                    {item.evidence.map((evidence, evidenceIndex) => (
                      <div key={`${evidence.label}-${evidenceIndex}`}>
                        <dt>{evidence.label}</dt>
                        <dd>{formatScalar(evidence.value)}</dd>
                      </div>
                    ))}
                  </dl>
                </details>
              ) : null}
            </div>
          </article>
        </div>
      ))}
    </div>
  );
}

function TraceLineage({ item }: { item: HierarchyTraceItem }) {
  const incoming = storedIncoming(item);
  return (
    <div className="trace-lineage" aria-label={`Incoming lineage for ${item.label}`}>
      <span>Incoming lineage</span>
      {incoming.length ? (
        <ul>
          {incoming.map((edge, index) => (
            <li key={`${edge.from_node_id}-${edge.relation || "parent"}-${index}`}>
              <div className="trace-lineage__source">
                <b>{edge.from_label || edge.from_node_id}</b>
                {edge.from_label ? <code>{edge.from_node_id}</code> : null}
              </div>
              <div className="trace-lineage__relation">
                <span>{humanize(edge.relation || "primary_parent")}</span>
                {edge.weight !== null && edge.weight !== undefined ? <em>Edge weight {formatPercent(edge.weight)}</em> : null}
              </div>
              {edge.rationale ? <p>{edge.rationale}</p> : null}
            </li>
          ))}
        </ul>
      ) : (
        <p>Trace root — no stored incoming edge.</p>
      )}
    </div>
  );
}

function storedIncoming(item: HierarchyTraceItem): HierarchyTraceIncoming[] {
  if (item.incoming_edges?.length) return item.incoming_edges;
  if (!item.parent_node_id) return [];
  return [{
    from_node_id: item.parent_node_id,
    from_label: item.parent_label,
    relation: "primary_parent",
  }];
}
