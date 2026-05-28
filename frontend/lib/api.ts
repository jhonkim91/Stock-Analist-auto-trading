export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type ApiStatus = "idle" | "loading" | "ok" | "error";

export type AsyncState<T> = {
  status: ApiStatus;
  message: string;
  data?: T;
};

export type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };
export type JsonRecord = Record<string, JsonValue>;
export type PortfolioWeighting = "equal_risk" | "equal_weight";

export type DataStatus = {
  symbol_count: number;
  daily_ohlcv_count: number;
  index_ohlcv_count: number;
  sector_ohlcv_count: number;
  fundamentals_count: number;
  indicator_snapshot_count: number;
  screen_results_count: number;
  reports_count: number;
  backtest_runs_count: number;
  orders_count: number;
  latest_trade_date: string | null;
  latest_indicator_date: string | null;
  latest_screen_date: string | null;
};

export type MarketRegime = {
  benchmark: string;
  trade_date: string;
  regime: string;
  market_score: number;
  close_vs_200dma: number | null;
  sma50_vs_200dma: number | null;
  weekly_close: number | null;
  weekly_sma30: number | null;
  weekly_sma30_slope: number | null;
  breadth_regime?: string;
  breadth_score?: number | null;
  breadth_score_available?: boolean;
  breadth_advance_decline_ratio?: number | null;
  breadth_advance_decline_available?: boolean;
  breadth_52w_high_low_ratio?: number | null;
  breadth_52w_high_low_available?: boolean;
  breadth_ma50_participation?: number | null;
  breadth_ma50_participation_available?: boolean;
};

export type MarketSessionWindow = {
  venue: string;
  name: string;
  session_kind?: string;
  order_acceptance_start?: string | null;
  trading_start?: string | null;
  trading_end?: string | null;
  order_acceptance_end?: string | null;
  current_session_allows_preview?: boolean;
  [key: string]: JsonValue | undefined;
};

export type MarketSession = {
  venue: string;
  session: string;
  session_kind: string;
  is_trading_day: boolean;
  is_trading_session: boolean;
  current_session_allows_preview: boolean;
  current_session: MarketSessionWindow | null;
  next_session: MarketSessionWindow | null;
  allowed_preview_sessions?: Record<string, boolean>;
  operational_layer?: JsonRecord;
  reason_codes: string[];
  trade_date?: string | null;
  as_of?: string | null;
};

export type MarketSessionWindows = {
  venue: string;
  session_windows: MarketSessionWindow[];
};

export type ScreenerResult = {
  trade_date: string;
  symbol: string;
  name: string;
  strategy_name: string;
  strategy_tag?: string;
  passed: boolean;
  grade: string;
  total_score: number;
  entry_price: number | null;
  stop_price: number | null;
  target_price: number | null;
  reward_risk_ratio: number | null;
  position_size: number;
  reason_summary: string;
  pass_flags_json: Record<string, boolean>;
  failed_conditions_json: string[];
  score_details_json: Record<string, number | string | null>;
  risk_details_json: Record<string, number | string | null>;
  triggered_conditions: string[];
  score_breakdown: JsonRecord;
  risk_flags: JsonRecord;
  data_quality_flags: JsonRecord;
  metadata: JsonRecord;
  risk_metadata: JsonRecord;
  explanation: string;
  rationale: string;
  pass_flags?: Record<string, boolean>;
  failed_conditions?: string[];
  risk_per_share?: number | null;
  position_notional?: number | null;
};

export type StrategyMetadata = {
  name: string;
  display_name: string;
  description: string;
  is_default: boolean;
  is_available: boolean;
  required_fields: string[];
  limitations: string[];
};

export type ReportItem = {
  id: string;
  report_id: string;
  report_date: string;
  report_type: string;
  title: string;
  model_version: string;
  strategy_version: string;
  data_timestamp: string;
  created_at: string;
  version: string;
  path: string;
};

export type ReportDetail = ReportItem & {
  markdown: string;
};

