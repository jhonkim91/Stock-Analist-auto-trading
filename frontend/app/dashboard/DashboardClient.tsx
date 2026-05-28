"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  callApi,
  formatNumber,
  formatPercent,
  type ActionResponse,
  type AsyncState,
  type BacktestRun,
  type BrokerStatus,
  type DataStatus,
  type MarketRegime,
  type ScreenerResult,
  type StrategyMetadata,
  summarizeResults
} from "../../lib/api";

const loadingState = <T,>(message: string): AsyncState<T> => ({ status: "loading", message });
const idleState = <T,>(message: string): AsyncState<T> => ({ status: "idle", message });

const actionLabels = {
  seed: "Seed Sample Data",
  indicators: "Recompute Indicators",
  screener: "Run Screener",
  report: "Generate Daily Report"
} as const;

type ActionKey = keyof typeof actionLabels;

function stateFromSettled<T>(result: PromiseSettledResult<T>, emptyMessage: string): AsyncState<T> {
  if (result.status === "fulfilled") {
    return { status: "ok", message: "조회 완료", data: result.value };
  }
  return { status: "error", message: result.reason instanceof Error ? result.reason.message : emptyMessage };
}

function formatMaybeNumber(value: number | null | undefined, digits = 2) {
  return typeof value === "number" && Number.isFinite(value) ? formatNumber(value, digits) : "-";
}

function formatMaybePercent(value: number | null | undefined) {
  return typeof value === "number" && Number.isFinite(value) ? formatPercent(value) : "-";
}

function KpiCard({ label, sub, tone, value }: { label: string; sub?: string; tone?: "pos" | "neg" | "muted"; value: React.ReactNode }) {
  return (
    <article className="dashboardMetricCard">
      <div className="metric-label">{label}</div>
      <div className={`metric-value ${tone ?? ""}`}>{value}</div>
      {sub ? <div className={`metric-sub ${tone ?? "muted"}`}>{sub}</div> : null}
    </article>
  );
}

function StatRow({ label, tone, value }: { label: string; tone?: "pos" | "neg" | "muted"; value: React.ReactNode }) {
  return (
    <div className="stat-row">
      <span className="stat-k">{label}</span>
      <span className={tone ?? ""}>{value}</span>
    </div>
  );
}

function PlayIcon() {
  return (
    <svg aria-hidden="true" className="buttonIcon" viewBox="0 0 24 24">
      <path d="m8 5 11 7-11 7Z" />
    </svg>
  );
}

