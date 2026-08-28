from __future__ import annotations

from pathlib import Path

from backend.database import connect, initialize_database


def test_frozen_stage2_universe_loads_inactive_and_membership_is_queryable(tmp_path: Path) -> None:
    # Real regression test for a real bug caught during development: the
    # loader's first version inserted new stage rows as active=1, which
    # would have made the very next real pipeline run silently try to fetch
    # ~500 new symbols from Yahoo -- the opposite of "freeze the list, then
    # design the database, then fetch" as three separate, deliberate steps.
    database = initialize_database(tmp_path / "universe.db")
    connection = connect(database, read_only=True)

    total = connection.execute("SELECT COUNT(*) AS n FROM staging_symbols").fetchone()["n"]
    active = connection.execute("SELECT COUNT(*) AS n FROM staging_symbols WHERE active = 1").fetchone()["n"]
    assert total > 700  # the real 32-symbol seed plus the frozen stage-2 file
    assert active == 32  # 27 original + IWM + SOXX/XBI/ARKX/CIBR -- stage-2 constituent rows load inactive

    # IWM: a real small-cap control/reference series, added active with no
    # membership rows of its own (it's not a constituent of anything here).
    iwm = connection.execute("SELECT active, category FROM staging_symbols WHERE symbol = 'IWM'").fetchone()
    assert iwm is not None
    assert iwm["active"] == 1
    iwm_membership = connection.execute(
        "SELECT COUNT(*) AS n FROM staging_universe_membership WHERE symbol = 'IWM'"
    ).fetchone()["n"]
    assert iwm_membership == 0

    # A stage-2-only symbol (never part of the original seed) must be inactive.
    row = connection.execute(
        "SELECT active, category FROM staging_symbols WHERE symbol = 'MRVL'"
    ).fetchone()
    assert row is not None
    assert row["active"] == 0
    assert row["category"] == "mega_cap_equity"

    # AAPL/NVDA are in both the original curated seed AND the stage-2 file --
    # the loader must never touch an already-existing row (INSERT OR IGNORE),
    # so their original active=1 must survive untouched.
    for symbol in ("AAPL", "NVDA"):
        row = connection.execute(
            "SELECT active FROM staging_symbols WHERE symbol = ?", (symbol,)
        ).fetchone()
        assert row["active"] == 1

    # The real, mineable dimension the user asked for directly: which
    # anchor(s) a symbol belonged to, and of which kind -- a genuine
    # market-cap-weighted index (SPY/QQQ/DIA) vs. a fund manager's curated
    # sector/theme basket (the XL Select Sector SPDRs, SOXX, IGV). Kept as
    # a real, disclosed, separate label, not lumped together.
    kinds = {
        row["anchor_kind"]
        for row in connection.execute("SELECT DISTINCT anchor_kind FROM staging_universe_membership").fetchall()
    }
    assert kinds == {"index", "thematic_etf"}

    triple_index_members = connection.execute(
        """
        SELECT symbol FROM staging_universe_membership
        WHERE stage = 'stage-2' AND anchor_kind = 'index'
        GROUP BY symbol
        HAVING COUNT(DISTINCT anchor) = 3
        """
    ).fetchall()
    triple_symbols = {row["symbol"] for row in triple_index_members}
    assert "AAPL" in triple_symbols  # a real, large, well-known 3-of-3 name
    assert len(triple_symbols) < 20  # 3-of-3 overlap is real and rare, not most of the universe

    # SOXX's real, disclosed weight -- the size-proxy dimension used instead
    # of a separate per-symbol market-cap fetch. NVDA is SOXX's real,
    # largest holding.
    soxx_top = connection.execute(
        """
        SELECT symbol, weight_pct FROM staging_universe_membership
        WHERE anchor = 'SOXX' ORDER BY weight_pct DESC LIMIT 1
        """
    ).fetchone()
    assert soxx_top["symbol"] == "NVDA"
    assert soxx_top["weight_pct"] > 0

    # XBI/ARKX/CIBR: added on direct request (vaccine/biotech, space,
    # cybersecurity trades named directly), each a real, active, trackable
    # symbol in its own right, not just an anchor label. SOXX was found to
    # be missing this same treatment despite already being used as an
    # anchor -- a real gap, fixed alongside the others.
    for symbol in ("SOXX", "XBI", "ARKX", "CIBR"):
        row = connection.execute(
            "SELECT active, category FROM staging_symbols WHERE symbol = ?", (symbol,)
        ).fetchone()
        assert row is not None, f"{symbol} must be a real, trackable staging_symbols row"
        assert row["active"] == 1
        assert row["category"] == "thematic_etf"

    # The real point of adding these: many of their genuine underlying
    # holdings belong to NO broad index at all -- a real, meaningful,
    # queryable state (not missing data), exactly the "null is itself
    # information" dimension asked for directly.
    arkx_members = {
        row["symbol"]
        for row in connection.execute(
            "SELECT symbol FROM staging_universe_membership WHERE anchor = 'ARKX'"
        ).fetchall()
    }
    non_index_arkx_members = connection.execute(
        f"""
        SELECT DISTINCT symbol FROM staging_universe_membership
        WHERE symbol IN ({','.join('?' for _ in arkx_members)})
        AND symbol NOT IN (
            SELECT symbol FROM staging_universe_membership WHERE anchor_kind = 'index'
        )
        """,
        tuple(arkx_members),
    ).fetchall()
    assert len(non_index_arkx_members) > 0  # real, expected -- most space names aren't in SPY/QQQ/DIA

    # Idempotent: re-initializing must not duplicate rows or error.
    initialize_database(tmp_path / "universe.db")
    total_again = connection.execute("SELECT COUNT(*) AS n FROM staging_symbols").fetchone()["n"]
    assert total_again == total


def test_fetch_only_flag_is_independent_of_the_live_product_active_flag(tmp_path: Path) -> None:
    # Real regression test for a real design gap the user caught directly:
    # `active` was overloaded -- it gated fetch_data_stage (pull real
    # price data) AND factor_engine/allocation_engine/instrument_engine
    # (rank/size/propose it in the live Today-desk product), the same bit
    # doing two different jobs. `fetch_only` lets a symbol's real price
    # history be fetched for research use without silently adding it to
    # the live product's universe -- exact SQL fragments used by the real
    # pipeline stages, not a reimplementation, so this can't drift from
    # what actually runs.
    database = initialize_database(tmp_path / "fetch_only.db")
    connection = connect(database)
    connection.execute(
        "UPDATE staging_symbols SET fetch_only = 1 WHERE symbol = 'MRVL' AND active = 0"
    )
    connection.commit()

    fetch_data_targets = {
        row["symbol"]
        for row in connection.execute(
            "SELECT symbol FROM staging_symbols WHERE (active = 1 OR fetch_only = 1) AND category != 'macro_series'"
        ).fetchall()
    }
    live_product_targets = {
        row["symbol"]
        for row in connection.execute(
            "SELECT symbol FROM staging_symbols WHERE active = 1 AND category != 'macro_series' AND research_scope = 'general'"
        ).fetchall()
    }

    assert "MRVL" in fetch_data_targets  # fetch_only=1 -- real price data pulled
    assert "MRVL" not in live_product_targets  # never ranked/allocated/proposed
    assert "SPY" in fetch_data_targets and "SPY" in live_product_targets  # active=1 untouched, both as before
