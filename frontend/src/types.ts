export type Nullable<T> = T | null;
export type Scalar = string | number | boolean | null;

export interface Provenance {
  as_of?: Nullable<string>;
  observed_at?: Nullable<string>;
  available_at?: Nullable<string>;
  ingested_at?: Nullable<string>;
  source_name?: Nullable<string>;
  source_version?: Nullable<string>;
  source_key?: Nullable<string>;
  created_at?: Nullable<string>;
}

export interface Snapshot extends Provenance {
  id: string;
  as_of: string;
  status: string;
  mode: string;
  title?: Nullable<string>;
  subtitle?: Nullable<string>;
  disclaimer?: Nullable<string>;
  data_classification?: Nullable<string>;
  is_live?: Nullable<boolean>;
  is_demo?: Nullable<boolean>;
  immutable?: Nullable<boolean>;
  dataset_snapshot_id?: Nullable<string>;
}

export interface PhilosophySection {
  key: string;
  title: string;
  body?: Nullable<string>;
  principle?: Nullable<string>;
}

export interface Philosophy {
  eyebrow?: Nullable<string>;
  title?: Nullable<string>;
  summary?: Nullable<string>;
  formula?: Nullable<string>;
  principles?: Nullable<string[]>;
  sections?: Nullable<PhilosophySection[]>;
}

export interface EvidenceItem {
  label: string;
  value?: Nullable<Scalar>;
  detail?: Nullable<string>;
  source?: Nullable<string>;
}

export interface RegimeFilter extends Provenance {
  name: string;
  value?: Nullable<Scalar>;
  threshold?: Nullable<Scalar>;
  status?: Nullable<string>;
  explanation?: Nullable<string>;
}

export interface WeightDatum {
  name: string;
  value?: Nullable<number>;
  unit?: Nullable<string>;
}

export interface ContributionDatum {
  name: string;
  value?: Nullable<number>;
  unit?: Nullable<string>;
  direction?: Nullable<string>;
  explanation?: Nullable<string>;
  evidence?: Nullable<EvidenceItem[]>;
}

export interface Regime extends Provenance {
  label?: Nullable<string>;
  confidence?: Nullable<number>;
  percentile_rank?: Nullable<number>;
  as_of?: Nullable<string>;
  summary?: Nullable<string>;
  filters?: Nullable<RegimeFilter[]>;
  weights?: Nullable<WeightDatum[]>;
  contributions?: Nullable<ContributionDatum[]>;
}

export interface Recommendation extends Provenance {
  posture?: Nullable<string>;
  summary?: Nullable<string>;
  confidence?: Nullable<number>;
  current_net_exposure?: Nullable<number>;
  target_net_exposure?: Nullable<number>;
  delta_net_exposure?: Nullable<number>;
  current_gross_exposure?: Nullable<number>;
  target_gross_exposure?: Nullable<number>;
  delta_gross_exposure?: Nullable<number>;
  current_weight?: Nullable<number>;
  target_weight?: Nullable<number>;
  delta_weight?: Nullable<number>;
  actionability?: Nullable<string>;
  change_summary?: Nullable<string>;
  rationale?: Nullable<string[]>;
  invalidation?: Nullable<string[]>;
  next_review_at?: Nullable<string>;
  status?: Nullable<string>;
}

export interface DecisionNode {
  id: string;
  parent_id?: Nullable<string>;
  layer?: Nullable<string>;
  type?: Nullable<string>;
  label: string;
  description?: Nullable<string>;
  summary?: Nullable<string>;
  value?: Nullable<Scalar>;
  value_unit?: Nullable<string>;
  current_value?: Nullable<number>;
  target_value?: Nullable<number>;
  delta_value?: Nullable<number>;
  weight?: Nullable<number>;
  contribution?: Nullable<number>;
  confidence?: Nullable<number>;
  status?: Nullable<string>;
  constraints?: Nullable<string[]>;
  evidence?: Nullable<EvidenceItem[]>;
}

