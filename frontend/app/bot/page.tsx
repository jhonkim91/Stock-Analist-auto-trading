"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { PaperModeBanner } from "../../components/paper-mode-banner";
import {
  formatNumber,
  type ApiStatus,
  type PaperBotDecision,
  type PaperBotRunResponse,
  type PaperBotStatus,
  type PaperBotStopResponse,
  type PaperStatus
} from "../../lib/api";
import { getBotStatus, getPaperStatus, runBotOnce, stopBot } from "../../lib/paperApi";

function Metric({ label, value }: { label: string; value: string | number | boolean | null | undefined }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value === undefined || value === null ? "-" : String(value)}</strong>
    </div>
  );
}

function DecisionRows({ decisions }: { decisions: PaperBotDecision[] }) {
  return (
    <tbody>
      {decisions.map((decision) => (
        <tr key={`${decision.symbol}-${decision.strategy_tag}-${decision.action}`}>
          <td>{decision.symbol}</td>
          <td>{decision.strategy_tag}</td>
          <td>{decision.action}</td>
          <td>{formatNumber(decision.total_score, 2)}</td>
          <td>{formatNumber(decision.qty)}</td>
          <td>{formatNumber(decision.limit_price, 2)}</td>
          <td>{decision.risk_passed ? "통과" : "차단"}</td>
          <td>{decision.paper_order_id ?? "-"}</td>
        </tr>
      ))}
    </tbody>
  );
}

