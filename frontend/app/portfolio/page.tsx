"use client";

import { useCallback, useEffect, useState } from "react";

import { callApi, formatNumber, type ApiStatus, type PaperPortfolioResponse, type PortfolioRisk } from "../../lib/api";

function PageIcon() {
  return (
    <svg className="pageTitleIcon" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 3 5 6v5c0 4.5 2.8 8.3 7 10 4.2-1.7 7-5.5 7-10V6l-7-3Z" />
      <path d="m9 12 2 2 4-5" />
    </svg>
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

function Kpi({ label, sub, tone, value }: { label: string; sub?: string; tone?: "pos" | "neg"; value: string }) {
  return (
    <div className="kpi">
      <div className="kpi-lbl">{label}</div>
      <div className={`kpi-val ${tone ?? ""}`}>{value}</div>
      {sub ? <div className="kpi-sub muted">{sub}</div> : null}
    </div>
  );
}

function krw(value: number | null | undefined) {
  return value === null || value === undefined ? "-" : `₩${formatNumber(value)}`;
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
  const warnings = risk?.warnings ?? [];

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <PageIcon />
          <h1>Portfolio / Risk</h1>
        </div>
        <div className="topbar-actions" title={message}>
          <span className="muted">synthetic · broker 미연동</span>
          <span className={`status ${status}`}>{message}</span>
        </div>
      </header>

      <section className="scroll">
        <div className="warn-box">
          <span aria-hidden="true">!</span>
          {warnings[0] ?? "No broker sync active — synthetic portfolio 기준"}
        </div>

        <div className="g4">
          <Kpi label="account_equity" value={krw(risk?.account_equity)} />
          <Kpi label="risk_per_trade" value={krw(risk?.risk_per_trade)} />
          <Kpi label="open_positions" value={formatNumber(risk?.open_positions_count)} sub="max 미설정" />
          <Kpi label="available_risk_budget" value={krw(risk?.available_risk_budget)} tone="pos" />
        </div>

        <div className="g2">
          <article>
            <div className="card-hd">
              <span className="card-title">broker 상태</span>
            </div>
            <StatRow label="broker_mode" value={risk?.broker_mode ?? "-"} tone="muted" />
            <StatRow label="latest_signal_date" value={risk?.latest_signal_date ?? "-"} tone="muted" />
            <StatRow label="proposed_positions" value={formatNumber(risk?.proposed_positions)} />
            <StatRow label="proposed_notional" value={krw(risk?.proposed_notional)} />
          </article>

          <article>
            <div className="card-hd">
              <span className="card-title">warnings</span>
            </div>
            <div className="mockStack">
              {(warnings.length ? warnings : ["No broker sync active"]).map((warning) => (
                <div className="mockNotice warn" key={warning}>
                  <span aria-hidden="true">!</span>
                  {warning}
                </div>
              ))}
              <div className="mockNotice">
                <span aria-hidden="true">i</span>
                preview-only safety boundary 유지
              </div>
            </div>
          </article>
        </div>

        <div className="g3">
          <article>
            <div className="card-hd">
              <span className="card-title">Paper Snapshot</span>
              <span className="bdg bdg-fail">실거래 아님</span>
            </div>
            <StatRow label="source" value={paperPortfolio?.source ?? "-"} />
            <StatRow label="snapshot_status" value={snapshot?.status ?? "-"} />
          </article>
          <article>
            <div className="card-hd">
              <span className="card-title">paper equity</span>
            </div>
            <StatRow label="total_equity" value={krw(snapshot?.total_equity)} />
            <StatRow label="market_value" value={krw(snapshot?.market_value)} />
          </article>
          <article>
            <div className="card-hd">
              <span className="card-title">separation</span>
            </div>
            <StatRow label="paper_positions_table" value={String(paperPortfolio?.separation_contract.paper_positions_table ?? "-")} />
            <StatRow label="mixed" value={String(paperPortfolio?.separation_contract.mixed ?? false)} tone="pos" />
          </article>
        </div>
      </section>
    </main>
  );
}