export interface DecisionEdge {
  id?: Nullable<string>;
  source?: Nullable<string>;
  target?: Nullable<string>;
  from?: Nullable<string>;
  to?: Nullable<string>;
  label?: Nullable<string>;
  relation?: Nullable<string>;
  weight?: Nullable<number>;
  rationale?: Nullable<string>;
}

export interface DecisionGraph {
  nodes?: Nullable<DecisionNode[]>;
  edges?: Nullable<DecisionEdge[]>;
  observations?: Nullable<DecisionObservation[]>;
}

export interface DecisionObservation extends Provenance {
  id: string;
  node_id?: Nullable<string>;
  label: string;
  value?: Nullable<Scalar>;
  unit?: Nullable<string>;
  status?: Nullable<string>;
  detail?: Nullable<string>;
}

export interface MetricDatum extends Provenance {
  key: string;
  label: string;
  value?: Nullable<number>;
  display_value?: Nullable<string>;
  unit?: Nullable<string>;
  status?: Nullable<string>;
  description?: Nullable<string>;
  period?: Nullable<string>;
}

export interface BacktestSummary extends Provenance {
  title?: Nullable<string>;
  label?: Nullable<string>;
  status?: Nullable<string>;
  summary?: Nullable<string>;
  methodology?: Nullable<string>;
  is_available?: Nullable<boolean>;
  period_start?: Nullable<string>;
  period_end?: Nullable<string>;
  information_cutoff_policy?: Nullable<string>;
  metrics?: Nullable<MetricDatum[]>;
}

export interface PositionLeg {
  instrument?: Nullable<string>;
  symbol?: Nullable<string>;
  instrument_type?: Nullable<string>;
  side?: Nullable<string>;
  action?: Nullable<string>;
  quantity?: Nullable<number>;
  ratio?: Nullable<number>;
  strike?: Nullable<number>;
  expiration?: Nullable<string>;
  expiry?: Nullable<string>;
  option_type?: Nullable<string>;
  bid?: Nullable<number>;
  ask?: Nullable<number>;
  mid?: Nullable<number>;
  multiplier?: Nullable<number>;
  dte?: Nullable<number>;
  open_interest?: Nullable<number>;
  volume?: Nullable<number>;
  implied_volatility?: Nullable<number>;
  delta?: Nullable<number>;
  gamma?: Nullable<number>;
  theta?: Nullable<number>;
  vega?: Nullable<number>;
}

export interface GreekSet {
  delta?: Nullable<number | { value: Nullable<number>; unit?: Nullable<string> }>;
  gamma?: Nullable<number | { value: Nullable<number>; unit?: Nullable<string> }>;
  vega?: Nullable<number | { value: Nullable<number>; unit?: Nullable<string> }>;
  theta?: Nullable<number | { value: Nullable<number>; unit?: Nullable<string> }>;
  rho?: Nullable<number | { value: Nullable<number>; unit?: Nullable<string> }>;
}

export interface PositionBlocker {
  key?: Nullable<string>;
  label: string;
  detail?: Nullable<string>;
  required?: Nullable<boolean>;
  resolved?: Nullable<boolean>;
}

export interface PositionCandidate extends Provenance {
  id: string;
  symbol: string;
  name?: Nullable<string>;
  side?: Nullable<string>;
  structure_type?: Nullable<string>;
  conviction?: Nullable<number>;
  action?: Nullable<string>;
  current_weight?: Nullable<number>;
  target_weight?: Nullable<number>;
  delta_weight?: Nullable<number>;
  allocation_basis?: Nullable<string>;
  confidence?: Nullable<number>;
  max_loss?: Nullable<number>;
  max_profit?: Nullable<number>;
  breakeven_low?: Nullable<number>;
  breakeven_high?: Nullable<number>;
  net_debit?: Nullable<number>;
  net_credit?: Nullable<number>;
  net_debit_credit?: Nullable<number>;
  cost_estimate?: Nullable<number>;
  cost_unit?: Nullable<string>;
  horizon?: Nullable<string>;
  status?: Nullable<string>;
  actionability?: Nullable<string>;
  market_data_complete?: Nullable<boolean>;
  input_completeness_scope?: Nullable<string>;
  blockers?: Nullable<Array<string | PositionBlocker>>;
  rationale?: Nullable<string[]>;
  risks?: Nullable<string[]>;
  legs?: Nullable<PositionLeg[]>;
  greeks?: Nullable<GreekSet>;
}

