"""Scratch script for docs/hypotheses/timing-research/vix-percentile-vxx-entry.md,
v3: tolerant compression definition + a real, disclosed threshold scan.

Reframed again per direct user feedback on v2: a strict unbroken streak
resets on a single one-day blip (VIX printing 15.1 for one day inside an
otherwise-compressed stretch), which doesn't match how compression is
actually read off a real dashboard. Also: "find the most reliable
bucket" by scanning many (threshold, duration) cells and picking the
best-looking one would be real data-mining -- v2's own scan showed
several cells have n<10 real episodes. This scans ONE axis (threshold)
at a fixed, tolerant window, with a real sample floor and a real
monotonicity check, not a max-picking sweep. Read-only against the
sealed dataset.

Run: .venv/bin/python -m backend.research_lab.vix_compression_threshold_scan
"""

from __future__ import annotations

from backend.database import connect, resolve_database_path
from backend.engine.research.significance import benjamini_hochberg, proportion_significance

WINDOW_DAYS = 21  # fixed, same as v2, not re-tuned
TOLERANCE = 0.90  # >=90% of the window below threshold -- tolerant of a 1-2 day blip, disclosed, not tuned
THRESHOLDS = [13.0, 14.0, 15.0, 16.0, 17.0, 18.0]
VIX_RELATIVE_EXPLOSION = 1.5  # same as v2, not re-tuned
FORWARD_WINDOW = 10  # the window that came closest to significance in v2
MIN_TRUSTED_N = 15  # real, disclosed floor -- a rate below this sample size is reported, not trusted


def main() -> None:
    connection = connect(resolve_database_path(), read_only=True)
    dataset_row = connection.execute(
        "SELECT id FROM dataset_snapshots WHERE immutable = 1 ORDER BY as_of DESC, rowid DESC LIMIT 1"
    ).fetchone()
    if dataset_row is None:
        print("No sealed dataset snapshot available -- run the real pipeline first.")
        return
    dataset_id = dataset_row["id"]

    rows = connection.execute(
        "SELECT observation_date, value FROM fred_observations "
        "WHERE dataset_snapshot_id = ? AND series_id = 'VIXCLS' AND value IS NOT NULL ORDER BY observation_date",
        (dataset_id,),
    ).fetchall()
    dates = [r["observation_date"] for r in rows]
    values = [r["value"] for r in rows]
    print(f"Dataset: {dataset_id}")
    print(f"{len(dates)} real VIXCLS observations, {dates[0]} to {dates[-1]}\n")

    def _has_explosion(start_index: int, window: int) -> bool | None:
        if start_index + window >= len(values):
            return None
        start_value = values[start_index]
        if start_value == 0:
            return None
        for i in range(start_index + 1, start_index + window + 1):
            if values[i] / start_value >= VIX_RELATIVE_EXPLOSION:
                return True
        return False

    baseline_hits = baseline_n = 0
    for i in range(len(values) - FORWARD_WINDOW):
        result = _has_explosion(i, FORWARD_WINDOW)
        if result is None:
            continue
        baseline_n += 1
        baseline_hits += 1 if result else 0
    baseline_rate = baseline_hits / baseline_n
    print(f"Real unconditional baseline, {FORWARD_WINDOW}d: {baseline_hits}/{baseline_n} = {baseline_rate:.1%}\n")

    results: list[dict] = []
    for threshold in THRESHOLDS:
        below = [1 if v < threshold else 0 for v in values]
        in_compression = False
        episode_starts: list[int] = []
        for i in range(WINDOW_DAYS - 1, len(below)):
            window_fraction = sum(below[i - WINDOW_DAYS + 1 : i + 1]) / WINDOW_DAYS
            qualifies = window_fraction >= TOLERANCE
            if qualifies and not in_compression:
                episode_starts.append(i)
            in_compression = qualifies

        hits = n = 0
        for i in episode_starts:
            result = _has_explosion(i, FORWARD_WINDOW)
            if result is None:
                continue
            n += 1
            hits += 1 if result else 0

        rate = hits / n if n else None
        results.append({"threshold": threshold, "episodes": len(episode_starts), "n": n, "hits": hits, "rate": rate})

    trusted = [r for r in results if r["n"] >= MIN_TRUSTED_N]
    for r in trusted:
        diff, p = proportion_significance(r["hits"], r["n"], baseline_hits, baseline_n)
        r["diff"], r["p"] = diff, p
    adjusted, significant = benjamini_hochberg([r["p"] for r in trusted]) if trusted else ([], [])
    for r, adj_p, sig in zip(trusted, adjusted, significant):
        r["adj_p"], r["significant"] = adj_p, sig

    print(f"=== Tolerant compression scan ({TOLERANCE:.0%} of last {WINDOW_DAYS}d below threshold), "
          f"{FORWARD_WINDOW}d explosion window ===\n")
    print(f"{'threshold':>9} {'episodes':>9} {'usable n':>9} {'rate':>8} {'vs baseline':>12} {'status':>16}")
    for r in results:
        trust_flag = "TRUSTED" if r["n"] >= MIN_TRUSTED_N else f"too few (n<{MIN_TRUSTED_N})"
        rate_str = f"{r['rate']:.1%}" if r["rate"] is not None else "n/a"
        extra = ""
        if r["n"] >= MIN_TRUSTED_N:
            matched = next(t for t in trusted if t["threshold"] == r["threshold"])
            extra = f"  diff={matched['diff']:+.1%} adj_p={matched['adj_p']:.4f} ({'SIG' if matched['significant'] else 'n.s.'})"
        print(f"{r['threshold']:>9.0f} {r['episodes']:>9} {r['n']:>9} {rate_str:>8} {'':>12}{extra}   {trust_flag}")

    print("\n=== Monotonicity check (trusted cells only, ordered strictest to loosest threshold) ===")
    trusted_sorted = sorted(trusted, key=lambda r: r["threshold"])
    rates = [r["rate"] for r in trusted_sorted]
    print("Rates, strictest (low threshold) to loosest (high threshold):", [f"{r:.1%}" for r in rates])
    increasing_as_stricter = all(rates[i] >= rates[i + 1] for i in range(len(rates) - 1))
    print(f"Monotonic (stricter compression -> higher explosion rate, no reversals): {increasing_as_stricter}")


if __name__ == "__main__":
    main()
