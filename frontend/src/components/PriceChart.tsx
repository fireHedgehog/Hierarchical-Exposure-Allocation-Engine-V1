import { useEffect, useMemo, useRef, useState } from "react";
import {
  CandlestickSeries,
  ColorType,
  createChart,
  createSeriesMarkers,
  HistogramSeries,
  LineSeries,
  type HistogramData,
  type SeriesMarker,
  type Time,
  type UTCTimestamp,
  type WhitespaceData,
} from "lightweight-charts";
import type { PriceBar, SymbolEvent } from "../types";
import { computeMacd, computeRsi } from "../utils/indicators";
import { formatDate, NOT_AVAILABLE } from "../utils/format";
import { Unavailable } from "./Ui";

const TIMEFRAMES = [
  { key: "1m", label: "1M", days: 30 },
  { key: "3m", label: "3M", days: 90 },
  { key: "6m", label: "6M", days: 182 },
  { key: "1y", label: "1Y", days: 365 },
  { key: "5y", label: "5Y", days: 365 * 5 },
  { key: "10y", label: "10Y", days: 365 * 10 },
  { key: "max", label: "Max", days: null as number | null },
] as const;

type TimeframeKey = (typeof TIMEFRAMES)[number]["key"];

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
  const [timeframe, setTimeframe] = useState<TimeframeKey>("1y");
  const allBars = useMemo(() => sanitizeBars(bars ?? []), [bars]);
  const cleanBars = useMemo(() => windowBars(allBars, timeframe), [allBars, timeframe]);
  const chartEvents = useMemo(() => (events ?? []).filter((event) => classifyChartEvent(event) !== "excluded"), [events]);

  useEffect(() => {
    if (!containerRef.current || !cleanBars.length) return;
    const container = containerRef.current;
    const chart = createChart(container, {
      width: container.clientWidth,
      height: 620,
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

    const candleSeries = chart.addSeries(
      CandlestickSeries,
      {
        upColor: "#55d9ae",
        downColor: "#ef6b73",
        borderUpColor: "#55d9ae",
        borderDownColor: "#ef6b73",
        wickUpColor: "rgba(85,217,174,0.8)",
        wickDownColor: "rgba(239,107,115,0.8)",
        priceLineColor: "rgba(105,232,198,0.5)",
        priceLineWidth: 1,
        lastValueVisible: true,
      },
      0,
    );
    candleSeries.setData(cleanBars.map(({ time, open, high, low, close }) => ({ time, open, high, low, close })));

    const volumeData = buildVolumeSeriesData(cleanBars);
    if (volumeData.some((point) => "value" in point)) {
      const volumeSeries = chart.addSeries(
        HistogramSeries,
        {
          priceFormat: { type: "volume" },
          priceScaleId: "volume",
          lastValueVisible: false,
          priceLineVisible: false,
        },
        0,
      );
      chart.priceScale("volume").applyOptions({
        scaleMargins: { top: 0.82, bottom: 0 },
        borderVisible: false,
      });
      volumeSeries.setData(volumeData);
    }

    // Markers are clipped to the visible timeframe window. lightweight-charts
    // clamps out-of-range markers to the nearest visible bar rather than
    // hiding them, which squishes decades of history into one ugly stack at
    // the chart edge on a short timeframe. The full history still lives in
    // the trade ledger table below the chart.
    const windowStart = timeSortValue(cleanBars[0].time);
    const windowEnd = timeSortValue(cleanBars[cleanBars.length - 1].time);
    const markers = chartEvents
      .map(eventMarker)
      .filter((marker): marker is SeriesMarker<Time> => marker !== null)
      .filter((marker) => {
        const t = timeSortValue(marker.time);
        return t >= windowStart && t <= windowEnd;
      })
      .sort((a, b) => timeSortValue(a.time) - timeSortValue(b.time));
    if (markers.length) createSeriesMarkers(candleSeries, markers);

    // RSI(14) and MACD(12,26,9) — computed client-side over the FULL fetched
    // history (not just the visible window, so short timeframes don't show a
    // sparse cold-start), using the identical formulas the backend's real
    // backtest already traded on (backend/engine/indicators/). These panes
    // only draw the lines; the trade decisions were made once, on the
    // server, over full history.
    const visibleTimes = new Set(cleanBars.map((bar) => timeSortValue(bar.time)));
    const fullCloses = allBars.map((bar) => bar.close);
    const fullRsi = computeRsi(fullCloses, 14);
    const fullMacd = computeMacd(fullCloses);
    const visibleIndices = allBars
      .map((bar, index) => ({ index, visible: visibleTimes.has(timeSortValue(bar.time)) }))
      .filter((item) => item.visible)
      .map((item) => item.index);
    const times = visibleIndices.map((index) => allBars[index].time);
    const rsi = visibleIndices.map((index) => fullRsi[index]);
    const rsiPoints = times
      .map((time, i) => (rsi[i] === null ? null : { time, value: rsi[i] as number }))
      .filter((point): point is { time: Time; value: number } => point !== null);
    if (rsiPoints.length) {
      const rsiSeries = chart.addSeries(
        LineSeries,
        { color: "#78a9ef", lineWidth: 1, priceScaleId: "rsi", lastValueVisible: true, title: "RSI(14)" },
        1,
      );
      rsiSeries.setData(rsiPoints);
      rsiSeries.createPriceLine({ price: 70, color: "rgba(239,107,115,0.4)", lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: "70" });
      rsiSeries.createPriceLine({ price: 30, color: "rgba(85,217,174,0.4)", lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: "30" });
      chart.priceScale("rsi").applyOptions({ autoScale: false, scaleMargins: { top: 0.1, bottom: 0.1 } });
      rsiSeries.applyOptions({ autoscaleInfoProvider: () => ({ priceRange: { minValue: 0, maxValue: 100 } }) });
    }

    const macdLine = visibleIndices.map((index) => fullMacd.macdLine[index]);
    const signalLine = visibleIndices.map((index) => fullMacd.signalLine[index]);
    const histogram = visibleIndices.map((index) => fullMacd.histogram[index]);
    const macdPoints = times
      .map((time, i) => (macdLine[i] === null ? null : { time, value: macdLine[i] as number }))
      .filter((point): point is { time: Time; value: number } => point !== null);
    const signalPoints = times
      .map((time, i) => (signalLine[i] === null ? null : { time, value: signalLine[i] as number }))
      .filter((point): point is { time: Time; value: number } => point !== null);
    const histogramPoints = times
      .map((time, i) =>
        histogram[i] === null
          ? null
          : { time, value: histogram[i] as number, color: (histogram[i] as number) >= 0 ? "rgba(85,217,174,0.5)" : "rgba(239,107,115,0.45)" },
      )
      .filter((point): point is { time: Time; value: number; color: string } => point !== null);
    if (macdPoints.length) {
      const histogramSeries = chart.addSeries(HistogramSeries, { priceScaleId: "macd", lastValueVisible: false, priceLineVisible: false }, 2);
      histogramSeries.setData(histogramPoints);
      const macdSeries = chart.addSeries(LineSeries, { color: "#67e4bf", lineWidth: 1, priceScaleId: "macd", title: "MACD" }, 2);
      macdSeries.setData(macdPoints);
      const signalSeries = chart.addSeries(LineSeries, { color: "#e5b15d", lineWidth: 1, priceScaleId: "macd", title: "Signal" }, 2);
      signalSeries.setData(signalPoints);
    }

    const panes = chart.panes();
    if (panes[0]) panes[0].setStretchFactor(4);
    if (panes[1]) panes[1].setStretchFactor(1.1);
    if (panes[2]) panes[2].setStretchFactor(1.1);

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
  }, [cleanBars, chartEvents, allBars]);

  if (!allBars.length) {
    return (
      <Unavailable
        title="Price history not available"
        detail="No valid database bars were returned for this symbol and snapshot."
      />
    );
  }

  const first = cleanBars[0] ?? allBars[0];
  const last = cleanBars[cleanBars.length - 1] ?? allBars[allBars.length - 1];
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
      <div className="chart-timeframes" role="group" aria-label="Chart timeframe">
        {TIMEFRAMES.map((option) => (
          <button
            key={option.key}
            type="button"
            className={`chart-timeframe-button ${timeframe === option.key ? "chart-timeframe-button--active" : ""}`}
            onClick={() => setTimeframe(option.key)}
          >
            {option.label}
          </button>
        ))}
      </div>
      <div
        className="price-chart"
        ref={containerRef}
        role="img"
        aria-label={`${symbol} candlestick chart with ${cleanBars.length} database bars, RSI and MACD panes, and ${chartEvents.length} persisted annotations`}
      />
      <p className="chart-footnote">
        Executed or backtest entry/exit history, signal observations, and price patterns are distinct. Proposals and candidates are excluded from chart markers. RSI/MACD panes are computed in the browser from the same bars for display only; the backtest's actual trades were decided once, on the server, over full history.
      </p>
    </div>
  );
}

function windowBars(bars: CleanBar[], timeframe: TimeframeKey): CleanBar[] {
  const option = TIMEFRAMES.find((item) => item.key === timeframe);
  if (!option || option.days === null || !bars.length) return bars;
  const lastSeconds = timeSortValue(bars[bars.length - 1].time);
  const cutoff = lastSeconds - option.days * 86400;
  const windowed = bars.filter((bar) => timeSortValue(bar.time) >= cutoff);
  return windowed.length ? windowed : bars;
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