export interface DataSource extends Provenance {
  id?: Nullable<string>;
  name: string;
  dataset?: Nullable<string>;
  key?: Nullable<string>;
  category?: Nullable<string>;
  is_live?: Nullable<boolean>;
  status?: Nullable<string>;
  freshness?: Nullable<string>;
  coverage?: Nullable<number | string>;
  missingness?: Nullable<number>;
  detail?: Nullable<string>;
  latency_seconds?: Nullable<number>;
  source_url?: Nullable<string>;
}

export interface DeskResponse {
  snapshot: Snapshot;
  philosophy?: Nullable<Philosophy>;
  regime?: Nullable<Regime>;
  recommendation?: Nullable<Recommendation>;
  decision_graph?: Nullable<DecisionGraph>;
  metrics?: Nullable<MetricDatum[]>;
  backtest?: Nullable<BacktestSummary>;
  position_candidates?: Nullable<PositionCandidate[]>;
  data_sources?: Nullable<DataSource[]>;
}

export interface MatrixColumn {
  key: string;
  label: string;
  unit?: Nullable<string>;
  description?: Nullable<string>;
  weight?: Nullable<number>;
}

export interface MatrixRow {
  symbol: string;
  name?: Nullable<string>;
  sector?: Nullable<string>;
  values: Record<string, Nullable<number>>;
  composite_score?: Nullable<number>;
  conviction?: Nullable<number>;
  rank?: Nullable<number>;
  status?: Nullable<string>;
  summary?: Nullable<string>;
  quality?: Nullable<Record<string, Nullable<string>>>;
  provenance?: Nullable<Record<string, Nullable<Provenance>>>;
}

export interface MatrixLegend {
  key?: Nullable<string>;
  legend_key?: Nullable<string>;
  label?: Nullable<string>;
  low_label?: Nullable<string>;
  neutral_label?: Nullable<string>;
  high_label?: Nullable<string>;
  description?: Nullable<string>;
}

export interface CrossSectionResponse {
  snapshot: Snapshot;
  dimensions?: Nullable<{ columns?: Nullable<MatrixColumn[]> }>;
  rows?: Nullable<MatrixRow[]>;
  legend?: Nullable<MatrixLegend | MatrixLegend[]>;
  data_sources?: Nullable<DataSource[]>;
}

export interface SymbolSummary {
  symbol: string;
  name?: Nullable<string>;
  sector?: Nullable<string>;
  status?: Nullable<string>;
  recommendation?: Nullable<string>;
  rank?: Nullable<number>;
  asset_type?: Nullable<string>;
  exchange?: Nullable<string>;
  currency?: Nullable<string>;
  summary?: Nullable<string>;
  last_price?: Nullable<number>;
  price_as_of?: Nullable<string>;
  composite_score?: Nullable<number>;
  freshness_status?: Nullable<string>;
  freshness_as_of?: Nullable<string>;
  candidate_count?: Nullable<number>;
  watchlist?: Nullable<boolean>;
}

export interface SymbolsResponse {
  snapshot?: Nullable<Snapshot>;
  symbols?: Nullable<SymbolSummary[]>;
  scope?: Nullable<string>;
}

export interface PriceBar extends Provenance {
  time: string | number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: Nullable<number>;
}