export type BacktestMetrics = {
  total_return: number;
  cagr: number;
  max_drawdown: number;
  win_rate: number;
  avg_win: number;
  avg_loss: number;
  profit_factor: number | null;
  expectancy: number;
  average_holding_days: number;
  trade_count: number;
  exposure: number;
  portfolio_turnover: number;
  average_active_positions: number;
  rebalance_count: number;
  portfolio_constructor_used: boolean;
  portfolio_selection_mode: string;
  portfolio_top_n: number;
  portfolio_max_positions: number;
  portfolio_weighting: string;
  [key: string]: number | string | boolean | null;
};

export type BacktestRunRequest = {
  strategy_name: string;
  start_date?: string | null;
  end_date?: string | null;
  initial_equity?: number | null;
  top_n?: number;
  max_positions?: number;
  rebalance_frequency?: "daily" | "weekly" | "monthly";
  weighting?: PortfolioWeighting;
  allow_overlap_positions?: boolean;
};

export type BacktestRun = {
  run_id: string;
  strategy_name: string;
  config_hash: string;
  start_date: string | null;
  end_date: string | null;
  metrics: BacktestMetrics;
  created_at: string;
};

export type StrategyValidationMetricSummary = {
  summary_source: string;
  error: string | null;
  trade_count: number | null;
  win_rate: number | null;
  total_return: number | null;
  max_drawdown: number | null;
};

export type StrategyValidationDelta = {
  baseline: string;
  trade_count_delta: number | null;
  win_rate_delta: number | null;
  total_return_delta: number | null;
  max_drawdown_delta: number | null;
};

export type StrategyValidationRow = {
  strategy_name: string;
  screener: {
    strategy_name: string;
    evaluated_count: number;
    pass_count: number;
    pass_rate: number | null;
    evaluated_trading_days: number;
    window_trading_days: number;
    window_start: string | null;
    window_end: string | null;
  };
  backtest: StrategyValidationMetricSummary;
  delta: StrategyValidationDelta;
  validation?: {
    walk_forward?: JsonRecord;
    overfitting?: {
      pbo?: JsonRecord;
      deflated_sharpe_ratio?: JsonRecord;
    };
    attribution?: JsonRecord;
  };
};

export type WalkForwardStrategySummary = {
  strategy_name: string;
  calculated: boolean;
  status: string;
  reason: string | null;
  summary?: {
    oos_window_count?: number | null;
    oos_total_return?: number | null;
    oos_avg_return?: number | null;
    [key: string]: JsonValue | undefined;
  } | null;
};

export type WalkForwardFrameworkSummary = {
  status: string;
  metric: string;
  calculated: boolean;
  reason: string | null;
  train_window_trading_days: number;
  test_window_trading_days: number;
  step_trading_days: number;
  rebalance_frequency?: string | null;
  strategy_count: number;
  calculated_strategy_count: number;
  unavailable_strategy_count: number;
  strategy_summaries: WalkForwardStrategySummary[];
};

export type OverfittingValidationMetric = {
  calculated: boolean;
  value: number | string;
  reason?: string | null;
  method?: string;
  probability_of_backtest_overfitting?: number | string;
  deflated_sharpe_ratio?: number | string;
  input_shape?: JsonRecord;
};

export type StrategyValidationFramework = {
  walk_forward: WalkForwardFrameworkSummary;
  overfitting: {
    pbo: OverfittingValidationMetric;
    deflated_sharpe_ratio: OverfittingValidationMetric;
  };
  attribution?: JsonRecord;
  trade_ledger_schema?: JsonRecord;
};

