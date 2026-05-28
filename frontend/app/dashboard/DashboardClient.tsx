"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { ValidationSummaryCard } from "../../components/validation-summary-card";
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
  type ReportItem,
  type ScreenerResult,
  type StrategyMetadata,
  type StrategyValidationSummary,
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

function numberValue(value: number | null | undefined) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function average(values: Array<number | null>) {
  const valid = values.filter((value): value is number => value !== null);
  return valid.length ? valid.reduce((sum, value) => sum + value, 0) / valid.length : null;
}

function minValue(values: Array<number | null>) {
  const valid = values.filter((value): value is number => value !== null);
  return valid.length ? Math.min(...valid) : null;
}

function percentOrDash(value: number | null) {
  return value === null ? "-" : formatPercent(value);
}

function DashboardMetricCard({
  label,
  value,
  sub,
  tone = "neu"
}: {
  label: string;
  value: string;
  sub: string;
  tone?: "pos" | "neg" | "neu";
}) {
  return (
    <article className="dashboardMetricCard">
      <div className="metric-label">{label}</div>
      <div className={`metric-value ${tone}`}>{value}</div>
      <div className={`metric-sub ${tone}`}>{sub}</div>
    </article>
  );
}

function BreadthItem({ label, value, tone = "neu" }: { label: string; value: string; tone?: "pos" | "neg" | "neu" }) {
  return (
    <div className="breadthItem">
      <div className={`breadthVal ${tone}`}>{value}</div>
      <div className="breadthLbl">{label}</div>
    </div>
  );
}