export interface SymbolEvent extends Provenance {
  id?: Nullable<string>;
  time: string | number;
  type: string;
  label: string;
  price?: Nullable<number>;
  detail?: Nullable<string>;
  status?: Nullable<string>;
}

export interface SymbolSignal extends Provenance {
  status: "none" | "watch" | "candidate" | "active" | "exited" | "invalidated" | string;
  direction?: Nullable<"bullish" | "bearish" | "neutral" | string>;
  strength?: Nullable<number>;
  label?: Nullable<string>;
  rationale?: Nullable<string>;
  source_node_id?: Nullable<string>;
}

export interface HierarchyTraceItem {
  id?: Nullable<string>;
  layer?: Nullable<string>;
  level?: Nullable<string>;
  node_id?: Nullable<string>;
  parent_node_id?: Nullable<string>;
  parent_label?: Nullable<string>;
  incoming_edges?: Nullable<HierarchyTraceIncoming[]>;
  label: string;
  value?: Nullable<Scalar>;
  contribution?: Nullable<number>;
  confidence?: Nullable<number>;
  explanation?: Nullable<string>;
  evidence?: Nullable<EvidenceItem[]>;
  current_value?: Nullable<number>;
  target_value?: Nullable<number>;
  delta_value?: Nullable<number>;
  value_unit?: Nullable<string>;
  constraints?: Nullable<string[]>;
}

export interface HierarchyTraceIncoming {
  from_node_id: string;
  from_label?: Nullable<string>;
  relation?: Nullable<string>;
  weight?: Nullable<number>;
  rationale?: Nullable<string>;
}

export interface SymbolDetailResponse extends Provenance {
  snapshot?: Nullable<Snapshot>;
  symbol: string;
  name?: Nullable<string>;
  sector?: Nullable<string>;
  industry?: Nullable<string>;
  asset_type?: Nullable<string>;
  exchange?: Nullable<string>;
  summary?: Nullable<string>;
  last_price?: Nullable<number>;
  price_as_of?: Nullable<string>;
  composite_score?: Nullable<number>;
  rank?: Nullable<number>;
  freshness?: Nullable<{ status?: Nullable<string>; as_of?: Nullable<string>; summary?: Nullable<string> }>;
  status?: Nullable<string>;
  currency?: Nullable<string>;
  bars?: Nullable<PriceBar[]>;
  events?: Nullable<SymbolEvent[]>;
  current_signal?: Nullable<SymbolSignal>;
  hierarchy_trace?: Nullable<HierarchyTraceItem[]>;
  recommendation?: Nullable<Recommendation>;
  metrics?: Nullable<MetricDatum[]>;
  position_candidates?: Nullable<PositionCandidate[]>;
  data_sources?: Nullable<DataSource[]>;
}

export interface HealthResponse {
  status?: Nullable<string>;
  data_status?: Nullable<string>;
  database?: Nullable<string>;
  version?: Nullable<string>;
  snapshot?: Nullable<Snapshot>;
}

export interface AdminProviderCounts {
  total: number;
  configured: number;
  healthy: number;
}

export interface AdminDataCounts {
  assets: number;
  ready: number;
  stale: number;
  missing: number;
  partial?: Nullable<number>;
  invalid?: Nullable<number>;
  invalid_assets?: Nullable<number>;
  invalid_symbols?: Nullable<number>;
}

export interface AdminStrategyCounts {
  total: number;
  active: number;
  watching: number;
  retired: number;
}

export interface PipelineStageDefinition {
  key: string;
  label: string;
  description?: Nullable<string>;
  order?: Nullable<number>;
  implementation_status?: Nullable<string>;
  required_provider_keys?: Nullable<string[]>;
}

export interface PipelineStageRun {
  key: string;
  order?: Nullable<number>;
  status?: Nullable<string>;
  started_at?: Nullable<string>;
  finished_at?: Nullable<string>;
  records_read?: Nullable<number>;
  records_written?: Nullable<number>;
  message?: Nullable<string>;
  error_code?: Nullable<string>;
}

