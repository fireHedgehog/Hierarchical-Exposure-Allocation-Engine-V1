import { useEffect, useMemo, useRef } from "react";
import {
  CandlestickSeries,
  ColorType,
  createChart,
  createSeriesMarkers,
  HistogramSeries,
  type HistogramData,
  type SeriesMarker,
  type Time,
  type UTCTimestamp,
  type WhitespaceData,
} from "lightweight-charts";
import type { PriceBar, SymbolEvent } from "../types";
import { formatDate, NOT_AVAILABLE } from "../utils/format";
import { Unavailable } from "./Ui";

export function PriceChart({
  bars,
  events,
  symbol,
  currency = "USD",
}: {
  bars?: PriceBar[] | null;
  events?: SymbolEvent[] | null;
  symbol: string;
  currency?: string | null;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cleanBars = useMemo(() => sanitizeBars(bars ?? []), [bars]);
  const chartEvents = useMemo(() => (events ?? []).filter((event) => classifyChartEvent(event) !== "excluded"), [events]);

  useEffect(() => {
    if (!containerRef.current || !cleanBars.length) return;
    const container = containerRef.current;
    const chart = createChart(container, {
      width: container.clientWidth,
      height: 430,
      layout: {
        background: { type: ColorType.Solid, color: "#0a1513" },
        textColor: "#879b95",
        fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
        fontSize: 11,
        attributionLogo: false,
      },
      grid: {
        vertLines: { color: "rgba(255,255,255,0.035)" },
        horzLines: { color: "rgba(255,255,255,0.045)" },
      },
      crosshair: {
        vertLine: { color: "rgba(105,232,198,0.34)", labelBackgroundColor: "#173c35" },
        horzLine: { color: "rgba(105,232,198,0.34)", labelBackgroundColor: "#173c35" },
      },
      rightPriceScale: {
        borderColor: "rgba(255,255,255,0.08)",
        scaleMargins: { top: 0.08, bottom: 0.24 },
      },
      timeScale: {
        borderColor: "rgba(255,255,255,0.08)",
        timeVisible: true,
        secondsVisible: false,
        rightOffset: 4,
        barSpacing: 8,
      },
      handleScroll: { mouseWheel: true, pressedMouseMove: true, horzTouchDrag: true, vertTouchDrag: false },
      handleScale: { axisPressedMouseMove: true, mouseWheel: true, pinch: true },
    });

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#55d9ae",
      downColor: "#ef6b73",
      borderUpColor: "#55d9ae",
      borderDownColor: "#ef6b73",
      wickUpColor: "rgba(85,217,174,0.8)",
      wickDownColor: "rgba(239,107,115,0.8)",
      priceLineColor: "rgba(105,232,198,0.5)",
      priceLineWidth: 1,
      lastValueVisible: true,
    });
    candleSeries.setData(cleanBars.map(({ time, open, high, low, close }) => ({ time, open, high, low, close })));

    const volumeData = buildVolumeSeriesData(cleanBars);
    if (volumeData.some((point) => "value" in point)) {
      const volumeSeries = chart.addSeries(HistogramSeries, {
        priceFormat: { type: "volume" },
        priceScaleId: "volume",
        lastValueVisible: false,
        priceLineVisible: false,
      });
      chart.priceScale("volume").applyOptions({
        scaleMargins: { top: 0.82, bottom: 0 },
        borderVisible: false,
      });
      volumeSeries.setData(volumeData);
    }

    const markers = chartEvents
      .map(eventMarker)
      .filter((marker): marker is SeriesMarker<Time> => marker !== null)
      .sort((a, b) => timeSortValue(a.time) - timeSortValue(b.time));
    if (markers.length) createSeriesMarkers(candleSeries, markers);

    chart.timeScale().fitContent();

    const resizeObserver = new ResizeObserver((entries) => {
      const width = entries[0]?.contentRect.width;
      if (width) chart.applyOptions({ width });
    });
    resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
    };
  }, [cleanBars, chartEvents]);

  if (!cleanBars.length) {
    return (
      <Unavailable
        title="Price history not available"
        detail="No valid database bars were returned for this symbol and snapshot."
      />
    );
  }

  const first = cleanBars[0];
  const last = cleanBars[cleanBars.length - 1];
  return (
    <div className="chart-block">
      <div className="chart-toolbar">
        <div>
          <span>{symbol}</span>
          <small>{currency || NOT_AVAILABLE} · database bars</small>
        </div>
        <div className="chart-range">
          <span>{formatDate(timeToDisplay(first.time))}</span>
          <i aria-hidden="true" />
          <span>{formatDate(timeToDisplay(last.time))}</span>
        </div>
        <div className="chart-legend" aria-label="Chart legend">
          <span className="chart-legend__up" /> Up bar
          <span className="chart-legend__down" /> Down bar
          <span className="chart-legend__entry" /> Entry history
          <span className="chart-legend__exit" /> Exit history
          <span className="chart-legend__signal" /> Signal annotation
          <span className="chart-legend__pattern" /> Pattern annotation
        </div>
      </div>
      <div
        className="price-chart"
        ref={containerRef}
        role="img"
        aria-label={`${symbol} candlestick chart with ${cleanBars.length} database bars and ${chartEvents.length} persisted annotations`}
      />
      <p className="chart-footnote">
        Executed or backtest entry/exit history, signal observations, and price patterns are distinct. Proposals and candidates are excluded from chart markers.
      </p>
    </div>
  );
}

