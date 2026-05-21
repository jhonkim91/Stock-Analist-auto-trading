"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { callApi, formatNumber, type ApiStatus, type PortfolioRisk } from "../../lib/api";

export default function PortfolioPage() {
  const [status, setStatus] = useState<ApiStatus>("loading");
  const [message, setMessage] = useState("조회 중");
  const [risk, setRisk] = useState<PortfolioRisk | null>(null);

  const loadRisk = useCallback(async (showLoading = true) => {
    if (showLoading) {
      setStatus("loading");
      setMessage("조회 중");
    }
    try {
      const data = await callApi<PortfolioRisk>("/api/portfolio/risk");
      setRisk(data);
      setStatus("ok");
      setMessage("조회 완료");
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "조회 실패");
      setRisk(null);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadRisk(false);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadRisk]);

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Phase 2</p>
          <h1>Portfolio / Risk</h1>
        </div>
        <nav className="nav">
          <Link href="/dashboard">Dashboard</Link>
          <Link href="/data">Data</Link>
          <Link href="/screener">Screener</Link>
          <Link href="/reports">Reports</Link>
          <Link href="/backtest">Backtest</Link>
          <Link href="/settings">Settings</Link>
        </nav>
        <span className={`status ${status}`}>{message}</span>
      </header>

      <section className="cardGrid">
        <article>
          <h2>account_equity</h2>
          <p className="bigNumber">{formatNumber(risk?.account_equity)}</p>
        </article>
        <article>
          <h2>risk_per_trade</h2>
          <p className="bigNumber">{formatNumber(risk?.risk_per_trade)}</p>
        </article>
        <article>
          <h2>max_daily_loss</h2>
          <p className="bigNumber">{formatNumber(risk?.max_daily_loss)}</p>
        </article>
        <article>
          <h2>open_positions_count</h2>
          <p className="bigNumber">{formatNumber(risk?.open_positions_count)}</p>
        </article>
        <article>
          <h2>total_position_notional</h2>
          <p className="bigNumber">{formatNumber(risk?.total_position_notional)}</p>
        </article>
        <article>
          <h2>available_risk_budget</h2>
          <p className="bigNumber">{formatNumber(risk?.available_risk_budget)}</p>
        </article>
      </section>

      <section className="grid">
        <article>
          <h2>Mock / Synthetic Status</h2>
          <div className="metricGrid">
            <div className="metric">
              <span>broker_mode</span>
              <strong>{risk?.broker_mode ?? "-"}</strong>
            </div>
            <div className="metric">
              <span>latest_signal_date</span>
              <strong>{risk?.latest_signal_date ?? "-"}</strong>
            </div>
            <div className="metric">
              <span>proposed_positions</span>
              <strong>{formatNumber(risk?.proposed_positions)}</strong>
            </div>
            <div className="metric">
              <span>proposed_notional</span>
              <strong>{formatNumber(risk?.proposed_notional)}</strong>
            </div>
          </div>
        </article>
        <article>
          <h2>warnings</h2>
          <ul className="plainList">
            {(risk?.warnings ?? []).map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </article>
      </section>
    </main>
  );
}
