from __future__ import annotations

import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE_PATH = PROJECT_ROOT / "data" / "desk.db"
SCHEMA_PATH = Path(__file__).with_name("schema.sql")

DESK_SNAPSHOT_CHILD_TABLES = (
    "philosophy_sections",
    "regime_filters",
    "regime_weights",
    "regime_contributions",
    "regime_evidence",
    "recommendation_points",
    "decision_nodes",
    "decision_edges",
    "decision_observations",
    "desk_metrics",
    "backtests",
    "backtest_metrics",
    "symbols",
    "symbol_hierarchy",
    "symbol_recommendations",
    "symbol_recommendation_points",
    "symbol_signals",
    "symbol_metrics",
    "position_candidates",
    "position_legs",
    "position_points",
    "position_blockers",
    "position_greeks",
    "data_sources",
    "symbol_data_sources",
    "factor_dimensions",
    "cross_section_rows",
    "factor_values",
    "cross_section_legend",
)

DATASET_SNAPSHOT_CHILD_TABLES = ("symbol_bars", "symbol_events", "fred_observations")


def resolve_database_path(database_path: str | Path | None = None) -> Path:
    if database_path is None:
        return DEFAULT_DATABASE_PATH
    return Path(database_path).expanduser().resolve()


def connect(database_path: str | Path, *, read_only: bool = False) -> sqlite3.Connection:
    path = resolve_database_path(database_path)
    if read_only:
        connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        connection.execute("PRAGMA query_only = ON")
    else:
        connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(database_path: str | Path | None = None) -> Path:
    """Create the schema only. Synthetic demo data is never inserted implicitly."""

    path = resolve_database_path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    with connect(path) as connection:
        try:
            # Keep the additive migration, compatibility columns, and trigger
            # installation in one transaction. A failed upgrade must not leave
            # schema_metadata claiming the latest version over a partially
            # installed schema.
            prelude = _catalog_compatibility_prelude(connection)
            connection.executescript(f"BEGIN IMMEDIATE;\n{prelude}\n{schema}")
            _install_compatible_columns(connection)
            _install_immutability_guards(connection)
        except BaseException:
            connection.rollback()
            raise
        else:
            connection.commit()
    return path


def _catalog_compatibility_prelude(connection: sqlite3.Connection) -> str:
    """Columns needed by catalog upserts must exist before schema.sql reaches them."""

    table = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'operator_providers'"
    ).fetchone()
    if table is None:
        return ""
    columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(operator_providers)").fetchall()
    }
    statements = []
    if "credential_revision" not in columns:
        statements.append(
            "ALTER TABLE operator_providers ADD COLUMN credential_revision "
            "INTEGER NOT NULL DEFAULT 0 CHECK (credential_revision >= 0);"
        )
    if "attribution_notice" not in columns:
        statements.append(
            "ALTER TABLE operator_providers ADD COLUMN attribution_notice TEXT;"
        )
    if "verification_ttl_seconds" not in columns:
        statements.append(
            "ALTER TABLE operator_providers ADD COLUMN verification_ttl_seconds "
            "INTEGER NOT NULL DEFAULT 31536000 CHECK (verification_ttl_seconds > 0);"
        )
    if "tier" not in columns:
        statements.append(
            "ALTER TABLE operator_providers ADD COLUMN tier "
            "TEXT NOT NULL DEFAULT 'paid' CHECK (tier IN ('free', 'paid'));"
        )

    strategy_versions_table = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'strategy_versions'"
    ).fetchone()
    if strategy_versions_table is not None:
        strategy_version_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(strategy_versions)").fetchall()
        }
        if "next_review_at" not in strategy_version_columns:
            statements.append(
                "ALTER TABLE strategy_versions ADD COLUMN next_review_at TEXT;"
            )
        if "verification_status" not in strategy_version_columns:
            statements.append(
                "ALTER TABLE strategy_versions ADD COLUMN verification_status TEXT "
                "NOT NULL DEFAULT 'registered_only' "
                "CHECK (verification_status IN ("
                "'registered_only', 'verified', 'not_significant', "
                "'collinear', 'decayed', 'outdated'));"
            )

    return "\n".join(statements)


