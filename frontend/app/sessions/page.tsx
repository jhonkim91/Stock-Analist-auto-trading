"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { callApi, type ApiStatus, type MarketSession, type MarketSessionWindow, type MarketSessionWindows } from "../../lib/api";

type VenueState = {
  session: MarketSession | null;
  windows: MarketSessionWindow[];
};

function StatusPill({ status, text }: { status: ApiStatus; text: string }) {
  return <span className={`status ${status}`}>{text}</span>;
}

function sessionTone(session: string | undefined) {
  if (session === "regular" || session === "main") {
    return "ok";
  }
  if (session === "closed") {
    return "error";
  }
  return "loading";
}

function timeRange(window: MarketSessionWindow) {
  const start = window.trading_start ?? window.order_acceptance_start ?? "-";
  const end = window.trading_end ?? window.order_acceptance_end ?? "-";
  return `${start} - ${end}`;
}

function SessionCard({ title, state }: { title: string; state: VenueState }) {
  const activeName = state.session?.session;
  return (
    <article>
      <div className="sectionHeader">
        <h2>{title}</h2>
        <span className={`status ${sessionTone(activeName)}`}>{activeName ?? "알 수 없음"}</span>
      </div>
      <div className="sessionBar">
        {state.windows.map((window) => {
          const isActive = window.name === activeName;
          return (
            <div className={`sessionSlot ${isActive ? "active" : ""}`} key={window.name}>
              <strong>{window.name}</strong>
              <span>{timeRange(window)}</span>
            </div>
          );
        })}
      </div>
      <div className="metricGrid">
        <div className="metric">
          <span>trading_day</span>
          <strong>{state.session?.is_trading_day ? "true" : "false"}</strong>
        </div>
        <div className="metric">
          <span>trading_session</span>
          <strong>{state.session?.is_trading_session ? "true" : "false"}</strong>
        </div>
        <div className="metric">
          <span>preview_allowed</span>
          <strong>{state.session?.current_session_allows_preview ? "true" : "false"}</strong>
        </div>
        <div className="metric">
          <span>submit_policy</span>
          <strong>미리보기 전용</strong>
        </div>
      </div>
      <p className="muted">{state.session?.reason_codes.join(", ") || "미리보기 메타데이터 전용 · 실제 제출 없음"}</p>
    </article>
  );
}

/** KRX/NXT 세션 preview metadata를 읽기 전용으로 표시한다. */
export default function SessionsPage() {
  const [status, setStatus] = useState<ApiStatus>("loading");
  const [message, setMessage] = useState("세션 조회 중");
  const [krx, setKrx] = useState<VenueState>({ session: null, windows: [] });
  const [nxt, setNxt] = useState<VenueState>({ session: null, windows: [] });

  const loadSessions = useCallback(async (showLoading = true) => {
    if (showLoading) {
      setStatus("loading");
      setMessage("세션 조회 중");
    }
    try {
      const [krxSession, krxWindows, nxtSession, nxtWindows] = await Promise.all([
        callApi<MarketSession>("/api/market/session?venue=KRX"),
        callApi<MarketSessionWindows>("/api/market/sessions?venue=KRX"),
        callApi<MarketSession>("/api/market/session?venue=NXT"),
        callApi<MarketSessionWindows>("/api/market/sessions?venue=NXT")
      ]);
      setKrx({ session: krxSession, windows: krxWindows.session_windows });
      setNxt({ session: nxtSession, windows: nxtWindows.session_windows });
      setStatus("ok");
      setMessage("세션 조회 완료");
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "세션 조회 실패");
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadSessions(false);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadSessions]);

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">세션 미리보기</p>
          <h1>장 세션</h1>
        </div>
        <nav className="nav">
          <Link href="/dashboard">대시보드</Link>
          <Link href="/data">데이터</Link>
          <Link href="/screener">스크리너</Link>
          <Link href="/reports">리포트</Link>
          <Link href="/backtest">백테스트</Link>
          <Link href="/portfolio">포트폴리오</Link>
          <Link href="/paper">모의투자</Link>
          <Link href="/settings">설정</Link>
        </nav>
        <StatusPill status={status} text={message} />
      </header>

      <section className="grid">
        <SessionCard state={krx} title="KRX" />
        <SessionCard state={nxt} title="NXT" />
      </section>
    </main>
  );
}