function ScoreBar({ value }: { value: number | null | undefined }) {
  const normalized = Math.max(0, Math.min(1, numberValue(value) ?? 0));
  const tone = normalized >= 0.7 ? "ok" : normalized >= 0.5 ? "warn" : "bad";
  return (
    <span className="scoreBar">
      <span className={`scoreFill ${tone}`} style={{ width: `${Math.round(normalized * 100)}%` }} />
    </span>
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
  const [strategySummary, setStrategySummary] = useState<AsyncState<StrategyValidationSummary>>(loadingState("검증 요약 조회 중"));
  const [strategyCatalog, setStrategyCatalog] = useState<StrategyMetadata[]>([]);
  const [selectedStrategyName, setSelectedStrategyName] = useState("");
  const [actionStates, setActionStates] = useState<Record<ActionKey, AsyncState<ActionResponse>>>({
    seed: idleState("대기"),
    indicators: idleState("대기"),
    screener: idleState("대기"),
    report: idleState("대기"),
    backtest: idleState("대기"),
    preview: idleState("대기")
  });
  const screenerSummary = useMemo(() => summarizeResults(screenerResults.data ?? []), [screenerResults.data]);
  const latestReportItem = latestReport.data?.[0];
  const latestBacktestRun = latestBacktest.data?.[0];
  const defaultStrategyCount = strategyCatalog.filter((strategy) => strategy.is_default).length;
  const availableStrategyCount = strategyCatalog.filter((strategy) => strategy.is_available && !strategy.is_default).length;
  const strategyRows = strategySummary.data?.strategies ?? [];
  const averageReturn = average(strategyRows.map((row) => numberValue(row.backtest.total_return)));
  const maxDrawdown = minValue(strategyRows.map((row) => numberValue(row.backtest.max_drawdown)));
  const topCandidates = useMemo(
    () =>
      [...(screenerResults.data ?? [])]
        .sort((a, b) => Number(b.passed) - Number(a.passed) || Number(b.total_score ?? 0) - Number(a.total_score ?? 0))
        .slice(0, 5),
    [screenerResults.data]
  );
  const maxAbsReturn = Math.max(
    0.01,
    ...strategyRows.map((row) => Math.abs(numberValue(row.backtest.total_return) ?? 0))
  );

  const loadOverview = useCallback(async (showLoading = true) => {
    if (showLoading) {
      setHealth(loadingState("API 연결 확인 중"));
      setDataStatus(loadingState("데이터 상태 조회 중"));
      setRegime(loadingState("시장 국면 조회 중"));
      setScreenerResults(loadingState("스크리너 조회 중"));
      setLatestReport(loadingState("리포트 조회 중"));
      setLatestBacktest(loadingState("백테스트 조회 중"));
      setBroker(loadingState("브로커 상태 조회 중"));
      setStrategySummary(loadingState("검증 요약 조회 중"));
    }

    const [healthResult, dataResult, regimeResult, screenerResult, reportResult, backtestResult, brokerResult, summaryResult] =
      await Promise.allSettled([
        callApi<ActionResponse>("/health"),
        callApi<DataStatus>("/api/data/status"),
        callApi<MarketRegime>("/api/market/regime"),
        callApi<ScreenerResult[]>("/api/screener/results?limit=100"),
        callApi<ReportItem[]>("/api/reports?limit=1"),
        callApi<BacktestRun[]>("/api/backtest/runs?limit=1"),
        callApi<BrokerStatus>("/api/broker/status"),
        callApi<StrategyValidationSummary>("/api/backtest/strategy-summary?lookback_days=252")
      ]);

    setHealth(stateFromSettled(healthResult, "API 연결 실패"));
    setDataStatus(stateFromSettled(dataResult, "데이터 상태 없음"));
    setRegime(stateFromSettled(regimeResult, "시장 국면 없음"));
    setScreenerResults(stateFromSettled(screenerResult, "스크리너 결과 없음"));
    setLatestReport(stateFromSettled(reportResult, "리포트 없음"));
    setLatestBacktest(stateFromSettled(backtestResult, "백테스트 없음"));
    setBroker(stateFromSettled(brokerResult, "브로커 상태 없음"));
    setStrategySummary(stateFromSettled(summaryResult, "검증 요약 없음"));
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
          <p className="eyebrow">Phase 2</p>
          <h1>Dashboard</h1>
        </div>
        <nav className="nav">
          <Link href="/dashboard">Dashboard</Link>
          <Link href="/data">Data</Link>
          <Link href="/screener">Screener</Link>
          <Link href="/reports">Reports</Link>
          <Link href="/backtest">Backtest</Link>
          <Link href="/portfolio">Portfolio</Link>
          <Link href="/paper">Paper</Link>
          <Link href="/settings">Settings</Link>
        </nav>
        <StatusPill status={health.status} text={health.message} />
      </header>

      <section className="dashboardContent">
        <section className="dashboardKpiGrid" aria-label="Dashboard KPI summary">
          <DashboardMetricCard
            label="Screener Pass Rate"
            value={percentOrDash(screenerSummary.total ? screenerSummary.passed / screenerSummary.total : null)}
            sub={`${formatNumber(screenerSummary.passed)} / ${formatNumber(screenerSummary.total)} passed`}
            tone={screenerSummary.passed > 0 ? "pos" : "neu"}
          />
          <DashboardMetricCard
            label="Active Strategies"
            value={formatNumber(defaultStrategyCount)}
            sub={`default · ${formatNumber(availableStrategyCount)} available`}
          />
          <DashboardMetricCard
            label="252D Avg Return"
            value={percentOrDash(averageReturn)}
            sub="computed available window"
            tone={averageReturn === null ? "neu" : averageReturn >= 0 ? "pos" : "neg"}
          />
          <DashboardMetricCard
            label="Max Drawdown"
            value={percentOrDash(maxDrawdown)}
            sub={strategyRows.length ? "strategy validation summary" : "waiting for summary"}
            tone="neg"
          />
        </section>

        <section className="breadthRow" aria-label="Market breadth summary">
          <BreadthItem label="Advance/Decline" value={percentOrDash(numberValue(regime.data?.breadth_advance_decline_ratio))} tone="pos" />
          <BreadthItem label="52w High/Low" value={percentOrDash(numberValue(regime.data?.breadth_52w_high_low_ratio))} />
          <BreadthItem label="MA50 Participation" value={percentOrDash(numberValue(regime.data?.breadth_ma50_participation))} />
          <BreadthItem label="Breadth Score" value={formatNumber(regime.data?.breadth_score, 2)} tone="pos" />
        </section>

        <section className="dashboardSplit">
          <article>
            <div className="sectionHeader">
              <h2>Top Screener Candidates</h2>
              <span className="muted">today · {formatNumber(topCandidates.length)} shown</span>
            </div>
            <div className="tableWrap compactTable">
              <table className="dashboardTable">
                <thead>
                  <tr>
                    <th>Symbol</th>
                    <th>Strategy</th>
                    <th>Score</th>
                    <th>Risk/Share</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {topCandidates.map((result) => (
                    <tr key={`${result.trade_date}-${result.symbol}-${result.strategy_name}`}>
                      <td>{result.symbol}</td>
                      <td>{result.strategy_name}</td>
                      <td>
                        <ScoreBar value={result.total_score} /> {formatNumber(result.total_score, 2)}
                      </td>
                      <td>{formatNumber(result.risk_per_share, 0)}</td>
                      <td>
                        <span className={`badge ${result.passed ? "pass" : "fail"}`}>{result.passed ? "pass" : "fail"}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </article>

          <article>
            <div className="sectionHeader">
              <h2>Strategy Validation (252D)</h2>
              <span className={`status ${strategySummary.status}`}>{strategySummary.message}</span>
            </div>
            <div className="strategyBars">
              {strategyRows.slice(0, 8).map((row) => {
                const totalReturn = numberValue(row.backtest.total_return);
                const width = totalReturn === null ? 0 : Math.round((Math.abs(totalReturn) / maxAbsReturn) * 100);
                const tone = totalReturn === null ? "neu" : totalReturn >= 0 ? "pos" : "neg";
                return (
                  <div className="attrRow" key={row.strategy_name}>
                    <span className="attrName">{row.strategy_name}</span>
                    <span className="attrBar">
                      <span className={`attrFill ${tone}`} style={{ width: `${width}%` }} />
                    </span>
                    <span className={`attrPnl ${tone}`}>{percentOrDash(totalReturn)}</span>
                  </div>
                );
              })}
              {strategyRows.length === 0 ? <p className="muted">strategy validation summary loading</p> : null}
            </div>
            <p className="muted">Baseline: {strategySummary.data?.baseline.status ?? "unspecified"} · preview-only</p>
          </article>
        </section>

        <section>
          <div className="sectionHeader dashboardValidationHeader">
            <h2>Validation Framework</h2>
            <span className="muted">walk-forward · PBO · DSR</span>
          </div>
          <ValidationSummaryCard summary={strategySummary.data ?? null} message={strategySummary.message} />
        </section>
      </section>

      <section className="panel">
        <div className="sectionHeader">
          <div>
            <h2>Backend Actions</h2>
            <p className="muted">sample seed, recompute, report, backtest, mock preview만 실행한다.</p>
          </div>
          <StatusPill status={health.status} text={health.message} />
        </div>
        <div className="toolbar compactToolbar" aria-label="Backend actions">
          <label>
            strategy_name
            <select value={selectedStrategyName} onChange={(event) => setSelectedStrategyName(event.target.value)}>
              {strategyCatalog.map((strategy) => (
                <option key={strategy.name} value={strategy.name}>
                  {strategy.display_name}
                </option>
              ))}
            </select>
          </label>
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
          <button
            type="button"
            onClick={() => runAction("backtest", "/api/backtest/run", { strategy_name: selectedStrategyName })}
            disabled={!selectedStrategyName}
          >
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
        </div>
        <div className="metricGrid">
          <Metric label="symbols" value={formatNumber(dataStatus.data?.symbol_count)} />
          <Metric label="orders" value={formatNumber(dataStatus.data?.orders_count)} />
          <Metric label="latest report" value={latestReportItem?.report_date ?? "-"} />
          <Metric label="latest backtest" value={latestBacktestRun?.strategy_name ?? "-"} />
          <Metric label="broker can_submit" value={broker.data?.can_submit ? "yes" : "no"} />
          <Metric label="paper enabled" value={broker.data?.paper_trading_enabled ? "enabled" : "disabled"} />
        </div>
      </section>

      <section className="panel">
        <div className="sectionHeader">
          <div>
            <h2>CSV Import / Data Quality</h2>
            <p className="muted">Phase 3A부터 CSV import는 validation preview와 confirm 단계를 거친다.</p>
            <p className="muted">validate 단계는 market data를 변경하지 않고 import_runs와 data_quality_checks만 기록한다.</p>
          </div>
          <Link className="textLink" href="/data">
            Data Quality 화면으로 이동
          </Link>
        </div>
        <div className="toolbar compactToolbar">
          <Link className="textLink" href="/data">
            CSV Validate / Confirm
          </Link>
        </div>
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
