import { BookOpen, CornerDownRight, Quote } from "lucide-react";
import type { Philosophy, Snapshot } from "../types";
import { NOT_AVAILABLE } from "../utils/format";
import { ProvenanceStrip, Unavailable } from "./Ui";

export function PhilosophyPanel({
  philosophy,
  snapshot,
}: {
  philosophy?: Philosophy | null;
  snapshot: Snapshot;
}) {
  if (!philosophy) {
    return (
      <Unavailable
        title="System philosophy not available"
        detail="No database-sourced philosophy record is attached to this snapshot."
      />
    );
  }

  const sections = philosophy.sections ?? [];

  return (
    <div className="philosophy-panel">
      <div className="philosophy-panel__quote" aria-hidden="true"><Quote /></div>
      {philosophy.title || philosophy.summary || philosophy.formula ? (
        <div className="philosophy-panel__lead">
          <p className="eyebrow">{philosophy.eyebrow || "System identity"}</p>
          <h2>{philosophy.title || NOT_AVAILABLE}</h2>
          <p>{philosophy.summary || NOT_AVAILABLE}</p>
          {philosophy.formula ? <code className="philosophy-formula">{philosophy.formula}</code> : null}
        </div>
      ) : null}
      <div className="philosophy-principles philosophy-principles--sections">
        <div className="philosophy-principles__title">
          <BookOpen aria-hidden="true" size={17} />
          <h3>Operating principles</h3>
        </div>
        {sections.length ? (
          <ol>
            {sections.map((section) => (
              <li key={section.key} className="philosophy-section">
                <CornerDownRight aria-hidden="true" size={14} />
                <div>
                  <strong>{section.title}</strong>
                  <p>{section.body || NOT_AVAILABLE}</p>
                  <blockquote>{section.principle || NOT_AVAILABLE}</blockquote>
                </div>
              </li>
            ))}
          </ol>
        ) : philosophy.principles?.length ? (
          <ol>
            {philosophy.principles.map((principle) => (
              <li key={principle}>
                <CornerDownRight aria-hidden="true" size={14} />
                <span>{principle}</span>
              </li>
            ))}
          </ol>
        ) : (
          <Unavailable compact />
        )}
      </div>
      <ProvenanceStrip provenance={snapshot} sourceLabel="Snapshot identity record" compact />
    </div>
  );
}