export type StrategyValidationSummary = {
  lookback_days: number;
  generated_at: string;
  window: {
    requested_trading_days: number;
    available_trading_days: number;
    start_date: string | null;
    end_date: string | null;
    basis: string;
  };
  screener_window: {
    requested_trading_days: number;
    available_trading_days: number;
    window_start: string | null;
    window_end: string | null;
    basis: string;
  };
  baseline: {
    status: string;
    run_id: string | null;
    snapshot_supplied: boolean;
  };
  report: {
    format: string;
    path: string;
    filename: string;
    bytes?: number;
    kind?: string;
  };
  validation_documentation_format: JsonRecord;
  validation_framework: StrategyValidationFramework;
  strategies: StrategyValidationRow[];
};

export type BrokerStatus = {
  mode: string;
  broker_mode: string;
  can_submit: boolean;
  preview_only: boolean;
  live_trading_enabled: boolean;
  paper_trading_enabled: boolean;
  token_issued: boolean;
  network_call_performed: boolean;
  adapter_selected: boolean;
  adapter_name: string;
  adapter_capability_checked: boolean;
  adapter_order_call_performed: boolean;
  adapter_network_call_performed: boolean;
  reason: string;
};

export type PaperRiskGate = {
  decision: "deny" | string;
  passed: boolean;
  reason_codes: string[];
};

export type PaperKillSwitch = {
  blocking: boolean;
  reason_codes: string[];
};

export type PaperCounts = {
  paper_orders_count: number;
  paper_fills_count: number;
  paper_positions_count: number;
  paper_audit_events_count: number;
  paper_portfolio_snapshots_count?: number;
  synthetic_positions_count?: number;
  paper_bot_runs_count?: number;
  paper_bot_decisions_count?: number;
  orders_count: number;
};

export type PaperStatus = {
  mode: string;
  enabled: boolean;
  configured_enabled: boolean;
  can_create: boolean;
  can_simulate_fills: boolean;
  preview_only: boolean;
  paper_order_supported: boolean;
  fill_simulator_supported: boolean;
  cancel_supported: boolean;
  paper_order_created: boolean;
  live_order_created: boolean;
  broker_order_created: boolean;
  fill_created: boolean;
  position_changed: boolean;
  token_issued: boolean;
  token_cache_enabled: boolean;
  network_call_performed: boolean;
  adapter_order_call_performed: boolean;
  adapter_network_call_performed: boolean;
  audit_persistence_enabled: boolean;
  paper_tables_write_enabled: boolean;
  reason: string;
  kill_switch: PaperKillSwitch;
  risk_gate: PaperRiskGate;
  counts: PaperCounts;
};

export type PaperPreviewRequest = {
  symbol: string;
  side: "buy" | "sell";
  qty: number;
  limit_price?: number | null;
  stop_price?: number | null;
  strategy_tag?: string | null;
  venue?: string | null;
  as_of?: string | null;
};

export type PaperPreviewResponse = PaperStatus & {
  preview_id: string;
  symbol: string;
  side: string;
  qty: number;
  limit_price: number | null;
  stop_price: number | null;
  strategy_tag: string | null;
};

export type PaperSubmitRequest = PaperPreviewRequest & {
  confirm: boolean;
  idempotency_key?: string | null;
};

export type PaperOrder = {
  paper_order_id: string;
  created_ts: string | null;
  updated_ts: string | null;
  symbol: string;
  side: string;
  qty: number;
  filled_qty: number;
  remaining_qty: number;
  order_type: string;
  limit_price: number | null;
  stop_price: number | null;
  status: string;
  idempotency_key: string | null;
  request_hash: string | null;
  strategy_tag: string | null;
  live_order_created: boolean;
  broker_order_created: boolean;
  network_call_performed: boolean;
  broker_order_id: string | null;
  broker_order_status: string | null;
  submitted_at: string | null;
  canceled_at: string | null;
};

export type PaperOrderListResponse = {
  ok: boolean;
  orders: PaperOrder[];
  counts: PaperCounts;
  live_order_created: boolean;
  broker_order_created: boolean;
  network_call_performed: boolean;
};