export interface PipelineDefinition {
  key: string;
  name: string;
  version?: Nullable<string>;
  description?: Nullable<string>;
  enabled?: Nullable<boolean>;
  manual_only: boolean;
  stages?: Nullable<PipelineStageDefinition[]>;
}

export interface PipelineRun {
  id: string;
  status?: Nullable<string>;
  dry_run?: Nullable<boolean>;
  pipeline_key?: Nullable<string>;
  pipeline_version?: Nullable<string>;
  trigger_type?: Nullable<string>;
  requested_at?: Nullable<string>;
  started_at?: Nullable<string>;
  finished_at?: Nullable<string>;
  dataset_snapshot_id?: Nullable<string>;
  desk_snapshot_id?: Nullable<string>;
  summary?: Nullable<string>;
  stages?: Nullable<PipelineStageRun[]>;
}

export interface PipelineResponse {
  definition: PipelineDefinition;
  latest_run?: Nullable<PipelineRun>;
}

export type ProductReadinessStatus =
  | "passed"
  | "action_required"
  | "blocked"
  | "failed"
  | "deferred";

export type ProductReadinessEvidenceStatus =
  | "qualifying"
  | "non_qualifying"
  | "missing";

export interface ProductReadinessEvidence {
  kind: string;
  record_id?: Nullable<string>;
  status: ProductReadinessEvidenceStatus;
  observed_at?: Nullable<string>;
  summary: string;
}

export interface ProductReadinessGate {
  key: string;
  milestone_key: string;
  name: string;
  layer: string;
  description: string;
  status: ProductReadinessStatus;
  acceptance_criterion: string;
  evaluator_key: string;
  next_action: string;
  target_route: string;
  sort_order: number;
  dependencies: string[];
  blocked_by: string[];
  evidence: ProductReadinessEvidence[];
}

export interface ProductReadinessMilestone {
  key: string;
  name: string;
  description: string;
  status: ProductReadinessStatus;
  sort_order: number;
  gates_total: number;
  gates_passed: number;
  current_gate_key?: Nullable<string>;
}

export interface ProductReadinessSummary {
  milestones_total: number;
  milestones_passed: number;
  gates_total: number;
  gates_passed: number;
  current_gate_key?: Nullable<string>;
  current_action?: Nullable<string>;
  target_route?: Nullable<string>;
}

export interface ProductReadiness {
  summary: ProductReadinessSummary;
  milestones?: Nullable<ProductReadinessMilestone[]>;
  gates?: Nullable<ProductReadinessGate[]>;
}

export interface AdminOverviewResponse {
  as_of?: Nullable<string>;
  manual_only: boolean;
  providers: AdminProviderCounts;
  data: AdminDataCounts;
  pipeline: PipelineResponse;
  strategies: AdminStrategyCounts;
  readiness?: Nullable<ProductReadiness>;
}

export interface CredentialStatus {
  label?: Nullable<string>;
  configured: boolean;
  source?: Nullable<"keyring" | "environment" | string>;
  managed?: Nullable<boolean>;
  environment_variable?: Nullable<string>;
  status?: Nullable<string>;
  last_verified_at?: Nullable<string>;
  verification_expires_at?: Nullable<string>;
  verification_status?: Nullable<string>;
  cooldown_seconds?: Nullable<number>;
  cooldown_remaining_seconds?: Nullable<number>;
  verification_ttl_seconds?: Nullable<number>;
  verification_policy_refresh_required?: Nullable<boolean>;
}

export interface ProviderVerification extends Provenance {
  id?: Nullable<string>;
  checked_at?: Nullable<string>;
  expires_at?: Nullable<string>;
  status?: Nullable<string>;
  verified_at?: Nullable<string>;
  detail?: Nullable<string>;
  message?: Nullable<string>;
  latency_ms?: Nullable<number>;
  http_status?: Nullable<number>;
  error_code?: Nullable<string>;
  credential_source?: Nullable<string>;
}

