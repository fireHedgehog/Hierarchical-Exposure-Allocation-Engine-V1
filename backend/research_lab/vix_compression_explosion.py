"""Scratch script for docs/hypotheses/timing-research/vix-percentile-vxx-entry.md,
v2 reframe: compression-episode explosion event study.

Reframed per direct correction: not a continuous IC over a long forward
window (H-TIME01 v1), but a real event study -- when VIX has been
compressed (real, disclosed threshold+duration) does a real "volatility
explosion" (a large single-day VXX jump) become more likely in the
near-term forward window than the unconditional base rate. Same reframe
shape as dow-theory-trend-structure.md -> dow-theory-risk-state.md and
the macro composite's own timing -> risk-context reframe. Read-only
against the sealed dataset.

Run: .venv/bin/python -m backend.research_lab.vix_compression_explosion
"""

from __future__ import annotations

from backend.database import connect, resolve_database_path
from backend.engine.research.significance import proportion_significance

COMPRESSION_THRESHOLD = 15.0  # disclosed, user's own number, not tuned
COMPRESSION_STREAK_DAYS = 21  # ~1 trading month, disclosed, not tuned
EXPLOSION_THRESHOLD = 0.10  # a single real day, VXX +10%, disclosed, not tuned
VIX_RELATIVE_EXPLOSION = 1.5  # VIXCLS itself rising 50% relative to the episode-start level, disclosed, not tuned
FORWARD_WINDOWS = (5, 10)  # trading days to watch for an explosion after an episode starts


def main() -> None:
    connection = connect(resolve_database_path(), read_only=True)
    dataset_row = connection.execute(
        "SELECT id FROM dataset_snapshots WHERE immutable = 1 ORDER BY as_of DESC, rowid DESC LIMIT 1"
    ).fetchone()
    if dataset_row is None:
        print("No sealed dataset snapshot available -- run the real pipeline first.")
        return
    dataset_id = dataset_row["id"]

    vix_rows = connection.execute(
        "SELECT observation_date, value FROM fred_observations "
        "WHERE dataset_snapshot_id = ? AND series_id = 'VIXCLS' AND value IS NOT NULL ORDER BY observation_date",
        (dataset_id,),
    ).fetchall()
    vix_dates = [row["observation_date"] for row in vix_rows]
    vix_values = [row["value"] for row in vix_rows]

    vxx_rows = connection.execute(
        "SELECT time, close FROM symbol_bars WHERE dataset_snapshot_id = ? AND security_id = 'us-etf-vxx' "
        "AND close IS NOT NULL ORDER BY time",
        (dataset_id,),
    ).fetchall()
    vxx_dates = [row["time"] for row in vxx_rows]
    vxx_closes = [row["close"] for row in vxx_rows]
    vxx_index_by_date = {d: i for i, d in enumerate(vxx_dates)}

    print(f"Dataset: {dataset_id}")
    print(f"VIXCLS: {len(vix_dates)} real observations, {vix_dates[0]} to {vix_dates[-1]}")
    print(f"VXX: {len(vxx_dates)} real bars, {vxx_dates[0]} to {vxx_dates[-1]}\n")

    # real compression streak, and real episode-start dates (streak crosses
    # the threshold for the first time -- not re-counted every day the
    # streak continues, to avoid pseudo-replication)
    streak = 0
    episode_starts: list[str] = []
    for date, value in zip(vix_dates, vix_values):
        if value < COMPRESSION_THRESHOLD:
            streak += 1
        else:
            streak = 0
        if streak == COMPRESSION_STREAK_DAYS:
            episode_starts.append(date)

    print(f"{len(episode_starts)} real compression episodes (VIX < {COMPRESSION_THRESHOLD} for "
          f"{COMPRESSION_STREAK_DAYS} consecutive real trading days), full 2004-2026 history")
    episode_starts_with_vxx = [d for d in episode_starts if d in vxx_index_by_date]
    print(f"{len(episode_starts_with_vxx)} of those fall within VXX's real 2018-2026 window\n")

    def _has_explosion(start_index: int, window: int) -> bool | None:
        if start_index + window >= len(vxx_closes):
            return None
        for i in range(start_index + 1, start_index + window + 1):
            if vxx_closes[i - 1] == 0:
                continue
            if vxx_closes[i] / vxx_closes[i - 1] - 1.0 >= EXPLOSION_THRESHOLD:
                return True
        return False

    for window in FORWARD_WINDOWS:
        episode_hits = 0
        episode_n = 0
        for date in episode_starts_with_vxx:
            result = _has_explosion(vxx_index_by_date[date], window)
            if result is None:
                continue
            episode_n += 1
            episode_hits += 1 if result else 0

        baseline_hits = 0
        baseline_n = 0
        for i in range(len(vxx_closes) - window):
            result = _has_explosion(i, window)
            if result is None:
                continue
            baseline_n += 1
            baseline_hits += 1 if result else 0

        print(f"=== Forward window: {window} trading days ===")
        if episode_n == 0:
            print("  No real compression episodes with enough forward VXX history to check.\n")
            continue
        print(f"  P(explosion | compression episode start): {episode_hits}/{episode_n} = {episode_hits/episode_n:.1%}")
        print(f"  P(explosion | unconditional baseline):     {baseline_hits}/{baseline_n} = {baseline_hits/baseline_n:.1%}")
        diff, p = proportion_significance(episode_hits, episode_n, baseline_hits, baseline_n)
        print(f"  Difference: {diff:+.1%}, p={p:.4f} ({'SIGNIFICANT' if p < 0.05 else 'not significant'})\n")

    print(f"=== Same test, on VIXCLS's OWN behavior (full 2004-2026, all {len(episode_starts)} episodes -- "
          f"not bottlenecked by VXX's short real history) ===\n")
    vix_index_by_date = {d: i for i, d in enumerate(vix_dates)}

    def _vix_has_explosion(start_index: int, window: int) -> bool | None:
        if start_index + window >= len(vix_values):
            return None
        start_value = vix_values[start_index]
        if start_value == 0:
            return None
        for i in range(start_index + 1, start_index + window + 1):
            if vix_values[i] / start_value >= VIX_RELATIVE_EXPLOSION:
                return True
        return False

    for window in FORWARD_WINDOWS:
        episode_hits = 0
        episode_n = 0
        for date in episode_starts:
            result = _vix_has_explosion(vix_index_by_date[date], window)
            if result is None:
                continue
            episode_n += 1
            episode_hits += 1 if result else 0

        baseline_hits = 0
        baseline_n = 0
        for i in range(len(vix_values) - window):
            result = _vix_has_explosion(i, window)
            if result is None:
                continue
            baseline_n += 1
            baseline_hits += 1 if result else 0

        print(f"=== Forward window: {window} trading days (VIXCLS >= {VIX_RELATIVE_EXPLOSION}x episode-start level) ===")
        print(f"  P(explosion | compression episode start): {episode_hits}/{episode_n} = {episode_hits/episode_n:.1%}")
        print(f"  P(explosion | unconditional baseline):     {baseline_hits}/{baseline_n} = {baseline_hits/baseline_n:.1%}")
        diff, p = proportion_significance(episode_hits, episode_n, baseline_hits, baseline_n)
        print(f"  Difference: {diff:+.1%}, p={p:.4f} ({'SIGNIFICANT' if p < 0.05 else 'not significant'})\n")


if __name__ == "__main__":
    main()
