PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

INSERT INTO schema_metadata (key, value) VALUES ('schema_version', '4')
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
    source_manifest_json TEXT NOT NULL DEFAULT '{}'
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
    next_review_at TEXT
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
    verification_ttl_seconds INTEGER NOT NULL DEFAULT 604800
        CHECK (
            verification_ttl_seconds > 0
            AND verification_ttl_seconds >= verification_cooldown_seconds
        ),
    sort_order INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
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

-- Research results remain DB-indexed. Files are optional, reproducible output
-- artifacts identified by repository-relative path and checksum; Markdown is
-- never an engine input or the canonical result store.
CREATE TABLE IF NOT EXISTS research_runs (
    research_run_id TEXT PRIMARY KEY,
    strategy_key TEXT NOT NULL,
    strategy_version TEXT NOT NULL,
    dataset_snapshot_id TEXT REFERENCES dataset_snapshots(id),
    code_commit TEXT,
    parameters_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL CHECK (
        status IN ('queued', 'running', 'completed', 'failed', 'cancelled')
    ),
    started_at TEXT,
    finished_at TEXT,
    summary TEXT NOT NULL,
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
    verification_ttl_seconds,
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
    'fred_v2', 900, 604800, 10, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
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
    ('daily_desk', 'fetch_data', 'Fetch data', 'Fetch point-in-time macro and market inputs into a new dataset snapshot.', 20, 'scaffolded', '["fred"]'),
    ('daily_desk', 'validate_data', 'Validate data', 'Apply completeness, freshness, schema, and look-ahead checks.', 30, 'scaffolded', '[]'),
    ('daily_desk', 'regime_filter', 'Regime filter', 'Classify state and compute regime evidence contributions.', 40, 'scaffolded', '[]'),
    ('daily_desk', 'factor_engine', 'Factor engine', 'Score the eligible cross-section with current strategy versions.', 50, 'scaffolded', '[]'),
    ('daily_desk', 'allocation_engine', 'Allocation engine', 'Translate state and factor evidence into bounded target exposure.', 60, 'scaffolded', '[]'),
    ('daily_desk', 'instrument_engine', 'Instrument engine', 'Compare legitimate cash and defined-risk expressions without placing orders.', 70, 'scaffolded', '[]'),
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