export type PaperSubmitResponse = {
  ok: boolean;
  status: string;
  paper_order_created: boolean;
  live_order_created: boolean;
  broker_order_created: boolean;
  network_call_performed: boolean;
  reason: string;
  reason_codes: string[];
  risk_gate: PaperRiskGate;
  request_hash: string;
  idempotency_key: string | null;
  order?: PaperOrder;
  counts: PaperCounts;
};

export type PaperCancelRequest = {
  paper_order_id: string;
  confirm: boolean;
  idempotency_key?: string | null;
};

export type PaperCancelResponse = {
  ok: boolean;
  status: string;
  cancel_supported: boolean;
  order_cancelled: boolean;
  paper_order_id: string;
  paper_order_created: boolean;
  live_order_created: boolean;
  broker_order_created: boolean;
  network_call_performed: boolean;
  reason: string;
  reason_codes: string[];
  request_hash: string;
  idempotency_key: string | null;
  counts: PaperCounts;
};

export type PaperFill = {
  paper_fill_id: string;
  paper_order_id: string | null;
  symbol: string;
  side: string;
  qty: number;
  price: number;
  fill_ts: string | null;
  fill_source: string;
  commission: number;
  slippage_bps: number;
  live_order_created: boolean;
  broker_order_created: boolean;
  network_call_performed: boolean;
  broker_fill_id: string | null;
  broker_order_id: string | null;
  broker_fill_ts: string | null;
};

export type PaperFillsResponse = {
  ok: boolean;
  fills: PaperFill[];
  counts: PaperCounts;
  source: string;
  live_order_created: boolean;
  broker_order_created: boolean;
  network_call_performed: boolean;
};

export type PaperPosition = {
  id: number;
  symbol: string;
  strategy_tag: string | null;
  qty: number;
  avg_price: number;
  realized_pnl: number;
  last_price: number | null;
  market_value: number | null;
  unrealized_pnl: number | null;
  updated_at: string | null;
  broker_position_key: string | null;
  account_alias: string | null;
  broker_synced_at: string | null;
};

export type PaperPositionsResponse = {
  ok: boolean;
  positions: PaperPosition[];
  counts: PaperCounts;
  source: string;
  synthetic_positions_included: boolean;
  live_order_created: boolean;
  broker_order_created: boolean;
  network_call_performed: boolean;
};

export type PaperPortfolioSnapshot = {
  snapshot_id: string;
  snapshot_ts: string | null;
  account_alias: string | null;
  cash_balance: number;
  buying_power: number;
  market_value: number;
  total_equity: number;
  unrealized_pnl: number;
  realized_pnl: number;
  source: string;
  status: string;
  created_at: string | null;
};

export type PaperPositionsSummary = {
  source: string;
  count: number;
  total_qty: number;
  market_value: number;
  unrealized_pnl: number;
};

export type PaperHolding = {
  symbol: string;
  name: string;
  quantity: number;
  orderable_quantity: number;
  average_price: number | null;
  purchase_amount: number | null;
  current_price: number | null;
  evaluation_amount: number | null;
  profit_loss_amount: number | null;
  profit_loss_rate: number | null;
};

export type PaperAccountSummary = {
  cash_total: number | null;
  securities_evaluation_amount: number | null;
  total_evaluation_amount: number | null;
  net_asset_amount: number | null;
  total_purchase_amount: number | null;
  total_stock_evaluation_amount: number | null;
  total_profit_loss_amount: number | null;
  previous_total_asset_amount: number | null;
  asset_change_amount: number | null;
  asset_change_rate: number | null;
};

export type PaperPortfolioResponse = {
  ok: boolean;
  source: string;
  snapshot: PaperPortfolioSnapshot | null;
  positions_summary: PaperPositionsSummary;
  holdings?: PaperHolding[];
  account_summary?: PaperAccountSummary;
  kis_balance?: JsonRecord;
  counts: PaperCounts;
  separation_contract: JsonRecord;
  reason: string | null;
  live_order_created: boolean;
  broker_order_created: boolean;
  network_call_performed: boolean;
};

export type PaperSyncScope = "orders" | "fills" | "positions" | "portfolio" | "all";

