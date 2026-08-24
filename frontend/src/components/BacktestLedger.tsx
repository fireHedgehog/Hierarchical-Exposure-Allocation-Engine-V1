import type { SymbolEvent } from "../types";
import { formatCurrency, formatDate, formatPercent, NOT_AVAILABLE } from "../utils/format";
import { classifyChartEvent } from "./PriceChart";
import { StatusPill, Unavailable } from "./Ui";

// Full backtest trade history, independent of the chart's selected
// timeframe (which only draws markers inside the visible window — see
// PriceChart.tsx). Reconstructed here from the persisted entry/exit events
// rather than a separate endpoint: the backtest engine writes them in
// strict chronological, non-overlapping pairs (one open position at a
// time), so pairing sorted events sequentially reproduces the exact trade
// log the server computed.

interface TradeRow {
  index: number;
  entryTime: string | number;
  entryPrice: number | null;
  entryDetail: string | null;
  exitTime: string | number | null;
  exitPrice: number | null;
  exitDetail: string | null;
  returnFraction: number | null;
  status: "closed" | "open";
}

export function BacktestLedger({ events, currency }: { events?: SymbolEvent[] | null; currency?: string | null }) {
  const trades = buildTrades(events ?? []);

  if (!trades.length) {
    return (
      <Unavailable
        title="Backtest trade history not available"
        detail="No persisted backtest entry/exit events are attached to this symbol."
      />
    );
  }

  return (
    <div className="operator-table-scroll">
      <table className="operator-table backtest-ledger-table">
        <thead>
          <tr>
            <th>#</th>
            <th>Entry date</th>
            <th>Entry price</th>
            <th>Exit date</th>
            <th>Exit price</th>
            <th>Return</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {trades.map((trade) => (
            <tr key={trade.index}>
              <td>{trade.index}</td>
              <td>{formatDate(trade.entryTime)}</td>
              <td>{formatCurrency(trade.entryPrice, currency || "USD")}</td>
              <td>{trade.exitTime !== null ? formatDate(trade.exitTime) : NOT_AVAILABLE}</td>
              <td>{trade.exitPrice !== null ? formatCurrency(trade.exitPrice, currency || "USD") : NOT_AVAILABLE}</td>
              <td className={trade.returnFraction !== null ? directionClass(trade.returnFraction) : ""}>
                {trade.returnFraction !== null ? formatPercent(trade.returnFraction) : NOT_AVAILABLE}
              </td>
              <td><StatusPill value={trade.status === "open" ? "open_position" : "closed"} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function directionClass(value: number): string {
  return `direction-${value > 0 ? "up" : value < 0 ? "down" : "flat"}`;
}

function buildTrades(events: SymbolEvent[]): TradeRow[] {
  const relevant = events
    .filter((event) => {
      const kind = classifyChartEvent(event);
      return kind === "entry" || kind === "exit";
    })
    .slice()
    .sort((a, b) => toMillis(a.time) - toMillis(b.time));

  const trades: TradeRow[] = [];
  let open: TradeRow | null = null;
  let index = 0;

  for (const event of relevant) {
    const kind = classifyChartEvent(event);
    if (kind === "entry") {
      index += 1;
      open = {
        index,
        entryTime: event.time,
        entryPrice: event.price ?? null,
        entryDetail: event.detail ?? null,
        exitTime: null,
        exitPrice: null,
        exitDetail: null,
        returnFraction: null,
        status: "open",
      };
      trades.push(open);
    } else if (kind === "exit" && open) {
      open.exitTime = event.time;
      open.exitPrice = event.price ?? null;
      open.exitDetail = event.detail ?? null;
      open.status = "closed";
      if (open.entryPrice !== null && open.exitPrice !== null && open.entryPrice !== 0) {
        open.returnFraction = (open.exitPrice - open.entryPrice) / open.entryPrice;
      }
      open = null;
    }
  }
  return trades;
}

function toMillis(value: string | number): number {
  if (typeof value === "number") return value > 10_000_000_000 ? value : value * 1000;
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? 0 : parsed.getTime();
}