def _install_compatible_columns(connection: sqlite3.Connection) -> None:
    """Add nullable contract fields without rewriting already-sealed snapshots."""

    columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(position_candidates)").fetchall()
    }
    if "allocation_basis" not in columns:
        connection.execute(
            "ALTER TABLE position_candidates ADD COLUMN allocation_basis TEXT "
            "CHECK (allocation_basis IN ('portfolio_weight', 'premium_budget', "
            "'notional_weight', 'risk_budget'))"
        )
    if "conviction" not in columns:
        connection.execute(
            "ALTER TABLE position_candidates ADD COLUMN conviction REAL"
        )
    if "input_completeness_scope" not in columns:
        connection.execute(
            "ALTER TABLE position_candidates ADD COLUMN input_completeness_scope TEXT "
            "CHECK (input_completeness_scope IN ('live_market_data', "
            "'synthetic_simulation_inputs', 'other'))"
        )

    cross_section_columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(cross_section_rows)").fetchall()
    }
    if "conviction" not in cross_section_columns:
        connection.execute("ALTER TABLE cross_section_rows ADD COLUMN conviction REAL")

    dataset_columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(dataset_snapshots)").fetchall()
    }
    if "engine_mode" not in dataset_columns:
        connection.execute(
            "ALTER TABLE dataset_snapshots ADD COLUMN engine_mode TEXT "
            "CHECK (engine_mode IS NULL OR engine_mode IN ('pilot', 'production'))"
        )
    desk_columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(desk_snapshots)").fetchall()
    }
    if "engine_mode" not in desk_columns:
        connection.execute(
            "ALTER TABLE desk_snapshots ADD COLUMN engine_mode TEXT "
            "CHECK (engine_mode IS NULL OR engine_mode IN ('pilot', 'production'))"
        )
    if "regime_percentile_rank" not in desk_columns:
        connection.execute(
            "ALTER TABLE desk_snapshots ADD COLUMN regime_percentile_rank REAL "
            "CHECK (regime_percentile_rank IS NULL OR (regime_percentile_rank >= 0 AND regime_percentile_rank <= 100))"
        )
    staging_symbol_columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(staging_symbols)").fetchall()
    }
    if "research_scope" not in staging_symbol_columns:
        connection.execute(
            "ALTER TABLE staging_symbols ADD COLUMN research_scope TEXT NOT NULL DEFAULT 'general' "
            "CHECK (research_scope IN ('general', 'narrow_proxy', 'reference_only'))"
        )
    # Corrected here, not in schema.sql: on an existing database schema.sql's
    # own script runs before this function, so an UPDATE referencing
    # research_scope there would fail with "no such column" the first time
    # this migration is needed -- caught by actually running it, not assumed.
    # Runs every startup, harmless once already correct.
    connection.execute(
        "UPDATE staging_symbols SET research_scope = 'narrow_proxy' "
        "WHERE symbol = 'VXX' AND research_scope != 'narrow_proxy'"
    )
    connection.execute(
        "UPDATE staging_symbols SET research_scope = 'reference_only' "
        "WHERE symbol = 'BTC-USD' AND research_scope != 'reference_only'"
    )

    event_columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(symbol_events)").fetchall()
    }
    legacy_event_status_added = False
    if "event_status" not in event_columns:
        # A v3 database may already have our sealed-dataset UPDATE guard. Drop
        # that known guard inside the migration transaction so the conservative
        # status backfill can run; `_install_immutability_guards` restores it
        # before commit. Any failure rolls the DROP and ALTER back together.
        connection.execute("DROP TRIGGER IF EXISTS immutable_symbol_events_update")
        connection.execute(
            "ALTER TABLE symbol_events ADD COLUMN event_status TEXT NOT NULL "
            "DEFAULT 'annotation' CHECK (event_status IN ('annotation', "
            "'signal_state', 'proposed', 'executed', 'cancelled'))"
        )
        legacy_event_status_added = True
    if legacy_event_status_added:
        # Only event types whose names unambiguously describe a fill are
        # promoted during v3 migration. Generic entry/exit/signal markers remain
        # conservative annotations because they do not prove execution.
        connection.execute(
            """
            UPDATE symbol_events
            SET event_status = 'executed'
            WHERE lower(event_type) IN (
                'execution_fill', 'order_fill', 'order_filled', 'trade_fill',
                'entry_fill', 'exit_fill'
            )
            """
        )

    # Operational revisions invalidate cached verification results without
    # retaining any derivative of the credential itself.
    provider_columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(operator_providers)").fetchall()
    }
    if "credential_revision" not in provider_columns:
        connection.execute(
            "ALTER TABLE operator_providers ADD COLUMN credential_revision "
            "INTEGER NOT NULL DEFAULT 0 CHECK (credential_revision >= 0)"
        )
    if "attribution_notice" not in provider_columns:
        connection.execute(
            "ALTER TABLE operator_providers ADD COLUMN attribution_notice TEXT"
        )
    if "verification_ttl_seconds" not in provider_columns:
        connection.execute(
            "ALTER TABLE operator_providers ADD COLUMN verification_ttl_seconds "
            "INTEGER NOT NULL DEFAULT 31536000 CHECK (verification_ttl_seconds > 0)"
        )
    connection.execute(
        """
        UPDATE operator_providers
        SET attribution_notice = ?
        WHERE provider_key = 'fred' AND attribution_notice IS NULL
        """,
        (
            "This product uses the FRED API but is not endorsed or certified by "
            "the Federal Reserve Bank of St. Louis.",
        ),
    )
    verification_columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(provider_verifications)").fetchall()
    }
    if "credential_revision" not in verification_columns:
        connection.execute(
            "ALTER TABLE provider_verifications ADD COLUMN credential_revision "
            "INTEGER NOT NULL DEFAULT 0 CHECK (credential_revision >= 0)"
        )
    if "runtime_id" not in verification_columns:
        connection.execute(
            "ALTER TABLE provider_verifications ADD COLUMN runtime_id TEXT"
        )

    invalid_research = connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM research_runs AS research
        LEFT JOIN dataset_snapshots AS dataset
          ON dataset.id = research.dataset_snapshot_id
        WHERE research.status = 'completed'
          AND (
              research.dataset_snapshot_id IS NULL
              OR dataset.id IS NULL
              OR dataset.immutable != 1
          )
        """
    ).fetchone()
    if invalid_research and invalid_research["count"]:
        raise sqlite3.IntegrityError(
            "completed research runs require sealed dataset provenance"
        )

    invalid_desks = connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM desk_snapshots AS desk
        LEFT JOIN dataset_snapshots AS dataset
          ON dataset.id = desk.dataset_snapshot_id
        WHERE desk.immutable = 1
          AND (
              desk.dataset_snapshot_id IS NULL
              OR dataset.id IS NULL
              OR dataset.immutable != 1
              OR dataset.data_classification != desk.data_classification
              OR dataset.is_live != desk.is_live
              OR dataset.is_demo != desk.is_demo
          )
        """
    ).fetchone()
    if invalid_desks and invalid_desks["count"]:
        raise sqlite3.IntegrityError(
            "published desk snapshots require sealed dataset provenance"
        )


