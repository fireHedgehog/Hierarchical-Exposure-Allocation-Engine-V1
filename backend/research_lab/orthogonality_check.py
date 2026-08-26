"""Follow-up check across this session's price/vol hypothesis papers.

Not a new hypothesis of its own -- a real check on a claim already made in
four papers' observation logs: that low-volatility-anomaly.md,
time-series-momentum.md, max-effect-lottery-demand.md, and
dow-theory-trend-structure.md were "four independently specified" tests
that all happened to land on the same directional signature. That claim was
never actually verified against real correlation -- this computes it, using
the exact effective_number_of_bets/pairwise_correlation_matrix
infrastructure already built (0.15) for exactly this question. Also
includes short-term-mean-reversion.md's confirmed signal, for a complete
picture. Read-only against the sealed dataset -- never writes anywhere.

Run: .venv/bin/python -m backend.research_lab.orthogonality_check
"""

from __future__ import annotations

from backend.database import connect, resolve_database_path
from backend.engine.research.signal_validation import effective_number_of_bets, pairwise_correlation_matrix


def _security_id_for(symbol: str, category: str) -> str:
    # Reproduced, not imported -- see backend/research_lab/README.md.
    slug = symbol.lower().replace("-", "")
    if category == "crypto_reference":
        return f"ref-{slug}"
    if category == "mega_cap_equity":
        return f"us-equity-{slug}"
    return f"us-etf-{symbol.lower()}"


def main() -> None:
    connection = connect(resolve_database_path(), read_only=True)
    dataset_row = connection.execute(
        "SELECT id FROM dataset_snapshots WHERE immutable = 1 ORDER BY as_of DESC, rowid DESC LIMIT 1"
    ).fetchone()
    if dataset_row is None:
        print("No sealed dataset snapshot available -- run the real pipeline first.")
        return
    dataset_id = dataset_row["id"]

    staging_rows = connection.execute(
        "SELECT symbol, category FROM staging_symbols WHERE active = 1 "
        "AND category NOT IN ('macro_series', 'crypto_reference')"
    ).fetchall()

    series_by_key: dict[str, list[float]] = {
        "ts_momentum_12m": [],
        "low_vol_63d": [],
        "max_return_21d": [],
        "dow_structure_intact": [],
        "reversal_1w": [],
    }

    for row in staging_rows:
        security_id = _security_id_for(row["symbol"], row["category"])
        bar_rows = connection.execute(
            "SELECT close, high, low FROM symbol_bars WHERE dataset_snapshot_id = ? AND security_id = ? "
            "AND close IS NOT NULL AND high IS NOT NULL AND low IS NOT NULL ORDER BY time",
            (dataset_id, security_id),
        ).fetchall()
        closes = [bar["close"] for bar in bar_rows]
        highs = [bar["high"] for bar in bar_rows]
        lows = [bar["low"] for bar in bar_rows]
        n = len(closes)
        if n < 300:
            continue

        # Same fractal swing detector as dow_theory_trend_structure.py.
        swing_high_idx: list[int] = []
        swing_high_val: list[float] = []
        swing_low_idx: list[int] = []
        swing_low_val: list[float] = []
        window = 5
        for j in range(window, n - window):
            high_segment = highs[j - window : j + window + 1]
            if highs[j] == max(high_segment):
                swing_high_idx.append(j)
                swing_high_val.append(highs[j])
            low_segment = lows[j - window : j + window + 1]
            if lows[j] == min(low_segment):
                swing_low_idx.append(j)
                swing_low_val.append(lows[j])

        import bisect

        for i in range(260, n - 21, 5):  # need >=252 bars of trailing history; stride=5
            if closes[i] == 0 or closes[i - 252] == 0 or closes[i - 63] == 0 or closes[i - 5] == 0:
                continue

            ts_mom = (closes[i] - closes[i - 252]) / abs(closes[i - 252])

            window63 = closes[i - 63 : i + 1]
            daily_returns_63 = [
                (window63[k] - window63[k - 1]) / window63[k - 1] for k in range(1, len(window63)) if window63[k - 1] != 0
            ]
            if len(daily_returns_63) < 2:
                continue
            realized_vol = (sum((r - sum(daily_returns_63) / len(daily_returns_63)) ** 2 for r in daily_returns_63) / len(daily_returns_63)) ** 0.5

            window21 = closes[i - 21 : i + 1]
            daily_returns_21 = [
                (window21[k] - window21[k - 1]) / window21[k - 1] for k in range(1, len(window21)) if window21[k - 1] != 0
            ]
            if not daily_returns_21:
                continue
            trailing_max = max(daily_returns_21)

            confirm_cutoff = i - 5
            high_count = bisect.bisect_right(swing_high_idx, confirm_cutoff)
            low_count = bisect.bisect_right(swing_low_idx, confirm_cutoff)
            if high_count < 2 or low_count < 2:
                continue
            intact = 1.0 if (
                swing_high_val[high_count - 1] > swing_high_val[high_count - 2]
                and swing_low_val[low_count - 1] > swing_low_val[low_count - 2]
            ) else 0.0

            reversal_1w = (closes[i] - closes[i - 5]) / abs(closes[i - 5])

            series_by_key["ts_momentum_12m"].append(ts_mom)
            series_by_key["low_vol_63d"].append(realized_vol)
            series_by_key["max_return_21d"].append(trailing_max)
            series_by_key["dow_structure_intact"].append(intact)
            series_by_key["reversal_1w"].append(reversal_1w)

    sample_size = len(series_by_key["ts_momentum_12m"])
    print(f"Dataset: {dataset_id}")
    print(f"Pooled, aligned samples: {sample_size}")

    matrix = pairwise_correlation_matrix(series_by_key)
    keys = sorted(series_by_key)
    print("\nPairwise correlation:")
    for (key_a, key_b), correlation in sorted(matrix.items(), key=lambda item: -abs(item[1])):
        flag = " <-- |r|>=0.5, likely the same underlying bet" if abs(correlation) >= 0.5 else ""
        print(f"  {key_a} vs {key_b}: r={correlation:+.3f}{flag}")

    enb = effective_number_of_bets(keys, matrix)
    print(f"\nEffective number of bets across these {len(keys)} signals: {enb:.2f}" if enb is not None else "\nENB not computable.")


if __name__ == "__main__":
    main()
