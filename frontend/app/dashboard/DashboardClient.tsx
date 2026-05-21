"use client";

import Link from "next/link";
import { ChangeEvent, useCallback, useEffect, useMemo, useState } from "react";

import {
  callApi,
  formatNumber,
  formatPercent,
  type ActionResponse,
  type AsyncState,
  type BacktestRun,
  type BrokerStatus,
  type DataStatus,
  type ImportResult,
  type MarketRegime,
  type ReportItem,
  type ScreenerResult,
  summarizeResults
} from "../../lib/api";

const loadingState = <T,>(message: string): AsyncState<T> => ({ status: "loading", message });
const idleState = <T,>(message: string): AsyncState<T> => ({ status: "idle", message });

const actionLabels = {
  seed: "Seed Sample Data",
  indicators: "Recompute Indicators",
  screener: "Run Screener",
  report: "Generate Daily Report",
  backtest: "Run Backtest",
  preview: "Preview Mock Order"
} as const;

type ActionKey = keyof typeof actionLabels;

function stateFromSettled<T>(result: PromiseSettledResult<T>, emptyMessage: string): AsyncState<T> {
  if (result.status === "fulfilled") {
    return { status: "ok", message: "조회 완료", data: result.value };
  }
  return { status: "error", message: result.reason instanceof Error ? result.reason.message : emptyMessage };
}

function StatusPill({ status, text }: { status: string; text: string }) {
  return <span className={`status ${status}`}>{text}</span>;
}

function Metric({ label, value }: { label: string; value: string | number | null | undefined }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value ?? "-"}</strong>
    </div>
  );
}

function JsonBlock({ data }: { data: unknown }) {
  return <pre className="compactPre">{JSON.stringify(data ?? {}, null, 2)}</pre>;
}