export interface ProviderLastVerification extends ProviderVerification {
  current: boolean;
  applies_to_credential: boolean;
  expired: boolean;
  future_dated?: Nullable<boolean>;
  effective_expires_at?: Nullable<string>;
}

export interface AdminProvider {
  key: string;
  name: string;
  category?: Nullable<string>;
  description?: Nullable<string>;
  enabled?: Nullable<boolean>;
  required?: Nullable<boolean>;
  documentation_url?: Nullable<string>;
  signup_url?: Nullable<string>;
  terms_url?: Nullable<string>;
  attribution_notice?: Nullable<string>;
  instructions?: Nullable<string>;
  capabilities?: Nullable<string[]>;
  credential: CredentialStatus;
  verification?: Nullable<ProviderLastVerification>;
  last_verification?: Nullable<ProviderLastVerification>;
}

export interface ProviderRoadmapSummary {
  planned_accounts: number;
  supported_accounts: number;
  verified_accounts: number;
  registrations_needed_now: number;
  verifications_needed_now: number;
  future_accounts_planned: number;
  capabilities_total: number;
  capabilities_ingestion_ready: number;
}

export interface ProviderRoadmapCoverage {
  key: string;
  name?: Nullable<string>;
  role?: Nullable<string>;
  integration_status?: Nullable<string>;
  note?: Nullable<string>;
}

export interface ProviderRoadmapAccount {
  key: string;
  operator_provider_key?: Nullable<string>;
  name: string;
  category?: Nullable<string>;
  role?: Nullable<string>;
  integration_status?: Nullable<string>;
  access_status?: Nullable<string>;
  required_for_first_slice: boolean;
  registration_available: boolean;
  verification_policy_refresh_required?: Nullable<boolean>;
  documentation_url?: Nullable<string>;
  signup_url?: Nullable<string>;
  pricing_url?: Nullable<string>;
  terms_url?: Nullable<string>;
  guidance?: Nullable<string>;
  licensing_note?: Nullable<string>;
  capabilities?: Nullable<ProviderRoadmapCoverage[]>;
}

export interface DataCapabilityRoadmap {
  key: string;
  name: string;
  category?: Nullable<string>;
  description?: Nullable<string>;
  requirement_level?: Nullable<string>;
  unlocks?: Nullable<string[]>;
  integration_status?: Nullable<string>;
  ingestion_ready: boolean;
  providers?: Nullable<ProviderRoadmapCoverage[]>;
}

export interface ProviderRoadmap {
  summary: ProviderRoadmapSummary;
  next_action?: Nullable<string>;
  accounts?: Nullable<ProviderRoadmapAccount[]>;
  capabilities?: Nullable<DataCapabilityRoadmap[]>;
}

export interface EngineMode {
  mode: "pilot" | "production";
  updated_at?: Nullable<string>;
  updated_reason?: Nullable<string>;
}

export interface StagingSymbol {
  symbol: string;
  name: string;
  category: string;
  tier: "free" | "paid";
  production_provider_key?: Nullable<string>;
  production_provider_name?: Nullable<string>;
  notes?: Nullable<string>;
  active: boolean;
}

export interface UniverseResponse {
  summary: {
    total: number;
    active: number;
    by_category: Record<string, number>;
  };
  symbols: StagingSymbol[];
}

export interface ProvidersResponse {
  as_of?: Nullable<string>;
  providers?: Nullable<AdminProvider[]>;
  roadmap?: Nullable<ProviderRoadmap>;
  engine_mode?: Nullable<EngineMode>;
}

