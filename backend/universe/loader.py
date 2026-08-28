"""Loads a frozen stage universe file (see this folder's own JSON files,
e.g. stage-2-2026-08-27.json) into staging_symbols and
staging_universe_membership.

Deliberately separate from schema.sql's own small, hand-typed 27-symbol
INSERT block: a few hundred rows is unwieldy as literal SQL text, and this
loader's job is real -- read a real, disclosed, frozen file, not invent
data. Idempotent (INSERT OR IGNORE throughout): safe to call on every
startup, matching this project's existing migration convention, and safe
to call once a symbol has since been hand-edited in staging_symbols (this
loader never overwrites an existing row).

A frozen file is never edited in place once committed -- a later stage
gets a new, separately-named file (see the folder's own JSON files for
the disclosed methodology/sources per stage). This loader can safely be
pointed at more than one stage file over time; each stage's rows are
additive.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

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

    existing_max_sort = connection.execute(
        "SELECT COALESCE(MAX(sort_order), 0) AS value FROM staging_symbols"
    ).fetchone()["value"]

    inserted_symbols = 0
    inserted_membership = 0
    next_sort = existing_max_sort + 1
    for entry in symbols:
        symbol = entry["symbol"]
        # active=0, fetch_only=1, deliberately: factor_engine/allocation_
        # engine/instrument_engine read active=1 only, so these symbols
        # never join the live Today-desk product. fetch_only=1 is the real
        # point of freezing this file -- these are extended data-library
        # symbols, meant to be fetched via the separate, admin-owned
        # library-fetch path (backend/universe/library_fetch.py -- fetching
        # is always admin/production work, never "research," per
        # developer-letter.md), without touching the live pipeline's
        # atomic, all-or-nothing fetch_data_stage at all.
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
        for membership in entry["memberships"]:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO staging_universe_membership (
                    symbol, stage, anchor, anchor_kind, weight_pct, frozen_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (symbol, stage, membership["anchor"], membership["anchor_kind"], membership["weight_pct"], frozen_at),
            )
            if cursor.rowcount:
                inserted_membership += 1

    return {"symbols_added": inserted_symbols, "membership_rows_added": inserted_membership}


def load_all_frozen_universes(connection: sqlite3.Connection) -> None:
    """Loads every stage-*.json file in this folder, oldest stage first
    (lexical sort matches the naming convention -- stage-2 before stage-3).
    Safe/idempotent; called on every startup like the rest of this
    project's additive migrations."""
    for path in sorted(UNIVERSE_DIR.glob("stage-*.json")):
        load_frozen_universe(connection, path)
