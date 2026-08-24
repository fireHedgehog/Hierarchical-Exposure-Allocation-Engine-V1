import { ArrowUpRight, Grid3X3 } from "lucide-react";
import { Link } from "react-router-dom";
import type { CrossSectionResponse, MatrixColumn } from "../types";
import { formatScalar, formatTimestamp, NOT_AVAILABLE } from "../utils/format";
import { columnExtent, heatCell } from "../utils/matrix";
import { ConvictionBadge, ProvenanceStrip, StatusPill, Unavailable } from "./Ui";

export function CrossSectionMatrix({ data }: { data: CrossSectionResponse }) {
  const rows = data.rows ?? [];
  const columns = data.dimensions?.columns ?? [];
  const cellCount = rows.length * columns.length;
  const availableCount = rows.reduce(
    (sum, row) => sum + columns.filter((column) => row.values[column.key] !== null && row.values[column.key] !== undefined).length,
    0,
  );
  const coverage = cellCount ? availableCount / cellCount : null;
  const extents = Object.fromEntries(columns.map((column) => [column.key, columnExtent(rows, column.key)]));
  const legend = legendLabels(data.legend);

  if (!rows.length || !columns.length) {
    return (
      <Unavailable
        title="Cross-sectional matrix not available"
        detail="The snapshot contains no cross-sectional rows or dimensions."
      />
    );
  }

  return (
    <div className="matrix-block">
      <div className="matrix-meta">
        <div>
          <Grid3X3 aria-hidden="true" size={17} />
          <span>{rows.length} securities</span>
        </div>
        <div>
          <span>As of</span>
          <b>{formatTimestamp(data.snapshot.as_of)}</b>
        </div>
        <div>
          <span>Coverage</span>
          <b>{coverage === null ? NOT_AVAILABLE : `${(coverage * 100).toFixed(1)}%`}</b>
        </div>
        <div>
          <span>Missing cells</span>
          <b>{cellCount - availableCount}</b>
        </div>
      </div>

      <div className="matrix-scroll" tabIndex={0} aria-label="Scrollable cross-sectional matrix">
        <table className="matrix-table">
          <caption className="sr-only">Cross-sectional factor values by security</caption>
          <thead>
            <tr>
              <th scope="col" className="matrix-symbol-column">Security</th>
              {columns.map((column) => (
                <th scope="col" key={column.key} title={column.description || undefined}>
                  <span>{column.label}</span>
                  {column.unit ? <small>{column.unit}</small> : null}
                  <small>Weight {column.weight === null || column.weight === undefined ? NOT_AVAILABLE : `${(column.weight * 100).toFixed(0)}%`}</small>
                </th>
              ))}
              <th scope="col">Composite</th>
              <th scope="col" title="-5 (max bearish) to +5 (max bullish)">Conviction</th>
              <th scope="col">Rank</th>
              <th scope="col">State</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.symbol} title={row.summary || undefined}>
                <th scope="row" className="matrix-symbol-column">
                  <Link to={`/symbols/${encodeURIComponent(row.symbol)}`}>
                    <strong>{row.symbol}</strong>
                    <span>{row.name || NOT_AVAILABLE}</span>
                    <small>{row.sector || NOT_AVAILABLE}</small>
                    {row.summary ? <span className="sr-only">Research summary: {row.summary}</span> : null}
                    <ArrowUpRight aria-hidden="true" size={13} />
                  </Link>
                </th>
                {columns.map((column) => (
                  <MatrixCell
                    column={column}
                    value={row.values[column.key]}
                    heat={heatCell(row.values[column.key], extents[column.key])}
                    quality={row.quality?.[column.key]}
                    provenance={row.provenance?.[column.key]}
                    key={column.key}
                  />
                ))}
                <td className="matrix-composite">{formatScalar(row.composite_score)}</td>
                <td><ConvictionBadge value={row.conviction} /></td>
                <td>{formatScalar(row.rank)}</td>
                <td><StatusPill value={row.status} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="matrix-footer">
        <div className="matrix-legend" aria-label="Matrix color legend">
          <span className="legend-low" /> {legend.low}
          <span className="legend-neutral" /> Relative midpoint
          <span className="legend-high" /> {legend.high}
          <span className="legend-missing" /> {legend.missing}
        </div>
        {legend.description ? <p>{legend.description}</p> : null}
      </div>
      <ProvenanceStrip provenance={data.snapshot} sourceLabel="Cross-sectional snapshot" compact />
    </div>
  );
}

function legendLabels(legend: CrossSectionResponse["legend"]): {
  low: string;
  high: string;
  missing: string;
  description: string | null;
} {
  if (Array.isArray(legend)) {
    const keyOf = (item: (typeof legend)[number]) => item.key || item.legend_key;
    const lower = legend.find((item) => keyOf(item) === "lower");
    const higher = legend.find((item) => keyOf(item) === "higher");
    const missing = legend.find((item) => keyOf(item) === "unavailable" || keyOf(item) === "missing");
    return {
      low: lower?.label || "Lower raw value",
      high: higher?.label || "Higher raw value",
      missing: missing?.label || "Missing",
      description: [lower?.description, higher?.description, missing?.description].filter(Boolean).join(" ") || null,
    };
  }
  return {
    low: legend?.low_label || "Lower raw value",
    high: legend?.high_label || "Higher raw value",
    missing: "Missing",
    description: legend?.description || null,
  };
}

function MatrixCell({
  column,
  value,
  heat,
  quality,
  provenance,
}: {
  column: MatrixColumn;
  value: number | null | undefined;
  heat: ReturnType<typeof heatCell>;
  quality?: string | null;
  provenance?: import("../types").Provenance | null;
}) {
  const display = formatScalar(value, column.unit);
  const accessibleDetail = [
    `${column.label}: ${display}`,
    `quality: ${quality || NOT_AVAILABLE}`,
    `source: ${provenance?.source_key || provenance?.source_name || NOT_AVAILABLE}`,
    `available: ${formatTimestamp(provenance?.available_at)}`,
  ].join(", ");
  return (
    <td
      className={`matrix-cell matrix-cell--${heat.tone}`}
      style={{ background: heat.background, borderColor: heat.border }}
      aria-label={accessibleDetail}
    >
      <details className="matrix-cell-detail">
        <summary>{display}</summary>
        <div>
          <span>Quality <b>{quality || NOT_AVAILABLE}</b></span>
          <span>Source <b>{provenance?.source_key || provenance?.source_name || NOT_AVAILABLE}</b></span>
          <span>Available <b>{formatTimestamp(provenance?.available_at)}</b></span>
        </div>
      </details>
    </td>
  );
}
