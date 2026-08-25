PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

INSERT INTO schema_metadata (key, value) VALUES ('schema_version', '16')
ON CONFLICT(key) DO UPDATE SET value = excluded.value;

INSERT OR IGNORE INTO schema_metadata (key, value) VALUES
    ('seed_policy', 'explicit_opt_in_only');

CREATE TABLE IF NOT EXISTS dataset_snapshots (
    id TEXT PRIMARY KEY,
    as_of TEXT NOT NULL,
    created_at TEXT NOT NULL,
    mode TEXT NOT NULL CHECK (mode IN ('demo', 'research', 'simulation', 'paper', 'live')),
    data_classification TEXT NOT NULL CHECK (data_classification IN ('synthetic', 'derived', 'real', 'mixed')),
    is_live INTEGER NOT NULL CHECK (is_live IN (0, 1)),
    is_demo INTEGER NOT NULL CHECK (is_demo IN (0, 1)),
    status TEXT NOT NULL,
    immutable INTEGER NOT NULL CHECK (immutable IN (0, 1)),
    source_manifest_json TEXT NOT NULL DEFAULT '{}',
    engine_mode TEXT CHECK (engine_mode IS NULL OR engine_mode IN ('pilot', 'production'))
);

CREATE TRIGGER IF NOT EXISTS dataset_snapshots_are_immutable_update
BEFORE UPDATE ON dataset_snapshots
WHEN OLD.immutable = 1
BEGIN
    SELECT RAISE(ABORT, 'immutable dataset snapshot cannot be updated');
END;

CREATE TRIGGER IF NOT EXISTS dataset_snapshots_are_immutable_delete
BEFORE DELETE ON dataset_snapshots
WHEN OLD.immutable = 1
BEGIN
    SELECT RAISE(ABORT, 'immutable dataset snapshot cannot be deleted');
END;

