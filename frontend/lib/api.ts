export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type ApiStatus = "idle" | "loading" | "ok" | "error";

export type AsyncState<T> = {
  status: ApiStatus;
  message: string;
  data?: T;
};

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
  pass_flags?: Record<string, boolean>;
  failed_conditions?: string[];
  risk_per_share?: number | null;
  position_notional?: number | null;
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
  [key: string]: number | string | null;
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

export type BrokerStatus = {
  mode: string;
  broker_mode: string;
  can_submit: boolean;
  live_trading_enabled: boolean;
  paper_trading_enabled: boolean;
  reason: string;
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
