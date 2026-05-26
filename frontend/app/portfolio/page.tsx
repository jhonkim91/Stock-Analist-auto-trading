"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { PaperModeBanner } from "../../components/paper-mode-banner";
import { callApi, formatNumber, type ApiStatus, type PaperPortfolioResponse, type PortfolioRisk } from "../../lib/api";

function Metric({ label, value }: { label: string; value: string | number | boolean | null | undefined }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value === undefined || value === null ? "-" : String(value)}</strong>
    </div>
  );
}

export default function PortfolioPage() {
  const [status, setStatus] = useState<ApiStatus>("loading");
  const [message, setMessage] = useState("조회 중");
  const [risk, setRisk] = useState<PortfolioRisk | null>(null);
  const [paperPortfolio, setPaperPortfolio] = useState<PaperPortfolioResponse | null>(null);

  const loadRisk = useCallback(async (showLoading = true) => {
    if (showLoading) {
      setStatus("loading");
      setMessage("조회 중");
    }
    try {
      const [riskData, paperData] = await Promise.all([
        callApi<PortfolioRisk>("/api/portfolio/risk"),
        callApi<PaperPortfolioResponse>("/api/paper/portfolio")
      ]);
      setRisk(riskData);
      setPaperPortfolio(paperData);
      setStatus("ok");
      setMessage("조회 완료");
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "조회 실패");
      setRisk(null);
      setPaperPortfolio(null);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadRisk(false);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadRisk]);

  const snapshot = paperPortfolio?.snapshot ?? null;

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Phase 8 · Portfolio</p>
          <h1>Portfolio / Risk</h1>
        </div>
        <nav className="nav">
          <Link href="/dashboard">Dashboard</Link>
          <Link href="/data">Data</Link>
          <Link href="/screener">Screener</Link>
          <Link href="/reports">Reports</Link>
          <Link href="/backtest">Backtest</Link>
          <Link href="/paper">Paper</Link>
          <Link href="/settings">Settings</Link>
        </nav>
        <span className={`status ${status}`}>{message}</span>
      </header>

      <PaperModeBanner title="모의투자 포트폴리오 · synthetic과 분리" />

      <section className="panel">
        <div className="sectionHeader">
          <h2>Synthetic Portfolio Risk</h2>
          <span className="badge">synthetic baseline</span>
        </div>
      </section>

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
            <Metric label="broker_mode" value={risk?.broker_mode ?? "-"} />
            <Metric label="latest_signal_date" value={risk?.latest_signal_date ?? "-"} />
            <Metric label="proposed_positions" value={formatNumber(risk?.proposed_positions)} />
            <Metric label="proposed_notional" value={formatNumber(risk?.proposed_notional)} />
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

      <section className="panel">
        <div className="sectionHeader">
          <h2>Paper Portfolio Snapshot</h2>
          <span className="badge fail">모의투자 · 실거래 아님</span>
        </div>
      </section>

      <section className="cardGrid">
        <article>
          <h2>paper total_equity</h2>
          <p className="bigNumber">{formatNumber(snapshot?.total_equity)}</p>
        </article>
        <article>
          <h2>paper market_value</h2>
          <p className="bigNumber">{formatNumber(snapshot?.market_value)}</p>
        </article>
        <article>
          <h2>paper position_count</h2>
          <p className="bigNumber">{formatNumber(paperPortfolio?.positions_summary.count)}</p>
        </article>
      </section>

      <section className="grid">
        <article>
          <h2>Paper Snapshot Source</h2>
          <div className="metricGrid">
            <Metric label="source" value={paperPortfolio?.source} />
            <Metric label="snapshot_id" value={snapshot?.snapshot_id} />
            <Metric label="snapshot_status" value={snapshot?.status} />
            <Metric label="reason" value={paperPortfolio?.reason ?? "ok"} />
          </div>
        </article>
        <article>
          <h2>State Separation</h2>
          <div className="metricGrid">
            <Metric label="paper_positions_table" value={String(paperPortfolio?.separation_contract.paper_positions_table ?? "-")} />
            <Metric label="paper_snapshots_table" value={String(paperPortfolio?.separation_contract.paper_snapshots_table ?? "-")} />
            <Metric label="mixed" value={String(paperPortfolio?.separation_contract.mixed ?? false)} />
            <Metric label="network_call" value={paperPortfolio?.network_call_performed} />
          </div>
        </article>
      </section>
    </main>
  );
}