/** 목업의 Dashboard 첫 화면 구조를 유지하면서 기존 API 상태와 preview-only 안전값을 표시한다. */
export default function DashboardClient() {
  const [health, setHealth] = useState<AsyncState<ActionResponse>>(loadingState("API 연결 확인 중"));
  const [dataStatus, setDataStatus] = useState<AsyncState<DataStatus>>(loadingState("데이터 상태 조회 중"));
  const [regime, setRegime] = useState<AsyncState<MarketRegime>>(loadingState("시장 국면 조회 중"));
  const [screenerResults, setScreenerResults] = useState<AsyncState<ScreenerResult[]>>(loadingState("스크리너 조회 중"));
  const [latestBacktest, setLatestBacktest] = useState<AsyncState<BacktestRun[]>>(loadingState("백테스트 조회 중"));
  const [broker, setBroker] = useState<AsyncState<BrokerStatus>>(loadingState("브로커 상태 조회 중"));
  const [strategyCatalog, setStrategyCatalog] = useState<StrategyMetadata[]>([]);
  const [selectedStrategyName, setSelectedStrategyName] = useState("");
  const [actionStates, setActionStates] = useState<Record<ActionKey, AsyncState<ActionResponse>>>({
    seed: idleState("대기"),
    indicators: idleState("대기"),
    screener: idleState("대기"),
    report: idleState("대기")
  });

  const screenerSummary = useMemo(() => summarizeResults(screenerResults.data ?? []), [screenerResults.data]);
  const latestBacktestRun = latestBacktest.data?.[0];
  const latestActionMessage = Object.values(actionStates).find((state) => state.status === "loading" || state.status === "error")?.message;

  const loadOverview = useCallback(async (showLoading = true) => {
    if (showLoading) {
      setHealth(loadingState("API 연결 확인 중"));
      setDataStatus(loadingState("데이터 상태 조회 중"));
      setRegime(loadingState("시장 국면 조회 중"));
      setScreenerResults(loadingState("스크리너 조회 중"));
      setLatestBacktest(loadingState("백테스트 조회 중"));
      setBroker(loadingState("브로커 상태 조회 중"));
    }

    const [healthResult, dataResult, regimeResult, screenerResult, backtestResult, brokerResult] = await Promise.allSettled([
      callApi<ActionResponse>("/health"),
      callApi<DataStatus>("/api/data/status"),
      callApi<MarketRegime>("/api/market/regime"),
      callApi<ScreenerResult[]>("/api/screener/results?limit=100"),
      callApi<BacktestRun[]>("/api/backtest/runs?limit=1"),
      callApi<BrokerStatus>("/api/broker/status")
    ]);

    setHealth(stateFromSettled(healthResult, "API 연결 실패"));
    setDataStatus(stateFromSettled(dataResult, "데이터 상태 없음"));
    setRegime(stateFromSettled(regimeResult, "시장 국면 없음"));
    setScreenerResults(stateFromSettled(screenerResult, "스크리너 결과 없음"));
    setLatestBacktest(stateFromSettled(backtestResult, "백테스트 없음"));
    setBroker(stateFromSettled(brokerResult, "브로커 상태 없음"));
  }, []);

  const loadStrategies = useCallback(async () => {
    try {
      const data = await callApi<StrategyMetadata[]>("/api/screener/strategies");
      setStrategyCatalog(data);
      setSelectedStrategyName((current) => current || data.find((strategy) => strategy.is_default)?.name || data[0]?.name || "");
    } catch {
      setStrategyCatalog([]);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadOverview(false);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadOverview]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadStrategies();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadStrategies]);

  async function runAction(key: ActionKey, path: string, body: object) {
    setActionStates((prev) => ({ ...prev, [key]: loadingState("실행 중") }));
    try {
      const data = await callApi<ActionResponse>(path, { method: "POST", body: JSON.stringify(body) });
      setActionStates((prev) => ({ ...prev, [key]: { status: "ok", message: "성공", data } }));
      await loadOverview(false);
    } catch (error) {
      setActionStates((prev) => ({
        ...prev,
        [key]: { status: "error", message: error instanceof Error ? error.message : "실행 실패" }
      }));
    }
  }

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <svg aria-hidden="true" className="pageTitleIcon" viewBox="0 0 24 24">
            <rect height="6" width="6" x="4" y="4" />
            <rect height="6" width="6" x="14" y="4" />
            <rect height="6" width="6" x="4" y="14" />
            <rect height="6" width="6" x="14" y="14" />
          </svg>
          <h1>Dashboard</h1>
        </div>
        <div className="topbar-actions">
          <select value={selectedStrategyName} onChange={(event) => setSelectedStrategyName(event.target.value)} aria-label="strategy_name">
            {strategyCatalog.map((strategy) => (
              <option key={strategy.name} value={strategy.name}>
                {strategy.name}
              </option>
            ))}
          </select>
          <button type="button" className="primary" onClick={() => runAction("screener", "/api/screener/run", {})}>
            <PlayIcon />
            <span>
              Run
              <br />
              Screener
            </span>
          </button>
        </div>
      </header>

      <section className="dashboardContent" title={latestActionMessage ?? health.message}>
        <section className="dashboardKpiGrid" aria-label="Dashboard KPI summary">
          <KpiCard label="API 상태" value={<span className={`bdg ${health.status === "ok" ? "bdg-ok" : "bdg-warn"}`}>{health.status}</span>} sub={health.status === "ok" ? "healthy" : health.message} />
          <KpiCard label="데이터 rows" value={formatNumber(dataStatus.data?.daily_ohlcv_count)} sub={`${dataStatus.data?.latest_trade_date ?? "-"} 기준`} />
          <KpiCard label="스크리너 pass" value={`${formatNumber(screenerSummary.passed)} / ${formatNumber(screenerSummary.total)}`} sub="오늘 기준" tone={screenerSummary.passed > 0 ? "pos" : "muted"} />
          <KpiCard label="orders_count" value={formatNumber(dataStatus.data?.orders_count)} sub="safety closed" tone="pos" />
        </section>

        <section className="dashboardSplit">
          <article>
            <div className="sectionHeader">
              <h2>시장 국면 (regime)</h2>
              <span className={`bdg ${regime.data?.regime === "bear" ? "bdg-fail" : "bdg-ok"}`}>{regime.data?.regime ?? "loading"}</span>
            </div>
            <StatRow label="regime" value={regime.data?.regime ?? "-"} tone={regime.data?.regime === "bear" ? "neg" : "pos"} />
            <StatRow label="market_score" value={formatMaybeNumber(regime.data?.market_score)} />
            <StatRow label="benchmark" value={regime.data?.benchmark ?? "-"} tone="muted" />
            <StatRow label="trade_date" value={regime.data?.trade_date ?? "-"} tone="muted" />
            <StatRow label="close_vs_200dma" value={formatMaybePercent(regime.data?.close_vs_200dma)} tone="pos" />
            <StatRow label="sma50_vs_200dma" value={formatMaybePercent(regime.data?.sma50_vs_200dma)} tone="pos" />
          </article>

          <article>
            <div className="sectionHeader">
              <h2>최신 백테스트</h2>
              <span className="muted">{latestBacktestRun?.strategy_name ?? "not_available"}</span>
            </div>
            <StatRow label="total_return" value={formatMaybePercent(latestBacktestRun?.metrics.total_return)} tone={(latestBacktestRun?.metrics.total_return ?? 0) >= 0 ? "pos" : "neg"} />
            <StatRow label="cagr" value={formatMaybePercent(latestBacktestRun?.metrics.cagr)} tone={(latestBacktestRun?.metrics.cagr ?? 0) >= 0 ? "pos" : "neg"} />
            <StatRow label="max_drawdown" value={formatMaybePercent(latestBacktestRun?.metrics.max_drawdown)} tone="neg" />
            <StatRow label="win_rate" value={formatMaybePercent(latestBacktestRun?.metrics.win_rate)} tone="pos" />
            <StatRow label="trade_count" value={formatNumber(latestBacktestRun?.metrics.trade_count)} />
            <Link className="textLink mockLink" href="/backtest">
              Backtest 페이지로 →
            </Link>
          </article>
        </section>

        <section>
          <div className="sec-lbl">빠른 실행</div>
          <div className="actionList" aria-label="Quick backend actions">
            <button type="button" onClick={() => runAction("seed", "/api/data/seed", {})}>
              <span className="action-icon seed" aria-hidden="true">
                <svg viewBox="0 0 24 24">
                  <ellipse cx="12" cy="6" rx="6" ry="2.5" />
                  <path d="M6 6v8c0 1.4 2.7 2.5 6 2.5s6-1.1 6-2.5V6" />
                  <path d="M9 12h6" />
                  <path d="M15 10l2 2-2 2" />
                </svg>
              </span>
              <span className="action-name">Seed Sample Data</span>
              <span className="action-desc">테스트 데이터 삽입</span>
            </button>
            <button type="button" onClick={() => runAction("indicators", "/api/indicators/recompute", {})}>
              <span className="action-icon calc" aria-hidden="true">
                <svg viewBox="0 0 24 24">
                  <rect height="14" rx="2" width="12" x="6" y="5" />
                  <path d="M9 9h6" />
                  <path d="M9 13h.01" />
                  <path d="M12 13h.01" />
                  <path d="M15 13h.01" />
                  <path d="M9 16h.01" />
                  <path d="M12 16h.01" />
                  <path d="M15 16h.01" />
                </svg>
              </span>
              <span className="action-name">Recompute Indicators</span>
              <span className="action-desc">기술 지표 재계산</span>
            </button>
            <button type="button" onClick={() => runAction("report", "/api/reports/daily", {})}>
              <span className="action-icon report" aria-hidden="true">
                <svg viewBox="0 0 24 24">
                  <path d="M7 4h7l4 4v12H7z" />
                  <path d="M14 4v5h5" />
                  <path d="M9 13h6" />
                  <path d="M9 16h4" />
                </svg>
              </span>
              <span className="action-name">Generate Daily Report</span>
              <span className="action-desc">오늘 리포트 생성</span>
            </button>
          </div>
        </section>

        <article>
          <div className="sectionHeader">
            <h2>Mock Broker 상태</h2>
            <span className="bdg bdg-fail">preview_only</span>
          </div>
          <div className="brokerGrid">
            <KpiCard label="mode" value={broker.data?.broker_mode ?? broker.data?.mode ?? "-"} />
            <KpiCard label="can_submit" value={broker.data?.can_submit ? "true" : "false"} tone={broker.data?.can_submit ? "neg" : "pos"} />
            <KpiCard label="live_trading" value={broker.data?.live_trading_enabled ? "enabled" : "disabled"} tone={broker.data?.live_trading_enabled ? "neg" : "pos"} />
            <KpiCard label="paper_trading" value={broker.data?.paper_trading_enabled ? "enabled" : "disabled"} tone={broker.data?.paper_trading_enabled ? "pos" : "muted"} />
          </div>
        </article>
      </section>
    </main>
  );
}