/** paper-only bot route를 조작하는 Phase 10 전용 화면이다. */
export default function BotPage() {
  const [status, setStatus] = useState<ApiStatus>("loading");
  const [message, setMessage] = useState("모의투자 bot 상태 조회 중");
  const [botStatus, setBotStatus] = useState<PaperBotStatus | null>(null);
  const [paperStatus, setPaperStatus] = useState<PaperStatus | null>(null);
  const [runResult, setRunResult] = useState<PaperBotRunResponse | null>(null);
  const [stopResult, setStopResult] = useState<PaperBotStopResponse | null>(null);
  const [autoSubmit, setAutoSubmit] = useState(false);

  const loadBotState = useCallback(async (showLoading = true) => {
    if (showLoading) {
      setStatus("loading");
      setMessage("모의투자 bot 상태 조회 중");
    }
    try {
      const [botData, paperData] = await Promise.all([getBotStatus(), getPaperStatus()]);
      setBotStatus(botData);
      setPaperStatus(paperData);
      setStatus("ok");
      setMessage("모의투자 bot 상태 조회 완료");
    } catch (error) {
      setBotStatus(null);
      setPaperStatus(null);
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "모의투자 bot 상태 조회 실패");
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadBotState(false);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadBotState]);

  async function runOnce() {
    setStatus("loading");
    setMessage("모의투자 bot run-once 요청 중");
    try {
      const result = await runBotOnce({ auto_submit: autoSubmit });
      setRunResult(result);
      setStopResult(null);
      setStatus("ok");
      setMessage(`모의투자 bot run-once ${result.status}`);
      await loadBotState(false);
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "모의투자 bot run-once 실패");
      setRunResult(null);
    }
  }

  async function stopScheduler() {
    setStatus("loading");
    setMessage("모의투자 bot stop 요청 중");
    try {
      const result = await stopBot();
      setStopResult(result);
      setRunResult(null);
      setStatus("ok");
      setMessage(`모의투자 bot ${result.status}`);
      await loadBotState(false);
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "모의투자 bot stop 실패");
      setStopResult(null);
    }
  }

  const reasonCodes = [
    ...(botStatus?.reason_codes ?? []),
    ...(paperStatus?.kill_switch.reason_codes ?? []),
    ...(runResult?.reason_codes ?? []),
    ...(stopResult?.reason_codes ?? [])
  ];

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Phase 10 · 모의 자동매매봇</p>
          <h1>모의 자동매매봇</h1>
        </div>
        <nav className="nav">
          <Link href="/dashboard">대시보드</Link>
          <Link href="/data">데이터</Link>
          <Link href="/screener">스크리너</Link>
          <Link href="/reports">리포트</Link>
          <Link href="/backtest">백테스트</Link>
          <Link href="/portfolio">포트폴리오</Link>
          <Link href="/paper">모의투자</Link>
          <Link href="/bot">자동매매봇</Link>
          <Link href="/settings">설정</Link>
        </nav>
        <span className={`status ${status}`}>{message}</span>
      </header>

      <PaperModeBanner title="모의 자동매매봇 제어 · 실거래 아님" />

      <section className="cardGrid">
        <article>
          <h2>봇 상태</h2>
          <div className="metricGrid">
            <Metric label="활성" value={botStatus?.enabled} />
            <Metric label="모드" value={botStatus?.mode} />
            <Metric label="스케줄러" value={botStatus?.scheduler_enabled} />
            <Metric label="반복 실행 허용" value={botStatus?.loop_allowed} />
          </div>
        </article>
        <article>
          <h2>킬 스위치 / 제출 게이트</h2>
          <div className="metricGrid">
            <Metric label="킬 스위치" value={botStatus?.kill_switch_enabled ?? paperStatus?.kill_switch.blocking} />
            <Metric label="자동 제출 설정" value={botStatus?.auto_submit} />
            <Metric label="자동 제출 허용" value={botStatus?.auto_submit_allowed} />
            <Metric label="세션 통과" value={botStatus?.session_check_passed} />
          </div>
        </article>
        <article>
          <h2>안전 표시</h2>
          <div className="metricGrid">
            <Metric label="모의투자 전용" value="실거래 아님" />
            <Metric label="실주문 생성됨" value={botStatus?.live_order_created} />
            <Metric label="증권사 주문 생성됨" value={botStatus?.broker_order_created} />
            <Metric label="네트워크 호출" value={botStatus?.network_call_performed} />
          </div>
        </article>
      </section>

      <section className="grid">
        <article>
          <h2>단일 실행 제어</h2>
          <p className="muted">
            기본은 미리보기 의사결정 반복입니다. 자동 제출은 설정과 화면 체크박스가 모두 켜져도 킬 스위치와 장 세션 게이트가 통과해야만 허용됩니다.
          </p>
          <div className="formRow compactToolbar">
            <label>
              자동 제출 명시적 동의
              <input checked={autoSubmit} type="checkbox" onChange={(event) => setAutoSubmit(event.target.checked)} />
            </label>
            <button type="button" onClick={runOnce}>
              모의투자 단일 실행
            </button>
            <button type="button" className="secondary" onClick={stopScheduler}>
              모의투자 중지
            </button>
            <button type="button" className="secondary" onClick={() => loadBotState()}>
              새로고침
            </button>
          </div>
          <div className="metricGrid">
            <Metric label="마지막 실행 상태" value={runResult?.status ?? stopResult?.status ?? "-"} />
            <Metric label="자동 제출 요청됨" value={runResult?.auto_submit_requested ?? autoSubmit} />
            <Metric label="제출 건수" value={formatNumber(runResult?.submitted_count)} />
            <Metric label="의사결정 건수" value={formatNumber(runResult?.decision_count)} />
          </div>
        </article>
        <article>
          <h2>장 세션 / 사유</h2>
          <div className="metricGrid">
            <Metric label="장 세션" value={botStatus?.session.session} />
            <Metric label="세션 상태" value={botStatus?.session.session_state} />
            <Metric label="거래일" value={botStatus?.session.trade_date} />
            <Metric label="최대 후보 수" value={botStatus?.max_candidates} />
          </div>
          <ul className="plainList">
            {reasonCodes.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        </article>
      </section>

      <section className="grid">
        <article>
          <h2>의사결정 미리보기</h2>
          <div className="tableWrap compactTable">
            <table className="miniTable">
              <thead>
                <tr>
                  <th>종목코드</th>
                  <th>전략</th>
                  <th>액션</th>
                  <th>점수</th>
                  <th>수량</th>
                  <th>지정가</th>
                  <th>리스크</th>
                  <th>모의 주문 ID</th>
                </tr>
              </thead>
              <DecisionRows decisions={runResult?.decisions ?? []} />
            </table>
          </div>
        </article>
        <article>
          <h2>실행 단계</h2>
          <div className="tableWrap compactTable">
            <table className="miniTable">
              <thead>
                <tr>
                  <th>단계</th>
                  <th>상태</th>
                  <th>사유</th>
                </tr>
              </thead>
              <tbody>
                {(runResult?.steps ?? []).map((step) => (
                  <tr key={step.name}>
                    <td>{step.name}</td>
                    <td>{step.status}</td>
                    <td>{step.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>
      </section>

      <section className="cardGrid">
        <article>
          <h2>봇 카운트</h2>
          <div className="metricGrid">
            <Metric label="모의 봇 실행 수" value={formatNumber(botStatus?.counts.paper_bot_runs_count)} />
            <Metric label="모의 봇 의사결정 수" value={formatNumber(botStatus?.counts.paper_bot_decisions_count)} />
            <Metric label="모의 주문 수" value={formatNumber(botStatus?.counts.paper_orders_count)} />
            <Metric label="주문 테이블" value={formatNumber(botStatus?.counts.orders_count)} />
          </div>
        </article>
        <article>
          <h2>지원 모드</h2>
          <p className="muted">{botStatus?.supported_modes.join(", ") ?? "-"}</p>
        </article>
        <article>
          <h2>원본 결과</h2>
          <pre className="compactPre">{JSON.stringify(runResult ?? stopResult ?? botStatus ?? {}, null, 2)}</pre>
        </article>
      </section>
    </main>
  );
}
