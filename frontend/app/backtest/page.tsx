"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  callApi,
  formatNumber,
  formatPercent,
  type ApiStatus,
  type BacktestRun,
  type BacktestRunRequest,
  type PortfolioWeighting,
  type StrategyValidationSummary,
  type StrategyMetadata
} from "../../lib/api";

const rankingStrategyNames = new Set(["momentum_rank", "relative_strength_leader"]);
const weightingOptions: PortfolioWeighting[] = ["equal_risk", "equal_weight"];

function positiveInteger(value: string, fallback: number) {
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function StatRow({ label, tone, value }: { label: string; tone?: "pos" | "neg" | "muted"; value: React.ReactNode }) {
  return (
    <div className="stat-row">
      <span className="stat-k">{label}</span>
      <span className={tone ?? ""}>{value}</span>
    </div>
  );
}

function PageIcon() {
  return (
    <svg className="pageTitleIcon" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 5v5h5" />
      <path d="M20 12a8 8 0 1 1-2.3-5.7L20 8.6" />
      <path d="M12 8v5l3 2" />
    </svg>
  );
}

export default function BacktestPage() {
  const [status, setStatus] = useState<ApiStatus>("loading");
  const [message, setMessage] = useState("조회 중");
  const [runs, setRuns] = useState<BacktestRun[]>([]);
  const [selectedRun, setSelectedRun] = useState<BacktestRun | null>(null);
  const [strategyCatalog, setStrategyCatalog] = useState<StrategyMetadata[]>([]);
  const [strategySummary, setStrategySummary] = useState<StrategyValidationSummary | null>(null);
  const [summaryMessage, setSummaryMessage] = useState("summary 조회 중");
  const [strategyName, setStrategyName] = useState("");
  const [topN, setTopN] = useState(5);
  const [maxPositions, setMaxPositions] = useState(5);
  const [weighting, setWeighting] = useState<PortfolioWeighting>("equal_risk");

  const isRankingStrategy = rankingStrategyNames.has(strategyName);

  const summaryRows = useMemo(() => (strategySummary?.strategies ?? []).slice(0, 6), [strategySummary]);

  const loadRuns = useCallback(async (showLoading = true) => {
    if (showLoading) {
      setStatus("loading");
      setMessage("조회 중");
    }
    try {
      const data = await callApi<BacktestRun[]>("/api/backtest/runs?limit=20");
      setRuns(data);
      setSelectedRun(data[0] ?? null);
      setStatus("ok");
      setMessage(`조회 완료: ${data.length}건`);
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "조회 실패");
      setRuns([]);
      setSelectedRun(null);
    }
  }, []);

  const loadStrategies = useCallback(async () => {
    try {
      const data = await callApi<StrategyMetadata[]>("/api/screener/strategies");
      setStrategyCatalog(data);
      setStrategyName((current) => current || data.find((strategy) => strategy.is_default)?.name || data[0]?.name || "");
    } catch {
      setStrategyCatalog([]);
    }
  }, []);

  const loadStrategySummary = useCallback(async () => {
    try {
      const data = await callApi<StrategyValidationSummary>("/api/backtest/strategy-summary?lookback_days=252");
      setStrategySummary(data);
      setSummaryMessage(`summary ${data.window.available_trading_days}/${data.lookback_days} trading days`);
    } catch (error) {
      setStrategySummary(null);
      setSummaryMessage(error instanceof Error ? error.message : "summary 조회 실패");
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadRuns(false);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadRuns]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadStrategies();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadStrategies]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadStrategySummary();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadStrategySummary]);

  async function runBacktest() {
    if (!strategyName) {
      setStatus("error");
      setMessage("select a strategy");
      return;
    }
    setStatus("loading");
    setMessage("백테스트 실행 중");
    try {
      const payload: BacktestRunRequest = { strategy_name: strategyName };
      if (isRankingStrategy) {
        payload.top_n = topN;
        payload.max_positions = maxPositions;
        payload.weighting = weighting;
      }
      await callApi<{ run_id: string }>("/api/backtest/run", {
        method: "POST",
        body: JSON.stringify(payload)
      });
      await loadRuns(false);
      await loadStrategySummary();
      setStatus("ok");
      setMessage("백테스트 실행 완료");
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "백테스트 실행 실패");
    }
  }

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <PageIcon />
          <h1>Backtest</h1>
        </div>
        <div className="topbar-actions" title={message}>
          <span className={`status ${status}`}>{message}</span>
          <button type="button" className="primary" onClick={runBacktest} disabled={!strategyName}>
            Run Backtest
          </button>
        </div>
      </header>

      <section className="scroll">
        <div className="g2">
          <article>
            <div className="sectionHeader">
              <h2>설정</h2>
            </div>
            <StatRow
              label="strategy_name"
              value={
                <select value={strategyName} onChange={(event) => setStrategyName(event.target.value)}>
                  {strategyCatalog.map((strategy) => (
                    <option key={strategy.name} value={strategy.name}>
                      {strategy.name}
                    </option>
                  ))}
                </select>
              }
            />
            {isRankingStrategy ? (
              <>
                <StatRow
                  label="top_n"
                  value={<input min={1} type="number" value={topN} onChange={(event) => setTopN(positiveInteger(event.target.value, topN))} />}
                />
                <StatRow
                  label="max_positions"
                  value={
                    <input
                      min={1}
                      type="number"
                      value={maxPositions}
                      onChange={(event) => setMaxPositions(positiveInteger(event.target.value, maxPositions))}
                    />
                  }
                />
              </>
            ) : null}
            <StatRow
              label="weighting"
              value={
                <select value={weighting} onChange={(event) => setWeighting(event.target.value as PortfolioWeighting)}>
                  {weightingOptions.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              }
            />
          </article>

          <article>
            <div className="sectionHeader">
              <h2>최근 실행 메트릭</h2>
            </div>
            <StatRow label="total_return" value={formatPercent(selectedRun?.metrics.total_return)} tone={(selectedRun?.metrics.total_return ?? 0) >= 0 ? "pos" : "neg"} />
            <StatRow label="cagr" value={formatPercent(selectedRun?.metrics.cagr)} tone={(selectedRun?.metrics.cagr ?? 0) >= 0 ? "pos" : "neg"} />
            <StatRow label="max_drawdown" value={formatPercent(selectedRun?.metrics.max_drawdown)} tone="neg" />
            <StatRow label="win_rate" value={formatPercent(selectedRun?.metrics.win_rate)} tone="pos" />
            <StatRow label="profit_factor" value={formatNumber(selectedRun?.metrics.profit_factor, 2)} tone="pos" />
            <StatRow label="trade_count" value={formatNumber(selectedRun?.metrics.trade_count)} />
          </article>
        </div>

        <article className="mockTableCard">
          <div className="sectionHeader">
            <h2>252D Validation Summary</h2>
            <span className="muted">baseline: {strategySummary?.baseline.status ?? "unspecified"}</span>
          </div>
          <div className="tableWrap">
          <table className="tbl">
            <thead>
              <tr>
                <th>strategy</th>
                <th>pass_rate</th>
                <th>trades</th>
                <th>win_rate</th>
                <th>return</th>
                <th>mdd</th>
              </tr>
            </thead>
            <tbody>
              {summaryRows.map((row) => (
                <tr key={row.strategy_name}>
                  <td>{row.strategy_name}</td>
                  <td>{formatPercent(row.screener.pass_rate)}</td>
                  <td>{formatNumber(row.backtest.trade_count)}</td>
                  <td>{formatPercent(row.backtest.win_rate)}</td>
                  <td>{formatPercent(row.backtest.total_return)}</td>
                  <td>{formatPercent(row.backtest.max_drawdown)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
          <p className="muted">{summaryMessage}</p>
        </article>

        <article className="mockTableCard">
          <div className="sectionHeader">
            <h2>Run History (최근 20건)</h2>
          </div>
          <div className="tableWrap">
          <table className="tbl">
            <thead>
              <tr>
                <th style={{ width: "28%" }}>run_id</th>
                <th>strategy</th>
                <th>return</th>
                <th>mdd</th>
                <th>win_rate</th>
                <th>trades</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr
                  key={run.run_id}
                  className={selectedRun?.run_id === run.run_id ? "selectedRow" : ""}
                  role="button"
                  tabIndex={0}
                  onClick={() => setSelectedRun(run)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      setSelectedRun(run);
                    }
                  }}
                >
                  <td>{run.run_id}</td>
                  <td>{run.strategy_name}</td>
                  <td>{formatPercent(run.metrics.total_return)}</td>
                  <td>{formatPercent(run.metrics.max_drawdown)}</td>
                  <td>{formatPercent(run.metrics.win_rate)}</td>
                  <td>{formatNumber(run.metrics.trade_count)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        </article>
      </section>
    </main>
  );
}