export type PaperSyncResponse = {
  ok: boolean;
  status: string;
  scope: PaperSyncScope | string;
  supported_scopes: string[];
  sync_performed: boolean;
  synced_scopes?: string[];
  reason: string;
  reason_codes: string[];
  counts: PaperCounts;
  dedupe: JsonRecord;
  live_order_created: boolean;
  broker_order_created: boolean;
  network_call_performed: boolean;
  synthetic_positions_touched: boolean;
};

export type PaperBotSessionStatus = {
  session_checked: boolean;
  session_check_passed: boolean;
  session_state?: string | null;
  session?: string | null;
  trade_date?: string | null;
  reason_codes: string[];
};

export type PaperBotStep = {
  name: string;
  status: string;
  reason: string;
};

export type PaperBotDecision = {
  symbol: string;
  strategy_tag: string;
  action: string;
  total_score: number | null;
  qty: number;
  limit_price: number | null;
  stop_price: number | null;
  target_price: number | null;
  risk_passed: boolean;
  reason_codes: string[];
  paper_order_id: string | null;
};

export type PaperBotStatus = {
  enabled: boolean;
  scheduler_enabled: boolean;
  auto_submit: boolean;
  kill_switch_enabled: boolean;
  mode: string;
  supported_modes: string[];
  loop_allowed: boolean;
  auto_submit_allowed: boolean;
  session: PaperBotSessionStatus;
  session_check_passed: boolean;
  loop_interval_seconds: number;
  max_candidates: number;
  default_strategy: string;
  sync_enabled: boolean;
  notification_enabled: boolean;
  report_generation_enabled: boolean;
  reason_codes: string[];
  live_order_created: boolean;
  broker_order_created: boolean;
  network_call_performed: boolean;
  counts: PaperCounts;
};

export type PaperBotRunRequest = {
  auto_submit?: boolean | null;
};

export type PaperBotRunResponse = {
  ok: boolean;
  status: string;
  run_id?: string;
  run_once: boolean;
  mode: string;
  auto_submit_requested: boolean;
  auto_submit_allowed: boolean;
  paper_order_submitted: boolean;
  submitted_count: number;
  decision_count: number;
  decisions: PaperBotDecision[];
  live_order_created: boolean;
  broker_order_created: boolean;
  network_call_performed: boolean;
  steps: PaperBotStep[];
  reason_codes: string[];
  session: PaperBotSessionStatus;
  counts: PaperCounts;
};

export type PaperBotStopResponse = {
  ok: boolean;
  status: string;
  mode: string;
  scheduler_enabled: boolean;
  loop_allowed: boolean;
  reason_codes: string[];
  live_order_created: boolean;
  broker_order_created: boolean;
  network_call_performed: boolean;
};

export type PortfolioRisk = {
  account_equity: number;
  risk_per_trade: number;
  max_daily_loss: number;
  open_positions_count: number;
  total_position_notional: number;
  available_risk_budget: number;
  warnings: string[];
  latest_signal_date: string | null;
  proposed_positions: number;
  proposed_notional: number;
  broker_mode: string;
};

export type ImportResult = {
  ok: boolean;
  inserted_count: number;
  updated_count: number;
  skipped_count: number;
  error_count: number;
};

export type DataSourceConfig = {
  source_id: string;
  provider_type: string;
  provider_name: string;
  enabled: boolean;
  network_enabled: boolean;
  manual_preview_only: boolean;
  requires_api_key: boolean;
  read_only_enabled: boolean;
  paper_trading_enabled: boolean;
  live_trading_enabled: boolean;
  websocket_enabled: boolean;
  supported_markets: string[];
  market: string;
  venue: string;
  timezone: string;
  zero_volume_policy: string;
  unknown_symbol_policy: string;
  max_rows: number;
  max_date_range_days: number;
  timeout_seconds: number;
  retry_count: number;
};

