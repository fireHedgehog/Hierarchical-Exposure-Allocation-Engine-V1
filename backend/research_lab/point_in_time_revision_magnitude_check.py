"""Scratch script -- real, direct measurement of how large the point-in-time
gap documented in docs/hypotheses/README.md's "Known methodology
limitations" actually is, for the specific series that matter most to
this project's findings. Not a general literature claim: two real, live
ALFRED queries per (series, date) -- the value as first published
(shortly after the real historical release), and the value as known
today (fully revised) -- compared directly. Read-only, no DB writes,
same FRED provider function fetch_data.py already uses.

Run: .venv/bin/python -m backend.research_lab.point_in_time_revision_magnitude_check
"""

from __future__ import annotations

from datetime import date, timedelta

from backend.database import connect, resolve_database_path
from backend.providers.fred import fetch_series_observations
from backend.secrets import KeyringEnvironmentSecretStore

# (series, observation_date, real days-after-quarter/month-end the first
# real release typically lands -- GDP's "advance" estimate ~30d, PAYEMS'
# first release ~5-35d after the reference month, CPI ~2-3 weeks; using a
# safely-past-first-release lag, disclosed, not tuned to any result)
CHECKS = [
    ("GDPC1", "2008-07-01", 160),   # Q3 2008 -- real lag found longer than the textbook ~120d assumption
    ("GDPC1", "2008-10-01", 160),   # Q4 2008 -- the sharpest real GDP contraction
    ("GDPC1", "2023-01-01", 160),   # same real lag, calm contrast
    ("PAYEMS", "2008-09-01", 40),   # crisis-era payrolls -- first Friday of the following month
    ("PAYEMS", "2008-10-01", 40),
    ("PAYEMS", "2023-01-01", 40),   # calm contrast
    ("CPIAUCSL", "2008-10-01", 60),  # observation_date is month start; CPI releases ~2-3 weeks after month END
]


def main() -> None:
    connection = connect(resolve_database_path(), read_only=True)
    provider = connection.execute(
        "SELECT credential_name, environment_variable FROM operator_providers WHERE provider_key = 'fred'"
    ).fetchone()
    secret = KeyringEnvironmentSecretStore().get(provider["credential_name"], provider["environment_variable"])
    if secret is None:
        print("No FRED credential configured -- cannot run this real check.")
        return

    # Same 1-day safety margin fetch_data.py itself uses: FRED validates
    # realtime_start/realtime_end against its own server clock (US time,
    # behind UTC) and rejects a pin later than that with a real HTTP 400.
    today = (date.today() - timedelta(days=1)).isoformat()
    print(f"Real live ALFRED comparison, first-release vintage vs. today's ({today}) fully-revised vintage\n")

    for series_id, observation_date, lag_days in CHECKS:
        first_release_date = (date.fromisoformat(observation_date) + timedelta(days=lag_days)).isoformat()
        try:
            first_release = fetch_series_observations(
                secret.value, series_id,
                observation_start=observation_date, observation_end=observation_date,
                realtime_start=first_release_date, realtime_end=first_release_date,
            )
            latest = fetch_series_observations(
                secret.value, series_id,
                observation_start=observation_date, observation_end=observation_date,
                realtime_start=today, realtime_end=today,
            )
        except Exception as error:  # real network/API call; report, don't crash the whole sweep
            print(f"{series_id} {observation_date}: fetch failed ({error})")
            continue

        first_value = next((o.value for o in first_release if o.observation_date == observation_date), None)
        latest_value = next((o.value for o in latest if o.observation_date == observation_date), None)
        if first_value is None or latest_value is None:
            print(f"{series_id} {observation_date}: no real observation returned for one of the two vintages")
            continue

        pct_change = (latest_value - first_value) / abs(first_value) * 100 if first_value else float("nan")
        print(f"{series_id:10s} {observation_date}  first-release (~{first_release_date}) = {first_value:>12.2f}   "
              f"today = {latest_value:>12.2f}   real revision = {pct_change:+.2f}%")

    print("\n=== The real, decision-relevant check: does the RAW level revision survive into the")
    print("    YoY GROWTH RATE scoring_v3.py actually uses (GDPC1 is_yoy=True), or does a rebase cancel out? ===\n")
    for obs_date, year_ago_date, vintage, label in [
        ("2008-07-01", "2007-07-01", "2008-12-08", "Q3 2008 (the crisis quarter driving H-MACRO11's biggest IC)"),
    ]:
        def _get(observation_date: str, realtime: str) -> float | None:
            rows = fetch_series_observations(
                secret.value, "GDPC1", observation_start=observation_date, observation_end=observation_date,
                realtime_start=realtime, realtime_end=realtime,
            )
            return next((o.value for o in rows if o.observation_date == observation_date), None)

        current_first, year_ago_first = _get(obs_date, vintage), _get(year_ago_date, vintage)
        current_today, year_ago_today = _get(obs_date, today), _get(year_ago_date, today)
        if None in (current_first, year_ago_first, current_today, year_ago_today):
            print(f"{label}: insufficient real data for one of the four real vintage points")
            continue
        yoy_first = (current_first / year_ago_first - 1) * 100
        yoy_today = (current_today / year_ago_today - 1) * 100
        print(f"{label}:")
        print(f"  Raw level revision (already shown above): ~+44%")
        print(f"  YoY growth, as known at the time (~{vintage}): {yoy_first:+.2f}%")
        print(f"  YoY growth, as known today:                  {yoy_today:+.2f}%")
        print(f"  Real difference in the actual composite input: {yoy_today - yoy_first:+.2f} percentage points")


if __name__ == "__main__":
    main()
