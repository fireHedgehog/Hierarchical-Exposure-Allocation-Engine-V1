// Client-side RSI/MACD for chart display only — mirrors the formulas in
// backend/engine/indicators/ exactly (Wilder's RSI, standard EMA-seeded
// MACD). The backtest's actual trading decisions are computed once, on the
// server, from these same formulas; this copy only draws the lines, it does
// not decide anything.

export function computeEma(values: number[], period: number): Array<number | null> {
  const n = values.length;
  const result: Array<number | null> = new Array(n).fill(null);
  if (n < period) return result;
  let seed = 0;
  for (let i = 0; i < period; i += 1) seed += values[i];
  seed /= period;
  result[period - 1] = seed;
  const alpha = 2 / (period + 1);
  let ema = seed;
  for (let i = period; i < n; i += 1) {
    ema = values[i] * alpha + ema * (1 - alpha);
    result[i] = ema;
  }
  return result;
}

export function computeRsi(closes: number[], period = 14): Array<number | null> {
  const n = closes.length;
  const result: Array<number | null> = new Array(n).fill(null);
  if (n <= period) return result;

  const gains: number[] = [];
  const losses: number[] = [];
  for (let i = 1; i < n; i += 1) {
    const delta = closes[i] - closes[i - 1];
    gains.push(Math.max(delta, 0));
    losses.push(Math.max(-delta, 0));
  }

  let avgGain = gains.slice(0, period).reduce((sum, value) => sum + value, 0) / period;
  let avgLoss = losses.slice(0, period).reduce((sum, value) => sum + value, 0) / period;
  result[period] = rsiFromAverages(avgGain, avgLoss);

  for (let i = period; i < gains.length; i += 1) {
    avgGain = (avgGain * (period - 1) + gains[i]) / period;
    avgLoss = (avgLoss * (period - 1) + losses[i]) / period;
    result[i + 1] = rsiFromAverages(avgGain, avgLoss);
  }
  return result;
}

function rsiFromAverages(avgGain: number, avgLoss: number): number {
  if (avgLoss === 0) return avgGain > 0 ? 100 : 50;
  const rs = avgGain / avgLoss;
  return 100 - 100 / (1 + rs);
}

export interface MacdResult {
  macdLine: Array<number | null>;
  signalLine: Array<number | null>;
  histogram: Array<number | null>;
}

export function computeMacd(closes: number[], fast = 12, slow = 26, signal = 9): MacdResult {
  const n = closes.length;
  const fastEma = computeEma(closes, fast);
  const slowEma = computeEma(closes, slow);
  const macdLine: Array<number | null> = new Array(n).fill(null);
  for (let i = 0; i < n; i += 1) {
    const f = fastEma[i];
    const s = slowEma[i];
    if (f !== null && s !== null) macdLine[i] = f - s;
  }

  const validIndices: number[] = [];
  for (let i = 0; i < n; i += 1) if (macdLine[i] !== null) validIndices.push(i);
  const signalLine: Array<number | null> = new Array(n).fill(null);
  if (validIndices.length >= signal) {
    const validValues = validIndices.map((i) => macdLine[i] as number);
    const signalOverValid = computeEma(validValues, signal);
    validIndices.forEach((i, offset) => {
      signalLine[i] = signalOverValid[offset];
    });
  }

  const histogram: Array<number | null> = new Array(n).fill(null);
  for (let i = 0; i < n; i += 1) {
    const m = macdLine[i];
    const s = signalLine[i];
    if (m !== null && s !== null) histogram[i] = m - s;
  }
  return { macdLine, signalLine, histogram };
}