CREATE TABLE IF NOT EXISTS securities (
    security_id TEXT PRIMARY KEY,
    primary_symbol TEXT NOT NULL,
    name TEXT NOT NULL,
    asset_type TEXT NOT NULL,
    exchange TEXT,
    currency TEXT NOT NULL,
    sector TEXT,
    active INTEGER NOT NULL CHECK (active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS security_aliases (
    security_id TEXT NOT NULL REFERENCES securities(security_id),
    provider TEXT NOT NULL,
    alias TEXT NOT NULL,
    valid_from TEXT,
    valid_to TEXT,
    PRIMARY KEY (security_id, provider, alias, valid_from)
);

CREATE TABLE IF NOT EXISTS desk_snapshots (
    id TEXT PRIMARY KEY,
    dataset_snapshot_id TEXT REFERENCES dataset_snapshots(id),
    as_of TEXT NOT NULL,
    created_at TEXT NOT NULL,
    mode TEXT NOT NULL CHECK (mode IN ('demo', 'research', 'simulation', 'paper', 'live')),
    data_classification TEXT NOT NULL CHECK (data_classification IN ('synthetic', 'derived', 'real', 'mixed')),
    is_live INTEGER NOT NULL CHECK (is_live IN (0, 1)),
    is_demo INTEGER NOT NULL CHECK (is_demo IN (0, 1)),
    status TEXT NOT NULL,
    immutable INTEGER NOT NULL CHECK (immutable IN (0, 1)),
    seed_revision TEXT NOT NULL,
    title TEXT NOT NULL,
    subtitle TEXT NOT NULL,
    disclaimer TEXT NOT NULL,
    regime_label TEXT NOT NULL,
    regime_confidence REAL,
    regime_summary TEXT NOT NULL,
    recommendation_posture TEXT NOT NULL,
    recommendation_summary TEXT NOT NULL,
    recommendation_confidence REAL,
    current_net_exposure REAL,
    current_gross_exposure REAL,
    target_net_exposure REAL,
    target_gross_exposure REAL,
    delta_net_exposure REAL,
    delta_gross_exposure REAL,
    change_summary TEXT NOT NULL,
    next_review_at TEXT,
    engine_mode TEXT CHECK (engine_mode IS NULL OR engine_mode IN ('pilot', 'production'))
);

CREATE TRIGGER IF NOT EXISTS desk_snapshots_are_immutable_update
BEFORE UPDATE ON desk_snapshots
WHEN OLD.immutable = 1
BEGIN
    SELECT RAISE(ABORT, 'immutable desk snapshot cannot be updated');
END;

CREATE TRIGGER IF NOT EXISTS desk_snapshots_are_immutable_delete
BEFORE DELETE ON desk_snapshots
WHEN OLD.immutable = 1
BEGIN
    SELECT RAISE(ABORT, 'immutable desk snapshot cannot be deleted');
END;

DROP TRIGGER IF EXISTS desk_snapshot_publish_requires_sealed_dataset_insert;
CREATE TRIGGER desk_snapshot_publish_requires_sealed_dataset_insert
BEFORE INSERT ON desk_snapshots
WHEN NEW.immutable = 1
 AND NOT EXISTS (
     SELECT 1 FROM dataset_snapshots AS dataset
     WHERE dataset.id = NEW.dataset_snapshot_id
       AND dataset.immutable = 1
       AND dataset.data_classification = NEW.data_classification
       AND dataset.is_live = NEW.is_live
       AND dataset.is_demo = NEW.is_demo
 )
BEGIN
    SELECT RAISE(ABORT, 'published desk snapshot requires matching sealed dataset provenance');
END;

DROP TRIGGER IF EXISTS desk_snapshot_publish_requires_sealed_dataset_update;
CREATE TRIGGER desk_snapshot_publish_requires_sealed_dataset_update
BEFORE UPDATE ON desk_snapshots
WHEN NEW.immutable = 1
 AND NOT EXISTS (
     SELECT 1 FROM dataset_snapshots AS dataset
     WHERE dataset.id = NEW.dataset_snapshot_id
       AND dataset.immutable = 1
       AND dataset.data_classification = NEW.data_classification
       AND dataset.is_live = NEW.is_live
       AND dataset.is_demo = NEW.is_demo
 )
BEGIN
    SELECT RAISE(ABORT, 'published desk snapshot requires matching sealed dataset provenance');
END;

CREATE TABLE IF NOT EXISTS philosophy_sections (
    snapshot_id TEXT NOT NULL REFERENCES desk_snapshots(id),
    section_key TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    principle TEXT NOT NULL,
    sort_order INTEGER NOT NULL,
    PRIMARY KEY (snapshot_id, section_key)
);

CREATE TABLE IF NOT EXISTS regime_filters (
    snapshot_id TEXT NOT NULL REFERENCES desk_snapshots(id),
    filter_key TEXT NOT NULL,
    name TEXT NOT NULL,
    value_json TEXT,
    threshold_json TEXT,
    status TEXT NOT NULL,
    explanation TEXT NOT NULL,
    observed_at TEXT,
    available_at TEXT,
    ingested_at TEXT NOT NULL,
    source_key TEXT,
    sort_order INTEGER NOT NULL,
    PRIMARY KEY (snapshot_id, filter_key)
);

CREATE TABLE IF NOT EXISTS regime_weights (
    snapshot_id TEXT NOT NULL REFERENCES desk_snapshots(id),
    weight_key TEXT NOT NULL,
    name TEXT NOT NULL,
    value REAL,
    unit TEXT,
    sort_order INTEGER NOT NULL,
    PRIMARY KEY (snapshot_id, weight_key)
);

CREATE TABLE IF NOT EXISTS regime_contributions (
    snapshot_id TEXT NOT NULL REFERENCES desk_snapshots(id),
    contribution_key TEXT NOT NULL,
    name TEXT NOT NULL,
    value REAL,
    unit TEXT,
    direction TEXT NOT NULL,
    explanation TEXT NOT NULL,
    sort_order INTEGER NOT NULL,
    PRIMARY KEY (snapshot_id, contribution_key)
);

CREATE TABLE IF NOT EXISTS regime_evidence (
    snapshot_id TEXT NOT NULL,
    contribution_key TEXT NOT NULL,
    evidence_key TEXT NOT NULL,
    label TEXT NOT NULL,
    value_json TEXT,
    detail TEXT,
    observed_at TEXT,
    available_at TEXT,
    ingested_at TEXT NOT NULL,
    sort_order INTEGER NOT NULL,
    PRIMARY KEY (snapshot_id, contribution_key, evidence_key),
    FOREIGN KEY (snapshot_id, contribution_key)
        REFERENCES regime_contributions(snapshot_id, contribution_key)
);

CREATE TABLE IF NOT EXISTS recommendation_points (
    snapshot_id TEXT NOT NULL REFERENCES desk_snapshots(id),
    point_type TEXT NOT NULL CHECK (point_type IN ('rationale', 'invalidation')),
    text TEXT NOT NULL,
    sort_order INTEGER NOT NULL,
    PRIMARY KEY (snapshot_id, point_type, sort_order)
);

CREATE TABLE IF NOT EXISTS decision_nodes (
    snapshot_id TEXT NOT NULL REFERENCES desk_snapshots(id),
    node_id TEXT NOT NULL,
    parent_node_id TEXT,
    node_type TEXT NOT NULL,
    label TEXT NOT NULL,
    status TEXT NOT NULL,
    summary TEXT NOT NULL,
    confidence REAL,
    current_value REAL,
    target_value REAL,
    delta_value REAL,
    value_unit TEXT,
    contribution REAL,
    constraints_json TEXT NOT NULL DEFAULT '[]',
    x REAL,
    y REAL,
    sort_order INTEGER NOT NULL,
    PRIMARY KEY (snapshot_id, node_id),
    FOREIGN KEY (snapshot_id, parent_node_id)
        REFERENCES decision_nodes(snapshot_id, node_id)
);

CREATE TABLE IF NOT EXISTS decision_edges (
    snapshot_id TEXT NOT NULL REFERENCES desk_snapshots(id),
    edge_id TEXT NOT NULL,
    from_node_id TEXT NOT NULL,
    to_node_id TEXT NOT NULL,
    relation TEXT NOT NULL,
    weight REAL,
    rationale TEXT NOT NULL,
    sort_order INTEGER NOT NULL,
    PRIMARY KEY (snapshot_id, edge_id),
    FOREIGN KEY (snapshot_id, from_node_id)
        REFERENCES decision_nodes(snapshot_id, node_id),
    FOREIGN KEY (snapshot_id, to_node_id)
        REFERENCES decision_nodes(snapshot_id, node_id)
);

CREATE TABLE IF NOT EXISTS decision_observations (
    snapshot_id TEXT NOT NULL,
    observation_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    label TEXT NOT NULL,
    value_json TEXT,
    unit TEXT,
    status TEXT NOT NULL,
    detail TEXT NOT NULL,
    source_key TEXT,
    source_record_id TEXT,
    observed_at TEXT,
    available_at TEXT,
    ingested_at TEXT NOT NULL,
    sort_order INTEGER NOT NULL,
    PRIMARY KEY (snapshot_id, observation_id),
    FOREIGN KEY (snapshot_id, node_id)
        REFERENCES decision_nodes(snapshot_id, node_id)
);

CREATE TABLE IF NOT EXISTS desk_metrics (
    snapshot_id TEXT NOT NULL REFERENCES desk_snapshots(id),
    metric_key TEXT NOT NULL,
    label TEXT NOT NULL,
    value_json TEXT,
    unit TEXT,
    status TEXT,
    description TEXT,
    sort_order INTEGER NOT NULL,
    PRIMARY KEY (snapshot_id, metric_key)
);

CREATE TABLE IF NOT EXISTS backtests (
    snapshot_id TEXT PRIMARY KEY REFERENCES desk_snapshots(id),
    label TEXT NOT NULL,
    status TEXT NOT NULL,
    is_available INTEGER NOT NULL CHECK (is_available IN (0, 1)),
    summary TEXT NOT NULL,
    methodology TEXT NOT NULL,
    period_start TEXT,
    period_end TEXT,
    information_cutoff_policy TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS backtest_metrics (
    snapshot_id TEXT NOT NULL REFERENCES backtests(snapshot_id),
    metric_key TEXT NOT NULL,
    label TEXT NOT NULL,
    value_json TEXT,
    unit TEXT,
    status TEXT,
    description TEXT,
    sort_order INTEGER NOT NULL,
    PRIMARY KEY (snapshot_id, metric_key)
);

CREATE TABLE IF NOT EXISTS symbols (
    snapshot_id TEXT NOT NULL REFERENCES desk_snapshots(id),
    security_id TEXT NOT NULL REFERENCES securities(security_id),
    symbol TEXT NOT NULL,
    name TEXT NOT NULL,
    asset_type TEXT NOT NULL,
    sector TEXT,
    exchange TEXT,
    currency TEXT NOT NULL,
    status TEXT NOT NULL,
    summary TEXT NOT NULL,
    last_price REAL,
    price_as_of TEXT,
    composite_score REAL,
    rank INTEGER,
    freshness_status TEXT NOT NULL,
    freshness_as_of TEXT,
    freshness_summary TEXT NOT NULL,
    PRIMARY KEY (snapshot_id, symbol),
    UNIQUE (snapshot_id, security_id)
);

CREATE TABLE IF NOT EXISTS symbol_hierarchy (
    snapshot_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    step_order INTEGER NOT NULL,
    level TEXT NOT NULL,
    label TEXT NOT NULL,
    node_id TEXT,
    current_value REAL,
    target_value REAL,
    delta_value REAL,
    value_unit TEXT,
    contribution REAL,
    constraints_json TEXT NOT NULL DEFAULT '[]',
    PRIMARY KEY (snapshot_id, symbol, step_order),
    FOREIGN KEY (snapshot_id, symbol) REFERENCES symbols(snapshot_id, symbol),
    FOREIGN KEY (snapshot_id, node_id) REFERENCES decision_nodes(snapshot_id, node_id)
);

CREATE TABLE IF NOT EXISTS symbol_recommendations (
    snapshot_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    posture TEXT NOT NULL,
    summary TEXT NOT NULL,
    confidence REAL,
    current_weight REAL,
    target_weight REAL,
    delta_weight REAL,
    next_review_at TEXT,
    actionability TEXT NOT NULL,
    PRIMARY KEY (snapshot_id, symbol),
    FOREIGN KEY (snapshot_id, symbol) REFERENCES symbols(snapshot_id, symbol)
);

CREATE TABLE IF NOT EXISTS symbol_recommendation_points (
    snapshot_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    point_type TEXT NOT NULL CHECK (point_type IN ('rationale', 'invalidation')),
    text TEXT NOT NULL,
    sort_order INTEGER NOT NULL,
    PRIMARY KEY (snapshot_id, symbol, point_type, sort_order),
    FOREIGN KEY (snapshot_id, symbol)
        REFERENCES symbol_recommendations(snapshot_id, symbol)
);

CREATE TABLE IF NOT EXISTS symbol_bars (
    dataset_snapshot_id TEXT NOT NULL REFERENCES dataset_snapshots(id),
    security_id TEXT NOT NULL REFERENCES securities(security_id),
    time TEXT NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume REAL,
    source_key TEXT,
    observed_at TEXT,
    available_at TEXT,
    ingested_at TEXT NOT NULL,
    PRIMARY KEY (dataset_snapshot_id, security_id, time)
);

CREATE TABLE IF NOT EXISTS symbol_events (
    dataset_snapshot_id TEXT NOT NULL REFERENCES dataset_snapshots(id),
    security_id TEXT NOT NULL REFERENCES securities(security_id),
    event_id TEXT NOT NULL,
    time TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_status TEXT NOT NULL DEFAULT 'annotation' CHECK (
        event_status IN ('annotation', 'signal_state', 'proposed', 'executed', 'cancelled')
    ),
    label TEXT NOT NULL,
    price REAL,
    detail TEXT,
    source_key TEXT,
    observed_at TEXT,
    available_at TEXT,
    ingested_at TEXT NOT NULL,
    PRIMARY KEY (dataset_snapshot_id, security_id, event_id)
);

-- Raw fetched FRED series observations, point-in-time (ALFRED vintage) aware.
-- One row per series/date/vintage; regime scoring reads from here, it never
-- refetches from FRED at read time. Dataset-snapshot-scoped like symbol_bars,
-- so it seals and becomes append-only with its parent dataset snapshot.
CREATE TABLE IF NOT EXISTS fred_observations (
    dataset_snapshot_id TEXT NOT NULL REFERENCES dataset_snapshots(id),
    series_id TEXT NOT NULL,
    observation_date TEXT NOT NULL,
    value REAL,
    realtime_start TEXT NOT NULL,
    realtime_end TEXT NOT NULL,
    units TEXT,
    frequency TEXT,
    source_key TEXT NOT NULL DEFAULT 'fred',
    observed_at TEXT NOT NULL,
    available_at TEXT NOT NULL,
    ingested_at TEXT NOT NULL,
    PRIMARY KEY (dataset_snapshot_id, series_id, observation_date, realtime_start)
);

-- A signal is an engine observation, not an order or a fill. Published signals
-- belong to the immutable desk snapshot and may therefore be audited alongside
-- the allocation and instrument recommendation which consumed them.
CREATE TABLE IF NOT EXISTS symbol_signals (
    snapshot_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN ('none', 'watch', 'candidate', 'active', 'exited', 'invalidated')
    ),
    direction TEXT CHECK (direction IN ('bullish', 'bearish', 'neutral')),
    strength REAL CHECK (strength IS NULL OR (strength >= 0 AND strength <= 1)),
    label TEXT NOT NULL,
    rationale TEXT NOT NULL,
    source_node_id TEXT,
    observed_at TEXT,
    available_at TEXT,
    ingested_at TEXT NOT NULL,
    PRIMARY KEY (snapshot_id, symbol),
    FOREIGN KEY (snapshot_id, symbol) REFERENCES symbols(snapshot_id, symbol),
    FOREIGN KEY (snapshot_id, source_node_id)
        REFERENCES decision_nodes(snapshot_id, node_id)
);

CREATE TABLE IF NOT EXISTS symbol_metrics (
    snapshot_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    metric_key TEXT NOT NULL,
    label TEXT NOT NULL,
    value_json TEXT,
    unit TEXT,
    status TEXT,
    description TEXT,
    sort_order INTEGER NOT NULL,
    PRIMARY KEY (snapshot_id, symbol, metric_key),
    FOREIGN KEY (snapshot_id, symbol) REFERENCES symbols(snapshot_id, symbol)
);

CREATE TABLE IF NOT EXISTS position_candidates (
    snapshot_id TEXT NOT NULL REFERENCES desk_snapshots(id),
    candidate_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    name TEXT NOT NULL,
    side TEXT NOT NULL,
    structure_type TEXT NOT NULL,
    -- conviction_from_composite(composite_score), the -5..+5 scale that
    -- actually selected this structure_type/side -- persisted so it's
    -- visible, not just used internally and discarded.
    conviction REAL,
    target_weight REAL,
    current_weight REAL,
    delta_weight REAL,
    allocation_basis TEXT CHECK (
        allocation_basis IN ('portfolio_weight', 'premium_budget', 'notional_weight', 'risk_budget')
    ),
    confidence REAL,
    max_loss REAL,
    max_profit REAL,
    breakeven_low REAL,
    breakeven_high REAL,
    net_debit_credit REAL,
    cost_estimate REAL,
    cost_unit TEXT,
    horizon TEXT NOT NULL,
    status TEXT NOT NULL,
    actionability TEXT NOT NULL,
    market_data_complete INTEGER NOT NULL CHECK (market_data_complete IN (0, 1)),
    input_completeness_scope TEXT CHECK (
        input_completeness_scope IN ('live_market_data', 'synthetic_simulation_inputs', 'other')
    ),
    source_key TEXT,
    observed_at TEXT,
    available_at TEXT,
    ingested_at TEXT,
    sort_order INTEGER NOT NULL,
    PRIMARY KEY (snapshot_id, candidate_id),
    FOREIGN KEY (snapshot_id, symbol) REFERENCES symbols(snapshot_id, symbol)
);

CREATE TABLE IF NOT EXISTS position_legs (
    snapshot_id TEXT NOT NULL,
    candidate_id TEXT NOT NULL,
    leg_order INTEGER NOT NULL,
    action TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    instrument_type TEXT NOT NULL,
    symbol TEXT NOT NULL,
    expiry TEXT,
    strike REAL,
    option_type TEXT,
    bid REAL,
    ask REAL,
    mid REAL,
    multiplier REAL,
    dte INTEGER,
    open_interest REAL,
    volume REAL,
    implied_volatility REAL,
    delta REAL,
    gamma REAL,
    theta REAL,
    vega REAL,
    PRIMARY KEY (snapshot_id, candidate_id, leg_order),
    FOREIGN KEY (snapshot_id, candidate_id)
        REFERENCES position_candidates(snapshot_id, candidate_id)
);

CREATE TABLE IF NOT EXISTS position_points (
    snapshot_id TEXT NOT NULL,
    candidate_id TEXT NOT NULL,
    point_type TEXT NOT NULL CHECK (point_type IN ('rationale', 'risk')),
    text TEXT NOT NULL,
    sort_order INTEGER NOT NULL,
    PRIMARY KEY (snapshot_id, candidate_id, point_type, sort_order),
    FOREIGN KEY (snapshot_id, candidate_id)
        REFERENCES position_candidates(snapshot_id, candidate_id)
);

CREATE TABLE IF NOT EXISTS position_blockers (
    snapshot_id TEXT NOT NULL,
    candidate_id TEXT NOT NULL,
    blocker_key TEXT NOT NULL,
    label TEXT NOT NULL,
    detail TEXT NOT NULL,
    required INTEGER NOT NULL CHECK (required IN (0, 1)),
    resolved INTEGER NOT NULL CHECK (resolved IN (0, 1)),
    sort_order INTEGER NOT NULL,
    PRIMARY KEY (snapshot_id, candidate_id, blocker_key),
    FOREIGN KEY (snapshot_id, candidate_id)
        REFERENCES position_candidates(snapshot_id, candidate_id)
);

CREATE TABLE IF NOT EXISTS position_greeks (
    snapshot_id TEXT NOT NULL,
    candidate_id TEXT NOT NULL,
    greek_key TEXT NOT NULL,
    value REAL,
    unit TEXT,
    PRIMARY KEY (snapshot_id, candidate_id, greek_key),
    FOREIGN KEY (snapshot_id, candidate_id)
        REFERENCES position_candidates(snapshot_id, candidate_id)
);

CREATE TABLE IF NOT EXISTS data_sources (
    snapshot_id TEXT NOT NULL REFERENCES desk_snapshots(id),
    source_key TEXT NOT NULL,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    status TEXT NOT NULL,
    is_live INTEGER NOT NULL CHECK (is_live IN (0, 1)),
    coverage TEXT NOT NULL,
    source_url TEXT,
    source_record_id TEXT,
    observed_at TEXT,
    available_at TEXT,
    ingested_at TEXT NOT NULL,
    latency_seconds REAL,
    detail TEXT NOT NULL,
    sort_order INTEGER NOT NULL,
    PRIMARY KEY (snapshot_id, source_key)
);

CREATE TABLE IF NOT EXISTS symbol_data_sources (
    snapshot_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    source_key TEXT NOT NULL,
    PRIMARY KEY (snapshot_id, symbol, source_key),
    FOREIGN KEY (snapshot_id, symbol) REFERENCES symbols(snapshot_id, symbol),
    FOREIGN KEY (snapshot_id, source_key) REFERENCES data_sources(snapshot_id, source_key)
);

CREATE TABLE IF NOT EXISTS factor_dimensions (
    snapshot_id TEXT NOT NULL REFERENCES desk_snapshots(id),
    factor_key TEXT NOT NULL,
    label TEXT NOT NULL,
    unit TEXT,
    description TEXT NOT NULL,
    weight REAL,
    sort_order INTEGER NOT NULL,
    PRIMARY KEY (snapshot_id, factor_key)
);

CREATE TABLE IF NOT EXISTS cross_section_rows (
    snapshot_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    composite_score REAL,
    -- conviction_from_composite(composite_score): the same -5..+5 scale
    -- instrument_engine uses to pick a structure, computed for every ranked
    -- symbol here (not just the ones that clear the |1.0| equity threshold),
    -- so the desk-wide bullish/bearish picture is visible in one place.
    conviction REAL,
    rank INTEGER,
    status TEXT NOT NULL,
    summary TEXT NOT NULL,
    PRIMARY KEY (snapshot_id, symbol),
    FOREIGN KEY (snapshot_id, symbol) REFERENCES symbols(snapshot_id, symbol)
);

CREATE TABLE IF NOT EXISTS factor_values (
    snapshot_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    factor_key TEXT NOT NULL,
    value REAL,
    quality_status TEXT NOT NULL,
    source_key TEXT,
    source_record_id TEXT,
    observed_at TEXT,
    available_at TEXT,
    ingested_at TEXT NOT NULL,
    PRIMARY KEY (snapshot_id, symbol, factor_key),
    FOREIGN KEY (snapshot_id, symbol)
        REFERENCES cross_section_rows(snapshot_id, symbol),
    FOREIGN KEY (snapshot_id, factor_key)
        REFERENCES factor_dimensions(snapshot_id, factor_key)
);

CREATE TABLE IF NOT EXISTS cross_section_legend (
    snapshot_id TEXT NOT NULL REFERENCES desk_snapshots(id),
    legend_key TEXT NOT NULL,
    label TEXT NOT NULL,
    description TEXT NOT NULL,
    sort_order INTEGER NOT NULL,
    PRIMARY KEY (snapshot_id, legend_key)
);

-- Operator-console tables are intentionally outside immutable decision
-- snapshots. They describe the mutable operating environment and append-only
-- run/audit history. Credentials are never stored in SQLite; credential_name is
-- only the opaque account name used by the OS credential store.
CREATE TABLE IF NOT EXISTS operator_providers (
    provider_key TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    description TEXT NOT NULL,
    enabled INTEGER NOT NULL CHECK (enabled IN (0, 1)),
    required INTEGER NOT NULL CHECK (required IN (0, 1)),
    credential_label TEXT,
    credential_name TEXT,
    environment_variable TEXT,
    documentation_url TEXT,
    signup_url TEXT,
    terms_url TEXT,
    attribution_notice TEXT,
    instructions TEXT NOT NULL,
    capabilities_json TEXT NOT NULL DEFAULT '[]',
    verifier_kind TEXT,
    credential_revision INTEGER NOT NULL DEFAULT 0 CHECK (credential_revision >= 0),
    verification_cooldown_seconds INTEGER NOT NULL DEFAULT 900
        CHECK (verification_cooldown_seconds >= 0),
    verification_ttl_seconds INTEGER NOT NULL DEFAULT 31536000
        CHECK (
            verification_ttl_seconds > 0
            AND verification_ttl_seconds >= verification_cooldown_seconds
        ),
    tier TEXT NOT NULL DEFAULT 'paid' CHECK (tier IN ('free', 'paid')),
    sort_order INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Pilot mode is a real, gated engine-wide choice, not a cosmetic label: it
-- blocks any pipeline stage whose required providers include a 'paid' tier
-- provider (see run_pipeline), and every snapshot a run produces is stamped
-- with the mode active when it ran. Singleton row, `id` always 1.
CREATE TABLE IF NOT EXISTS engine_operating_mode (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    mode TEXT NOT NULL CHECK (mode IN ('pilot', 'production')),
    updated_at TEXT NOT NULL,
    updated_reason TEXT
);

INSERT OR IGNORE INTO engine_operating_mode (id, mode, updated_at, updated_reason)
VALUES (1, 'pilot', CURRENT_TIMESTAMP, 'Default for a fresh clone: free-data-only pilot mode.');

-- Staging position-sizing defaults. Kept here, not as a Python constant, so a
-- fresh clone and every running instance see the same inspectable, editable
-- number instead of one buried in source. instrument_engine reads this row;
-- see backend/engine/instruments/sizing.py for the sizing formula itself.
CREATE TABLE IF NOT EXISTS staging_budget_config (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    notional_budget REAL NOT NULL,
    risk_per_position_fraction REAL NOT NULL,
    rationale TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

INSERT OR IGNORE INTO staging_budget_config (id, notional_budget, risk_per_position_fraction, rationale, updated_at)
VALUES (
    1, 1000000.0, 0.02,
    'A disclosed, naive staging default, not a real account or a recommendation. This staging universe is 21 US-listed rotation symbols plus GLD and a BTC-USD reference, not a global long/short book (unlike, say, a 300+-symbol worldwide 13F); a flat $1M notional with a 2%-of-budget max risk per position is a simple, real, inspectable convention to turn percentages into concrete share/contract counts, nothing more.',
    CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS provider_verifications (
    verification_id TEXT PRIMARY KEY,
    provider_key TEXT NOT NULL REFERENCES operator_providers(provider_key),
    checked_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN (
            'healthy', 'not_configured', 'invalid_credentials', 'rate_limited',
            'unreachable', 'provider_error', 'invalid_response'
        )
    ),
    http_status INTEGER,
    latency_ms INTEGER,
    error_code TEXT,
    message TEXT NOT NULL,
    credential_revision INTEGER NOT NULL DEFAULT 0 CHECK (credential_revision >= 0),
    runtime_id TEXT,
    credential_source TEXT CHECK (
        credential_source IN ('keyring', 'environment')
    )
);

-- The provider roadmap is application configuration, not a credential store.
-- It keeps future data requirements visible without accepting secrets for an
-- adapter that does not exist yet.
CREATE TABLE IF NOT EXISTS data_capabilities (
    capability_key TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    description TEXT NOT NULL,
    requirement_level TEXT NOT NULL CHECK (
        requirement_level IN ('required_now', 'required_later', 'optional')
    ),
    unlocks_json TEXT NOT NULL DEFAULT '[]',
    sort_order INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS provider_onboarding_plan (
    plan_key TEXT PRIMARY KEY,
    operator_provider_key TEXT REFERENCES operator_providers(provider_key),
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    role TEXT NOT NULL,
    integration_status TEXT NOT NULL CHECK (
        integration_status IN ('planned', 'verification_ready', 'ingestion_ready')
    ),
    required_for_first_slice INTEGER NOT NULL CHECK (required_for_first_slice IN (0, 1)),
    documentation_url TEXT,
    signup_url TEXT,
    pricing_url TEXT,
    terms_url TEXT,
    guidance TEXT NOT NULL,
    licensing_note TEXT NOT NULL,
    sort_order INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS provider_plan_capabilities (
    plan_key TEXT NOT NULL REFERENCES provider_onboarding_plan(plan_key),
    capability_key TEXT NOT NULL REFERENCES data_capabilities(capability_key),
    coverage_role TEXT NOT NULL CHECK (coverage_role IN ('primary', 'supplemental')),
    coverage_note TEXT NOT NULL,
    PRIMARY KEY (plan_key, capability_key)
);

-- The pilot/staging symbol roster. Database-driven per this project's own
-- rule that universe eligibility must never be a hard-coded ticker list in
-- frontend or strategy code. Auto-installed on every schema init (like
-- operator_providers/provider_onboarding_plan below) so a fresh clone has a
-- real, free-data-tier starting universe with zero manual setup. This is a
-- flat starting roster, not yet the effective-dated, membership-revisioned
-- universe the roadmap's "versioned_security_universe" gate calls for —
-- that remains future work; this table is its free-tier seed data.
CREATE TABLE IF NOT EXISTS staging_symbols (
    symbol TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL CHECK (category IN (
        'macro_series', 'broad_equity_etf', 'sector_equity_etf',
        'bond_duration_etf', 'commodity_etf', 'crypto_reference',
        'mega_cap_equity', 'thematic_etf'
    )),
    tier TEXT NOT NULL DEFAULT 'free' CHECK (tier IN ('free', 'paid')),
    production_provider_key TEXT REFERENCES provider_onboarding_plan(plan_key),
    notes TEXT,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    sort_order INTEGER NOT NULL
);

-- Readiness definitions are application configuration. Their current state is
-- never stored here: the API derives it from provider verification, data,
-- immutable snapshots, pipeline runs, and research evidence on every read.
CREATE TABLE IF NOT EXISTS readiness_milestones (
    milestone_key TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    sort_order INTEGER NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS readiness_gates (
    gate_key TEXT PRIMARY KEY,
    milestone_key TEXT NOT NULL REFERENCES readiness_milestones(milestone_key),
    name TEXT NOT NULL,
    layer TEXT NOT NULL,
    description TEXT NOT NULL,
    acceptance_criterion TEXT NOT NULL,
    evaluator_key TEXT NOT NULL,
    next_action TEXT NOT NULL,
    target_route TEXT NOT NULL CHECK (
        target_route LIKE '/%' AND target_route NOT LIKE '//%'
    ),
    sort_order INTEGER NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS readiness_gate_dependencies (
    gate_key TEXT NOT NULL REFERENCES readiness_gates(gate_key),
    dependency_gate_key TEXT NOT NULL REFERENCES readiness_gates(gate_key),
    PRIMARY KEY (gate_key, dependency_gate_key),
    CHECK (gate_key != dependency_gate_key)
);

CREATE TABLE IF NOT EXISTS data_assets (
    asset_key TEXT PRIMARY KEY,
    provider_key TEXT REFERENCES operator_providers(provider_key),
    label TEXT NOT NULL,
    kind TEXT NOT NULL,
    symbol TEXT,
    frequency TEXT,
    classification TEXT NOT NULL CHECK (
        classification IN ('synthetic', 'derived', 'real', 'mixed')
    ),
    row_count INTEGER NOT NULL DEFAULT 0 CHECK (row_count >= 0),
    period_start TEXT,
    period_end TEXT,
    last_observation_at TEXT,
    last_fetched_at TEXT,
    max_age_seconds INTEGER CHECK (max_age_seconds IS NULL OR max_age_seconds >= 0),
    status TEXT NOT NULL CHECK (
        status IN ('ready', 'stale', 'missing', 'partial', 'not_applicable')
    ),
    dataset_snapshot_id TEXT REFERENCES dataset_snapshots(id),
    detail TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pipeline_definitions (
    pipeline_key TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    description TEXT NOT NULL,
    enabled INTEGER NOT NULL CHECK (enabled IN (0, 1)),
    manual_only INTEGER NOT NULL CHECK (manual_only IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pipeline_stage_definitions (
    pipeline_key TEXT NOT NULL REFERENCES pipeline_definitions(pipeline_key),
    stage_key TEXT NOT NULL,
    label TEXT NOT NULL,
    description TEXT NOT NULL,
    stage_order INTEGER NOT NULL,
    implementation_status TEXT NOT NULL CHECK (
        implementation_status IN ('ready', 'scaffolded', 'disabled')
    ),
    required_provider_keys_json TEXT NOT NULL DEFAULT '[]',
    PRIMARY KEY (pipeline_key, stage_key)
);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id TEXT PRIMARY KEY,
    pipeline_key TEXT NOT NULL REFERENCES pipeline_definitions(pipeline_key),
    pipeline_version TEXT NOT NULL,
    trigger_type TEXT NOT NULL CHECK (trigger_type IN ('manual', 'scheduled')),
    dry_run INTEGER NOT NULL CHECK (dry_run IN (0, 1)),
    requested_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    status TEXT NOT NULL CHECK (
        status IN ('queued', 'running', 'completed', 'partial', 'blocked', 'failed')
    ),
    dataset_snapshot_id TEXT REFERENCES dataset_snapshots(id),
    desk_snapshot_id TEXT REFERENCES desk_snapshots(id),
    summary TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pipeline_stage_runs (
    run_id TEXT NOT NULL REFERENCES pipeline_runs(run_id),
    stage_key TEXT NOT NULL,
    stage_order INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN (
            'pending', 'running', 'completed', 'completed_with_warnings',
            'skipped', 'blocked', 'not_implemented', 'failed'
        )
    ),
    started_at TEXT,
    finished_at TEXT,
    records_read INTEGER,
    records_written INTEGER,
    message TEXT NOT NULL,
    error_code TEXT,
    PRIMARY KEY (run_id, stage_key)
);

CREATE TABLE IF NOT EXISTS strategies (
    strategy_key TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    family TEXT NOT NULL,
    summary TEXT NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN ('draft', 'active', 'watching', 'retired')
    ),
    current_version TEXT,
    added_at TEXT,
    retired_at TEXT,
    retirement_reason TEXT,
    public_spec_url TEXT CHECK (
        public_spec_url IS NULL OR public_spec_url LIKE 'https://%'
    ),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS strategy_versions (
    strategy_key TEXT NOT NULL REFERENCES strategies(strategy_key),
    version TEXT NOT NULL,
    created_at TEXT NOT NULL,
    thesis TEXT NOT NULL,
    expected_edge TEXT NOT NULL,
    change_summary TEXT NOT NULL,
    parameters_json TEXT NOT NULL DEFAULT '{}',
    code_reference TEXT,
    promoted_at TEXT,
    next_review_at TEXT,
    -- Distinct from strategies.status (which is lifecycle: draft/active/
    -- watching/retired). This is a separate fact: has this specific version
    -- actually passed Milestone 4's statistical gate, and if not, why not.
    -- Never a kill switch -- a version stays 'active' in the live pipeline
    -- (strategies.status) no matter what this says. Deleting or disabling a
    -- naive-but-real function because it failed validation would break a
    -- working page in exchange for a correctness claim staging never made;
    -- the honest fix is always a label here, never removing the function.
    --   registered_only -- real function, not yet tested at all (default)
    --   verified        -- passed significance + decorrelation + decay
    --   not_significant -- tested; p-value indicates noise, not a real edge
    --   collinear       -- tested; redundant with another registered factor
    --   decayed         -- was verified; a later re-test shows it faded
    --   outdated        -- superseded by a newer approach, kept for reference
    verification_status TEXT NOT NULL DEFAULT 'registered_only' CHECK (
        verification_status IN (
            'registered_only', 'verified', 'not_significant',
            'collinear', 'decayed', 'outdated'
        )
    ),
    PRIMARY KEY (strategy_key, version)
);

CREATE TABLE IF NOT EXISTS strategy_diagnostics (
    strategy_key TEXT NOT NULL,
    version TEXT NOT NULL,
    metric_key TEXT NOT NULL,
    label TEXT NOT NULL,
    value REAL,
    unit TEXT,
    status TEXT NOT NULL,
    window_label TEXT,
    as_of TEXT,
    description TEXT NOT NULL,
    sort_order INTEGER NOT NULL,
    PRIMARY KEY (strategy_key, version, metric_key),
    FOREIGN KEY (strategy_key, version)
        REFERENCES strategy_versions(strategy_key, version)
);

CREATE TABLE IF NOT EXISTS strategy_lifecycle_events (
    event_id TEXT PRIMARY KEY,
    strategy_key TEXT NOT NULL REFERENCES strategies(strategy_key),
    occurred_at TEXT NOT NULL,
    from_status TEXT,
    to_status TEXT NOT NULL,
    reason TEXT NOT NULL,
    strategy_version TEXT
);

-- Sub-strategy granularity: a strategy_versions row (e.g.
-- macd_rsi_single_name_timing naive-v2) is itself an ensemble of named,
-- independently versioned, independently retireable components -- e.g.
-- MACD crossover and RSI overbought-exit are two separate components, not
-- one fused function. This is the missing layer identified 2026-08-25: the
-- top-level strategy stays a stable caller regardless of internal change;
-- retiring one component is a DB flag flip (status), never a code deploy or
-- a break in the pipeline. See docs/engine-milestones.md.
--
-- component_type distinguishes two real shapes:
--   'computed'        a real function over real fetched data (e.g. MACD
--                      crossover detection). value comes from the engine
--                      function each run; this row is metadata only
--                      (active/weight/verification), never a stored number.
--   'manual_override'  a human-set standing value with no data source (e.g.
--                      a geopolitical/war-risk override, normally neutral
--                      at 0, settable to an extreme like -100 to force the
--                      ensemble's hand on something no feed captures).
--                      override_value IS this component's current value
--                      until an operator changes it again; full audit trail
--                      required, same discretion as a credential write.
--
-- roles_json tags what an ensemble can use this component FOR, since not
-- every family combines components the same way: macro/momentum are a
-- null-tolerant WEIGHTED SUM of ['contribution']-tagged components; timing
-- is a role-tagged SIGNAL ENSEMBLE where ['entry','exit']-tagged components
-- are combined by a rule, not a weighted average -- see
-- engine/timing/backtest_v2.py's module docstring for why these need
-- different aggregation shapes, not one forced abstraction.
CREATE TABLE IF NOT EXISTS strategy_components (
    strategy_key TEXT NOT NULL,
    version TEXT NOT NULL,
    component_key TEXT NOT NULL,
    name TEXT NOT NULL,
    component_type TEXT NOT NULL CHECK (component_type IN ('computed', 'manual_override')),
    roles_json TEXT NOT NULL DEFAULT '["contribution"]',
    code_reference TEXT,
    base_weight REAL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (
        status IN ('draft', 'active', 'watching', 'retired')
    ),
    verification_status TEXT NOT NULL DEFAULT 'registered_only' CHECK (
        verification_status IN (
            'registered_only', 'verified', 'not_significant',
            'collinear', 'decayed', 'outdated'
        )
    ),
    decay_rate REAL,
    override_value REAL,
    override_set_by TEXT,
    override_set_at TEXT,
    override_reason TEXT,
    next_review_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (strategy_key, version, component_key),
    FOREIGN KEY (strategy_key, version) REFERENCES strategy_versions(strategy_key, version),
    CHECK (component_type != 'manual_override' OR code_reference IS NULL),
    CHECK (component_type = 'manual_override' OR override_value IS NULL)
);

-- Real engine algorithm registry. Every function in backend/engine/ that
-- makes a real, standalone decision-relevant claim gets a row here the same
-- day it ships, not as documentation prose — a maturity/verification/review
-- record anyone can query, matching the operator_providers/staging_symbols
-- pattern rather than living only as a code comment. "naive-v1" means
-- exactly what docs/engine-milestones.md's Milestone 3 vocabulary says:
-- real function over real data, hand-picked coefficients accepted,
-- unvalidated by design. Milestone 4 (statistical significance,
-- decorrelation, decay, fitted weights) is what promotes a version past
-- naive-v1; decay_rate/estimated_capacity_usd stay NULL until it does.
INSERT OR IGNORE INTO strategies (strategy_key, name, family, summary, status, current_version, added_at, retired_at, retirement_reason, public_spec_url, created_at, updated_at) VALUES
    ('macro_regime_composite', 'Macro regime composite', 'macro_regime', '8-factor macro composite (growth, inflation, PPI, core PCE, employment, liquidity, volatility, rates) mapped to a regime label and confidence.', 'active', 'naive-v1', '2026-08-24', NULL, NULL, NULL, '2026-08-24T00:00:00Z', '2026-08-24T00:00:00Z'),
    ('cross_sectional_momentum', 'Cross-sectional momentum ranking', 'cross_sectional_discovery', 'Blended 1M/3M/6M z-score momentum ranking across the staging universe.', 'active', 'naive-v1', '2026-08-24', NULL, NULL, NULL, '2026-08-24T00:00:00Z', '2026-08-24T00:00:00Z'),
    ('macd_rsi_single_name_timing', 'MACD/RSI single-name timing', 'single_name_timing', 'Long-only MACD(12,26,9) bullish-crossover entry, MACD bearish-crossover or RSI(14)>=70 exit, per symbol.', 'active', 'naive-v1', '2026-08-24', NULL, NULL, NULL, '2026-08-24T00:00:00Z', '2026-08-24T00:00:00Z'),
    ('risk_envelope_allocation', 'Risk envelope allocation', 'portfolio_construction', 'Regime confidence scales a gross-exposure multiplier (0.5x-1.5x) against the equal-weight baseline; sleeve targets aggregate factor_engine''s per-symbol tilts.', 'active', 'naive-v1', '2026-08-24', NULL, NULL, NULL, '2026-08-24T00:00:00Z', '2026-08-24T00:00:00Z'),
    ('conviction_instrument_selection', 'Conviction-scaled instrument selection', 'instrument_expression', '-5..+5 conviction scale maps to equity tilt / credit spread / debit spread / LEAPS, priced with real Black-Scholes (real spot, real realized volatility, real 10Y Treasury rate).', 'active', 'naive-v1', '2026-08-24', NULL, NULL, NULL, '2026-08-24T00:00:00Z', '2026-08-24T00:00:00Z');

-- Honest placeholders, not fabricated implementations: these two named
-- desks have no strategy_versions row because no real function exists yet
-- ('unknown data stays null'). status='draft' and current_version=NULL are
-- the actual, queryable "not started" facts -- shown on the Strategy
-- registry list/detail pages and the Methodology page's not-implemented
-- cards. Registering the placeholder itself (rather than omitting it
-- entirely) is what lets a future maintainer see the full 6-desk shape at
-- a glance instead of having to know it exists from memory or a comment.
INSERT OR IGNORE INTO strategies (strategy_key, name, family, summary, status, current_version, added_at, retired_at, retirement_reason, public_spec_url, created_at, updated_at) VALUES
    ('sentiment_text_mining', 'Sentiment / text mining', 'sentiment_analysis', 'Social/news-derived sentiment. Not started -- no free or paid text/social data source is connected (see roadmap.md).', 'draft', NULL, NULL, NULL, NULL, NULL, '2026-08-25T00:00:00Z', '2026-08-25T00:00:00Z'),
    ('fundamental_analysis', 'Fundamental analysis (EPS / earnings)', 'fundamental_analysis', 'Company fundamentals -- EPS, earnings surprises, estimate revisions. Not started -- Intrinio/Benzinga are planned providers, not yet registered or adapted (see roadmap.md).', 'draft', NULL, NULL, NULL, NULL, NULL, '2026-08-25T00:00:00Z', '2026-08-25T00:00:00Z');

INSERT OR IGNORE INTO strategy_versions (strategy_key, version, created_at, thesis, expected_edge, change_summary, parameters_json, code_reference, promoted_at, next_review_at) VALUES
    ('macro_regime_composite', 'naive-v1', '2026-08-24T00:00:00Z',
     'Each macro series'' deviation from a naive target/center, weighted and summed, proxies the market''s risk-on/risk-off regime; regime confidence should correlate with forward risk-asset performance.',
     'None claimed yet. Weights (WEIGHTS dict) are hand-picked, not fit or validated against forward returns. Milestone 4 tests each factor''s real significance before any weight is trusted.',
     'Initial real implementation: fetch_data/validate_data/regime_filter proven end-to-end against live FRED data.',
     '{"weights":{"growth":0.15,"inflation":0.15,"ppi":0.10,"pce":0.15,"employment":0.10,"liquidity":0.15,"volatility":0.10,"rates":0.10},"growth_scale":0.03,"inflation_target":0.02,"inflation_scale":0.03,"ppi_target":0.02,"ppi_scale":0.05,"pce_target":0.02,"pce_scale":0.02,"employment_scale":0.02,"liquidity_center":0.0,"liquidity_scale":1.0,"volatility_center":20.0,"volatility_scale":10.0,"rates_center":4.0,"rates_scale":2.0,"composite_risk_on_threshold":0.15,"composite_risk_off_threshold":-0.15}',
     'backend/engine/regime/scoring.py', '2026-08-24T00:00:00Z', '2027-02-24'),
    ('cross_sectional_momentum', 'naive-v1', '2026-08-24T00:00:00Z',
     'Relative momentum (return rank vs. peers) persists over 1-6 month horizons; a symbol scoring well across all three horizons is more likely to continue outperforming its peers near-term.',
     'None claimed yet. Horizon blend weights (0.2/0.3/0.5) are hand-picked. No IC, decay, or turnover evidence has been measured.',
     'Initial real implementation: real 10-year Yahoo price history, real cross-sectional z-score ranking.',
     '{"horizons":[["1m",21,0.2],["3m",63,0.3],["6m",126,0.5]],"z_score_scale_divisor":2.0,"bullish_threshold":0.1,"bearish_threshold":-0.1}',
     'backend/engine/factors/momentum.py', '2026-08-24T00:00:00Z', '2027-02-24'),
    ('macd_rsi_single_name_timing', 'naive-v1', '2026-08-24T00:00:00Z',
     'A MACD bullish crossover signals building upward momentum worth entering; an RSI-overbought reading or MACD bearish crossover signals momentum exhaustion worth exiting.',
     'None claimed. The desk-level aggregate backtest (see docs/engine-milestones.md Milestone 3) shows this losing to buy-and-hold on average across the staging universe. Real, working, and expected to need work.',
     'Initial real implementation: full trade log, Sharpe ratio, win rate, max drawdown, desk-level aggregate.',
     '{"macd_fast":12,"macd_slow":26,"macd_signal":9,"rsi_period":14,"rsi_overbought":70.0,"min_bars":60}',
     'backend/engine/timing/backtest.py', '2026-08-24T00:00:00Z', '2027-02-24'),
    ('risk_envelope_allocation', 'naive-v1', '2026-08-24T00:00:00Z',
     'Higher regime confidence (more risk-supportive macro backdrop) should justify carrying more gross exposure than a neutral baseline, and vice versa.',
     'None claimed. The 0.5x-1.5x band and the confidence-to-multiplier mapping (confidence*2.0) are hand-picked, not fit. No covariance-aware sizing yet.',
     'Initial real implementation: real decision graph (desk -> risk envelope -> sleeves).',
     '{"multiplier_floor":0.5,"multiplier_ceiling":1.5,"confidence_to_multiplier_scale":2.0}',
     'backend/engine/allocation/envelope.py', '2026-08-24T00:00:00Z', '2027-02-24'),
    ('conviction_instrument_selection', 'naive-v1', '2026-08-24T00:00:00Z',
     'Higher-conviction views justify progressively more capital-efficient, defined-risk option structures instead of simply sizing up a plain equity position.',
     'None claimed for the structure-selection thresholds (2.5/3.5/4.5 breakpoints are hand-picked). Black-Scholes pricing is standard, correct math, but uses realized (not market-implied) volatility -- every candidate is explicitly labeled theoretical-pricing-only.',
     'Initial real implementation: real Black-Scholes pricing over real spot/volatility/rate inputs.',
     '{"credit_spread_threshold":2.5,"debit_spread_threshold":3.5,"leaps_threshold":4.5,"credit_spread_dte":35,"debit_spread_dte":60,"leaps_dte":545,"credit_put_spread_short_otm":0.05,"credit_put_spread_long_otm":0.10,"bull_call_spread_short_otm":0.08,"bear_put_spread_short_otm":0.08}',
     'backend/engine/instruments/structures.py', '2026-08-24T00:00:00Z', '2027-02-24');

INSERT OR IGNORE INTO strategy_diagnostics (strategy_key, version, metric_key, label, value, unit, status, window_label, as_of, description, sort_order)
SELECT strategy_key, 'naive-v1', 'decay_rate', 'Signal decay rate', NULL, 'fraction_per_period', 'not_computed', NULL, NULL,
       'Not yet measured. Requires Milestone 4: statistical significance testing and decay estimation over real forward returns.', 1
FROM strategies WHERE strategy_key IN (
    'macro_regime_composite', 'cross_sectional_momentum', 'macd_rsi_single_name_timing',
    'risk_envelope_allocation', 'conviction_instrument_selection'
);
INSERT OR IGNORE INTO strategy_diagnostics (strategy_key, version, metric_key, label, value, unit, status, window_label, as_of, description, sort_order)
SELECT strategy_key, 'naive-v1', 'estimated_capacity_usd', 'Estimated capacity', NULL, 'usd', 'not_computed', NULL, NULL,
       'Not yet measured. Requires liquidity/market-impact modeling not yet built.', 2
FROM strategies WHERE strategy_key IN (
    'macro_regime_composite', 'cross_sectional_momentum', 'macd_rsi_single_name_timing',
    'risk_envelope_allocation', 'conviction_instrument_selection'
);

INSERT OR IGNORE INTO strategy_lifecycle_events (event_id, strategy_key, occurred_at, from_status, to_status, reason, strategy_version) VALUES
    ('naive-v1-macro_regime_composite-active', 'macro_regime_composite', '2026-08-24T00:00:00Z', NULL, 'active', 'Registered directly as active: real function over real data, proven end-to-end in the live pipeline (Milestone 3). Naive/unvalidated by design -- Milestone 4 is the statistical validation gate.', 'naive-v1'),
    ('naive-v1-cross_sectional_momentum-active', 'cross_sectional_momentum', '2026-08-24T00:00:00Z', NULL, 'active', 'Registered directly as active: real function over real data, proven end-to-end in the live pipeline (Milestone 3). Naive/unvalidated by design -- Milestone 4 is the statistical validation gate.', 'naive-v1'),
    ('naive-v1-macd_rsi_single_name_timing-active', 'macd_rsi_single_name_timing', '2026-08-24T00:00:00Z', NULL, 'active', 'Registered directly as active: real function over real data, proven end-to-end in the live pipeline (Milestone 3). Naive/unvalidated by design -- Milestone 4 is the statistical validation gate.', 'naive-v1'),
    ('naive-v1-risk_envelope_allocation-active', 'risk_envelope_allocation', '2026-08-24T00:00:00Z', NULL, 'active', 'Registered directly as active: real function over real data, proven end-to-end in the live pipeline (Milestone 3). Naive/unvalidated by design -- Milestone 4 is the statistical validation gate.', 'naive-v1'),
    ('naive-v1-conviction_instrument_selection-active', 'conviction_instrument_selection', '2026-08-24T00:00:00Z', NULL, 'active', 'Registered directly as active: real function over real data, proven end-to-end in the live pipeline (Milestone 3). Naive/unvalidated by design -- Milestone 4 is the statistical validation gate.', 'naive-v1');

-- naive-v2: macro_regime_composite's per-factor scoring moved from a fixed
-- hand-picked target (v1) to a real surprise against the series' own
-- trailing statistical average -- the "beat vs. miss" framing real macro
-- markets actually price, not a level check against an arbitrary number.
-- v1's code (engine/regime/scoring.py) stays untouched and importable so
-- any dataset snapshot already sealed under naive-v1 stays honestly
-- reproducible; this is a NEW version row, not a rewrite of the old one.
INSERT OR IGNORE INTO strategy_versions (strategy_key, version, created_at, thesis, expected_edge, change_summary, parameters_json, code_reference, promoted_at, next_review_at) VALUES
    ('macro_regime_composite', 'naive-v2', '2026-08-25T00:00:00Z',
     'Markets price the SURPRISE in a macro release relative to an expectation already priced in, not its raw level or its distance from an arbitrary fixed target (Andersen, Bollerslev, Diebold & Vega, 2003; Balduzzi, Elton & Green, 2001) -- the same logic CME FedWatch-style tools apply to policy-rate expectations (Krueger & Kuttner, 1996).',
     'None claimed. No free real-time consensus/survey-expectations feed exists for this project (Trading Economics is the planned paid source; not purchased). The "expectation" is a disclosed, naive trailing statistical mean -- an adaptive-expectations proxy (Muth, 1961), not a market consensus. Milestone 4 still has to test this version''s real significance before any weight is trusted.',
     'naive-v2: replaced fixed-target per-factor scoring with real surprise-vs-trailing-mean scoring for all 8 factors. Same weights, same aggregation, same confidence/label thresholds as naive-v1 -- only the per-factor contribution formula changed, per the project''s "one strategy, one step improve" rule.',
     '{"expectation_windows":{"growth":6,"inflation":6,"ppi":6,"pce":6,"employment":6,"liquidity":12,"volatility":60,"rates":60},"surprise_scales":{"growth":0.015,"inflation":0.01,"ppi":0.02,"pce":0.008,"employment":0.005,"liquidity":0.1,"volatility":5.0,"rates":0.2}}',
     'backend/engine/regime/scoring_v2.py', '2026-08-25T00:00:00Z', '2027-02-25');

UPDATE strategies SET current_version = 'naive-v2', updated_at = '2026-08-25T00:00:00Z'
WHERE strategy_key = 'macro_regime_composite';

INSERT OR IGNORE INTO strategy_diagnostics (strategy_key, version, metric_key, label, value, unit, status, window_label, as_of, description, sort_order) VALUES
    ('macro_regime_composite', 'naive-v2', 'decay_rate', 'Signal decay rate', NULL, 'fraction_per_period', 'not_computed', NULL, NULL,
     'Not yet measured. Requires Milestone 4: statistical significance testing and decay estimation over real forward returns.', 1),
    ('macro_regime_composite', 'naive-v2', 'estimated_capacity_usd', 'Estimated capacity', NULL, 'usd', 'not_computed', NULL, NULL,
     'Not yet measured. Requires liquidity/market-impact modeling not yet built.', 2);

INSERT OR IGNORE INTO strategy_lifecycle_events (event_id, strategy_key, occurred_at, from_status, to_status, reason, strategy_version) VALUES
    ('naive-v2-macro_regime_composite-promoted', 'macro_regime_composite', '2026-08-25T00:00:00Z', 'active', 'active',
     'Promoted naive-v1 -> naive-v2: per-factor scoring reframed from a fixed hand-picked target to a real surprise against the series'' own trailing statistical average, motivated by the macro-announcement-surprise literature (see strategy_versions.thesis for citations). Still naive by design -- Milestone 4''s statistical validation gate has not run against this version yet.',
     'naive-v2');

-- naive-v2: cross_sectional_momentum's horizon blend weights (v1: fixed
-- 0.2/0.3/0.5) are replaced by a real per-horizon Pearson-correlation
-- significance test (pooled horizon-return vs. 21-trading-day-forward-return
-- across the staging universe, Benjamini-Hochberg corrected -- the same
-- method already proven in engine/research/factor_symbol_correlation.py,
-- Milestone 4 step 1), run fresh every pipeline run against whatever price
-- history was actually fetched. Weight is proportional to |r| among
-- horizons that clear correction; if none clear it, every horizon falls
-- back to equal weight -- a real, honestly-labeled result, never a blocked
-- or hidden score. v1's code (engine/factors/momentum.py) stays untouched
-- and importable so any dataset snapshot already sealed under naive-v1
-- stays honestly reproducible; this is a NEW version row, not a rewrite.
INSERT OR IGNORE INTO strategy_versions (strategy_key, version, created_at, thesis, expected_edge, change_summary, parameters_json, code_reference, promoted_at, next_review_at) VALUES
    ('cross_sectional_momentum', 'naive-v2', '2026-08-25T00:00:00Z',
     'If a momentum horizon''s historical value actually correlates with real forward returns across the staging universe, it should be weighted by that measured relationship instead of a hand-picked constant; a horizon with no measurable relationship should not be weighted as if it does.',
     'None claimed. The per-horizon test is real (Pearson r + Benjamini-Hochberg correction, same method as the macro factor-significance research), but it is one narrow test, not the full Milestone 4 gate -- no decorrelation across the three horizons and no fitted (vs. |r|-proportional or equal) weight has run yet.',
     'naive-v2: replaced v1''s fixed 0.2/0.3/0.5 horizon blend with weights computed fresh every run from a real significance test over that run''s own fetched price history. Same 1m/3m/6m horizons, same cross-sectional z-score ranking -- only the horizon-weighting mechanism changed, per the project''s "one strategy, one step improve" rule.',
     '{"horizons_days":{"1m":21,"3m":63,"6m":126},"forward_horizon_trading_days":21,"min_samples":24,"stride_days":5,"correction_method":"benjamini_hochberg","alpha":0.05,"weight_rule":"proportional_to_abs_correlation_among_significant_horizons_else_equal_weight"}',
     'backend/engine/factors/momentum_v2.py', '2026-08-25T00:00:00Z', '2027-02-25');

UPDATE strategies SET current_version = 'naive-v2', updated_at = '2026-08-25T00:00:00Z'
WHERE strategy_key = 'cross_sectional_momentum';

INSERT OR IGNORE INTO strategy_diagnostics (strategy_key, version, metric_key, label, value, unit, status, window_label, as_of, description, sort_order) VALUES
    ('cross_sectional_momentum', 'naive-v2', 'decay_rate', 'Signal decay rate', NULL, 'fraction_per_period', 'not_computed', NULL, NULL,
     'Not yet measured. Requires Milestone 4: decorrelation across horizons and decay estimation over real forward returns.', 1),
    ('cross_sectional_momentum', 'naive-v2', 'estimated_capacity_usd', 'Estimated capacity', NULL, 'usd', 'not_computed', NULL, NULL,
     'Not yet measured. Requires liquidity/market-impact modeling not yet built.', 2);

INSERT OR IGNORE INTO strategy_lifecycle_events (event_id, strategy_key, occurred_at, from_status, to_status, reason, strategy_version) VALUES
    ('naive-v2-cross_sectional_momentum-promoted', 'cross_sectional_momentum', '2026-08-25T00:00:00Z', 'active', 'active',
     'Promoted naive-v1 -> naive-v2: horizon blend weights reframed from hand-picked constants to a real, per-run Pearson/Benjamini-Hochberg significance test against pooled forward returns (see strategy_versions.thesis). Still naive by design -- full Milestone 4 rigor (decorrelation, fitted weights, decay) has not run against this version yet.',
     'naive-v2');

-- naive-v2: macd_rsi_single_name_timing split into two independently
-- registered, independently retireable strategy_components (macd_crossover,
-- rsi_overbought_exit) instead of one fused function -- the granularity
-- gap identified 2026-08-25. Retiring rsi_overbought_exit (status='retired')
-- degrades gracefully: MACD alone still forms a complete entry+exit rule.
-- Retiring macd_crossover is a real structural constraint, not a bug: it is
-- the only registered entry trigger today, so removing it leaves the
-- strategy with an honest 'no_entry_signal_active' status and zero trades,
-- never a crash or a fabricated rule (see engine/timing/backtest_v2.py).
-- v1's fused function (engine/timing/backtest.py) stays untouched and
-- importable so any dataset snapshot already sealed under it stays
-- honestly reproducible; this is a NEW version row, not a rewrite.
INSERT OR IGNORE INTO strategy_versions (strategy_key, version, created_at, thesis, expected_edge, change_summary, parameters_json, code_reference, promoted_at, next_review_at) VALUES
    ('macd_rsi_single_name_timing', 'naive-v2', '2026-08-25T00:00:00Z',
     'A trading rule built from named, independently retireable components is safer to iterate on than one fused function: a desk that decides MACD or RSI individually deserves review, decay-tracking, or retirement should be able to do that with a DB flag, not a code change that risks breaking the whole strategy.',
     'None claimed. This version changes the strategy''s internal structure (component granularity), not its trading logic when both components are active -- the entry/exit rule is identical to naive-v1 in the default (both-active) configuration.',
     'naive-v2: split into 2 registered strategy_components (macd_crossover: entry+exit; rsi_overbought_exit: exit only), combined by a role-tagged signal ensemble instead of one fused function. Same MACD(12,26,9)/RSI(14)/70-overbought parameters as naive-v1.',
     '{"macd_fast":12,"macd_slow":26,"macd_signal":9,"rsi_period":14,"rsi_overbought":70.0,"min_bars":60,"components":["macd_crossover","rsi_overbought_exit"]}',
     'backend/engine/timing/backtest_v2.py', '2026-08-25T00:00:00Z', '2027-02-25');

UPDATE strategies SET current_version = 'naive-v2', updated_at = '2026-08-25T00:00:00Z'
WHERE strategy_key = 'macd_rsi_single_name_timing';

INSERT OR IGNORE INTO strategy_components (strategy_key, version, component_key, name, component_type, roles_json, code_reference, base_weight, status, verification_status, decay_rate, next_review_at, created_at, updated_at) VALUES
    ('macd_rsi_single_name_timing', 'naive-v2', 'macd_crossover', 'MACD bullish/bearish crossover', 'computed', '["entry","exit"]', 'backend/engine/indicators/macd.py', NULL, 'active', 'registered_only', NULL, '2027-02-25', '2026-08-25T00:00:00Z', '2026-08-25T00:00:00Z'),
    ('macd_rsi_single_name_timing', 'naive-v2', 'rsi_overbought_exit', 'RSI(14) >= 70 overbought exit', 'computed', '["exit"]', 'backend/engine/indicators/rsi.py', NULL, 'active', 'registered_only', NULL, '2027-02-25', '2026-08-25T00:00:00Z', '2026-08-25T00:00:00Z');

INSERT OR IGNORE INTO strategy_diagnostics (strategy_key, version, metric_key, label, value, unit, status, window_label, as_of, description, sort_order) VALUES
    ('macd_rsi_single_name_timing', 'naive-v2', 'decay_rate', 'Signal decay rate', NULL, 'fraction_per_period', 'not_computed', NULL, NULL,
     'Not yet measured at the strategy level. Component-level decay (per macd_crossover / rsi_overbought_exit) also not yet measured -- see strategy_components.decay_rate.', 1),
    ('macd_rsi_single_name_timing', 'naive-v2', 'estimated_capacity_usd', 'Estimated capacity', NULL, 'usd', 'not_computed', NULL, NULL,
     'Not yet measured. Requires liquidity/market-impact modeling not yet built.', 2);

INSERT OR IGNORE INTO strategy_lifecycle_events (event_id, strategy_key, occurred_at, from_status, to_status, reason, strategy_version) VALUES
    ('naive-v2-macd_rsi_single_name_timing-promoted', 'macd_rsi_single_name_timing', '2026-08-25T00:00:00Z', 'active', 'active',
     'Promoted naive-v1 -> naive-v2: split into 2 independently registered, independently retireable strategy_components (macd_crossover, rsi_overbought_exit) instead of one fused function -- proves an engine algorithm can be revised and isolation-tested standalone, then swapped in as a small diff, without breaking the pipeline or existing tests. Trading logic unchanged when both components are active.',
     'naive-v2');

-- Research results remain DB-indexed. Files are optional, reproducible output
-- artifacts identified by repository-relative path and checksum; Markdown is
-- never an engine input or the canonical result store.
CREATE TABLE IF NOT EXISTS research_runs (
    research_run_id TEXT PRIMARY KEY,
    strategy_key TEXT NOT NULL,
    strategy_version TEXT NOT NULL,
    -- Which strategy_components row this run evaluates, if it targets one
    -- specific sub-signal rather than the whole ensemble (e.g. IC for just
    -- macd_crossover). NULL means the run evaluates the strategy/version as
    -- a whole -- both are legitimate, not every desk has component-level
    -- granularity yet.
    component_key TEXT,
    dataset_snapshot_id TEXT REFERENCES dataset_snapshots(id),
    code_commit TEXT,
    parameters_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL CHECK (
        status IN ('queued', 'running', 'completed', 'failed', 'cancelled')
    ),
    started_at TEXT,
    finished_at TEXT,
    summary TEXT NOT NULL,
    -- A completed run can still turn out to be a real, human mistake (wrong
    -- window, a bug in the extraction step) discovered after the fact.
    -- Research history stays append-only -- correcting a mistake means
    -- recording a NEW run and pointing the old one here, never deleting or
    -- silently editing sealed evidence. superseded_by_run_id says "a later
    -- run replaces this one's conclusion"; invalidated_reason says "this
    -- run's numbers should not be trusted" -- independent facts, since a run
    -- can be invalidated with no replacement yet.
    superseded_by_run_id TEXT REFERENCES research_runs(research_run_id),
    invalidated_reason TEXT,
    CHECK (status != 'completed' OR dataset_snapshot_id IS NOT NULL),
    FOREIGN KEY (strategy_key, strategy_version)
        REFERENCES strategy_versions(strategy_key, version)
);

CREATE TRIGGER IF NOT EXISTS research_completed_requires_sealed_dataset_insert
BEFORE INSERT ON research_runs
WHEN NEW.status = 'completed'
 AND (
     NEW.dataset_snapshot_id IS NULL
     OR COALESCE(
         (SELECT immutable FROM dataset_snapshots WHERE id = NEW.dataset_snapshot_id),
         0
     ) != 1
 )
BEGIN
    SELECT RAISE(ABORT, 'completed research run requires a sealed dataset snapshot');
END;

CREATE TRIGGER IF NOT EXISTS research_completed_requires_sealed_dataset_update
BEFORE UPDATE ON research_runs
WHEN NEW.status = 'completed'
 AND (
     NEW.dataset_snapshot_id IS NULL
     OR COALESCE(
         (SELECT immutable FROM dataset_snapshots WHERE id = NEW.dataset_snapshot_id),
         0
     ) != 1
 )
BEGIN
    SELECT RAISE(ABORT, 'completed research run requires a sealed dataset snapshot');
END;

CREATE TABLE IF NOT EXISTS research_artifacts (
    research_run_id TEXT NOT NULL REFERENCES research_runs(research_run_id),
    artifact_key TEXT NOT NULL,
    relative_path TEXT NOT NULL CHECK (
        relative_path NOT LIKE '/%'
        AND relative_path NOT LIKE '%://%'
        AND relative_path NOT LIKE '../%'
        AND relative_path NOT LIKE '%/../%'
    ),
    media_type TEXT NOT NULL,
    sha256 TEXT NOT NULL CHECK (
        length(sha256) = 64 AND sha256 NOT GLOB '*[^0-9a-f]*'
    ),
    size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
    curated INTEGER NOT NULL CHECK (curated IN (0, 1)),
    created_at TEXT NOT NULL,
    PRIMARY KEY (research_run_id, artifact_key)
);

-- Milestone 4, step 1 (docs/engine-milestones.md): real macro-factor x
-- staging-symbol significance testing (backend/engine/research/). Deliberately
-- NOT a `strategies`/`research_runs` row -- this is validation research
-- feeding INTO macro_regime_composite and risk_envelope_allocation, not a
-- decision-making strategy itself. Deliberately NOT registered in
-- DATASET_SNAPSHOT_CHILD_TABLES (database.py): a run only makes sense
-- AFTER its dataset_snapshot_id is already sealed, so it must stay
-- insertable post-seal, unlike fred_observations/symbol_bars.
CREATE TABLE IF NOT EXISTS factor_significance_runs (
    run_id TEXT PRIMARY KEY,
    dataset_snapshot_id TEXT NOT NULL REFERENCES dataset_snapshots(id),
    method TEXT NOT NULL,
    forward_horizon_days INTEGER NOT NULL,
    correction_method TEXT NOT NULL,
    alpha REAL NOT NULL,
    min_samples INTEGER NOT NULL,
    factor_count INTEGER NOT NULL,
    symbol_count INTEGER NOT NULL,
    test_count INTEGER NOT NULL,
    significant_count INTEGER NOT NULL,
    summary TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS factor_significance_results (
    run_id TEXT NOT NULL REFERENCES factor_significance_runs(run_id),
    factor_key TEXT NOT NULL,
    symbol TEXT NOT NULL,
    sample_size INTEGER NOT NULL,
    correlation REAL,
    p_value REAL,
    adjusted_p_value REAL,
    significant INTEGER NOT NULL CHECK (significant IN (0, 1)),
    direction TEXT NOT NULL CHECK (direction IN ('positive', 'negative', 'inconclusive')),
    status TEXT NOT NULL CHECK (status IN ('ok', 'insufficient_data')),
    PRIMARY KEY (run_id, factor_key, symbol)
);

CREATE INDEX IF NOT EXISTS idx_factor_significance_results_significant
    ON factor_significance_results(run_id, significant, factor_key);

-- General-purpose quant research evidence layer, generalizing the pattern
-- proven narrowly by factor_significance_runs/results (macro-factor-vs-
-- symbol correlation only) to any research category, against any strategy
-- or strategy_component. Reused, not duplicated, going forward: adding a
-- new research category (backtest performance, robustness, trading
-- reality, portfolio risk -- not built yet, catalogued below so the full
-- shape is visible) means new catalog rows and new utility functions in
-- backend/engine/research/, never new tables or new UI.
--
-- research_metric_catalog is the full enumerated vocabulary of what CAN be
-- computed -- registering a metric here is not a claim it has been
-- computed for anything yet. research_run_metrics holds only what a real
-- research_runs row actually produced. The evidence page renders one row
-- per catalog entry per subject: a real value where research_run_metrics
-- has one, an honest dash where it doesn't -- "I enumerate all possible
-- metrics from my knowledge does not mean we always need to run all" (the
-- standing instruction this table exists to satisfy), not an implied
-- oversight.
CREATE TABLE IF NOT EXISTS research_metric_catalog (
    metric_key TEXT PRIMARY KEY,
    category TEXT NOT NULL CHECK (category IN (
        'data_integrity', 'signal_validation', 'backtest_performance',
        'robustness_validation', 'trading_reality', 'portfolio_risk'
    )),
    label TEXT NOT NULL,
    unit TEXT,
    description TEXT NOT NULL,
    -- JSON array of strategies.family values this metric structurally
    -- applies to; '[]' means universal (e.g. every category-1 data-
    -- integrity check, or a correlation-based category-2 check, applies
    -- regardless of desk type). A non-universal example: backtest_performance
    -- metrics (Sharpe, drawdown, ...) apply to tradable/timing families, not
    -- to macro_regime -- a regime classifier has no trade to have a Sharpe
    -- ratio on, matching this project's own "macro only needs a p-test and
    -- PCA, not a detailed backtest" framing.
    applicable_families_json TEXT NOT NULL DEFAULT '[]',
    sort_order INTEGER NOT NULL
);

INSERT OR IGNORE INTO research_metric_catalog (metric_key, category, label, unit, description, applicable_families_json, sort_order) VALUES
    -- 1. Data integrity
    ('point_in_time_data', 'data_integrity', 'Point-in-time data', NULL, 'Every input value was actually available (observed_at/available_at) at or before the decision timestamp used to test it.', '[]', 1),
    ('no_look_ahead_bias', 'data_integrity', 'No look-ahead bias', NULL, 'No feature or label uses information not yet knowable at the simulated decision time.', '[]', 2),
    ('no_survivorship_bias', 'data_integrity', 'No survivorship bias', NULL, 'The evaluated universe includes symbols that were later delisted or removed, not only current survivors.', '[]', 3),
    ('corporate_action_adjustment', 'data_integrity', 'Corporate action adjustment', NULL, 'Splits, dividends, and other corporate actions are correctly reflected in the price series used.', '[]', 4),
    ('delisting_returns', 'data_integrity', 'Delisting returns', NULL, 'A delisted security'' final return is captured, not silently dropped from the sample.', '[]', 5),
    ('universe_membership_at_t', 'data_integrity', 'Universe membership at time t', NULL, 'Eligibility is evaluated against the universe as it stood at each historical decision date, not today''s universe applied retroactively.', '[]', 6),
    ('publication_reporting_lag', 'data_integrity', 'Publication / reporting lag', NULL, 'The real gap between a value''s observation date and its actual public availability date is modeled, not assumed to be zero.', '[]', 7),
    -- 2. Signal / factor validation
    ('factor_ic', 'signal_validation', 'Factor IC (Information Coefficient)', 'correlation', 'Pearson correlation between a factor''s value and the real forward return it is meant to predict.', '[]', 10),
    ('factor_rank_ic', 'signal_validation', 'Rank IC', 'correlation', 'Spearman rank correlation between a factor''s value and the real forward return -- robust to outliers and nonlinearity that Pearson IC is not.', '[]', 11),
    ('ic_mean', 'signal_validation', 'IC mean', 'correlation', 'Mean IC across multiple evaluation periods.', '[]', 12),
    ('ic_std', 'signal_validation', 'IC std', 'correlation', 'Standard deviation of IC across multiple evaluation periods -- how stable the relationship is, not just its average.', '[]', 13),
    ('icir', 'signal_validation', 'ICIR', 'ratio', 'IC mean divided by IC std -- an information-ratio-style measure of a factor''s risk-adjusted predictive consistency.', '[]', 14),
    ('factor_return', 'signal_validation', 'Factor return', 'fraction', 'Return of a portfolio built purely from this factor''s ranking.', '[]', 15),
    ('long_short_spread', 'signal_validation', 'Long-short spread', 'fraction', 'Return difference between the factor''s top and bottom ranked buckets.', '[]', 16),
    ('factor_hit_rate', 'signal_validation', 'Hit rate', 'fraction', 'Share of periods where the factor''s ranking direction matched the realized outcome direction.', '[]', 17),
    ('factor_turnover', 'signal_validation', 'Factor turnover', 'fraction', 'How much the factor''s cross-sectional ranking churns period to period -- high turnover raises real trading cost for the same signal.', '[]', 18),
    ('decay_half_life', 'signal_validation', 'Decay / half-life', 'periods', 'How many periods it takes for the factor''s predictive power (IC) to fall to half its initial value.', '[]', 19),
    ('factor_correlation', 'signal_validation', 'Factor correlation', 'correlation', 'Pairwise correlation between this factor and every other registered factor in its family -- the raw input to effective-number-of-bets and redundancy detection.', '[]', 20),
    ('effective_number_of_bets', 'signal_validation', 'Effective number of bets', 'count', 'PCA-based measure of how many genuinely independent bets a factor family actually represents -- N correlated factors are worth far fewer than N independent ones.', '[]', 21),
    ('exposure_correlation', 'signal_validation', 'Exposure correlation', 'correlation', 'Correlation between this factor''s resulting portfolio exposure and another factor''s or the market''s.', '[]', 22),
    ('marginal_contribution', 'signal_validation', 'Marginal contribution', 'fraction', 'The factor''s unique contribution to combined predictive power after accounting for its correlation with already-registered factors.', '[]', 23),
    -- 4. Backtest performance metrics
    ('cagr', 'backtest_performance', 'CAGR / annualized return', 'fraction', 'Compound annual growth rate of the strategy''s equity curve.', '["single_name_timing","cross_sectional_discovery","instrument_expression"]', 30),
    ('annualized_volatility', 'backtest_performance', 'Annualized volatility', 'fraction', 'Standard deviation of returns, annualized.', '["single_name_timing","cross_sectional_discovery","instrument_expression"]', 31),
    ('sharpe_ratio', 'backtest_performance', 'Sharpe ratio', 'ratio', 'Annualized mean return divided by annualized volatility.', '["single_name_timing","cross_sectional_discovery","instrument_expression"]', 32),
    ('sortino_ratio', 'backtest_performance', 'Sortino ratio', 'ratio', 'Like Sharpe, but only penalizing downside volatility.', '["single_name_timing","cross_sectional_discovery","instrument_expression"]', 33),
    ('max_drawdown', 'backtest_performance', 'Maximum drawdown', 'fraction', 'Largest peak-to-trough decline in the equity curve.', '["single_name_timing","cross_sectional_discovery","instrument_expression"]', 34),
    ('drawdown_duration', 'backtest_performance', 'Drawdown duration', 'periods', 'How long the strategy stayed below its prior peak.', '["single_name_timing","cross_sectional_discovery","instrument_expression"]', 35),
    ('calmar_ratio', 'backtest_performance', 'Calmar ratio', 'ratio', 'CAGR divided by maximum drawdown.', '["single_name_timing","cross_sectional_discovery","instrument_expression"]', 36),
    ('trade_hit_rate', 'backtest_performance', 'Hit rate / win rate', 'fraction', 'Share of closed trades with a positive return.', '["single_name_timing"]', 37),
    ('payoff_ratio', 'backtest_performance', 'Payoff ratio', 'ratio', 'Average winning trade divided by average losing trade.', '["single_name_timing"]', 38),
    ('profit_factor', 'backtest_performance', 'Profit factor', 'ratio', 'Gross profit divided by gross loss.', '["single_name_timing"]', 39),
    ('value_at_risk', 'backtest_performance', 'Value at Risk (VaR)', 'fraction', 'Loss threshold not expected to be exceeded at a given confidence level.', '["single_name_timing","cross_sectional_discovery","instrument_expression","portfolio_construction"]', 40),
    ('expected_shortfall', 'backtest_performance', 'Expected Shortfall (CVaR)', 'fraction', 'Average loss in the tail beyond the VaR threshold.', '["single_name_timing","cross_sectional_discovery","instrument_expression","portfolio_construction"]', 41),
    ('return_skewness', 'backtest_performance', 'Skewness', 'ratio', 'Asymmetry of the return distribution.', '["single_name_timing","cross_sectional_discovery","instrument_expression"]', 42),
    ('return_kurtosis', 'backtest_performance', 'Kurtosis', 'ratio', 'Tail-heaviness of the return distribution relative to normal.', '["single_name_timing","cross_sectional_discovery","instrument_expression"]', 43),
    ('portfolio_turnover', 'backtest_performance', 'Turnover', 'fraction', 'How much the resulting positions actually trade, period to period -- distinct from factor_turnover (ranking churn) upstream of it.', '["single_name_timing","cross_sectional_discovery","portfolio_construction"]', 44),
    ('market_beta', 'backtest_performance', 'Market beta', 'ratio', 'Sensitivity of strategy returns to the broad market.', '["single_name_timing","cross_sectional_discovery","instrument_expression","portfolio_construction"]', 45),
    ('jensens_alpha', 'backtest_performance', 'Jensen''s alpha', 'fraction', 'Return in excess of what market beta alone would predict (CAPM residual).', '["single_name_timing","cross_sectional_discovery","instrument_expression","portfolio_construction"]', 46),
    -- 5. Robustness / statistical validation
    ('in_sample_out_of_sample', 'robustness_validation', 'In-sample / out-of-sample', NULL, 'Performance is compared between the period a rule was developed on and a genuinely unseen later period.', '[]', 50),
    ('walk_forward_validation', 'robustness_validation', 'Walk-forward validation', NULL, 'Repeated re-fit-then-test on rolling, non-overlapping forward windows.', '[]', 51),
    ('rolling_window_analysis', 'robustness_validation', 'Rolling window analysis', NULL, 'Metric stability measured across overlapping rolling windows rather than one fixed period.', '[]', 52),
    ('parameter_sensitivity', 'robustness_validation', 'Parameter sensitivity', NULL, 'How much results change under small, reasonable changes to hand-picked parameters -- a cliff-edge result is a red flag.', '[]', 53),
    ('subsample_stability', 'robustness_validation', 'Subsample stability', NULL, 'Results hold up across different sub-periods or sub-universes, not just the full sample.', '[]', 54),
    ('regime_analysis', 'robustness_validation', 'Regime analysis', NULL, 'Performance broken out by macro/vol regime rather than reported as one blended average.', '[]', 55),
    ('bootstrap_monte_carlo', 'robustness_validation', 'Bootstrap / Monte Carlo', NULL, 'Resampling-based confidence bounds on a metric, rather than a single point estimate.', '[]', 56),
    ('multiple_hypothesis_testing', 'robustness_validation', 'Multiple-hypothesis testing', NULL, 'How many hypotheses were actually tried before this one was reported -- the honest denominator behind any p-value.', '[]', 57),
    ('false_discovery_rate', 'robustness_validation', 'False discovery rate', 'fraction', 'Benjamini-Hochberg-style correction already implemented and used in this project (engine/research/significance.py) for macro-factor and momentum-horizon testing.', '[]', 58),
    ('deflated_sharpe_ratio', 'robustness_validation', 'Deflated Sharpe ratio', 'ratio', 'Sharpe ratio adjusted for the number of trials, track record length, and return non-normality (Bailey & Lopez de Prado, 2014).', '["single_name_timing","cross_sectional_discovery","instrument_expression"]', 59),
    ('probability_of_backtest_overfitting', 'robustness_validation', 'Probability of Backtest Overfitting (PBO)', 'fraction', 'Combinatorially-symmetric cross-validation estimate of the probability that the selected strategy is overfit (Bailey, Borwein, Lopez de Prado & Zhu, 2017).', '["single_name_timing","cross_sectional_discovery","instrument_expression"]', 60),
    -- 6. Trading reality
    ('transaction_costs', 'trading_reality', 'Transaction costs', 'fraction', 'Commissions and fees actually deducted from simulated returns.', '["single_name_timing","cross_sectional_discovery","instrument_expression","portfolio_construction"]', 70),
    ('bid_ask_spread', 'trading_reality', 'Bid-ask spread', 'fraction', 'Real quoted spread cost paid crossing the market on entry and exit, not a mid-price fill.', '["single_name_timing","instrument_expression"]', 71),
    ('slippage', 'trading_reality', 'Slippage', 'fraction', 'Difference between the intended and actually achievable execution price.', '["single_name_timing","instrument_expression"]', 72),
    ('market_impact', 'trading_reality', 'Market impact', 'fraction', 'Price movement caused by the order itself, scaling with size relative to liquidity.', '["single_name_timing","instrument_expression","portfolio_construction"]', 73),
    ('borrow_cost', 'trading_reality', 'Borrow cost', 'fraction', 'Cost of borrowing shares to hold a short position.', '["single_name_timing","instrument_expression"]', 74),
    ('short_availability', 'trading_reality', 'Short availability', NULL, 'Whether shares are actually borrowable for a proposed short, not merely assumed available.', '["single_name_timing","instrument_expression"]', 75),
    ('liquidity_constraints', 'trading_reality', 'Liquidity constraints', NULL, 'Position size checked against real traded volume, not sized as if infinitely liquid.', '["single_name_timing","instrument_expression","portfolio_construction"]', 76),
    ('adv_participation_limit', 'trading_reality', 'ADV participation limit', 'fraction', 'Order size capped as a fraction of average daily volume.', '["single_name_timing","instrument_expression","portfolio_construction"]', 77),
    ('execution_delay', 'trading_reality', 'Execution delay', 'periods', 'Real gap between signal generation and achievable fill, not same-bar fills assumed for free.', '["single_name_timing","instrument_expression"]', 78),
    ('capacity', 'trading_reality', 'Capacity', 'usd', 'Maximum capital the strategy can absorb before its own trading materially degrades its edge.', '["single_name_timing","cross_sectional_discovery","instrument_expression","portfolio_construction"]', 79),
    -- 7. Portfolio / risk layer
    ('position_sizing', 'portfolio_risk', 'Position sizing', NULL, 'The rule mapping conviction/signal strength to an actual position size.', '["instrument_expression","portfolio_construction"]', 90),
    ('volatility_targeting', 'portfolio_risk', 'Volatility targeting', NULL, 'Position size scaled to hit a target portfolio volatility rather than a fixed notional.', '["portfolio_construction"]', 91),
    ('risk_budgeting', 'portfolio_risk', 'Risk budgeting', NULL, 'Risk, not capital, allocated across sleeves/positions as the primary budget unit.', '["portfolio_construction"]', 92),
    ('factor_exposure_limits', 'portfolio_risk', 'Factor exposure limits', NULL, 'Portfolio-level caps on net exposure to any one factor.', '["portfolio_construction"]', 93),
    ('sector_industry_constraints', 'portfolio_risk', 'Sector / industry constraints', NULL, 'Caps on concentration within any one sector or industry.', '["portfolio_construction"]', 94),
    ('single_name_concentration_limits', 'portfolio_risk', 'Single-name concentration limits', NULL, 'Caps on how much of the portfolio any one security can represent.', '["portfolio_construction"]', 95),
    ('beta_neutralization', 'portfolio_risk', 'Beta neutralization', NULL, 'Whether and how market-beta exposure is hedged out of the portfolio.', '["portfolio_construction"]', 96),
    ('dollar_neutralization', 'portfolio_risk', 'Dollar neutralization', NULL, 'Long and short dollar exposure balanced to a target net.', '["portfolio_construction"]', 97),
    ('factor_neutralization', 'portfolio_risk', 'Factor neutralization', NULL, 'Unwanted factor exposures hedged out so a position expresses the intended bet only.', '["portfolio_construction"]', 98),
    ('correlation_covariance_control', 'portfolio_risk', 'Correlation / covariance control', NULL, 'Portfolio construction accounts for the real covariance between positions, not just their individual risk.', '["portfolio_construction"]', 99),
    ('gross_net_exposure_limits', 'portfolio_risk', 'Gross / net exposure limits', NULL, 'Hard caps on total long+short (gross) and long-short (net) exposure.', '["portfolio_construction"]', 100),
    ('drawdown_control', 'portfolio_risk', 'Drawdown control', NULL, 'A rule that reduces risk in response to realized drawdown, rather than a static allocation regardless of recent losses.', '["portfolio_construction"]', 101);

-- Real results for the catalog above. subject_key is whatever the metric
-- is ABOUT within this run -- a factor_key, a strategy_component_key, a
-- symbol, or the sentinel '_ensemble_' for a metric describing the whole
-- group (e.g. effective_number_of_bets is a property of an entire
-- correlation matrix, not any one factor). Mirrors strategy_diagnostics'
-- exact EAV shape at the run level instead of the strategy-version level,
-- because one research run typically produces many metrics for many
-- subjects at once.
CREATE TABLE IF NOT EXISTS research_run_metrics (
    research_run_id TEXT NOT NULL REFERENCES research_runs(research_run_id),
    subject_key TEXT NOT NULL,
    metric_key TEXT NOT NULL REFERENCES research_metric_catalog(metric_key),
    label TEXT NOT NULL,
    value REAL,
    unit TEXT,
    status TEXT NOT NULL,
    description TEXT,
    PRIMARY KEY (research_run_id, subject_key, metric_key)
);

CREATE INDEX IF NOT EXISTS idx_research_run_metrics_metric
    ON research_run_metrics(metric_key, subject_key);

-- Append-only audit/history boundaries. In-progress runs may advance to a
-- terminal state; once terminal, their headers and stage records are sealed.
CREATE TRIGGER IF NOT EXISTS provider_verifications_append_only_update
BEFORE UPDATE ON provider_verifications
BEGIN
    SELECT RAISE(ABORT, 'provider verification history is append-only');
END;

CREATE TRIGGER IF NOT EXISTS provider_verifications_append_only_delete
BEFORE DELETE ON provider_verifications
BEGIN
    SELECT RAISE(ABORT, 'provider verification history is append-only');
END;

CREATE TRIGGER IF NOT EXISTS pipeline_runs_terminal_update
BEFORE UPDATE ON pipeline_runs
WHEN OLD.status IN ('completed', 'partial', 'blocked', 'failed')
BEGIN
    SELECT RAISE(ABORT, 'terminal pipeline run is immutable');
END;

CREATE TRIGGER IF NOT EXISTS pipeline_runs_append_only_delete
BEFORE DELETE ON pipeline_runs
BEGIN
    SELECT RAISE(ABORT, 'pipeline run history is append-only');
END;

CREATE TRIGGER IF NOT EXISTS pipeline_stage_runs_terminal_insert
BEFORE INSERT ON pipeline_stage_runs
WHEN COALESCE(
    (SELECT status FROM pipeline_runs WHERE run_id = NEW.run_id), ''
) IN ('completed', 'partial', 'blocked', 'failed')
BEGIN
    SELECT RAISE(ABORT, 'terminal pipeline stages are immutable');
END;

CREATE TRIGGER IF NOT EXISTS pipeline_stage_runs_terminal_update
BEFORE UPDATE ON pipeline_stage_runs
WHEN COALESCE(
    (SELECT status FROM pipeline_runs WHERE run_id = OLD.run_id), ''
) IN ('completed', 'partial', 'blocked', 'failed')
BEGIN
    SELECT RAISE(ABORT, 'terminal pipeline stages are immutable');
END;

CREATE TRIGGER IF NOT EXISTS pipeline_stage_runs_terminal_delete
BEFORE DELETE ON pipeline_stage_runs
BEGIN
    SELECT RAISE(ABORT, 'pipeline stage history is append-only');
END;

CREATE TRIGGER IF NOT EXISTS strategy_lifecycle_append_only_update
BEFORE UPDATE ON strategy_lifecycle_events
BEGIN
    SELECT RAISE(ABORT, 'strategy lifecycle history is append-only');
END;

CREATE TRIGGER IF NOT EXISTS strategy_lifecycle_append_only_delete
BEFORE DELETE ON strategy_lifecycle_events
BEGIN
    SELECT RAISE(ABORT, 'strategy lifecycle history is append-only');
END;

CREATE TRIGGER IF NOT EXISTS research_runs_terminal_update
BEFORE UPDATE ON research_runs
WHEN OLD.status IN ('completed', 'failed', 'cancelled')
BEGIN
    SELECT RAISE(ABORT, 'terminal research run is immutable');
END;

CREATE TRIGGER IF NOT EXISTS research_runs_append_only_delete
BEFORE DELETE ON research_runs
BEGIN
    SELECT RAISE(ABORT, 'research run history is append-only');
END;

CREATE TRIGGER IF NOT EXISTS research_artifacts_completed_run_insert
BEFORE INSERT ON research_artifacts
WHEN COALESCE(
    (SELECT status FROM research_runs WHERE research_run_id = NEW.research_run_id),
    ''
) != 'completed'
BEGIN
    SELECT RAISE(ABORT, 'research artifacts require a completed run');
END;

CREATE TRIGGER IF NOT EXISTS research_artifacts_immutable_update
BEFORE UPDATE ON research_artifacts
BEGIN
    SELECT RAISE(ABORT, 'research artifact manifest is immutable');
END;

CREATE TRIGGER IF NOT EXISTS research_artifacts_immutable_delete
BEFORE DELETE ON research_artifacts
BEGIN
    SELECT RAISE(ABORT, 'research artifact manifest is immutable');
END;

-- Provider and pipeline catalog rows are application configuration, not market
-- observations. Installing the schema makes the empty application operable
-- without silently inventing a decision snapshot.
INSERT INTO operator_providers (
    provider_key, name, category, description, enabled, required,
    credential_label, credential_name, environment_variable,
    documentation_url, signup_url, terms_url, attribution_notice, instructions,
    capabilities_json, verifier_kind, verification_cooldown_seconds,
    verification_ttl_seconds, tier,
    sort_order, created_at, updated_at
) VALUES (
    'fred', 'FRED / ALFRED', 'macro',
    'Federal Reserve Economic Data release and vintage-aware macro inputs.',
    1, 1, 'FRED API key', 'fred_api_key', 'HEAE_FRED_API_KEY',
    'https://fred.stlouisfed.org/docs/api/fred/v2/',
    'https://fredaccount.stlouisfed.org/apikeys',
    'https://fred.stlouisfed.org/docs/api/terms_of_use.html',
    'This product uses the FRED API but is not endorsed or certified by the Federal Reserve Bank of St. Louis.',
    'Create a distinct key for this application in your FRED account, store it here, then run one smoke verification. The key stays in the OS credential store.',
    '["macro_releases","release_observations","vintage_metadata"]',
    'fred_v2', 900, 31536000, 'free', 10, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
)
ON CONFLICT(provider_key) DO UPDATE SET
    name = excluded.name,
    category = excluded.category,
    description = excluded.description,
    required = excluded.required,
    credential_label = excluded.credential_label,
    credential_name = excluded.credential_name,
    environment_variable = excluded.environment_variable,
    documentation_url = excluded.documentation_url,
    signup_url = excluded.signup_url,
    terms_url = excluded.terms_url,
    attribution_notice = excluded.attribution_notice,
    instructions = excluded.instructions,
    capabilities_json = excluded.capabilities_json,
    verifier_kind = excluded.verifier_kind,
    verification_cooldown_seconds = excluded.verification_cooldown_seconds,
    verification_ttl_seconds = excluded.verification_ttl_seconds,
    tier = excluded.tier,
    sort_order = excluded.sort_order,
    credential_revision = operator_providers.credential_revision + CASE
        WHEN operator_providers.credential_name IS NOT excluded.credential_name
          OR operator_providers.environment_variable IS NOT excluded.environment_variable
          OR operator_providers.verifier_kind IS NOT excluded.verifier_kind
        THEN 1 ELSE 0 END,
    updated_at = CASE
        WHEN operator_providers.credential_name IS NOT excluded.credential_name
          OR operator_providers.environment_variable IS NOT excluded.environment_variable
          OR operator_providers.verifier_kind IS NOT excluded.verifier_kind
        THEN CURRENT_TIMESTAMP ELSE operator_providers.updated_at END;

INSERT INTO data_capabilities (
    capability_key, name, category, description, requirement_level,
    unlocks_json, sort_order
) VALUES
    (
        'macro_actuals_vintages', 'Macro actuals and vintages', 'macro',
        'Release observations, revisions, and point-in-time availability needed for the first regime state.',
        'required_now', '["fetch_data","regime_filter"]', 10
    ),
    (
        'macro_consensus_expectations', 'Macro consensus expectations', 'macro',
        'Timestamped pre-release forecasts used to research economic surprises without confusing forecasts with actuals.',
        'required_later', '["regime_filter","event_research"]', 20
    ),
    (
        'equity_reference_events', 'Equity reference and issuer events', 'equity',
        'Stable identifiers, listings and delistings, corporate actions, fundamentals, earnings, and licensed transcript coverage.',
        'required_later', '["factor_engine","symbol_research"]', 30
    ),
    (
        'equity_market_history', 'Equity market history', 'equity',
        'Point-in-time prices and quotes with adjustment lineage for cross-sectional research and backtests.',
        'required_later', '["factor_engine","symbol_research","backtests"]', 40
    ),
    (
        'options_reference_history', 'Options reference and market history', 'options',
        'Contract terms, chains, quotes, open interest, volatility, and Greeks for legitimate option expressions.',
        'required_later', '["instrument_engine","position_research"]', 50
    )
ON CONFLICT(capability_key) DO UPDATE SET
    name = excluded.name,
    category = excluded.category,
    description = excluded.description,
    requirement_level = excluded.requirement_level,
    unlocks_json = excluded.unlocks_json,
    sort_order = excluded.sort_order;

INSERT INTO provider_onboarding_plan (
    plan_key, operator_provider_key, name, category, role, integration_status,
    required_for_first_slice, documentation_url, signup_url, pricing_url,
    terms_url, guidance, licensing_note, sort_order
) VALUES
    (
        'fred', 'fred', 'FRED / ALFRED', 'macro',
        'Macro actuals, release history, and vintages', 'verification_ready', 1,
        'https://fred.stlouisfed.org/docs/api/fred/v2/',
        'https://fredaccount.stlouisfed.org/apikeys', NULL,
        'https://fred.stlouisfed.org/docs/api/terms_of_use.html',
        'This is the only account requested now. Once its smoke test is healthy, no additional registration is needed for the first regime slice.',
        'Observe the FRED API terms and source-level restrictions. Store raw responses only in ignored local data.',
        10
    ),
    (
        'intrinio', NULL, 'Intrinio', 'market and options',
        'US security master, equity history, corporate actions, and historical options',
        'planned', 0,
        'https://docs.intrinio.com/documentation/api_v2/getting_started',
        'https://intrinio.com/', 'https://intrinio.com/pricing',
        'https://docs.intrinio.com/terms',
        'Planned for the full desk. Do not purchase or enter a key until its adapter and entitlement smoke tests are implemented.',
        'Personal, display, redistribution, commercial, and model-use rights differ by plan; confirm the intended local and public UI use before subscribing.',
        20
    ),
    (
        'benzinga', NULL, 'Benzinga', 'company events',
        'Fundamentals, earnings estimates and results, and licensed call transcripts',
        'planned', 0,
        'https://docs.benzinga.com/',
        'https://www.benzinga.com/apis/', NULL,
        'https://www.benzinga.com/disclaimer',
        'Planned for the full desk. Request product entitlements only after separate Fundamentals, Earnings, and Transcript checks exist.',
        'A valid token does not prove every product entitlement. Keep licensed payloads local and confirm display or redistribution rights.',
        30
    ),
    (
        'trading_economics', NULL, 'Trading Economics', 'macro expectations',
        'Point-in-time economic calendar and survey consensus',
        'planned', 0,
        'https://docs.tradingeconomics.com/economic_calendar/snapshot/',
        'https://docs.tradingeconomics.com/get_started/',
        'https://tradingeconomics.com/api/pricing.aspx', NULL,
        'Planned for surprise research after the first FRED regime slice. Do not register until the point-in-time calendar adapter is ready.',
        'Single-user, request, and public-distribution rights vary by plan; confirm them before enabling a shared or public surface.',
        40
    )
ON CONFLICT(plan_key) DO UPDATE SET
    operator_provider_key = excluded.operator_provider_key,
    name = excluded.name,
    category = excluded.category,
    role = excluded.role,
    integration_status = excluded.integration_status,
    required_for_first_slice = excluded.required_for_first_slice,
    documentation_url = excluded.documentation_url,
    signup_url = excluded.signup_url,
    pricing_url = excluded.pricing_url,
    terms_url = excluded.terms_url,
    guidance = excluded.guidance,
    licensing_note = excluded.licensing_note,
    sort_order = excluded.sort_order;

INSERT INTO provider_plan_capabilities (
    plan_key, capability_key, coverage_role, coverage_note
) VALUES
    ('fred', 'macro_actuals_vintages', 'primary', 'Credential verification is implemented; ingestion is the next product slice.'),
    ('intrinio', 'equity_reference_events', 'primary', 'Security master, delisted coverage, identifiers, and corporate-action adjustments.'),
    ('intrinio', 'equity_market_history', 'primary', 'Historical US equity pricing and reference coverage.'),
    ('intrinio', 'options_reference_history', 'primary', 'Historical end-of-day options coverage; intraday depth depends on entitlement.'),
    ('benzinga', 'equity_reference_events', 'supplemental', 'Fundamentals, earnings estimates and results, plus licensed transcript coverage.'),
    ('trading_economics', 'macro_consensus_expectations', 'primary', 'Timestamped calendar events, forecasts, consensus, actuals, and revisions.')
ON CONFLICT(plan_key, capability_key) DO UPDATE SET
    coverage_role = excluded.coverage_role,
    coverage_note = excluded.coverage_note;

INSERT INTO staging_symbols (
    symbol, name, category, tier, production_provider_key, notes, active, sort_order
) VALUES
    ('INDPRO', 'Industrial Production Index', 'macro_series', 'free', 'fred', 'Already used by regime_filter.', 1, 10),
    ('CPIAUCSL', 'CPI for All Urban Consumers', 'macro_series', 'free', 'fred', 'Already used by regime_filter.', 1, 11),
    ('NFCI', 'Chicago Fed National Financial Conditions Index', 'macro_series', 'free', 'fred', 'Already used by regime_filter.', 1, 12),
    ('VIXCLS', 'CBOE Volatility Index', 'macro_series', 'free', 'fred', 'Already used by regime_filter.', 1, 13),
    ('SPY', 'SPDR S&P 500 ETF Trust', 'broad_equity_etf', 'free', 'intrinio', NULL, 1, 20),
    ('QQQ', 'Invesco QQQ Trust', 'broad_equity_etf', 'free', 'intrinio', NULL, 1, 21),
    ('DIA', 'SPDR Dow Jones Industrial Average ETF Trust', 'broad_equity_etf', 'free', 'intrinio', NULL, 1, 22),
    ('TLT', 'iShares 20+ Year Treasury Bond ETF', 'bond_duration_etf', 'free', 'intrinio', NULL, 1, 30),
    ('IEF', 'iShares 7-10 Year Treasury Bond ETF', 'bond_duration_etf', 'free', 'intrinio', NULL, 1, 31),
    ('GLD', 'SPDR Gold Shares', 'commodity_etf', 'free', 'intrinio', NULL, 1, 40),
    ('BTC-USD', 'Bitcoin / U.S. dollar reference series', 'crypto_reference', 'free', NULL, 'No production provider selected yet; research reference only, per roadmap.md — never spliced into a listed instrument''s history.', 1, 50),
    ('XLC', 'Communication Services Select Sector SPDR Fund', 'sector_equity_etf', 'free', 'intrinio', NULL, 1, 60),
    ('XLY', 'Consumer Discretionary Select Sector SPDR Fund', 'sector_equity_etf', 'free', 'intrinio', NULL, 1, 61),
    ('XLP', 'Consumer Staples Select Sector SPDR Fund', 'sector_equity_etf', 'free', 'intrinio', NULL, 1, 62),
    ('XLE', 'Energy Select Sector SPDR Fund', 'sector_equity_etf', 'free', 'intrinio', NULL, 1, 63),
    ('XLF', 'Financial Select Sector SPDR Fund', 'sector_equity_etf', 'free', 'intrinio', NULL, 1, 64),
    ('XLV', 'Health Care Select Sector SPDR Fund', 'sector_equity_etf', 'free', 'intrinio', NULL, 1, 65),
    ('XLI', 'Industrial Select Sector SPDR Fund', 'sector_equity_etf', 'free', 'intrinio', NULL, 1, 66),
    ('XLB', 'Materials Select Sector SPDR Fund', 'sector_equity_etf', 'free', 'intrinio', NULL, 1, 67),
    ('XLRE', 'Real Estate Select Sector SPDR Fund', 'sector_equity_etf', 'free', 'intrinio', NULL, 1, 68),
    ('XLK', 'Technology Select Sector SPDR Fund', 'sector_equity_etf', 'free', 'intrinio', NULL, 1, 69),
    ('XLU', 'Utilities Select Sector SPDR Fund', 'sector_equity_etf', 'free', 'intrinio', NULL, 1, 70),
    ('AAPL', 'Apple Inc.', 'mega_cap_equity', 'free', 'intrinio', NULL, 1, 80),
    ('NVDA', 'NVIDIA Corporation', 'mega_cap_equity', 'free', 'intrinio', NULL, 1, 81),
    ('SMH', 'VanEck Semiconductor ETF', 'thematic_etf', 'free', 'intrinio', NULL, 1, 90),
    ('IGV', 'iShares Expanded Tech-Software Sector ETF', 'thematic_etf', 'free', 'intrinio', NULL, 1, 91)
ON CONFLICT(symbol) DO UPDATE SET
    name = excluded.name,
    category = excluded.category,
    tier = excluded.tier,
    production_provider_key = excluded.production_provider_key,
    notes = excluded.notes,
    sort_order = excluded.sort_order;

INSERT INTO readiness_milestones (
    milestone_key, name, description, sort_order
) VALUES
    (
        'first_real_regime', 'First real regime',
        'Replace the synthetic state fixture with one inspectable regime decision sourced from point-in-time macro data.',
        10
    ),
    (
        'real_selection_desk', 'Real selection and allocation desk',
        'Move from a governed investable universe through relative selection, symbol timing, portfolio risk, and cash expression.',
        20
    ),
    (
        'full_instrument_desk', 'Full instrument desk',
        'Add trustworthy option-market inputs and compare defined-risk expressions without making options mandatory for every view.',
        30
    ),
    (
        'research_shadow', 'Research and shadow readiness',
        'Require point-in-time portfolio evidence and repeated recoverable manual operation before automation.',
        40
    ),
    (
        'automation_execution', 'Automation and execution boundary',
        'Keep scheduling and broker execution visibly deferred until separately reviewed operating controls exist.',
        50
    )
ON CONFLICT(milestone_key) DO UPDATE SET
    name = excluded.name,
    description = excluded.description,
    sort_order = excluded.sort_order;

INSERT INTO readiness_gates (
    gate_key, milestone_key, name, layer, description,
    acceptance_criterion, evaluator_key, next_action, target_route, sort_order
) VALUES
    (
        'fred_provider_access', 'first_real_regime', 'FRED provider access', 'provider',
        'Prove that the credential currently resolved by this process is accepted by FRED.',
        'The current FRED credential has a non-expired healthy smoke verification that applies to the same credential revision and runtime identity.',
        'provider_access_fred',
        'Register or reverify the FRED key on the Credentials page.',
        '/operations/credentials', 10
    ),
    (
        'macro_pit_ingestion', 'first_real_regime', 'Point-in-time macro ingestion', 'data',
        'Land selected FRED/ALFRED observations in a non-demo dataset through the manual pipeline.',
        'A completed non-dry fetch stage and ready real FRED inventory refer to the same non-demo dataset snapshot with stored observations.',
        'macro_pit_ingestion',
        'Implement the paced FRED/ALFRED ingestion adapter, then run the fetch stage manually.',
        '/operations', 20
    ),
    (
        'macro_validation_seal', 'first_real_regime', 'Macro validation and dataset seal', 'validation',
        'Validate timestamps, source identity, completeness, units, freshness, and revision lineage before sealing inputs.',
        'A completed non-dry validation stage refers to an immutable, non-demo, real dataset snapshot.',
        'macro_validation_seal',
        'Implement validation, resolve every required defect, and seal the accepted macro dataset.',
        '/operations/data', 30
    ),
    (
        'real_regime_snapshot', 'first_real_regime', 'First real regime snapshot', 'state',
        'Compute and publish one real regime state with inspectable contributions and evidence.',
        'A completed regime stage publishes an immutable non-demo real desk snapshot containing at least one regime contribution and its timestamped evidence.',
        'real_regime_snapshot',
        'Implement the first regime model and publish its immutable decision snapshot.',
        '/', 40
    ),
    (
        'versioned_security_universe', 'real_selection_desk', 'Versioned security universe', 'universe',
        'Replace the hard-coded demo list with governed, point-in-time research universes.',
        'A sealed universe revision uses stable exposure, research-reference, and security IDs; point-in-time membership; explicit roles or cohorts; and recorded inclusion and exclusion reasons. DIA may be evaluated as a U.S.-equity sleeve candidate. A governed BTC/USD reference may drive digital-asset research, while IBIT is eligible only as a separately classified execution instrument from its actual availability date; BTC history must never be presented as pre-listing IBIT history or trades.',
        'versioned_security_universe',
        'Implement versioned universe definitions and membership provenance; do not expand the synthetic fixture as a substitute.',
        '/operations/data', 50
    ),
    (
        'real_market_history', 'real_selection_desk', 'Real market history and actions', 'data',
        'Provide bias-controlled price history and adjustment lineage for the governed universe.',
        'Ready real market-history inventory, stored bars, and corporate-action or adjustment lineage refer to the same immutable non-demo dataset.',
        'real_market_history',
        'Connect market/reference ingestion and validate prices, listings, delistings, and corporate actions.',
        '/operations/data', 60
    ),
    (
        'cross_sectional_selection', 'real_selection_desk', 'Cross-sectional candidate selection', 'selection',
        'Rank the eligible universe before applying any single-symbol timing decision.',
        'A completed factor stage publishes an immutable non-demo real snapshot with multiple ranked securities and timestamped factor values.',
        'cross_sectional_snapshot',
        'Implement one preregistered cross-sectional family, beginning with broad relative selection rather than symbol-by-symbol searching.',
        '/', 70
    ),
    (
        'symbol_time_series_confirmation', 'real_selection_desk', 'Single-symbol timing confirmation', 'timing',
        'Ask whether each selected candidate has a valid entry, exit, watch, or explicit no-signal state.',
        'Every ranked security in the qualifying real snapshot has a timestamped symbol-signal record; an explicit none state is valid evidence and does not manufacture a trade.',
        'symbol_timing_snapshot',
        'Implement the per-symbol time-series confirmation layer downstream of cross-sectional selection.',
        '/symbols', 80
    ),
    (
        'portfolio_risk_allocation', 'real_selection_desk', 'Portfolio exposure and risk allocation', 'portfolio',
        'Translate evidence into a coherent target after overlap, concentration, liquidity, and aggregate risk.',
        'A completed allocation stage publishes an immutable non-demo real snapshot with target net and gross exposure plus an inspectable risk-budget decision node.',
        'portfolio_allocation_snapshot',
        'Implement the exposure map, covariance and redundancy controls, risk budgets, and constrained allocation.',
        '/', 90
    ),
    (
        'cash_long_short_expression', 'real_selection_desk', 'Cash long/short expression', 'instrument',
        'Express portfolio deltas as legitimate cash long, short, reduce, hold, or no-trade outcomes before adding optional complexity.',
        'A completed instrument stage publishes an immutable non-demo real snapshot and has no unresolved required blocker on any persisted candidate; an explicit no-trade outcome is acceptable.',
        'cash_expression_snapshot',
        'Implement cash-equity expression and persist either eligible candidates or an explicit no-trade result.',
        '/', 100
    ),
    (
        'options_expression', 'full_instrument_desk', 'Options data and expression comparison', 'instrument',
        'Compare calls, puts, and defined-risk spreads only after the underlying target and risk budget exist.',
        'Ready real option-chain inventory and a completed instrument stage refer to non-demo immutable inputs; persisted option candidates have complete market data and no unresolved required blockers.',
        'options_expression_snapshot',
        'Connect licensed option history and quotes, then test entitlement, liquidity, Greeks, costs, and maximum-loss accounting.',
        '/operations/data', 110
    ),
    (
        'walk_forward_evidence', 'research_shadow', 'Walk-forward portfolio evidence', 'research',
        'Evaluate frozen strategy revisions with point-in-time inputs, costs, baselines, uncertainty, and portfolio-level outcomes.',
        'A completed research run references an immutable non-demo real dataset and records the required strategy diagnostics; a positive return is not itself the acceptance criterion.',
        'walk_forward_research',
        'Run the first version-locked point-in-time portfolio evaluation and persist its diagnostics and provenance.',
        '/operations/strategies', 120
    ),
    (
        'repeated_shadow_recovery', 'research_shadow', 'Repeated shadow runs and recovery', 'operations',
        'Prove that manual operation is reproducible, idempotent, restartable, observable, and recoverable.',
        'Repeated non-demo full runs have normalized input hashes, stage output references, locks, bounded retries, and a tested interrupted-run recovery record.',
        'shadow_recovery',
        'Add idempotency, run locking, stage resume, recovery tests, and a reviewed sequence of successful shadow runs.',
        '/operations', 130
    ),
    (
        'scheduling', 'automation_execution', 'Scheduling', 'automation',
        'Automation remains a policy decision after repeated manual reproducibility, not a shortcut around it.',
        'A separately reviewed scheduling gate defines calendars, alert ownership, timeouts, recovery, and safe disablement after shadow readiness passes.',
        'deferred_policy',
        'Keep scheduling disabled until the manual-shadow milestone is passed and a scheduling review is accepted.',
        '/operations', 140
    ),
    (
        'broker_execution_boundary', 'automation_execution', 'Broker execution boundary', 'execution',
        'Order placement is a distinct authorization and safety system, not another pipeline stage.',
        'A separately reviewed broker boundary covers authentication, account reconciliation, order intent, limits, duplicate prevention, acknowledgements, fills, kill switches, and operator authorization.',
        'deferred_policy',
        'Keep broker connectivity and order placement disabled until a separate execution design is explicitly authorized.',
        '/operations', 150
    )
ON CONFLICT(gate_key) DO UPDATE SET
    milestone_key = excluded.milestone_key,
    name = excluded.name,
    layer = excluded.layer,
    description = excluded.description,
    acceptance_criterion = excluded.acceptance_criterion,
    evaluator_key = excluded.evaluator_key,
    next_action = excluded.next_action,
    target_route = excluded.target_route,
    sort_order = excluded.sort_order;

INSERT INTO readiness_gate_dependencies (gate_key, dependency_gate_key) VALUES
    ('macro_pit_ingestion', 'fred_provider_access'),
    ('macro_validation_seal', 'macro_pit_ingestion'),
    ('real_regime_snapshot', 'macro_validation_seal'),
    ('versioned_security_universe', 'real_regime_snapshot'),
    ('real_market_history', 'versioned_security_universe'),
    ('cross_sectional_selection', 'real_market_history'),
    ('symbol_time_series_confirmation', 'cross_sectional_selection'),
    ('portfolio_risk_allocation', 'symbol_time_series_confirmation'),
    ('cash_long_short_expression', 'portfolio_risk_allocation'),
    ('options_expression', 'portfolio_risk_allocation'),
    ('walk_forward_evidence', 'cash_long_short_expression'),
    ('repeated_shadow_recovery', 'walk_forward_evidence'),
    ('scheduling', 'repeated_shadow_recovery'),
    ('broker_execution_boundary', 'scheduling')
ON CONFLICT(gate_key, dependency_gate_key) DO NOTHING;

INSERT INTO pipeline_definitions (
    pipeline_key, name, version, description, enabled, manual_only,
    created_at, updated_at
) VALUES (
    'daily_desk', 'Daily desk pipeline', '0.1.0',
    'Operator-triggered ingestion, validation, hierarchy evaluation, and immutable snapshot publication.',
    1, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
)
ON CONFLICT(pipeline_key) DO UPDATE SET
    name = excluded.name,
    version = excluded.version,
    description = excluded.description,
    manual_only = excluded.manual_only;

INSERT INTO pipeline_stage_definitions (
    pipeline_key, stage_key, label, description, stage_order,
    implementation_status, required_provider_keys_json
) VALUES
    ('daily_desk', 'preflight', 'Preflight', 'Check provider credentials, data inventory, and pipeline readiness.', 10, 'ready', '["fred"]'),
    ('daily_desk', 'fetch_data', 'Fetch data', 'Fetch point-in-time macro and market inputs into a new dataset snapshot.', 20, 'ready', '["fred"]'),
    ('daily_desk', 'validate_data', 'Validate data', 'Apply completeness, freshness, schema, and look-ahead checks.', 30, 'ready', '[]'),
    ('daily_desk', 'regime_filter', 'Regime filter', 'Classify state and compute regime evidence contributions.', 40, 'ready', '[]'),
    ('daily_desk', 'factor_engine', 'Factor engine', 'Score the eligible cross-section with current strategy versions.', 50, 'ready', '[]'),
    ('daily_desk', 'allocation_engine', 'Allocation engine', 'Translate state and factor evidence into bounded target exposure.', 60, 'ready', '[]'),
    ('daily_desk', 'instrument_engine', 'Instrument engine', 'Compare legitimate cash and defined-risk expressions without placing orders.', 70, 'ready', '[]'),
    ('daily_desk', 'publish_snapshot', 'Publish snapshot', 'Seal one internally consistent desk snapshot after every required gate passes.', 80, 'scaffolded', '[]')
ON CONFLICT(pipeline_key, stage_key) DO UPDATE SET
    label = excluded.label,
    description = excluded.description,
    stage_order = excluded.stage_order,
    implementation_status = excluded.implementation_status,
    required_provider_keys_json = excluded.required_provider_keys_json;

CREATE INDEX IF NOT EXISTS idx_snapshots_as_of ON desk_snapshots(as_of DESC);
CREATE INDEX IF NOT EXISTS idx_symbols_snapshot_rank ON symbols(snapshot_id, rank);
CREATE INDEX IF NOT EXISTS idx_bars_security_time ON symbol_bars(dataset_snapshot_id, security_id, time);
CREATE INDEX IF NOT EXISTS idx_events_security_time ON symbol_events(dataset_snapshot_id, security_id, time);
CREATE INDEX IF NOT EXISTS idx_candidates_snapshot_order ON position_candidates(snapshot_id, sort_order);
CREATE INDEX IF NOT EXISTS idx_verifications_provider_checked
    ON provider_verifications(provider_key, checked_at DESC);
CREATE INDEX IF NOT EXISTS idx_data_assets_status ON data_assets(status, provider_key);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_requested
    ON pipeline_runs(pipeline_key, requested_at DESC);
CREATE INDEX IF NOT EXISTS idx_strategy_status ON strategies(status, family);
CREATE INDEX IF NOT EXISTS idx_research_runs_strategy
    ON research_runs(strategy_key, strategy_version, started_at DESC);