export type ReadOnlyProviderStatus = {
  source_id: string;
  provider_type: string;
  provider_name: string;
  asset_scope: string[];
  capabilities: string[];
  enabled: boolean;
  network_enabled: boolean;
  read_only_enabled: boolean;
  manual_preview_only: boolean;
  requires_api_key: boolean;
  supported_markets: string[];
  market: string;
  venue: string;
  status: string;
  blocked_reason: string;
  reason_codes: string[];
  network_call_performed: boolean;
  token_issued: boolean;
  token_cache_enabled: boolean;
  adapter_order_call_performed: boolean;
  adapter_network_call_performed: boolean;
  credential_fields_exposed: boolean;
};

export type SourceFreshness = {
  source_id: string;
  provider_type: string;
  provider_name: string;
  source_kind: string;
  enabled: boolean;
  read_only_enabled: boolean;
  network_enabled: boolean;
  asset_scope: string[];
  status: string;
  freshness_status: string;
  reason_code: string;
  latest_confirmed_at: string | null;
  latest_confirmed_trade_date: string | null;
  trading_date_lag: number | null;
};

export type DataQualitySummary = {
  market: string;
  venue: string;
  latest_trade_date: string | null;
  row_counts: {
    daily_ohlcv: number;
    symbol_master: number;
    active_symbols: number;
    trading_calendar: number;
    import_runs: number;
    confirmed_import_runs: number;
    data_quality_checks: number;
  };
  source_freshness: SourceFreshness[];
  missing_rows: {
    basis: string;
    lookback_trading_dates: number;
    date_count: number;
    active_symbol_count: number;
    expected_rows: number;
    actual_rows: number;
    missing_rows_estimate: number;
    coverage_ratio: number | null;
    latest_trade_date_missing_symbol_count: number;
    missing_symbol_sample: string[];
  };
  duplicate_summary: {
    physical_duplicate_groups: number;
    physical_duplicate_rows: number;
    physical_duplicate_sample: Array<{
      trade_date: string;
      symbol: string;
      venue: string;
      row_count: number;
    }>;
    quality_duplicate_code_counts: Record<string, number>;
  };
  quality_counts: {
    total: number;
    by_severity: Record<string, number>;
    top_check_codes: Array<{
      check_code: string;
      count: number;
    }>;
  };
  safety_counts: {
    orders_count: number;
    paper_orders_count: number;
    paper_fills_count: number;
    paper_positions_count: number;
    paper_audit_events_count: number;
    token_issued: boolean;
    token_cache_enabled: boolean;
    network_call_performed: boolean;
    adapter_order_call_performed: boolean;
    adapter_network_call_performed: boolean;
  };
};

export type DataPreviewRow = {
  row_number: number;
  trade_date: string;
  symbol: string;
  open: number;
  high: number;
  low: number;
  close: number;
  adj_close: number;
  volume: number;
  turnover_value: number;
  market: string;
  venue: string;
  provider: string;
  quality_flags: string[];
};

export type ImportRun = {
  run_id: string;
  source_id: string;
  provider_type: string;
  original_filename: string;
  file_hash: string;
  status: string;
  can_confirm: boolean;
  total_rows: number;
  valid_rows: number;
  error_count: number;
  warning_count: number;
  info_count: number;
  inserted_count: number;
  updated_count: number;
  skipped_count: number;
  created_at: string;
  confirmed_at: string | null;
  preview_rows: DataPreviewRow[];
  staged_rows?: DataPreviewRow[];
  source_config_snapshot: Record<string, unknown>;
  provider_metadata: {
    provider_name?: string;
    source_id?: string;
    provider_mode?: "mock" | "network" | string;
    data_origin?: string;
    provider_symbol?: string | null;
    internal_symbol?: string;
    raw_row_count?: number;
    normalized_row_count?: number;
    start_date?: string;
    end_date?: string;
    timezone?: string;
    raw_hash?: string;
    network_enabled?: boolean;
    fetch_started_at?: string | null;
    fetch_finished_at?: string | null;
  };
};

