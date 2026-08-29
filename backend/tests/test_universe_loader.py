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
    # The reviewed snapshot has 775 price identities. AAPL and NVDA already
    # exist in the 32-row active seed, so it contributes 773 new rows.
    assert total == 805
    assert active == 32

    snapshot_symbols = connection.execute(
        """
        SELECT COUNT(DISTINCT symbol) AS n
        FROM staging_universe_membership
        WHERE stage = 'stage-2'
        """
    ).fetchone()["n"]
    assert snapshot_symbols == 775

    mapped_snapshot_symbols = connection.execute(
        """
        SELECT COUNT(DISTINCT membership.symbol) AS n
        FROM staging_universe_membership AS membership
        JOIN securities AS sec ON sec.primary_symbol = membership.symbol
        WHERE membership.stage = 'stage-2'
        """
    ).fetchone()["n"]
    ambiguous_mappings = connection.execute(
        """
        SELECT COUNT(*) AS n FROM (
            SELECT membership.symbol
            FROM staging_universe_membership AS membership
            JOIN securities AS sec ON sec.primary_symbol = membership.symbol
            WHERE membership.stage = 'stage-2'
            GROUP BY membership.symbol
            HAVING COUNT(DISTINCT sec.security_id) != 1
        )
        """
    ).fetchone()["n"]
    assert mapped_snapshot_symbols == 775
    assert ambiguous_mappings == 0

    anchor_audit = connection.execute(
        """
        SELECT source_roster_complete, price_symbol_mapping_complete,
               complete_for_price_universe
        FROM staging_universe_anchors
        WHERE stage = 'stage-2'
        ORDER BY anchor
        """
    ).fetchall()
    assert len(anchor_audit) == 19
    assert all(row["source_roster_complete"] == 1 for row in anchor_audit)
    assert all(row["price_symbol_mapping_complete"] == 1 for row in anchor_audit)
    assert all(row["complete_for_price_universe"] == 1 for row in anchor_audit)

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


def test_stage_members_use_library_path_not_live_pipeline(tmp_path: Path) -> None:
    # The live fetch stage and live engines use active=1. Explicit stage
    # membership uses the separately paced, per-symbol library path; one bad or
    # slow research symbol must never enlarge or abort the Today-desk fetch.
    database = initialize_database(tmp_path / "fetch_only.db")
    connection = connect(database)
    fetch_data_targets = {
        row["symbol"]
        for row in connection.execute(
            "SELECT symbol FROM staging_symbols WHERE active = 1 AND category != 'macro_series'"
        ).fetchall()
    }
    library_fetch_targets = {
        row["symbol"]
        for row in connection.execute(
            "SELECT DISTINCT symbol FROM staging_universe_membership WHERE stage = 'stage-2'"
        ).fetchall()
    }
    live_product_targets = {
        row["symbol"]
        for row in connection.execute(
            "SELECT symbol FROM staging_symbols WHERE active = 1 AND category != 'macro_series' AND research_scope = 'general'"
        ).fetchall()
    }

    assert "MRVL" in library_fetch_targets
    assert "MRVL" not in fetch_data_targets
    assert "MRVL" not in live_product_targets  # never ranked/allocated/proposed
    assert "SPY" in fetch_data_targets and "SPY" in live_product_targets