export default function DashboardClient() {
  const [health, setHealth] = useState<AsyncState<ActionResponse>>(loadingState("API 연결 확인 중"));
  const [dataStatus, setDataStatus] = useState<AsyncState<DataStatus>>(loadingState("데이터 상태 조회 중"));
  const [regime, setRegime] = useState<AsyncState<MarketRegime>>(loadingState("시장 국면 조회 중"));
  const [screenerResults, setScreenerResults] = useState<AsyncState<ScreenerResult[]>>(loadingState("스크리너 조회 중"));
  const [latestReport, setLatestReport] = useState<AsyncState<ReportItem[]>>(loadingState("리포트 조회 중"));
  const [latestBacktest, setLatestBacktest] = useState<AsyncState<BacktestRun[]>>(loadingState("백테스트 조회 중"));
  const [broker, setBroker] = useState<AsyncState<BrokerStatus>>(loadingState("브로커 상태 조회 중"));
  const [actionStates, setActionStates] = useState<Record<ActionKey, AsyncState<ActionResponse>>>({
    seed: idleState("대기"),
    indicators: idleState("대기"),
    screener: idleState("대기"),
    report: idleState("대기"),
    backtest: idleState("대기"),
    preview: idleState("대기")
  });
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [importState, setImportState] = useState<AsyncState<ImportResult>>(idleState("CSV 파일을 선택하세요"));

  const screenerSummary = useMemo(() => summarizeResults(screenerResults.data ?? []), [screenerResults.data]);
  const latestReportItem = latestReport.data?.[0];
  const latestBacktestRun = latestBacktest.data?.[0];

  const loadOverview = useCallback(async (showLoading = true) => {
    if (showLoading) {
      setHealth(loadingState("API 연결 확인 중"));
      setDataStatus(loadingState("데이터 상태 조회 중"));
      setRegime(loadingState("시장 국면 조회 중"));
      setScreenerResults(loadingState("스크리너 조회 중"));
      setLatestReport(loadingState("리포트 조회 중"));
      setLatestBacktest(loadingState("백테스트 조회 중"));
      setBroker(loadingState("브로커 상태 조회 중"));
    }

    const [healthResult, dataResult, regimeResult, screenerResult, reportResult, backtestResult, brokerResult] =
      await Promise.allSettled([
        callApi<ActionResponse>("/health"),
        callApi<DataStatus>("/api/data/status"),
        callApi<MarketRegime>("/api/market/regime"),
        callApi<ScreenerResult[]>("/api/screener/results?limit=100"),
        callApi<ReportItem[]>("/api/reports?limit=1"),
        callApi<BacktestRun[]>("/api/backtest/runs?limit=1"),
        callApi<BrokerStatus>("/api/broker/status")
      ]);

    setHealth(stateFromSettled(healthResult, "API 연결 실패"));
    setDataStatus(stateFromSettled(dataResult, "데이터 상태 없음"));
    setRegime(stateFromSettled(regimeResult, "시장 국면 없음"));
    setScreenerResults(stateFromSettled(screenerResult, "스크리너 결과 없음"));
    setLatestReport(stateFromSettled(reportResult, "리포트 없음"));
    setLatestBacktest(stateFromSettled(backtestResult, "백테스트 없음"));
    setBroker(stateFromSettled(brokerResult, "브로커 상태 없음"));
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadOverview(false);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadOverview]);

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

  async function importCsv() {
    if (!selectedFile) {
      setImportState({ status: "error", message: "CSV 파일을 먼저 선택하세요" });
      return;
    }
    setImportState(loadingState("CSV import 실행 중"));
    const formData = new FormData();
    formData.append("file", selectedFile);
    try {
      const data = await callApi<ImportResult>("/api/data/import/daily-ohlcv", { method: "POST", body: formData });
      setImportState({ status: "ok", message: "CSV import 성공", data });
      await loadOverview(false);
    } catch (error) {
      setImportState({ status: "error", message: error instanceof Error ? error.message : "CSV import 실패" });
    }
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    setSelectedFile(event.target.files?.[0] ?? null);
  }

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Phase 2</p>
          <h1>Dashboard</h1>
        </div>
        <nav className="nav">
          <Link href="/dashboard">Dashboard</Link>
          <Link href="/screener">Screener</Link>
          <Link href="/reports">Reports</Link>
          <Link href="/backtest">Backtest</Link>
          <Link href="/portfolio">Portfolio</Link>
          <Link href="/settings">Settings</Link>
        </nav>
        <StatusPill status={health.status} text={health.message} />
      </header>

      <section className="toolbar" aria-label="Backend actions">
        <button type="button" onClick={() => runAction("seed", "/api/data/seed", {})}>
          {actionLabels.seed}
        </button>
        <button type="button" onClick={() => runAction("indicators", "/api/indicators/recompute", {})}>
          {actionLabels.indicators}
        </button>
        <button type="button" onClick={() => runAction("screener", "/api/screener/run", {})}>
          {actionLabels.screener}
        </button>
        <button type="button" onClick={() => runAction("report", "/api/reports/daily", {})}>
          {actionLabels.report}
        </button>
        <button type="button" onClick={() => runAction("backtest", "/api/backtest/run", { strategy_name: "trend_breakout" })}>
          {actionLabels.backtest}
        </button>
        <button
          type="button"
          className="secondary"
          onClick={() =>
            runAction("preview", "/api/broker/orders/preview", {
              symbol: "KR009",
              side: "buy",
              qty: 10,
              strategy_tag: "dashboard_preview"
            })
          }
        >
          {actionLabels.preview}
        </button>
      </section>

      <section className="cardGrid">
        <article>
          <h2>Backend Health</h2>
          <StatusPill status={health.status} text={health.message} />
          <JsonBlock data={health.data} />
        </article>
        <article>
          <h2>Data Status</h2>
          <StatusPill status={dataStatus.status} text={dataStatus.message} />
          <div className="metricGrid">
            <Metric label="symbols" value={formatNumber(dataStatus.data?.symbol_count)} />
            <Metric label="daily rows" value={formatNumber(dataStatus.data?.daily_ohlcv_count)} />
            <Metric label="indicators" value={formatNumber(dataStatus.data?.indicator_snapshot_count)} />
            <Metric label="orders" value={formatNumber(dataStatus.data?.orders_count)} />
          </div>
          <p className="muted">latest trade date: {dataStatus.data?.latest_trade_date ?? "-"}</p>
        </article>
        <article>
          <h2>Latest Market Regime</h2>
          <StatusPill status={regime.status} text={regime.message} />
          <div className="metricGrid">
            <Metric label="regime" value={regime.data?.regime} />
            <Metric label="market score" value={formatNumber(regime.data?.market_score, 2)} />
            <Metric label="benchmark" value={regime.data?.benchmark} />
            <Metric label="date" value={regime.data?.trade_date} />
          </div>
        </article>
        <article>
          <h2>Latest Screener Summary</h2>
          <StatusPill status={screenerResults.status} text={screenerResults.message} />
          <div className="metricGrid">
            <Metric label="rows" value={formatNumber(screenerSummary.total)} />
            <Metric label="passed" value={formatNumber(screenerSummary.passed)} />
            <Metric label="latest date" value={screenerSummary.latestDate} />
            <Metric label="strategies" value={screenerSummary.strategies.length} />
          </div>
          <Link className="textLink" href="/screener">
            Screener results
          </Link>
        </article>
        <article>
          <h2>Latest Report</h2>
          <StatusPill status={latestReport.status} text={latestReport.message} />
          <p className="strongLine">{latestReportItem?.title ?? "생성된 리포트 없음"}</p>
          <p className="muted">{latestReportItem?.created_at ?? "-"}</p>
          <Link className="textLink" href="/reports">
            Reports
          </Link>
        </article>
        <article>
          <h2>Latest Backtest Summary</h2>
          <StatusPill status={latestBacktest.status} text={latestBacktest.message} />
          <div className="metricGrid">
            <Metric label="strategy" value={latestBacktestRun?.strategy_name} />
            <Metric label="return" value={formatPercent(latestBacktestRun?.metrics.total_return)} />
            <Metric label="drawdown" value={formatPercent(latestBacktestRun?.metrics.max_drawdown)} />
            <Metric label="trades" value={formatNumber(latestBacktestRun?.metrics.trade_count)} />
          </div>
          <Link className="textLink" href="/backtest">
            Backtest
          </Link>
        </article>
        <article>
          <h2>Mock Broker Status</h2>
          <StatusPill status={broker.status} text={broker.message} />
          <div className="metricGrid">
            <Metric label="mode" value={broker.data?.mode} />
            <Metric label="can submit" value={broker.data?.can_submit ? "yes" : "no"} />
            <Metric label="live" value={broker.data?.live_trading_enabled ? "enabled" : "disabled"} />
            <Metric label="paper" value={broker.data?.paper_trading_enabled ? "enabled" : "disabled"} />
          </div>
        </article>
      </section>

      <section className="panel">
        <div className="sectionHeader">
          <div>
            <h2>CSV Import</h2>
            <p className="muted">필수 컬럼: symbol, trade_date, open, high, low, close, volume</p>
            <p className="muted">선택 컬럼: turnover_value, market, provider, adj_close</p>
          </div>
          <a
            className="textLink"
            href={`data:text/csv;charset=utf-8,${encodeURIComponent(
              "symbol,trade_date,open,high,low,close,volume\nSAMPLE,2026-05-20,100,110,95,105,10000\n"
            )}`}
            download="sample_daily_ohlcv.csv"
          >
            sample CSV 다운로드
          </a>
        </div>
        <div className="formRow">
          <input type="file" accept=".csv,text/csv" onChange={handleFileChange} />
          <button type="button" onClick={importCsv}>
            Import CSV
          </button>
        </div>
        <StatusPill status={importState.status} text={importState.message} />
        {importState.data ? (
          <div className="metricGrid">
            <Metric label="inserted_count" value={formatNumber(importState.data.inserted_count)} />
            <Metric label="updated_count" value={formatNumber(importState.data.updated_count)} />
            <Metric label="skipped_count" value={formatNumber(importState.data.skipped_count)} />
            <Metric label="error_count" value={formatNumber(importState.data.error_count)} />
          </div>
        ) : null}
        {importState.status === "ok" ? (
          <div className="toolbar compactToolbar">
            <button type="button" onClick={() => runAction("indicators", "/api/indicators/recompute", {})}>
              Recompute Indicators
            </button>
            <button type="button" onClick={() => runAction("screener", "/api/screener/run", {})}>
              Run Screener
            </button>
          </div>
        ) : null}
      </section>

      <section className="grid">
        <article>
          <h2>Action Results</h2>
          <div className="actionList">
            {Object.entries(actionLabels).map(([key, label]) => {
              const state = actionStates[key as ActionKey];
              return (
                <details key={key} open={state.status === "ok" || state.status === "error"}>
                  <summary>
                    {label} <StatusPill status={state.status} text={state.message} />
                  </summary>
                  <JsonBlock data={state.data} />
                </details>
              );
            })}
          </div>
        </article>
        <article>
          <h2>Full Data Status</h2>
          <JsonBlock data={dataStatus.data} />
        </article>
      </section>
    </main>
  );
}