def _install_immutability_guards(connection: sqlite3.Connection) -> None:
    """Make every published snapshot append-only, including all child records."""

    for table in DESK_SNAPSHOT_CHILD_TABLES:
        connection.execute(
            f"""
            CREATE TRIGGER IF NOT EXISTS immutable_{table}_insert
            BEFORE INSERT ON {table}
            WHEN COALESCE((SELECT immutable FROM desk_snapshots WHERE id = NEW.snapshot_id), 0) = 1
            BEGIN
                SELECT RAISE(ABORT, 'cannot insert into sealed desk snapshot');
            END
            """
        )
        connection.execute(
            f"""
            CREATE TRIGGER IF NOT EXISTS immutable_{table}_update
            BEFORE UPDATE ON {table}
            WHEN COALESCE((SELECT immutable FROM desk_snapshots WHERE id = OLD.snapshot_id), 0) = 1
              OR COALESCE((SELECT immutable FROM desk_snapshots WHERE id = NEW.snapshot_id), 0) = 1
            BEGIN
                SELECT RAISE(ABORT, 'cannot update sealed desk snapshot');
            END
            """
        )
        connection.execute(
            f"""
            CREATE TRIGGER IF NOT EXISTS immutable_{table}_delete
            BEFORE DELETE ON {table}
            WHEN COALESCE((SELECT immutable FROM desk_snapshots WHERE id = OLD.snapshot_id), 0) = 1
            BEGIN
                SELECT RAISE(ABORT, 'cannot delete from sealed desk snapshot');
            END
            """
        )

    for table in DATASET_SNAPSHOT_CHILD_TABLES:
        connection.execute(
            f"""
            CREATE TRIGGER IF NOT EXISTS immutable_{table}_insert
            BEFORE INSERT ON {table}
            WHEN COALESCE((SELECT immutable FROM dataset_snapshots WHERE id = NEW.dataset_snapshot_id), 0) = 1
            BEGIN
                SELECT RAISE(ABORT, 'cannot insert into sealed dataset snapshot');
            END
            """
        )
        connection.execute(
            f"""
            CREATE TRIGGER IF NOT EXISTS immutable_{table}_update
            BEFORE UPDATE ON {table}
            WHEN COALESCE((SELECT immutable FROM dataset_snapshots WHERE id = OLD.dataset_snapshot_id), 0) = 1
              OR COALESCE((SELECT immutable FROM dataset_snapshots WHERE id = NEW.dataset_snapshot_id), 0) = 1
            BEGIN
                SELECT RAISE(ABORT, 'cannot update sealed dataset snapshot');
            END
            """
        )
        connection.execute(
            f"""
            CREATE TRIGGER IF NOT EXISTS immutable_{table}_delete
            BEFORE DELETE ON {table}
            WHEN COALESCE((SELECT immutable FROM dataset_snapshots WHERE id = OLD.dataset_snapshot_id), 0) = 1
            BEGIN
                SELECT RAISE(ABORT, 'cannot delete from sealed dataset snapshot');
            END
            """
        )


def snapshot_count(database_path: str | Path) -> int:
    with connect(database_path, read_only=True) as connection:
        row = connection.execute("SELECT COUNT(*) AS count FROM desk_snapshots").fetchone()
    return int(row["count"])
