"""Scratch script for
docs/hypotheses/asset-selection-research/theme-relative-strength.md.

H-SECT10: does a theme ETF's (SMH, IGV) relative strength against a
specific broad index (QQQ, SPY, DIA) persist into the next
non-overlapping block, at real "a few weeks" windows -- a genuinely
different specification from H-SECT01 (theme-vs-single-index, not
sector-vs-sector-pool; neither theme ETF was in that universe at all).
Read-only against the sealed dataset.

Run: .venv/bin/python -m backend.research_lab.theme_relative_strength
"""

from __future__ import annotations

from backend.database import connect, resolve_database_path
from backend.engine.research.significance import benjamini_hochberg, pearson_significance

THEMES = ["SMH", "IGV"]
BENCHMARKS = ["QQQ", "SPY", "DIA"]
WINDOWS = [10, 21]  # trading days -- "a few weeks", disclosed, not tuned


def _closes(connection, dataset_id: str, symbol: str) -> dict[str, float]:
    security_id = f"us-etf-{symbol.lower()}"
    rows = connection.execute(
        "SELECT time, close FROM symbol_bars WHERE dataset_snapshot_id = ? AND security_id = ? "
        "AND close IS NOT NULL ORDER BY time",
        (dataset_id, security_id),
    ).fetchall()
    return {row["time"]: row["close"] for row in rows}


def _block_returns(dates: list[str], closes: dict[str, float], window: int) -> list[float]:
    returns: list[float] = []
    i = 0
    while i + window < len(dates):
        start_close = closes[dates[i]]
        end_close = closes[dates[i + window]]
        returns.append(end_close / start_close - 1.0 if start_close else 0.0)
        i += window
    return returns


def main() -> None:
    connection = connect(resolve_database_path(), read_only=True)
    dataset_row = connection.execute(
        "SELECT id FROM dataset_snapshots WHERE immutable = 1 ORDER BY as_of DESC, rowid DESC LIMIT 1"
    ).fetchone()
    if dataset_row is None:
        print("No sealed dataset snapshot available -- run the real pipeline first.")
        return
    dataset_id = dataset_row["id"]

    all_symbols = THEMES + BENCHMARKS
    closes = {symbol: _closes(connection, dataset_id, symbol) for symbol in all_symbols}
    common_dates = sorted(set.intersection(*(set(c) for c in closes.values())))
    print(f"Dataset: {dataset_id}")
    print(f"{len(common_dates)} common real trading days, {common_dates[0]} to {common_dates[-1]}\n")

    results: list[dict] = []
    for window in WINDOWS:
        theme_block_returns = {t: _block_returns(common_dates, closes[t], window) for t in THEMES}
        benchmark_block_returns = {b: _block_returns(common_dates, closes[b], window) for b in BENCHMARKS}

        for theme in THEMES:
            for benchmark in BENCHMARKS:
                n_blocks = min(len(theme_block_returns[theme]), len(benchmark_block_returns[benchmark]))
                relative_strength = [
                    theme_block_returns[theme][i] - benchmark_block_returns[benchmark][i] for i in range(n_blocks)
                ]
                absolute_forward = theme_block_returns[theme]

                rs_now = relative_strength[:-1]
                rs_next = relative_strength[1:]
                r_persist, p_persist = pearson_significance(rs_now, rs_next)
                results.append({
                    "kind": "persistence", "theme": theme, "benchmark": benchmark, "window": window,
                    "n": len(rs_now), "correlation": r_persist, "p_value": p_persist,
                })

                abs_next = absolute_forward[1:n_blocks]
                rs_now_for_abs = relative_strength[: len(abs_next)]
                r_abs, p_abs = pearson_significance(rs_now_for_abs, abs_next)
                results.append({
                    "kind": "predicts_absolute_return", "theme": theme, "benchmark": benchmark, "window": window,
                    "n": len(rs_now_for_abs), "correlation": r_abs, "p_value": p_abs,
                })

    adjusted, significant = benjamini_hochberg([r["p_value"] for r in results])
    for r, adj_p, sig in zip(results, adjusted, significant):
        r["adjusted_p"] = adj_p
        r["significant"] = sig

    print(f"=== {len(results)} tests, Benjamini-Hochberg corrected ===\n")
    for r in sorted(results, key=lambda r: r["adjusted_p"]):
        flag = "SIGNIFICANT" if r["significant"] else "not significant"
        print(f"{r['kind']:24s} {r['theme']:4s} vs {r['benchmark']:4s}  {r['window']:2d}d  n={r['n']:4d}  "
              f"r={r['correlation']:+.3f}  adj_p={r['adjusted_p']:.4f}  ({flag})")

    sig_count = sum(1 for r in results if r["significant"])
    print(f"\n{sig_count} of {len(results)} significant after correction "
          f"(chance alone at alpha=0.05 would produce ~{0.05 * len(results):.1f})")


if __name__ == "__main__":
    main()
