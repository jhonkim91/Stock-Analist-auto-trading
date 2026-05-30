"use client";

import { useCallback, useEffect, useState } from "react";

import { callApi, formatNumber, type ApiStatus, type PaperPortfolioResponse, type PortfolioRisk } from "../../lib/api";
import { AllocationBars } from "../../components/mini-chart";

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
  const holdings = paperPortfolio?.holdings ?? [];

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <PageIcon />
          <h1>포트폴리오 / 리스크</h1>
        </div>
        <div className="topbar-actions" title={message}>
          <span className="muted">합성 데이터 · 브로커 미연동</span>
          <span className={`status ${status}`}>{message}</span>
          <button type="button" onClick={() => void loadRisk(true)} disabled={status === "loading"}>
            새로고침
          </button>
        </div>
      </header>

      <section className="scroll">
        <div className="warn-box">
          <span aria-hidden="true">!</span>
          {warnings[0] ?? "브로커 동기화 미작동 — 합성 포트폴리오 기준"}
        </div>

        <div className="g4">
          <Kpi label="계좌 자산" value={krw(risk?.account_equity)} />
          <Kpi label="거래당 리스크" value={krw(risk?.risk_per_trade)} />
          <Kpi label="보유 포지션" value={formatNumber(risk?.open_positions_count)} sub="최대치 미설정" />
          <Kpi label="가용 리스크 예산" value={krw(risk?.available_risk_budget)} tone="pos" />
        </div>

        <div className="g2">
          <article>
            <div className="card-hd">
              <span className="card-title">브로커 상태</span>
            </div>
            <StatRow label="브로커 모드" value={risk?.broker_mode ?? "-"} tone="muted" />
            <StatRow label="최근 시그널 일자" value={risk?.latest_signal_date ?? "-"} tone="muted" />
            <StatRow label="제안 포지션 수" value={formatNumber(risk?.proposed_positions)} />
            <StatRow label="제안 명목 금액" value={krw(risk?.proposed_notional)} />
          </article>

          <article>
            <div className="card-hd">
              <span className="card-title">경고</span>
            </div>
            <div className="mockStack">
              {(warnings.length ? warnings : ["브로커 동기화 미작동"]).map((warning) => (
                <div className="mockNotice warn" key={warning}>
                  <span aria-hidden="true">!</span>
                  {warning}
                </div>
              ))}
              <div className="mockNotice">
                <span aria-hidden="true">i</span>
                미리보기 전용 안전 경계 유지
              </div>
            </div>
          </article>
        </div>

        <div className="g3">
          <article>
            <div className="card-hd">
              <span className="card-title">모의투자 스냅샷</span>
              <span className="bdg bdg-fail">실거래 아님</span>
            </div>
            <StatRow label="출처" value={paperPortfolio?.source ?? "-"} />
            <StatRow label="스냅샷 상태" value={snapshot?.status ?? "-"} />
          </article>
          <article>
            <div className="card-hd">
              <span className="card-title">모의투자 자산</span>
            </div>
            <StatRow label="총 자산" value={krw(snapshot?.total_equity)} />
            <StatRow label="평가 금액" value={krw(snapshot?.market_value)} />
          </article>
          <article>
            <div className="card-hd">
              <span className="card-title">계정 분리</span>
            </div>
            <StatRow label="모의투자 포지션 테이블" value={String(paperPortfolio?.separation_contract.paper_positions_table ?? "-")} />
            <StatRow label="혼합 여부" value={String(paperPortfolio?.separation_contract.mixed ?? false)} tone="pos" />
          </article>
        </div>

        <article>
          <div className="card-hd">
            <span className="card-title">보유 종목 · 포트폴리오 비중</span>
            <span className="muted">{holdings.length}종목</span>
          </div>
          <AllocationBars holdings={holdings} />
        </article>
      </section>
    </main>
  );
}
