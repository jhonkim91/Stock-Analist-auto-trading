"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { ValidationSummaryCard } from "../../components/validation-summary-card";
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

const metricLabels: Array<[keyof BacktestRun["metrics"], string, "percent" | "number"]> = [
  ["total_return", "total_return", "percent"],
  ["cagr", "cagr", "percent"],
  ["max_drawdown", "max_drawdown", "percent"],
  ["win_rate", "win_rate", "percent"],
  ["avg_win", "avg_win", "number"],
  ["avg_loss", "avg_loss", "number"],
  ["profit_factor", "profit_factor", "number"],
  ["expectancy", "expectancy", "number"],
  ["average_holding_days", "average_holding_days", "number"],
  ["trade_count", "trade_count", "number"],
  ["exposure", "exposure", "percent"],
  ["portfolio_turnover", "portfolio_turnover", "percent"],
  ["average_active_positions", "average_active_positions", "number"],
  ["rebalance_count", "rebalance_count", "number"]
];

const rankingStrategyNames = new Set(["momentum_rank", "relative_strength_leader"]);
const weightingOptions: PortfolioWeighting[] = ["equal_risk", "equal_weight"];

function positiveInteger(value: string, fallback: number) {
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function formatMetric(value: number | string | boolean | null | undefined, type: "percent" | "number") {
  if (typeof value !== "number") {
    return typeof value === "boolean" ? String(value) : value ?? "-";
  }
  return type === "percent" ? formatPercent(value) : formatNumber(value, 4);
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

  const strategyNames = useMemo(() => {
    const names = new Set(strategyCatalog.map((strategy) => strategy.name));
    runs.forEach((run) => names.add(run.strategy_name));
    return Array.from(names);
  }, [runs, strategyCatalog]);

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
          <p className="eyebrow">Phase 2</p>
          <h1>Backtest</h1>
        </div>
        <nav className="nav">
          <Link href="/dashboard">Dashboard</Link>
          <Link href="/data">Data</Link>
          <Link href="/screener">Screener</Link>
          <Link href="/reports">Reports</Link>
          <Link href="/portfolio">Portfolio</Link>
          <Link href="/paper">Paper</Link>
          <Link href="/settings">Settings</Link>
        </nav>
        <span className={`status ${status}`}>{message}</span>
      </header>

      <section className="panel">
        <div className="formRow">
          <label>
            strategy_name
            <select value={strategyName} onChange={(event) => setStrategyName(event.target.value)}>
              {strategyCatalog.map((strategy) => (
                <option key={strategy.name} value={strategy.name}>
                  {strategy.display_name}
                </option>
              ))}
            </select>
          </label>
          {isRankingStrategy ? (
            <>
              <label>
                top_n
                <input
                  min={1}
                  type="number"
                  value={topN}
                  onChange={(event) => setTopN(positiveInteger(event.target.value, topN))}
                />
              </label>
              <label>
                max_positions
                <input
                  min={1}
                  type="number"
                  value={maxPositions}
                  onChange={(event) => setMaxPositions(positiveInteger(event.target.value, maxPositions))}
                />
              </label>
              <label>
                weighting
                <select value={weighting} onChange={(event) => setWeighting(event.target.value as PortfolioWeighting)}>
                  {weightingOptions.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </label>
            </>
          ) : null}
          <button type="button" onClick={runBacktest} disabled={!strategyName}>
            Run Backtest
          </button>
        </div>
      </section>

      {selectedRun ? (
        <section className="cardGrid compactCards">
          {metricLabels.map(([key, label, type]) => (
            <article key={String(key)}>
              <h2>{label}</h2>
              <p className="bigNumber">{formatMetric(selectedRun.metrics[key], type)}</p>
            </article>
          ))}
        </section>
      ) : null}

      <section className="panel">
        <div className="sectionHeader">
          <h2>Validation Framework</h2>
          <span className="muted">{summaryMessage}</span>
        </div>
        <ValidationSummaryCard summary={strategySummary} message={summaryMessage} />
      </section>

      <section className="grid wideLeft">
        <div className="tableWrap">
          <table>
            <thead>
              <tr>
                <th>run_id</th>
                <th>strategy_name</th>
                <th>created_at</th>
                <th>total_return</th>
                <th>cagr</th>
                <th>max_drawdown</th>
                <th>win_rate</th>
                <th>trade_count</th>
                <th>exposure</th>
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
                  <td>{run.created_at}</td>
                  <td>{formatPercent(run.metrics.total_return)}</td>
                  <td>{formatPercent(run.metrics.cagr)}</td>
                  <td>{formatPercent(run.metrics.max_drawdown)}</td>
                  <td>{formatPercent(run.metrics.win_rate)}</td>
                  <td>{formatNumber(run.metrics.trade_count)}</td>
                  <td>{formatPercent(run.metrics.exposure)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <aside className="detailPanel">
          <h2>252D Validation Summary</h2>
          <p className="muted">
            baseline: {strategySummary?.baseline.status ?? "unspecified"} · {summaryMessage}
          </p>
          <table className="miniTable">
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
              {(strategySummary?.strategies ?? []).map((row) => (
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

          <h2>Strategy Comparison</h2>
          <table className="miniTable">
            <thead>
              <tr>
                <th>strategy</th>
                <th>runs</th>
                <th>best return</th>
                <th>latest drawdown</th>
              </tr>
            </thead>
            <tbody>
              {strategyNames.map((strategy) => {
                const strategyRuns = runs.filter((run) => run.strategy_name === strategy);
                const latest = strategyRuns[0];
                const bestReturn = strategyRuns.reduce(
                  (best, run) => Math.max(best, Number(run.metrics.total_return ?? 0)),
                  Number.NEGATIVE_INFINITY
                );
                return (
                  <tr key={strategy}>
                    <td>{strategy}</td>
                    <td>{formatNumber(strategyRuns.length)}</td>
                    <td>{strategyRuns.length ? formatPercent(bestReturn) : "-"}</td>
                    <td>{latest ? formatPercent(latest.metrics.max_drawdown) : "-"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          <h2>Selected Metrics</h2>
          <pre className="tinyPre">{JSON.stringify(selectedRun?.metrics ?? {}, null, 2)}</pre>
        </aside>
      </section>
    </main>
  );
}
