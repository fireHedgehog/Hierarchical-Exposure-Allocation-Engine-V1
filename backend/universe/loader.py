"""Load the reviewed current-vintage universe into staging tables.

Deliberately separate from schema.sql's own small, hand-typed 27-symbol
INSERT block: a few hundred rows is unwieldy as literal SQL text, and this
loader's job is real -- read a real, disclosed, frozen file, not invent
data. Symbol rows and fetched price history are additive; membership and its
compact anchor provenance are reconciled exactly for the stage because this
research fixture is disposable and correctable. Git retains earlier versions.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from backend.pipeline.stages.common import _security_id_for

UNIVERSE_DIR = Path(__file__).resolve().parent

# Real equities from a frozen stage file get this staging_symbols category.
# Not a perfect fit for every member (not every S&P 500 constituent is
# literally "mega cap") -- a deliberate, disclosed simplification. A
# precise per-size category taxonomy would require widening
# staging_symbols' category CHECK constraint, which means rebuilding that
# live table; not worth the real risk to already-fetched, expensive-to-
# replace historical data for a label-precision nicety. The real,
# genuinely useful dimension (which anchor index a symbol belongs to) is
# tracked properly in staging_universe_membership instead.
STAGE_EQUITY_CATEGORY = "mega_cap_equity"
STAGE_EQUITY_PROVIDER_KEY = "intrinio"


def load_frozen_universe(connection: sqlite3.Connection, path: Path | str) -> dict[str, int]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    stage = payload["stage"]
    frozen_at = payload["frozen_at"]
    symbols = payload["symbols"]
    anchor_sources = payload.get("anchor_sources", {})
    compiled_at = payload.get("compiled_at") or frozen_at

    connection.execute("DELETE FROM staging_universe_membership WHERE stage = ?", (stage,))
    connection.execute("DELETE FROM staging_universe_anchors WHERE stage = ?", (stage,))
    for anchor, metadata in anchor_sources.items():
        connection.execute(
            """
            INSERT INTO staging_universe_anchors (
                stage, anchor, anchor_kind, source_url, source_kind,
                source_as_of, source_as_of_raw, coverage_status,
                source_row_count, source_reported_count, eligible_row_count,
                mapped_member_count, excluded_row_count, rejected_row_count,
                source_roster_complete, price_symbol_mapping_complete,
                complete_for_price_universe, excluded_rows_json,
                rejected_rows_json, compiled_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                stage,
                anchor,
                metadata["anchor_kind"],
                metadata["source"],
                metadata["source_kind"],
                metadata.get("as_of"),
                metadata.get("source_as_of_raw"),
                metadata["coverage_status"],
                metadata["source_row_count"],
                metadata.get("source_reported_count"),
                metadata["eligible_row_count"],
                metadata["mapped_member_count"],
                metadata["excluded_row_count"],
                metadata["rejected_row_count"],
                int(bool(metadata["source_roster_complete"])),
                int(bool(metadata["price_symbol_mapping_complete"])),
                int(bool(metadata["complete_for_price_universe"])),
                json.dumps(metadata.get("excluded_rows", []), ensure_ascii=False),
                json.dumps(metadata.get("rejected_rows", []), ensure_ascii=False),
                compiled_at,
            ),
        )

    existing_max_sort = connection.execute(
        "SELECT COALESCE(MAX(sort_order), 0) AS value FROM staging_symbols"
    ).fetchone()["value"]

    inserted_symbols = 0
    inserted_security_mappings = 0
    inserted_membership = 0
    next_sort = existing_max_sort + 1
    for entry in symbols:
        symbol = entry["symbol"]
        # active=0 deliberately keeps stage-only members out of the Today
        # desk. fetch_only=1 remains a compatibility hint; the admin library
        # fetch binds eligibility to this stage's actual membership rows,
        # including active/cohort overlaps such as AAPL and NVDA.
        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO staging_symbols (
                symbol, name, category, tier, production_provider_key,
                notes, active, fetch_only, sort_order
            ) VALUES (?, ?, ?, 'free', ?, NULL, 0, 1, ?)
            """,
            (symbol, entry["name"], STAGE_EQUITY_CATEGORY, STAGE_EQUITY_PROVIDER_KEY, next_sort),
        )
        if cursor.rowcount:
            inserted_symbols += 1
            next_sort += 1

        # Compile the current-vintage price identity before any provider
        # fetch. Ingestion may use exactly one reviewed mapping; it must never
        # grow or guess the security master as a side effect of receiving bars.
        mapped = connection.execute(
            "SELECT security_id FROM securities WHERE primary_symbol = ? ORDER BY security_id",
            (symbol,),
        ).fetchall()
        if len(mapped) > 1:
            raise sqlite3.IntegrityError(
                f"{symbol}: current staging universe has multiple security mappings"
            )
        if not mapped:
            security_id = _security_id_for(symbol, STAGE_EQUITY_CATEGORY)
            collision = connection.execute(
                "SELECT primary_symbol FROM securities WHERE security_id = ?",
                (security_id,),
            ).fetchone()
            if collision is not None and collision["primary_symbol"] != symbol:
                raise sqlite3.IntegrityError(
                    f"{symbol}: security id {security_id} belongs to {collision['primary_symbol']}"
                )
            connection.execute(
                """
                INSERT INTO securities (
                    security_id, primary_symbol, name, asset_type,
                    exchange, currency, sector, active
                ) VALUES (?, ?, ?, 'equity', NULL, 'USD', NULL, 1)
                """,
                (security_id, symbol, entry["name"]),
            )
            inserted_security_mappings += 1
        for membership in entry["memberships"]:
            anchor_source = anchor_sources.get(membership["anchor"], {})
            membership_as_of = anchor_source.get("as_of") or frozen_at
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO staging_universe_membership (
                    symbol, stage, anchor, anchor_kind, weight_pct, frozen_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    symbol,
                    stage,
                    membership["anchor"],
                    membership["anchor_kind"],
                    membership["weight_pct"],
                    membership_as_of,
                ),
            )
            if cursor.rowcount:
                inserted_membership += 1

    return {
        "symbols_added": inserted_symbols,
        "security_mappings_added": inserted_security_mappings,
        "membership_rows_added": inserted_membership,
    }


def load_all_frozen_universes(connection: sqlite3.Connection) -> None:
    """Loads every stage-*.json file in this folder, oldest stage first
    (lexical sort matches the naming convention -- stage-2 before stage-3).
    Safe/idempotent; called on every startup like the rest of this
    project's additive migrations."""
    for path in sorted(UNIVERSE_DIR.glob("stage-*.json")):
        load_frozen_universe(connection, path)