export type DataQualityCheck = {
  id: number;
  run_id: string;
  row_number: number | null;
  symbol: string | null;
  trade_date: string | null;
  field: string | null;
  check_code: string;
  severity: "error" | "warning" | "info";
  message: string;
  created_at: string;
};

export type KisStatus = {
  source_id: string;
  enabled: boolean;
  network_enabled: boolean;
  read_only_enabled: boolean;
  app_key_configured: boolean;
  app_secret_configured: boolean;
  token_cache_enabled: boolean;
  broker_enabled: boolean;
  websocket_enabled: boolean;
  disabled_reason: string;
};

export type NotificationChannelStatus = {
  alias: string;
  type: string;
  enabled: boolean;
  mode: string;
  dry_run: boolean;
  configured: boolean;
  credential_fields: Record<string, boolean>;
  can_dispatch: boolean;
  reason_codes: string[];
  secrets_redacted: boolean;
};

export type NotificationStatus = {
  enabled: boolean;
  default_dry_run: boolean;
  config_status: string;
  reason_codes: string[];
  network_delivery_allowed: boolean;
  secrets_redacted: boolean;
  supported_events: string[];
  channels: NotificationChannelStatus[];
};

export type NotificationTestRequest = {
  channel_alias?: string | null;
  message: string;
  dry_run: boolean;
};

export type NotificationTestResponse = {
  ok: boolean;
  status: string;
  attempted: boolean;
  delivered: boolean;
  dry_run: boolean;
  message_length?: number;
  payload_shape?: JsonRecord;
  channel?: NotificationChannelStatus;
  reason_codes: string[];
  secrets_redacted?: boolean;
};

export type ReportNotifyRequest = {
  mode: "summary" | "summary_and_file";
  channel_alias?: string | null;
  dry_run?: boolean | null;
};

export type ReportNotifyResponse = {
  ok: boolean;
  status: string;
  delivered: boolean;
  report_id: string;
  mode: string;
  channel_alias: string | null;
  dry_run: boolean;
  message_count: number;
  message_lengths: number[];
  max_message_length: number;
  reason_codes: string[];
  secrets_redacted: boolean;
  report_preserved: boolean;
  attachment?: JsonRecord;
  payload_shape?: JsonRecord;
  portfolio_snapshot?: JsonRecord;
  notification_event_id?: string;
  attempted?: boolean;
  channel_limits?: JsonRecord;
};

export type SettingsPayload = Record<string, unknown>;

export type ActionResponse = Record<string, unknown>;

export async function callApi<T>(path: string, init?: RequestInit): Promise<T> {
  const isFormData = init?.body instanceof FormData;
  const headers = new Headers(init?.headers);
  if (!isFormData && init?.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers
  });
  const contentType = response.headers.get("content-type") ?? "";
  const data = contentType.includes("application/json") ? ((await response.json()) as T & { detail?: string }) : undefined;
  if (!response.ok) {
    const detail = data && "detail" in data ? data.detail : undefined;
    throw new Error(typeof detail === "string" ? detail : `HTTP ${response.status}`);
  }
  return data as T;
}

export function summarizeResults(results: ScreenerResult[]) {
  return {
    total: results.length,
    passed: results.filter((result) => result.passed).length,
    strategies: Array.from(new Set(results.map((result) => result.strategy_name))).sort(),
    latestDate: results[0]?.trade_date ?? null
  };
}

export const numberFormatter = new Intl.NumberFormat("ko-KR");
export const percentFormatter = new Intl.NumberFormat("ko-KR", {
  maximumFractionDigits: 2,
  style: "percent"
});

export function formatNumber(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-";
  }
  return new Intl.NumberFormat("ko-KR", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits
  }).format(value);
}

export function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-";
  }
  return percentFormatter.format(value);
}

export function reportMarkdownUrl(reportId: string): string {
  return `${API_BASE}/api/reports/${encodeURIComponent(reportId)}/markdown`;
}
