from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable, Sequence

from backend.database import DEFAULT_DATABASE_PATH, connect, initialize_database, resolve_database_path


DEMO_SNAPSHOT_ID = "demo-2026-08-21-v3"
DEMO_DATASET_ID = "demo-market-2026-08-21-v3"
DEMO_AS_OF = "2026-08-21T20:00:00Z"
DEMO_INGESTED_AT = "2026-08-21T20:05:00Z"


def _json(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def _insert_many(
    connection: Any,
    table: str,
    columns: Sequence[str],
    rows: Iterable[Sequence[Any]],
    *,
    or_ignore: bool = False,
) -> None:
    placeholders = ", ".join("?" for _ in columns)
    column_list = ", ".join(columns)
    insert = "INSERT OR IGNORE" if or_ignore else "INSERT"
    connection.executemany(
        f"{insert} INTO {table} ({column_list}) VALUES ({placeholders})",
        rows,
    )


def _ensure_demo_operational_catalog(connection: Any) -> None:
    """Backfill mutable operator catalog rows without touching sealed snapshots."""

    asset_columns = (
        "asset_key", "provider_key", "label", "kind", "symbol",
        "frequency", "classification", "row_count", "period_start",
        "period_end", "last_observation_at", "last_fetched_at",
        "max_age_seconds", "status", "dataset_snapshot_id", "detail",
        "updated_at",
    )
    demo_assets = [
        ("demo_daily_bars", None, "Synthetic daily bars", "price_bars", None, "daily", "synthetic", 48, "2026-08-12T20:00:00Z", DEMO_AS_OF, DEMO_AS_OF, DEMO_INGESTED_AT, None, "ready", DEMO_DATASET_ID, "Eight synthetic bars for each of six symbols; never use as live market history.", DEMO_INGESTED_AT),
        ("demo_chart_events", None, "Synthetic chart annotations", "symbol_events", None, "event", "synthetic", 8, "2026-08-18T20:00:00Z", DEMO_AS_OF, DEMO_AS_OF, DEMO_INGESTED_AT, None, "ready", DEMO_DATASET_ID, "Synthetic review, pattern, and signal-state annotations; no executions or fills.", DEMO_INGESTED_AT),
        ("demo_tlt_options", None, "Synthetic TLT option structure", "option_chain_fixture", "TLT", "snapshot", "synthetic", 2, DEMO_AS_OF, DEMO_AS_OF, DEMO_AS_OF, DEMO_INGESTED_AT, None, "ready", DEMO_DATASET_ID, "Two synthetic legs support simulation only.", DEMO_INGESTED_AT),
    ]
    placeholders = ", ".join("?" for _ in asset_columns)
    connection.executemany(
        f"""
        INSERT INTO data_assets ({', '.join(asset_columns)})
        VALUES ({placeholders})
        ON CONFLICT(asset_key) DO UPDATE SET
            provider_key = excluded.provider_key,
            label = excluded.label,
            kind = excluded.kind,
            symbol = excluded.symbol,
            frequency = excluded.frequency,
            classification = excluded.classification,
            row_count = excluded.row_count,
            period_start = excluded.period_start,
            period_end = excluded.period_end,
            last_observation_at = excluded.last_observation_at,
            last_fetched_at = excluded.last_fetched_at,
            max_age_seconds = excluded.max_age_seconds,
            status = excluded.status,
            dataset_snapshot_id = excluded.dataset_snapshot_id,
            detail = excluded.detail,
            updated_at = excluded.updated_at
        """,
        demo_assets,
    )
    # Live/current inventory is operator-owned. A demo reseed may add missing
    # placeholders, but must never reset rows already populated by ingestion.
    _insert_many(
        connection,
        "data_assets",
        asset_columns,
        [
            ("fred_release_observations", "fred", "FRED release observations", "macro_release", None, "release", "real", 0, None, None, None, None, 129600, "missing", None, "No live FRED release observations have been fetched.", DEMO_INGESTED_AT),
            ("live_market_bars", None, "Live market bars", "price_bars", None, "daily", "real", 0, None, None, None, None, 129600, "missing", None, "No live symbol-history provider is connected.", DEMO_INGESTED_AT),
            ("live_option_chains", None, "Live option chains", "option_chain", None, "intraday", "real", 0, None, None, None, None, 900, "missing", None, "No live option-chain provider is connected.", DEMO_INGESTED_AT),
        ],
        or_ignore=True,
    )
    _insert_many(
        connection,
        "strategies",
        (
            "strategy_key", "name", "family", "summary", "status",
            "current_version", "added_at", "retired_at",
            "retirement_reason", "public_spec_url", "created_at", "updated_at",
        ),
        [
            ("state_conditioned_exposure", "State-conditioned exposure", "allocation", "Maps state confidence and portfolio constraints into bounded net and gross exposure.", "active", "0.1.0-demo", DEMO_INGESTED_AT, None, None, None, DEMO_INGESTED_AT, DEMO_INGESTED_AT),
            ("defined_risk_overlay", "Defined-risk overlay", "instrument", "Compares capped-loss option structures only after exposure and premium budgets are decided.", "watching", "0.1.0-demo", DEMO_INGESTED_AT, None, None, None, DEMO_INGESTED_AT, DEMO_INGESTED_AT),
        ],
        or_ignore=True,
    )
    _insert_many(
        connection,
        "strategy_versions",
        (
            "strategy_key", "version", "created_at", "thesis",
            "expected_edge", "change_summary", "parameters_json",
            "code_reference", "promoted_at",
        ),
        [
            ("state_conditioned_exposure", "0.1.0-demo", DEMO_INGESTED_AT, "Risk should vary with a falsifiable state hypothesis and explicit confidence constraints.", "Avoid applying the same factor weights and exposure budget in incompatible states.", "Initial synthetic specification; no performance claim.", _json({"maximum_net_exposure": 0.8, "minimum_cash": 0.2}), None, DEMO_INGESTED_AT),
            ("defined_risk_overlay", "0.1.0-demo", DEMO_INGESTED_AT, "A strong directional view may be expressed with a capped premium budget after exposure and premium budgets are decided.", "Make convexity, maximum loss, liquidity, and decay visible before considering implementation.", "Initial synthetic specification; live execution disabled.", _json({"defined_risk_only": True, "live_execution": False}), None, None),
        ],
        or_ignore=True,
    )
    diagnostic_rows = []
    for strategy_key in ("state_conditioned_exposure", "defined_risk_overlay"):
        for order, (metric_key, label, unit, description) in enumerate(
            [
                ("decay_rate", "Signal decay rate", "fraction_per_period", "Not measured; a point-in-time research run is required."),
                ("information_coefficient", "Information coefficient", "correlation", "Not measured; no historical forecast panel exists."),
                ("sharpe", "Sharpe ratio", "ratio", "Not measured; no audited backtest exists."),
            ],
            1,
        ):
            diagnostic_rows.append((strategy_key, "0.1.0-demo", metric_key, label, None, unit, "unavailable", None, None, description, order))
    _insert_many(
        connection,
        "strategy_diagnostics",
        ("strategy_key", "version", "metric_key", "label", "value", "unit", "status", "window_label", "as_of", "description", "sort_order"),
        diagnostic_rows,
        or_ignore=True,
    )
    _insert_many(
        connection,
        "strategy_lifecycle_events",
        ("event_id", "strategy_key", "occurred_at", "from_status", "to_status", "reason", "strategy_version"),
        [
            ("demo-state-added", "state_conditioned_exposure", DEMO_INGESTED_AT, None, "active", "Added as a synthetic architecture fixture; effectiveness remains untested.", "0.1.0-demo"),
            ("demo-overlay-added", "defined_risk_overlay", DEMO_INGESTED_AT, None, "watching", "Added for simulation and data-contract development; no live promotion is permitted.", "0.1.0-demo"),
        ],
        or_ignore=True,
    )


def seed_demo(database_path: str | Path | None = None) -> tuple[Path, bool]:
    """Insert one immutable synthetic snapshot.

    This function is intentionally never called by application startup. Operators must
    run this module explicitly when they want the demo fixture.
    """

    path = initialize_database(database_path)
    with connect(path) as connection:
        existing = connection.execute(
            "SELECT 1 FROM desk_snapshots WHERE id = ?", (DEMO_SNAPSHOT_ID,)
        ).fetchone()
        if existing:
            _ensure_demo_operational_catalog(connection)
            return path, False

        connection.execute(
            """
            INSERT INTO dataset_snapshots (
                id, as_of, created_at, mode, data_classification, is_live, is_demo,
                status, immutable, source_manifest_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                DEMO_DATASET_ID,
                DEMO_AS_OF,
                DEMO_INGESTED_AT,
                "demo",
                "synthetic",
                0,
                1,
                "demo_not_live",
                0,
                _json({"sources": ["synthetic_market_fixture"], "live_sources": 0}),
            ),
        )

        security_specs = [
            ("us-etf-spy", "SPY", "SPDR S&P 500 ETF Trust", "ETF", "ARCA", "USD", "Broad market", 1),
            ("us-etf-qqq", "QQQ", "Invesco QQQ Trust", "ETF", "NASDAQ", "USD", "Technology / growth", 1),
            ("us-etf-iwm", "IWM", "iShares Russell 2000 ETF", "ETF", "ARCA", "USD", "Small cap", 1),
            ("us-etf-xlf", "XLF", "Financial Select Sector SPDR Fund", "ETF", "ARCA", "USD", "Financials", 1),
            ("us-etf-tlt", "TLT", "iShares 20+ Year Treasury Bond ETF", "ETF", "NASDAQ", "USD", "Treasury duration", 1),
            ("us-etf-gld", "GLD", "SPDR Gold Shares", "ETF", "ARCA", "USD", "Precious metals", 1),
        ]
        _insert_many(
            connection,
            "securities",
            ("security_id", "primary_symbol", "name", "asset_type", "exchange", "currency", "sector", "active"),
            security_specs,
            or_ignore=True,
        )
        _insert_many(
            connection,
            "security_aliases",
            ("security_id", "provider", "alias", "valid_from", "valid_to"),
            [(security_id, "demo", symbol, "2026-08-21", None) for security_id, symbol, *_ in security_specs],
            or_ignore=True,
        )

        connection.execute(
            """
            INSERT INTO desk_snapshots (
                id, dataset_snapshot_id, as_of, created_at, mode, data_classification,
                is_live, is_demo, status,
                immutable, seed_revision, title, subtitle, disclaimer, regime_label,
                regime_confidence, regime_summary, recommendation_posture,
                recommendation_summary, recommendation_confidence,
                current_net_exposure, current_gross_exposure,
                target_net_exposure, target_gross_exposure,
                delta_net_exposure, delta_gross_exposure, change_summary,
                next_review_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                DEMO_SNAPSHOT_ID,
                DEMO_DATASET_ID,
                DEMO_AS_OF,
                DEMO_INGESTED_AT,
                "demo",
                "synthetic",
                0,
                1,
                "demo_not_live",
                0,
                "backend-demo-v3",
                "Hierarchical desk decision snapshot",
                "A synthetic, inspectable example of state-to-instrument allocation",
                "DEMO / SYNTHETIC / NOT LIVE. Values are fixtures, not market data, investment advice, or executable orders.",
                "Disinflation with uncertain growth (demo hypothesis)",
                0.62,
                "Synthetic growth evidence is mixed while inflation pressure is easing; the hierarchy therefore keeps risk below its full budget.",
                "Measured risk-on below full allocation",
                "Retain selective equity exposure, reduce undifferentiated beta, and reserve convex structures for review after live option data exists.",
                0.58,
                0.61,
                0.75,
                0.55,
                0.72,
                -0.06,
                -0.03,
                "Illustrative target lowers net exposure by six percentage points and reallocates a small risk budget toward defined-risk structures.",
                "2026-08-28T20:00:00Z",
            ),
        )

        _insert_many(
            connection,
            "philosophy_sections",
            ("snapshot_id", "section_key", "title", "body", "principle", "sort_order"),
            [
                (DEMO_SNAPSHOT_ID, "state_before_signal", "State before signal", "Signals are interpreted inside a market-state hypothesis rather than voted together without context.", "A factor is evidence, not a command.", 1),
                (DEMO_SNAPSHOT_ID, "allocation_before_instrument", "Allocation before instrument", "The system decides risk budget, strategy family, and exposure before choosing a stock, ETF, or option structure.", "Instrument selection implements a decision; it does not create the thesis.", 2),
                (DEMO_SNAPSHOT_ID, "falsification", "Falsification over persuasion", "Every recommendation carries conditions that would invalidate it and a scheduled review time.", "A decision that cannot be falsified cannot be governed.", 3),
                (DEMO_SNAPSHOT_ID, "uncertainty", "Uncertainty remains visible", "Missing measurements remain null, blocked positions remain blocked, and confidence constrains exposure.", "Unknown is a first-class state, not a zero.", 4),
            ],
        )

        regime_filters = [
            ("breadth", "Synthetic equity breadth", 0.51, 0.55, "caution", "The fixture sits below the illustrative threshold required for full beta.", "2026-08-21T20:00:00Z"),
            ("trend", "Synthetic medium-term trend", 0.14, 0.0, "pass", "The fixture remains above its neutral trend threshold.", "2026-08-21T20:00:00Z"),
            ("volatility", "Synthetic volatility index", 18.7, 22.0, "pass", "The fixture is below the defensive-volatility threshold.", "2026-08-21T20:00:00Z"),
            ("liquidity", "Synthetic liquidity impulse", -0.15, 0.0, "caution", "The fixture is negative and limits the permitted gross exposure.", "2026-08-21T20:00:00Z"),
        ]
        _insert_many(
            connection,
            "regime_filters",
            ("snapshot_id", "filter_key", "name", "value_json", "threshold_json", "status", "explanation", "observed_at", "available_at", "ingested_at", "source_key", "sort_order"),
            [
                (DEMO_SNAPSHOT_ID, key, name, _json(value), _json(threshold), status, explanation, observed, observed, DEMO_INGESTED_AT, "synthetic_macro_fixture", order)
                for order, (key, name, value, threshold, status, explanation, observed) in enumerate(regime_filters, 1)
            ],
        )

        _insert_many(
            connection,
            "regime_weights",
            ("snapshot_id", "weight_key", "name", "value", "unit", "sort_order"),
            [
                (DEMO_SNAPSHOT_ID, "macro", "Macro state", 0.30, "fraction", 1),
                (DEMO_SNAPSHOT_ID, "cross_section", "Cross-sectional evidence", 0.25, "fraction", 2),
                (DEMO_SNAPSHOT_ID, "trend", "Trend persistence", 0.20, "fraction", 3),
                (DEMO_SNAPSHOT_ID, "portfolio_risk", "Portfolio risk", 0.15, "fraction", 4),
                (DEMO_SNAPSHOT_ID, "implementation", "Implementation quality", 0.10, "fraction", 5),
            ],
        )

        _insert_many(
            connection,
            "regime_contributions",
            ("snapshot_id", "contribution_key", "name", "value", "unit", "direction", "explanation", "sort_order"),
            [
                (DEMO_SNAPSHOT_ID, "growth", "Growth", -0.18, "score", "negative", "Mixed synthetic activity evidence reduces the state score.", 1),
                (DEMO_SNAPSHOT_ID, "inflation", "Inflation", 0.12, "score", "positive", "The synthetic disinflation input supports duration and valuation-sensitive exposure.", 2),
                (DEMO_SNAPSHOT_ID, "liquidity", "Liquidity", -0.08, "score", "negative", "A negative synthetic liquidity impulse caps gross risk.", 3),
                (DEMO_SNAPSHOT_ID, "trend", "Trend", 0.06, "score", "positive", "Positive synthetic trend keeps the portfolio from moving fully defensive.", 4),
            ],
        )

        _insert_many(
            connection,
            "regime_evidence",
            ("snapshot_id", "contribution_key", "evidence_key", "label", "value_json", "detail", "observed_at", "available_at", "ingested_at", "sort_order"),
            [
                (DEMO_SNAPSHOT_ID, "growth", "activity_diffusion", "Synthetic activity diffusion", _json(48.2), "Below the neutral fixture level of 50.", DEMO_AS_OF, DEMO_AS_OF, DEMO_INGESTED_AT, 1),
                (DEMO_SNAPSHOT_ID, "inflation", "inflation_impulse", "Synthetic inflation impulse", _json(-0.24), "Negative values indicate easing pressure in this fixture.", DEMO_AS_OF, DEMO_AS_OF, DEMO_INGESTED_AT, 1),
                (DEMO_SNAPSHOT_ID, "liquidity", "liquidity_z", "Synthetic liquidity z-score", _json(-0.15), "A small negative fixture value.", DEMO_AS_OF, DEMO_AS_OF, DEMO_INGESTED_AT, 1),
                (DEMO_SNAPSHOT_ID, "trend", "trend_score", "Synthetic trend score", _json(0.14), "Positive but not strong enough to remove the breadth constraint.", DEMO_AS_OF, DEMO_AS_OF, DEMO_INGESTED_AT, 1),
            ],
        )

        _insert_many(
            connection,
            "recommendation_points",
            ("snapshot_id", "point_type", "text", "sort_order"),
            [
                (DEMO_SNAPSHOT_ID, "rationale", "Positive synthetic trend argues against a fully defensive allocation.", 1),
                (DEMO_SNAPSHOT_ID, "rationale", "Weak synthetic breadth and liquidity argue against using the full risk budget.", 2),
                (DEMO_SNAPSHOT_ID, "rationale", "Defined-risk option structures may advance through synthetic simulation while remaining ineligible for live execution.", 3),
                (DEMO_SNAPSHOT_ID, "invalidation", "Move to defensive review if the trend fixture falls below zero while breadth remains below 0.55.", 1),
                (DEMO_SNAPSHOT_ID, "invalidation", "Reconsider the duration tilt if the inflation impulse becomes positive and persistent.", 2),
                (DEMO_SNAPSHOT_ID, "invalidation", "Do not treat a synthetic option structure as live-actionable until real quotes, volatility, open interest, spread, and contract metadata pass validation.", 3),
            ],
        )

        nodes = [
            ("desk", None, "desk", "Desk allocation", "constrained", "Top-level allocation is below its full synthetic risk budget.", 0.58, 0.61, 0.55, -0.06, "net_exposure", 1.0, ["demo_only", "no_live_orders"], 0.0, 0.0),
            ("state", "desk", "state", "Market state", "mixed", "Disinflation is offset by uncertain growth and negative synthetic liquidity.", 0.62, None, None, None, None, 0.32, ["reassess_on_new_macro_vintage"], 1.0, -1.0),
            ("risk_budget", "desk", "risk_budget", "Risk budget", "capped", "Gross and net exposure are constrained by confidence and liquidity.", 0.58, 0.75, 0.72, -0.03, "gross_exposure", 0.24, ["target_volatility_0.10", "minimum_cash_0.20"], -1.0, -1.0),
            ("equity_family", "risk_budget", "strategy_family", "Selective equity beta", "active", "Keep equity risk but reduce broad undifferentiated beta.", 0.61, 0.59, 0.55, -0.04, "portfolio_weight", 0.46, ["sector_cap_0.25", "single_etf_cap_0.30"], -1.5, -2.0),
            ("convex_family", "risk_budget", "strategy_family", "Convex overlays", "simulation_only", "Synthetic defined-risk structures may be simulated; live expressions require validated option data.", 0.50, 0.0, 0.016, 0.016, "premium_budget", 0.08, ["defined_risk_only", "synthetic_simulation_allowed", "live_chain_required_for_execution"], 0.0, -2.0),
            ("defensive_family", "risk_budget", "strategy_family", "Defensive diversifiers", "active", "Maintain a modest duration and gold allocation.", 0.57, 0.12, 0.14, 0.02, "portfolio_weight", 0.18, ["combined_cap_0.20"], 1.5, -2.0),
            ("large_cap", "equity_family", "exposure", "U.S. large-cap beta", "reduce", "Lower the largest broad-beta concentration.", 0.64, 0.34, 0.28, -0.06, "portfolio_weight", 0.29, ["minimum_weight_0.20"], -2.2, -3.0),
            ("quality_growth", "equity_family", "exposure", "Quality growth tilt", "hold", "Retain a smaller quality-growth tilt.", 0.60, 0.12, 0.13, 0.01, "portfolio_weight", 0.12, ["maximum_weight_0.15"], -1.5, -3.0),
            ("small_cap", "equity_family", "exposure", "U.S. small-cap beta", "conditional_add", "Valuation support is offset by weaker quality and liquidity evidence.", 0.52, 0.06, 0.07, 0.01, "portfolio_weight", 0.05, ["implementation_must_be_defined_risk"], -0.8, -3.0),
            ("duration", "defensive_family", "exposure", "Long-duration Treasuries", "conditional_add", "Synthetic disinflation supports a modest duration increase.", 0.59, 0.08, 0.10, 0.02, "portfolio_weight", 0.10, ["inflation_invalidation"], 0.8, -3.0),
            ("gold", "defensive_family", "exposure", "Gold diversifier", "hold", "Retain the diversifier without increasing it on missing quality evidence.", 0.49, 0.04, 0.04, 0.0, "portfolio_weight", 0.08, ["maximum_weight_0.06"], 1.6, -3.0),
            ("financials", "equity_family", "exposure", "Financials tilt", "hold", "No strong synthetic edge justifies a change.", 0.47, 0.07, 0.07, 0.0, "portfolio_weight", 0.04, ["maximum_weight_0.10"], -2.9, -3.0),
            ("spy", "large_cap", "instrument", "SPY rebalance", "review_only", "Illustrative ETF weight reduction, not an order.", 0.64, 0.34, 0.28, -0.06, "portfolio_weight", 0.29, ["live_quote_required", "human_approval_required"], -2.2, -4.0),
            ("qqq", "quality_growth", "instrument", "QQQ hold", "review_only", "Illustrative quality-growth holding.", 0.60, 0.12, 0.13, 0.01, "portfolio_weight", 0.12, ["live_quote_required"], -1.5, -4.0),
            ("iwm_spread", "small_cap", "instrument", "IWM call spread hypothesis", "blocked", "Cannot be priced or selected without a live option chain.", 0.45, 0.0, 0.008, 0.008, "premium_budget", 0.03, ["live_chain_required", "iv_required", "liquidity_required"], -0.8, -4.0),
            ("tlt_spread", "duration", "instrument", "TLT call spread simulation", "simulation_ready", "A fully specified synthetic spread closes the simulation loop; live execution remains outside this snapshot.", 0.56, 0.0, 0.008, 0.008, "premium_budget", 0.03, ["synthetic_only", "live_execution_disabled"], 0.8, -4.0),
            ("gld", "gold", "instrument", "GLD hold", "review_only", "Illustrative diversifier holding.", 0.49, 0.04, 0.04, 0.0, "portfolio_weight", 0.08, ["live_quote_required"], 1.6, -4.0),
            ("xlf", "financials", "instrument", "XLF hold", "review_only", "Illustrative financials holding.", 0.47, 0.07, 0.07, 0.0, "portfolio_weight", 0.04, ["live_quote_required"], -2.9, -4.0),
        ]
        _insert_many(
            connection,
            "decision_nodes",
            ("snapshot_id", "node_id", "parent_node_id", "node_type", "label", "status", "summary", "confidence", "current_value", "target_value", "delta_value", "value_unit", "contribution", "constraints_json", "x", "y", "sort_order"),
            [
                (DEMO_SNAPSHOT_ID, node_id, parent_id, node_type, label, status, summary, confidence, current, target, delta, unit, contribution, _json(constraints), x, y, order)
                for order, (node_id, parent_id, node_type, label, status, summary, confidence, current, target, delta, unit, contribution, constraints, x, y) in enumerate(nodes, 1)
            ],
        )

        edge_specs = [
            ("desk_state", "desk", "state", "conditioned_by", 0.32, "The state hypothesis determines which evidence receives weight."),
            ("desk_risk", "desk", "risk_budget", "bounded_by", 0.24, "Confidence and portfolio constraints cap the aggregate allocation."),
            ("risk_equity", "risk_budget", "equity_family", "allocates_to", 0.46, "Most active risk remains selective equity beta."),
            ("risk_convex", "risk_budget", "convex_family", "reserves_for", 0.08, "A small premium budget is reserved but not actionable."),
            ("risk_defensive", "risk_budget", "defensive_family", "allocates_to", 0.18, "Diversifiers absorb part of the risk budget."),
            ("equity_large", "equity_family", "large_cap", "expresses_as", 0.29, "Broad large-cap exposure remains the largest sleeve."),
            ("equity_quality", "equity_family", "quality_growth", "expresses_as", 0.12, "Quality growth is retained as a smaller tilt."),
            ("equity_small", "equity_family", "small_cap", "expresses_as", 0.05, "Small-cap exposure is conditional and size-limited."),
            ("equity_financials", "equity_family", "financials", "expresses_as", 0.04, "Financials remain neutral in the fixture."),
            ("defensive_duration", "defensive_family", "duration", "expresses_as", 0.10, "Disinflation evidence supports duration."),
            ("defensive_gold", "defensive_family", "gold", "expresses_as", 0.08, "Gold remains a diversifier."),
            ("large_spy", "large_cap", "spy", "implemented_by", 1.0, "SPY is the illustrative implementation vehicle."),
            ("quality_qqq", "quality_growth", "qqq", "implemented_by", 1.0, "QQQ is the illustrative quality-growth vehicle."),
            ("small_iwm", "small_cap", "iwm_spread", "candidate_instrument", 1.0, "The call spread is blocked pending live chain validation."),
            ("duration_tlt", "duration", "tlt_spread", "candidate_instrument", 1.0, "The synthetic call spread is complete enough for simulation, not live execution."),
            ("convex_iwm", "convex_family", "iwm_spread", "funds_defined_risk_overlay", 0.5, "The premium-budget branch funds the blocked small-cap overlay hypothesis."),
            ("convex_tlt", "convex_family", "tlt_spread", "funds_defined_risk_overlay", 0.5, "The premium-budget branch funds the simulation-ready duration overlay."),
            ("gold_gld", "gold", "gld", "implemented_by", 1.0, "GLD is the illustrative diversifier vehicle."),
            ("financials_xlf", "financials", "xlf", "implemented_by", 1.0, "XLF is the illustrative sector vehicle."),
        ]
        _insert_many(
            connection,
            "decision_edges",
            ("snapshot_id", "edge_id", "from_node_id", "to_node_id", "relation", "weight", "rationale", "sort_order"),
            [(DEMO_SNAPSHOT_ID, *edge, order) for order, edge in enumerate(edge_specs, 1)],
        )

        observations = [
            ("obs_breadth", "state", "Synthetic breadth", 0.51, "fraction", "caution", "Below the illustrative full-risk threshold."),
            ("obs_inflation", "state", "Synthetic inflation impulse", -0.24, "z_score", "supportive", "Easing pressure supports the duration hypothesis."),
            ("obs_liquidity", "risk_budget", "Synthetic liquidity impulse", -0.15, "z_score", "caution", "Negative input constrains gross exposure."),
            ("obs_vol", "risk_budget", "Synthetic volatility", 18.7, "index", "pass", "Below the illustrative defensive threshold."),
            ("obs_option_chain", "convex_family", "Live option chain", None, None, "unavailable", "No live chain is connected; live execution remains blocked even where a synthetic simulation fixture exists."),
            ("obs_tlt_simulation_chain", "tlt_spread", "Synthetic option-chain fixture", "complete", None, "simulation", "Two synthetic option legs and their payoff inputs are complete enough for simulation."),
        ]
        _insert_many(
            connection,
            "decision_observations",
            ("snapshot_id", "observation_id", "node_id", "label", "value_json", "unit", "status", "detail", "source_key", "source_record_id", "observed_at", "available_at", "ingested_at", "sort_order"),
            [
                (DEMO_SNAPSHOT_ID, observation_id, node_id, label, _json(value), unit, status, detail, "synthetic_desk_fixture", observation_id, DEMO_AS_OF if value is not None else None, DEMO_AS_OF if value is not None else None, DEMO_INGESTED_AT, order)
                for order, (observation_id, node_id, label, value, unit, status, detail) in enumerate(observations, 1)
            ],
        )

        metrics = [
            ("current_net_exposure", "Current net exposure", 0.61, "fraction", "demo", "Synthetic current portfolio exposure."),
            ("target_net_exposure", "Target net exposure", 0.55, "fraction", "demo", "Illustrative target from the hierarchy."),
            ("target_gross_exposure", "Target gross exposure", 0.72, "fraction", "demo", "Illustrative gross cap."),
            ("cash_buffer", "Cash buffer", 0.25, "fraction", "demo", "Synthetic unallocated and cash weight."),
            ("portfolio_volatility_target", "Volatility target", 0.10, "annualized_fraction", "demo", "Governance constraint, not a measured forecast."),
            ("live_feeds_connected", "Live feeds connected", 0, "count", "blocked", "A true zero: this demo has no live providers."),
            ("live_actionable_candidates", "Live-actionable candidates", 0, "count", "blocked", "A true zero: this demo cannot authorize live execution."),
            ("simulation_ready_candidates", "Simulation-ready candidates", 1, "count", "simulation", "One fully specified synthetic structure closes the simulation loop."),
        ]
        _insert_many(
            connection,
            "desk_metrics",
            ("snapshot_id", "metric_key", "label", "value_json", "unit", "status", "description", "sort_order"),
            [(DEMO_SNAPSHOT_ID, key, label, _json(value), unit, status, description, order) for order, (key, label, value, unit, status, description) in enumerate(metrics, 1)],
        )

        connection.execute(
            """
            INSERT INTO backtests (
                snapshot_id, label, status, is_available, summary, methodology,
                period_start, period_end, information_cutoff_policy
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                DEMO_SNAPSHOT_ID,
                "Point-in-time strategy evaluation",
                "not_run",
                0,
                "No point-in-time backtest has been run for this synthetic snapshot; performance fields are intentionally null.",
                "Reserved for walk-forward evaluation with vintage-aware macro data, costs, and frozen decision rules.",
                None,
                None,
                "Every feature must be available no later than the simulated decision timestamp.",
            ),
        )
        _insert_many(
            connection,
            "backtest_metrics",
            ("snapshot_id", "metric_key", "label", "value_json", "unit", "status", "description", "sort_order"),
            [
                (DEMO_SNAPSHOT_ID, "cagr", "CAGR", _json(None), "annualized_fraction", "unavailable", "Not calculated.", 1),
                (DEMO_SNAPSHOT_ID, "sharpe", "Sharpe ratio", _json(None), None, "unavailable", "Not calculated.", 2),
                (DEMO_SNAPSHOT_ID, "max_drawdown", "Maximum drawdown", _json(None), "fraction", "unavailable", "Not calculated.", 3),
                (DEMO_SNAPSHOT_ID, "turnover", "Turnover", _json(None), "annualized_fraction", "unavailable", "Not calculated.", 4),
            ],
        )

        symbol_specs = [
            ("SPY", "SPDR S&P 500 ETF Trust", "ETF", "Broad market", "ARCA", "review_reduce", "Illustrative broad U.S. equity beta.", 642.10, 0.61, 2),
            ("QQQ", "Invesco QQQ Trust", "ETF", "Technology / growth", "NASDAQ", "review_hold", "Illustrative quality-growth tilt.", 587.40, 0.62, 1),
            ("IWM", "iShares Russell 2000 ETF", "ETF", "Small cap", "ARCA", "blocked_candidate", "Illustrative small-cap exposure with a blocked defined-risk candidate.", 241.30, 0.54, 3),
            ("XLF", "Financial Select Sector SPDR Fund", "ETF", "Financials", "ARCA", "review_hold", "Illustrative neutral financials sleeve.", 55.20, 0.53, 4),
            ("TLT", "iShares 20+ Year Treasury Bond ETF", "ETF", "Treasury duration", "NASDAQ", "simulation_candidate", "Illustrative duration exposure with a fully specified synthetic call-spread simulation.", 98.70, 0.52, 5),
            ("GLD", "SPDR Gold Shares", "ETF", "Precious metals", "ARCA", "review_hold", "Illustrative portfolio diversifier.", 314.60, 0.51, 6),
        ]
        security_by_symbol = {symbol: security_id for security_id, symbol, *_ in security_specs}
        _insert_many(
            connection,
            "symbols",
            ("snapshot_id", "security_id", "symbol", "name", "asset_type", "sector", "exchange", "currency", "status", "summary", "last_price", "price_as_of", "composite_score", "rank", "freshness_status", "freshness_as_of", "freshness_summary"),
            [
                (DEMO_SNAPSHOT_ID, security_by_symbol[symbol], symbol, name, asset_type, sector, exchange, "USD", status, summary, price, DEMO_AS_OF, score, rank, "synthetic_fixture", DEMO_AS_OF, "Synthetic closing fixture; no live quote is connected.")
                for symbol, name, asset_type, sector, exchange, status, summary, price, score, rank in symbol_specs
            ],
        )

        _insert_many(
            connection,
            "symbol_signals",
            (
                "snapshot_id", "symbol", "status", "direction", "strength",
                "label", "rationale", "source_node_id", "observed_at",
                "available_at", "ingested_at",
            ),
            [
                (DEMO_SNAPSHOT_ID, "SPY", "watch", "bearish", 0.42, "Synthetic de-risking watch", "The synthetic hierarchy proposes less broad beta, but this signal is only a review state and is not an order.", "spy", DEMO_AS_OF, DEMO_AS_OF, DEMO_INGESTED_AT),
                (DEMO_SNAPSHOT_ID, "QQQ", "none", None, None, "No current signal", "The synthetic fixture records no independent entry or exit signal.", "qqq", DEMO_AS_OF, DEMO_AS_OF, DEMO_INGESTED_AT),
                (DEMO_SNAPSHOT_ID, "IWM", "none", None, None, "No current signal", "The option hypothesis is blocked; no entry signal has been published.", "iwm_spread", DEMO_AS_OF, DEMO_AS_OF, DEMO_INGESTED_AT),
                (DEMO_SNAPSHOT_ID, "XLF", "none", None, None, "No current signal", "The synthetic factor evidence supports no change.", "xlf", DEMO_AS_OF, DEMO_AS_OF, DEMO_INGESTED_AT),
                (DEMO_SNAPSHOT_ID, "TLT", "candidate", "bullish", 0.56, "Synthetic duration candidate", "This is a simulation-only signal state backed by synthetic inputs; it is not an instruction, order, or fill.", "tlt_spread", DEMO_AS_OF, DEMO_AS_OF, DEMO_INGESTED_AT),
                (DEMO_SNAPSHOT_ID, "GLD", "none", None, None, "No current signal", "The synthetic diversifier allocation remains unchanged.", "gld", DEMO_AS_OF, DEMO_AS_OF, DEMO_INGESTED_AT),
            ],
        )

        hierarchy_specs = {
            "SPY": [("desk", "Desk allocation", "desk"), ("state", "Market state", "state"), ("risk_budget", "Risk budget", "risk_budget"), ("allocation_family", "Selective equity beta", "equity_family"), ("exposure", "U.S. large-cap beta", "large_cap"), ("instrument", "SPY rebalance", "spy")],
            "QQQ": [("desk", "Desk allocation", "desk"), ("state", "Market state", "state"), ("risk_budget", "Risk budget", "risk_budget"), ("allocation_family", "Selective equity beta", "equity_family"), ("exposure", "Quality growth tilt", "quality_growth"), ("instrument", "QQQ hold", "qqq")],
            "IWM": [("desk", "Desk allocation", "desk"), ("state", "Market state", "state"), ("risk_budget", "Risk budget", "risk_budget"), ("allocation_family", "Selective equity beta", "equity_family"), ("exposure", "U.S. small-cap beta", "small_cap"), ("funding_family", "Convex overlay premium budget", "convex_family"), ("instrument", "IWM call spread hypothesis", "iwm_spread")],
            "XLF": [("desk", "Desk allocation", "desk"), ("state", "Market state", "state"), ("risk_budget", "Risk budget", "risk_budget"), ("allocation_family", "Selective equity beta", "equity_family"), ("exposure", "Financials tilt", "financials"), ("instrument", "XLF hold", "xlf")],
            "TLT": [("desk", "Desk allocation", "desk"), ("state", "Market state", "state"), ("risk_budget", "Risk budget", "risk_budget"), ("allocation_family", "Defensive diversifiers", "defensive_family"), ("exposure", "Long-duration Treasuries", "duration"), ("funding_family", "Convex overlay premium budget", "convex_family"), ("instrument", "TLT call spread simulation", "tlt_spread")],
            "GLD": [("desk", "Desk allocation", "desk"), ("state", "Market state", "state"), ("risk_budget", "Risk budget", "risk_budget"), ("allocation_family", "Defensive diversifiers", "defensive_family"), ("exposure", "Gold diversifier", "gold"), ("instrument", "GLD hold", "gld")],
        }
        node_lookup = {node[0]: node for node in nodes}
        hierarchy_rows = []
        for symbol, steps in hierarchy_specs.items():
            for order, (level, label, node_id) in enumerate(steps, 1):
                node = node_lookup[node_id]
                hierarchy_rows.append((DEMO_SNAPSHOT_ID, symbol, order, level, label, node_id, node[7], node[8], node[9], node[10], node[11], _json(node[12])))
        _insert_many(
            connection,
            "symbol_hierarchy",
            ("snapshot_id", "symbol", "step_order", "level", "label", "node_id", "current_value", "target_value", "delta_value", "value_unit", "contribution", "constraints_json"),
            hierarchy_rows,
        )

        recommendations = [
            ("SPY", "reduce", "Review a six-point reduction in broad beta; this is not an order.", 0.64, 0.34, 0.28, -0.06, "review_only"),
            ("QQQ", "hold", "Retain the illustrative quality-growth tilt pending live validation.", 0.60, 0.12, 0.13, 0.01, "review_only"),
            ("IWM", "conditional_add", "Consider only a defined-risk structure after the option data blockers resolve.", 0.45, 0.06, 0.07, 0.01, "blocked"),
            ("XLF", "hold", "No change is supported by the synthetic evidence.", 0.47, 0.07, 0.07, 0.0, "review_only"),
            ("TLT", "conditional_add", "Simulate a modest defined-risk duration expression; live execution remains disabled.", 0.56, 0.08, 0.10, 0.02, "simulation_ready"),
            ("GLD", "hold", "Retain the illustrative diversifier allocation.", 0.49, 0.04, 0.04, 0.0, "review_only"),
        ]
        _insert_many(
            connection,
            "symbol_recommendations",
            ("snapshot_id", "symbol", "posture", "summary", "confidence", "current_weight", "target_weight", "delta_weight", "next_review_at", "actionability"),
            [(DEMO_SNAPSHOT_ID, symbol, posture, summary, confidence, current, target, delta, "2026-08-28T20:00:00Z", actionability) for symbol, posture, summary, confidence, current, target, delta, actionability in recommendations],
        )
        recommendation_point_rows = []
        for symbol, _, _, _, _, _, delta, actionability in recommendations:
            recommendation_point_rows.extend(
                [
                    (DEMO_SNAPSHOT_ID, symbol, "rationale", f"The hierarchy assigns a synthetic target-weight change of {delta:+.3f}.", 1),
                    (DEMO_SNAPSHOT_ID, symbol, "invalidation", "Re-evaluate when state, risk-budget, or freshness constraints change.", 1),
                ]
            )
            if actionability == "blocked":
                recommendation_point_rows.append((DEMO_SNAPSHOT_ID, symbol, "invalidation", "No implementation is permitted while required market data is unavailable.", 2))
        _insert_many(
            connection,
            "symbol_recommendation_points",
            ("snapshot_id", "symbol", "point_type", "text", "sort_order"),
            recommendation_point_rows,
        )

        base_prices = {symbol: price for symbol, _, _, _, _, _, _, price, _, _ in symbol_specs}
        bar_rows = []
        bar_times = [
            "2026-08-12T20:00:00Z", "2026-08-13T20:00:00Z", "2026-08-14T20:00:00Z",
            "2026-08-17T20:00:00Z", "2026-08-18T20:00:00Z", "2026-08-19T20:00:00Z",
            "2026-08-20T20:00:00Z", "2026-08-21T20:00:00Z",
        ]
        moves = [-0.018, -0.011, -0.014, -0.006, -0.009, -0.004, -0.002, 0.0]
        for symbol_index, (symbol, price) in enumerate(base_prices.items(), 1):
            for time, move in zip(bar_times, moves, strict=True):
                close = round(price * (1 + move + symbol_index * 0.0004), 2)
                open_price = round(close * 0.997, 2)
                high = round(close * 1.006, 2)
                low = round(open_price * 0.994, 2)
                volume = float(9_000_000 + symbol_index * 1_250_000)
                bar_rows.append((DEMO_DATASET_ID, security_by_symbol[symbol], time, open_price, high, low, close, volume, "synthetic_market_fixture", time, time, DEMO_INGESTED_AT))
        _insert_many(
            connection,
            "symbol_bars",
            ("dataset_snapshot_id", "security_id", "time", "open", "high", "low", "close", "volume", "source_key", "observed_at", "available_at", "ingested_at"),
            bar_rows,
        )

        event_rows = [
            ("SPY", "spy_state_review", "2026-08-19T18:00:00Z", "state_review", "annotation", "Synthetic state review", None, "Fixture event; not a real market release."),
            ("SPY", "spy_higher_high", "2026-08-18T20:00:00Z", "pattern_higher_high", "annotation", "Synthetic higher-high annotation", 638.25, "Derived from the short synthetic chart fixture; it is a chart annotation, not a trade."),
            ("QQQ", "qqq_rank_change", "2026-08-20T20:00:00Z", "rank_change", "annotation", "Synthetic cross-sectional rank update", 584.20, "Fixture price marker."),
            ("IWM", "iwm_blocker", "2026-08-21T20:00:00Z", "candidate_blocked", "proposed", "Option-chain blocker recorded", None, "No live option chain was available."),
            ("XLF", "xlf_review", "2026-08-21T20:00:00Z", "weight_review", "annotation", "No-change review", 55.20, "Synthetic target remained unchanged."),
            ("TLT", "tlt_simulation", "2026-08-21T20:00:00Z", "simulation_candidate", "proposed", "Synthetic call-spread simulation recorded", 98.70, "Fixture structure is complete for simulation only; it is not a market order."),
            ("TLT", "tlt_signal_candidate", "2026-08-20T20:00:00Z", "signal_entry", "signal_state", "Synthetic signal entered candidate state", 98.10, "Signal-state annotation only; no order was submitted and no fill occurred."),
            ("GLD", "gld_review", "2026-08-21T20:00:00Z", "weight_review", "annotation", "Diversifier review", 314.60, "Synthetic target remained unchanged."),
        ]
        _insert_many(
            connection,
            "symbol_events",
            ("dataset_snapshot_id", "security_id", "event_id", "time", "event_type", "event_status", "label", "price", "detail", "source_key", "observed_at", "available_at", "ingested_at"),
            [(DEMO_DATASET_ID, security_by_symbol[symbol], event_id, time, event_type, event_status, label, price, detail, "synthetic_desk_fixture", time, time, DEMO_INGESTED_AT) for symbol, event_id, time, event_type, event_status, label, price, detail in event_rows],
        )

        symbol_metric_rows = []
        metric_values = {
            "SPY": (0.14, 0.51), "QQQ": (0.21, 0.57), "IWM": (0.07, 0.49),
            "XLF": (0.05, 0.47), "TLT": (-0.03, 0.41), "GLD": (0.09, 0.46),
        }
        for symbol, (trend_score, risk_score) in metric_values.items():
            symbol_metric_rows.extend(
                [
                    (DEMO_SNAPSHOT_ID, symbol, "trend_score", "Synthetic trend score", _json(trend_score), "score", "demo", "Fixture value; not live.", 1),
                    (DEMO_SNAPSHOT_ID, symbol, "risk_score", "Synthetic risk score", _json(risk_score), "score", "demo", "Fixture value; not live.", 2),
                    (DEMO_SNAPSHOT_ID, symbol, "live_bid_ask_spread", "Live bid/ask spread", _json(None), "fraction", "unavailable", "No live quote source is connected.", 3),
                ]
            )
        _insert_many(
            connection,
            "symbol_metrics",
            ("snapshot_id", "symbol", "metric_key", "label", "value_json", "unit", "status", "description", "sort_order"),
            symbol_metric_rows,
        )

        candidates = [
            ("spy-rebalance", "SPY", "SPY weight rebalance", "reduce", "etf_weight", 0.28, 0.34, -0.06, "portfolio_weight", 0.64, None, None, None, None, None, None, None, "1-4 weeks", "review_only", "review_only", 0, "live_market_data", "synthetic_desk_fixture", DEMO_AS_OF, DEMO_AS_OF, DEMO_INGESTED_AT),
            ("iwm-call-spread", "IWM", "IWM defined-risk call spread", "long", "call_spread", 0.008, 0.0, 0.008, "premium_budget", 0.45, None, None, None, None, None, None, None, "3-6 months", "blocked_missing_market_data", "blocked", 0, "live_market_data", "synthetic_desk_fixture", DEMO_AS_OF, DEMO_AS_OF, DEMO_INGESTED_AT),
            ("tlt-call-spread", "TLT", "TLT synthetic defined-risk call spread", "long", "call_spread", 0.008, 0.0, 0.008, "premium_budget", 0.56, 285.0, 715.0, 102.85, None, 285.0, 6.0, "USD", "3-6 months", "synthetic_simulation_ready", "simulation_ready", 1, "synthetic_simulation_inputs", "synthetic_options_fixture", DEMO_AS_OF, DEMO_AS_OF, DEMO_INGESTED_AT),
        ]
        _insert_many(
            connection,
            "position_candidates",
            ("snapshot_id", "candidate_id", "symbol", "name", "side", "structure_type", "target_weight", "current_weight", "delta_weight", "allocation_basis", "confidence", "max_loss", "max_profit", "breakeven_low", "breakeven_high", "net_debit_credit", "cost_estimate", "cost_unit", "horizon", "status", "actionability", "market_data_complete", "input_completeness_scope", "source_key", "observed_at", "available_at", "ingested_at", "sort_order"),
            [(DEMO_SNAPSHOT_ID, *candidate, order) for order, candidate in enumerate(candidates, 1)],
        )

        _insert_many(
            connection,
            "position_legs",
            ("snapshot_id", "candidate_id", "leg_order", "action", "quantity", "instrument_type", "symbol", "expiry", "strike", "option_type", "bid", "ask", "mid", "multiplier", "dte", "open_interest", "volume", "implied_volatility", "delta", "gamma", "theta", "vega"),
            [
                (DEMO_SNAPSHOT_ID, "spy-rebalance", 1, "sell", 1, "ETF", "SPY", *([None] * 15)),
                (DEMO_SNAPSHOT_ID, "iwm-call-spread", 1, "buy", 1, "option", "IWM", None, None, "call", *([None] * 12)),
                (DEMO_SNAPSHOT_ID, "iwm-call-spread", 2, "sell", 1, "option", "IWM", None, None, "call", *([None] * 12)),
                (DEMO_SNAPSHOT_ID, "tlt-call-spread", 1, "buy", 1, "option", "TLT", "2026-12-18", 100.0, "call", 5.60, 5.80, 5.70, 100.0, 119, 12500.0, 4200.0, 0.22, 0.54, 0.035, -0.028, 0.102),
                (DEMO_SNAPSHOT_ID, "tlt-call-spread", 2, "sell", 1, "option", "TLT", "2026-12-18", 110.0, "call", 2.75, 2.95, 2.85, 100.0, 119, 9800.0, 2600.0, 0.21, 0.31, 0.028, -0.021, 0.089),
            ],
        )

        _insert_many(
            connection,
            "position_points",
            ("snapshot_id", "candidate_id", "point_type", "text", "sort_order"),
            [
                (DEMO_SNAPSHOT_ID, "spy-rebalance", "rationale", "The broad-beta sleeve exceeds its illustrative hierarchy target.", 1),
                (DEMO_SNAPSHOT_ID, "spy-rebalance", "risk", "A reduction can underperform if breadth and liquidity improve quickly.", 1),
                (DEMO_SNAPSHOT_ID, "iwm-call-spread", "rationale", "A defined-risk structure would cap premium-at-risk if small-cap breadth improves.", 1),
                (DEMO_SNAPSHOT_ID, "iwm-call-spread", "risk", "No expiry, strikes, debit, or Greeks can be selected from synthetic data.", 1),
                (DEMO_SNAPSHOT_ID, "tlt-call-spread", "rationale", "A fully specified synthetic vertical closes the state-to-payoff simulation loop with capped premium-at-risk.", 1),
                (DEMO_SNAPSHOT_ID, "tlt-call-spread", "risk", "Every contract, quote, Greek, and payoff value is synthetic; the structure is ineligible for live execution.", 1),
            ],
        )

        blocker_rows = [
            ("spy-rebalance", "live_quote", "Live ETF quote", "Required to estimate executable price and cost.", 1, 0),
            ("spy-rebalance", "approval", "Human approval", "The engine is decision support and cannot authorize an order.", 1, 0),
            ("iwm-call-spread", "option_chain", "Live option chain", "Required to select an expiry and strikes.", 1, 0),
            ("iwm-call-spread", "option_quotes", "Bid/ask quotes", "Required to estimate debit and maximum loss.", 1, 0),
            ("iwm-call-spread", "iv_greeks", "Implied volatility and Greeks", "Required to compare structures and exposures.", 1, 0),
            ("iwm-call-spread", "liquidity", "Open interest and spread checks", "Required to reject illiquid contracts.", 1, 0),
        ]
        _insert_many(
            connection,
            "position_blockers",
            ("snapshot_id", "candidate_id", "blocker_key", "label", "detail", "required", "resolved", "sort_order"),
            [(DEMO_SNAPSHOT_ID, candidate_id, blocker_key, label, detail, required, resolved, order) for order, (candidate_id, blocker_key, label, detail, required, resolved) in enumerate(blocker_rows, 1)],
        )
        _insert_many(
            connection,
            "position_greeks",
            ("snapshot_id", "candidate_id", "greek_key", "value", "unit"),
            [
                *[
                    (DEMO_SNAPSHOT_ID, "iwm-call-spread", greek, None, unit)
                    for greek, unit in (("delta", "per_contract"), ("gamma", "per_contract"), ("theta", "currency_per_day"), ("vega", "currency_per_vol_point"))
                ],
                (DEMO_SNAPSHOT_ID, "tlt-call-spread", "delta", 23.0, "delta_equivalent_shares"),
                (DEMO_SNAPSHOT_ID, "tlt-call-spread", "gamma", 0.7, "shares_per_dollar"),
                (DEMO_SNAPSHOT_ID, "tlt-call-spread", "theta", -0.70, "USD_per_day"),
                (DEMO_SNAPSHOT_ID, "tlt-call-spread", "vega", 1.30, "USD_per_vol_point"),
            ],
        )

        sources = [
            ("synthetic_desk_fixture", "Synthetic desk fixture", "decision", "demo_fixture_loaded", 0, "Regime, hierarchy, and recommendations", None, "fixture:desk:v1", DEMO_AS_OF, DEMO_AS_OF, 300.0, "Locally seeded synthetic content; never live."),
            ("synthetic_macro_fixture", "Synthetic macro fixture", "macro", "demo_fixture_loaded", 0, "Illustrative macro observations", None, "fixture:macro:v1", DEMO_AS_OF, DEMO_AS_OF, 300.0, "Locally seeded synthetic content; never live."),
            ("synthetic_market_fixture", "Synthetic market fixture", "market", "demo_fixture_loaded", 0, "Illustrative daily bars and factor values", None, "fixture:market:v1", DEMO_AS_OF, DEMO_AS_OF, 300.0, "Locally seeded synthetic content; never live."),
            ("synthetic_options_fixture", "Synthetic options fixture", "options", "simulation_fixture_loaded", 0, "One complete illustrative TLT vertical", None, "fixture:options:v1", DEMO_AS_OF, DEMO_AS_OF, 300.0, "Synthetic contract, quote, liquidity, Greek, and payoff values for simulation only."),
            ("fred_live", "FRED / ALFRED", "macro", "not_connected", 0, "No live coverage", "https://fred.stlouisfed.org/docs/api/fred/", None, None, None, None, "No credentials or ingestion job are configured."),
            ("bls_live", "U.S. Bureau of Labor Statistics", "macro_release", "not_connected", 0, "No live coverage", "https://www.bls.gov/developers/", None, None, None, None, "No API ingestion job is configured."),
            ("market_live", "Live market data provider", "market", "not_connected", 0, "No live coverage", None, None, None, None, None, "No quote or bar provider is configured."),
            ("options_live", "Live options data provider", "options", "not_connected", 0, "No live coverage", None, None, None, None, None, "No option chain, quote, volatility, or Greeks provider is configured."),
        ]
        _insert_many(
            connection,
            "data_sources",
            ("snapshot_id", "source_key", "name", "category", "status", "is_live", "coverage", "source_url", "source_record_id", "observed_at", "available_at", "ingested_at", "latency_seconds", "detail", "sort_order"),
            [
                (DEMO_SNAPSHOT_ID, key, name, category, status, is_live, coverage, url, record_id, observed_at, available_at, DEMO_INGESTED_AT, latency, detail, order)
                for order, (key, name, category, status, is_live, coverage, url, record_id, observed_at, available_at, latency, detail) in enumerate(sources, 1)
            ],
        )
        _insert_many(
            connection,
            "symbol_data_sources",
            ("snapshot_id", "symbol", "source_key"),
            [
                (DEMO_SNAPSHOT_ID, symbol, source_key)
                for symbol in base_prices
                for source_key in ("synthetic_market_fixture", "market_live", "options_live")
            ] + [(DEMO_SNAPSHOT_ID, "TLT", "synthetic_options_fixture")],
        )

        dimensions = [
            ("momentum", "Momentum", "score_0_to_1", "Synthetic medium-term trend strength.", 0.20),
            ("valuation", "Valuation", "score_0_to_1", "Synthetic relative valuation support.", 0.18),
            ("quality", "Quality", "score_0_to_1", "Synthetic balance-sheet and profitability support.", 0.18),
            ("macro_fit", "Macro fit", "score_0_to_1", "Compatibility with the current synthetic state hypothesis.", 0.20),
            ("liquidity", "Liquidity", "score_0_to_1", "Synthetic implementation-liquidity quality.", 0.14),
            ("downside", "Downside asymmetry", "score_0_to_1", "Synthetic downside-risk profile.", 0.10),
        ]
        _insert_many(
            connection,
            "factor_dimensions",
            ("snapshot_id", "factor_key", "label", "unit", "description", "weight", "sort_order"),
            [(DEMO_SNAPSHOT_ID, key, label, unit, description, weight, order) for order, (key, label, unit, description, weight) in enumerate(dimensions, 1)],
        )

        cross_values = {
            "SPY": (0.61, 2, "eligible", "Balanced fixture scores; broad-beta concentration drives the reduce review.", [0.56, 0.45, 0.68, 0.58, 0.95, 0.52]),
            "QQQ": (0.62, 1, "eligible", "Highest synthetic composite, limited by concentration constraints.", [0.72, 0.30, 0.74, 0.55, 0.91, 0.43]),
            "IWM": (0.54, 3, "conditional", "Valuation support is offset by quality and liquidity.", [0.48, 0.70, 0.42, 0.61, 0.66, 0.46]),
            "XLF": (0.53, 4, "neutral", "No synthetic dimension is strong enough to justify a change.", [0.44, 0.63, 0.51, 0.49, 0.79, 0.50]),
            "TLT": (0.52, 5, "incomplete", "Macro fit and downside scores exist; valuation and quality are not applicable in this fixture.", [0.37, None, None, 0.67, 0.87, 0.72]),
            "GLD": (0.51, 6, "incomplete", "Diversifier evidence exists; valuation and quality are unavailable in this fixture.", [0.53, None, None, 0.62, 0.83, 0.65]),
        }
        _insert_many(
            connection,
            "cross_section_rows",
            ("snapshot_id", "symbol", "composite_score", "rank", "status", "summary"),
            [(DEMO_SNAPSHOT_ID, symbol, composite, rank, status, summary) for symbol, (composite, rank, status, summary, _) in cross_values.items()],
        )
        factor_value_rows = []
        factor_keys = [item[0] for item in dimensions]
        for symbol, (_, _, _, _, values) in cross_values.items():
            for factor_key, value in zip(factor_keys, values, strict=True):
                factor_value_rows.append(
                    (
                        DEMO_SNAPSHOT_ID,
                        symbol,
                        factor_key,
                        value,
                        "available" if value is not None else "unavailable",
                        "synthetic_market_fixture" if value is not None else None,
                        f"fixture:{symbol}:{factor_key}" if value is not None else None,
                        DEMO_AS_OF if value is not None else None,
                        DEMO_AS_OF if value is not None else None,
                        DEMO_INGESTED_AT,
                    )
                )
        _insert_many(
            connection,
            "factor_values",
            ("snapshot_id", "symbol", "factor_key", "value", "quality_status", "source_key", "source_record_id", "observed_at", "available_at", "ingested_at"),
            factor_value_rows,
        )
        _insert_many(
            connection,
            "cross_section_legend",
            ("snapshot_id", "legend_key", "label", "description", "sort_order"),
            [
                (DEMO_SNAPSHOT_ID, "higher", "Higher score", "More supportive synthetic evidence within that dimension.", 1),
                (DEMO_SNAPSHOT_ID, "lower", "Lower score", "Less supportive synthetic evidence within that dimension.", 2),
                (DEMO_SNAPSHOT_ID, "unavailable", "Unavailable", "The JSON value is null; it is neither neutral nor zero.", 3),
            ],
        )

        _ensure_demo_operational_catalog(connection)

        # Publish only after the complete decision and dataset graphs exist. Once these
        # flags change, SQLite guards reject every child INSERT, UPDATE, and DELETE.
        connection.execute(
            "UPDATE dataset_snapshots SET immutable = 1 WHERE id = ?",
            (DEMO_DATASET_ID,),
        )
        connection.execute(
            "UPDATE desk_snapshots SET immutable = 1 WHERE id = ?",
            (DEMO_SNAPSHOT_ID,),
        )

    return path, True


def main() -> None:
    parser = argparse.ArgumentParser(description="Explicitly seed the immutable synthetic HEAE demo snapshot.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DATABASE_PATH, help="SQLite database path")
    args = parser.parse_args()
    path, created = seed_demo(resolve_database_path(args.db))
    result = "created" if created else "already present"
    print(f"Synthetic demo snapshot {result} in {path}")


if __name__ == "__main__":
    main()