interface CleanBar extends Omit<PriceBar, "time"> {
  time: Time;
}

interface VolumeBarInput {
  time: Time;
  open: number;
  close: number;
  volume?: number | null;
}

export function buildVolumeSeriesData(
  bars: readonly VolumeBarInput[],
): Array<HistogramData<Time> | WhitespaceData<Time>> {
  return bars.map((bar) => {
    if (typeof bar.volume !== "number" || !Number.isFinite(bar.volume)) return { time: bar.time };
    return {
      time: bar.time,
      value: bar.volume,
      color: bar.close >= bar.open ? "rgba(85,217,174,0.24)" : "rgba(239,107,115,0.23)",
    };
  });
}

function sanitizeBars(bars: PriceBar[]): CleanBar[] {
  const unique = new Map<string, CleanBar>();
  for (const bar of bars) {
    if (![bar.open, bar.high, bar.low, bar.close].every(Number.isFinite)) continue;
    const time = toChartTime(bar.time);
    if (time === null) continue;
    unique.set(String(time), { ...bar, time });
  }
  return Array.from(unique.values()).sort((a, b) => timeSortValue(a.time) - timeSortValue(b.time));
}

function toChartTime(value: string | number): Time | null {
  if (typeof value === "number") {
    if (!Number.isFinite(value)) return null;
    return Math.floor(value > 10_000_000_000 ? value / 1000 : value) as UTCTimestamp;
  }
  const trimmed = value.trim();
  if (/^\d{4}-\d{2}-\d{2}$/.test(trimmed)) return trimmed;
  const parsed = new Date(trimmed);
  if (Number.isNaN(parsed.getTime())) return null;
  return Math.floor(parsed.getTime() / 1000) as UTCTimestamp;
}

function timeSortValue(value: Time): number {
  if (typeof value === "number") return value;
  if (typeof value === "string") return new Date(value).getTime() / 1000;
  return Date.UTC(value.year, value.month - 1, value.day) / 1000;
}

function timeToDisplay(value: Time): string | number {
  if (typeof value === "number") return value;
  if (typeof value === "string") return value;
  return `${value.year}-${String(value.month).padStart(2, "0")}-${String(value.day).padStart(2, "0")}`;
}

export type ChartEventKind = "entry" | "exit" | "signal" | "pattern" | "excluded";

export function classifyChartEvent(event: SymbolEvent): ChartEventKind {
  const type = event.type.trim().toLowerCase().replace(/[\s-]+/g, "_");
  const status = (event.status || "").trim().toLowerCase().replace(/[\s-]+/g, "_");

  const isEntry = /(^|_)(entry|entered|opened|open)(_|$)/.test(type);
  const isExit = /(^|_)(exit|exited|closed|close)(_|$)/.test(type);

  // A persisted event status is the source of truth. In particular, a type such
  // as `signal_entry` describes the event's vocabulary, while `executed` is what
  // permits it to appear as a fill. Unknown explicit states are excluded rather
  // than reinterpreted with legacy naming heuristics.
  if (status) {
    if (status === "proposed" || status === "cancelled") return "excluded";
    if (status === "executed") {
      if (isEntry) return "entry";
      if (isExit) return "exit";
      return "excluded";
    }
    if (status === "signal_state") return "signal";
    if (status === "annotation") {
      if (type.startsWith("pattern_")) return "pattern";
      if (type.startsWith("signal_")) return "signal";
      return "excluded";
    }
    return "excluded";
  }

  // Rows created before event_status existed have no explicit state. Keep the
  // conservative type heuristics for those legacy rows only.
  if (/(proposal|candidate|recommend|target|review)/.test(type)) return "excluded";
  if (type.startsWith("pattern_")) return "pattern";
  if (type.startsWith("signal_")) return "signal";
  const executionContext = /(^|_)(execution|fill|filled|trade|order|position|backtest|simulated_trade)(_|$)/.test(type);
  if ((executionContext || type === "entry") && isEntry) return "entry";
  if ((executionContext || type === "exit") && isExit) return "exit";
  return "excluded";
}

function eventMarker(event: SymbolEvent): SeriesMarker<Time> | null {
  const time = toChartTime(event.time);
  if (time === null) return null;
  const kind = classifyChartEvent(event);
  if (kind === "excluded") return null;
  if (kind === "pattern") {
    return { time, position: "aboveBar", color: "#e5b15d", shape: "square", text: event.label };
  }
  if (kind === "signal") {
    const isBearishOrExit = /(bear|down|exit|sell)/.test(`${event.type} ${event.label}`.toLowerCase());
    return {
      time,
      position: isBearishOrExit ? "aboveBar" : "belowBar",
      color: "#78a9ef",
      shape: "circle",
      text: event.label,
    };
  }
  const isExit = kind === "exit";
  return {
    time,
    position: isExit ? "aboveBar" : "belowBar",
    color: isExit ? "#f28a91" : "#67e4bf",
    shape: isExit ? "arrowDown" : "arrowUp",
    text: event.label,
  };
}
