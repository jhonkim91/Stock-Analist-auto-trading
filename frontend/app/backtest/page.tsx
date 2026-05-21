"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { callApi, formatNumber, formatPercent, type ApiStatus, type BacktestRun } from "../../lib/api";

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
  ["exposure", "exposure", "percent"]
];

const strategies = ["trend_breakout", "vcp_breakout", "canslim_lite"];

function formatMetric(value: number | string | null | undefined, type: "percent" | "number") {
  if (typeof value !== "number") {
    return value ?? "-";
  }
  return type === "percent" ? formatPercent(value) : formatNumber(value, 4);
}

export default function BacktestPage() {
  const [status, setStatus] = useState<ApiStatus>("loading");
  const [message, setMessage] = useState("조회 중");
  const [runs, setRuns] = useState<BacktestRun[]>([]);
  const [selectedRun, setSelectedRun] = useState<BacktestRun | null>(null);
  const [strategyName, setStrategyName] = useState("trend_breakout");

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

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadRuns(false);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadRuns]);

  async function runBacktest() {
    setStatus("loading");
    setMessage("백테스트 실행 중");
    try {
      await callApi<{ run_id: string }>("/api/backtest/run", {
        method: "POST",
        body: JSON.stringify({ strategy_name: strategyName })
      });
      await loadRuns(false);
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
          <Link href="/settings">Settings</Link>
        </nav>
        <span className={`status ${status}`}>{message}</span>
      </header>

      <section className="panel">
        <div className="formRow">
          <label>
            strategy_name
            <select value={strategyName} onChange={(event) => setStrategyName(event.target.value)}>
              {strategies.map((strategy) => (
                <option key={strategy} value={strategy}>
                  {strategy}
                </option>
              ))}
            </select>
          </label>
          <button type="button" onClick={runBacktest}>
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
              {strategies.map((strategy) => {
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