export interface AdminDataAsset {
  key: string;
  provider_key?: Nullable<string>;
  label: string;
  kind?: Nullable<string>;
  symbol?: Nullable<string>;
  frequency?: Nullable<string>;
  classification?: Nullable<string>;
  row_count?: Nullable<number>;
  period_start?: Nullable<string>;
  period_end?: Nullable<string>;
  last_observation_at?: Nullable<string>;
  last_fetched_at?: Nullable<string>;
  max_age_seconds?: Nullable<number>;
  age_seconds?: Nullable<number>;
  freshness?: Nullable<string>;
  status?: Nullable<string>;
  detail?: Nullable<string>;
}

export interface AdminDataResponse {
  as_of?: Nullable<string>;
  summary: AdminDataCounts;
  assets?: Nullable<AdminDataAsset[]>;
  symbols?: Nullable<AdminSymbolData[]>;
  scope?: Nullable<string>;
  symbol_search?: Nullable<AdminSymbolSearch>;
}

export interface AdminSymbolData {
  symbol: string;
  name?: Nullable<string>;
  row_count?: Nullable<number>;
  period_start?: Nullable<string>;
  period_end?: Nullable<string>;
  last_observation_at?: Nullable<string>;
  last_fetched_at?: Nullable<string>;
  classification?: Nullable<string>;
  freshness?: Nullable<string>;
  status?: Nullable<string>;
  dataset_snapshot_id?: Nullable<string>;
  watchlist?: Nullable<boolean>;
  category?: Nullable<string>;
}

export interface AdminSymbolSearch {
  q?: Nullable<string>;
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface StrategyDecay {
  value?: Nullable<number>;
  unit?: Nullable<string>;
  status?: Nullable<string>;
  as_of?: Nullable<string>;
}

export interface StrategySummary {
  key: string;
  name: string;
  family?: Nullable<string>;
  summary?: Nullable<string>;
  status?: Nullable<string>;
  version?: Nullable<string>;
  verification_status?: Nullable<string>;
  code_reference?: Nullable<string>;
  next_review_at?: Nullable<string>;
  last_checked_at?: Nullable<string>;
  decay?: Nullable<StrategyDecay>;
  added_at?: Nullable<string>;
  retired_at?: Nullable<string>;
  public_spec_url?: Nullable<string>;
}

export interface StrategyDiagnostic extends Provenance {
  metric_key: string;
  label?: Nullable<string>;
  value?: Nullable<Scalar>;
  unit?: Nullable<string>;
  status?: Nullable<string>;
  window_label?: Nullable<string>;
  description?: Nullable<string>;
}

export interface StrategyComponent {
  component_key: string;
  name?: Nullable<string>;
  component_type?: Nullable<string>; // 'computed' | 'manual_override'
  roles?: Nullable<string[]>;
  code_reference?: Nullable<string>;
  base_weight?: Nullable<Scalar>;
  status?: Nullable<string>;
  verification_status?: Nullable<string>;
  decay_rate?: Nullable<Scalar>;
  override_value?: Nullable<Scalar>;
  override_set_by?: Nullable<string>;
  override_set_at?: Nullable<string>;
  override_reason?: Nullable<string>;
  next_review_at?: Nullable<string>;
}

export interface StrategyVersion {
  version: string;
  created_at?: Nullable<string>;
  thesis?: Nullable<string>;
  expected_edge?: Nullable<string>;
  change_summary?: Nullable<string>;
  parameters?: Nullable<Record<string, unknown>>;
  code_reference?: Nullable<string>;
  promoted_at?: Nullable<string>;
  next_review_at?: Nullable<string>;
  verification_status?: Nullable<string>;
  diagnostics?: Nullable<StrategyDiagnostic[]>;
  components?: Nullable<StrategyComponent[]>;
}

export interface StrategyLifecycleEvent {
  event_id?: Nullable<string>;
  occurred_at?: Nullable<string>;
  from_status?: Nullable<string>;
  to_status?: Nullable<string>;
  reason?: Nullable<string>;
  strategy_version?: Nullable<string>;
}

export interface ResearchArtifact {
  artifact_key?: Nullable<string>;
  relative_path?: Nullable<string>;
  media_type?: Nullable<string>;
  sha256?: Nullable<string>;
  size_bytes?: Nullable<number>;
  curated?: Nullable<boolean>;
  created_at?: Nullable<string>;
}

export interface StrategyResearchRun {
  id: string;
  strategy_version?: Nullable<string>;
  dataset_snapshot_id?: Nullable<string>;
  code_commit?: Nullable<string>;
  parameters?: Nullable<Record<string, unknown>>;
  status?: Nullable<string>;
  started_at?: Nullable<string>;
  finished_at?: Nullable<string>;
  summary?: Nullable<string>;
  artifacts?: Nullable<ResearchArtifact[]>;
}

export interface StrategyDetail extends StrategySummary {
  retirement_reason?: Nullable<string>;
  versions?: Nullable<StrategyVersion[]>;
  lifecycle?: Nullable<StrategyLifecycleEvent[]>;
  research_runs?: Nullable<StrategyResearchRun[]>;
}

export interface StrategiesResponse {
  summary: AdminStrategyCounts;
  strategies?: Nullable<StrategySummary[]>;
}

export interface StrategyDetailResponse {
  strategy: StrategyDetail;
}

export interface FactorSignificanceResult {
  factor_key: string;
  symbol: string;
  sample_size: number;
  correlation?: Nullable<number>;
  p_value?: Nullable<number>;
  adjusted_p_value?: Nullable<number>;
  significant: boolean;
  direction: "positive" | "negative" | "inconclusive" | string;
  status: "ok" | "insufficient_data" | string;
}

export interface FactorSignificanceRun {
  run_id: string;
  dataset_snapshot_id?: Nullable<string>;
  method: string;
  forward_horizon_days: number;
  correction_method: string;
  alpha: number;
  min_samples: number;
  factor_count: number;
  symbol_count: number;
  test_count: number;
  significant_count: number;
  summary: string;
  started_at?: Nullable<string>;
  finished_at?: Nullable<string>;
  results?: Nullable<FactorSignificanceResult[]>;
}

export interface FactorSignificanceRunResponse {
  run: FactorSignificanceRun;
}

export interface FactorCorrelationPair {
  key_a: string;
  key_b: string;
  correlation: number;
  flagged_redundant: boolean;
}

export interface SignalValidationRun {
  run_id: string;
  strategy_key: string;
  strategy_version?: Nullable<string>;
  dataset_snapshot_id?: Nullable<string>;
  summary: string;
  started_at?: Nullable<string>;
  finished_at?: Nullable<string>;
  factor_correlations: FactorCorrelationPair[];
  effective_number_of_bets?: Nullable<number>;
  factor_count?: Nullable<number>;
}

export interface SignalValidationRunResponse {
  run: SignalValidationRun;
}

export interface StrategyBacktestRun {
  run_id: string;
  strategy_key: string;
  strategy_version?: Nullable<string>;
  dataset_snapshot_id?: Nullable<string>;
  summary: string;
  started_at?: Nullable<string>;
  finished_at?: Nullable<string>;
  cagr?: Nullable<number>;
  annualized_volatility?: Nullable<number>;
  sharpe_ratio?: Nullable<number>;
  max_drawdown?: Nullable<number>;
  calmar_ratio?: Nullable<number>;
  portfolio_turnover?: Nullable<number>;
}

export interface StrategyBacktestRunResponse {
  run: StrategyBacktestRun;
}

export interface ResearchCatalogMetric {
  metric_key: string;
  category: string;
  granularity: "component" | "ensemble" | "strategy" | "desk" | string;
  label: string;
  unit?: Nullable<string>;
  description: string;
  applicable_families: string[];
  has_data: boolean;
}

export interface ResearchMetricCatalogResponse {
  metrics: ResearchCatalogMetric[];
}
