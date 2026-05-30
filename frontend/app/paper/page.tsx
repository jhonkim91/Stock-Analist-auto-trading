"use client";

import { useCallback, useEffect, useState } from "react";

import { formatNumber, type ApiStatus, type PaperPreviewRequest, type PaperPreviewResponse, type PaperStatus } from "../../lib/api";
import { getPaperStatus, previewPaperOrder } from "../../lib/paperApi";

function PageIcon() {
  return (
    <svg className="pageTitleIcon" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M10 2v6l-5 9a3 3 0 0 0 2.6 4.5h8.8A3 3 0 0 0 19 17L14 8V2" />
      <path d="M8 2h8M8 14h8" />
    </svg>
  );
}

function StatusPill({ status, text }: { status: ApiStatus; text: string }) {
  return <span className={`status ${status}`}>{text}</span>;
}

function StatRow({ label, tone, value }: { label: string; tone?: "pos" | "neg" | "muted"; value: React.ReactNode }) {
  return (
    <div className="stat-row">
      <span className="stat-k">{label}</span>
      <span className={tone ?? ""}>{value}</span>
    </div>
  );
}

function boolTone(value: boolean | null | undefined, positiveWhenTrue = true): "pos" | "neg" | "muted" {
  if (value === null || value === undefined) {
    return "muted";
  }
  return value === positiveWhenTrue ? "pos" : "neg";
}

export default function PaperPage() {
  const [status, setStatus] = useState<ApiStatus>("loading");
  const [message, setMessage] = useState("모의투자 상태 조회 중");
  const [paperStatus, setPaperStatus] = useState<PaperStatus | null>(null);
  const [preview, setPreview] = useState<PaperPreviewResponse | null>(null);
  const [form, setForm] = useState<PaperPreviewRequest>({
    symbol: "KR009",
    side: "buy",
    qty: 10,
    limit_price: 100,
    stop_price: 90,
    strategy_tag: "paper_ui",
    venue: null,
    as_of: null
  });

  const loadPaperState = useCallback(async (showLoading = true) => {
    if (showLoading) {
      setStatus("loading");
      setMessage("모의투자 상태 조회 중");
    }
    try {
      const statusData = await getPaperStatus();
      setPaperStatus(statusData);
      setStatus("ok");
      setMessage("모의투자 상태 조회 완료");
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "모의투자 상태 조회 실패");
      setPaperStatus(null);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadPaperState(false);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadPaperState]);

  function updateForm<Key extends keyof PaperPreviewRequest>(key: Key, value: PaperPreviewRequest[Key]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function runPreview() {
    setStatus("loading");
    setMessage("모의투자 미리보기 실행 중");
    try {
      const data = await previewPaperOrder(form);
      setPreview(data);
      setPaperStatus(data);
      setStatus("ok");
      setMessage(`미리보기: ${data.risk_gate.decision}`);
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "모의투자 미리보기 실패");
      setPreview(null);
    }
  }

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <PageIcon />
          <h1>
            모의투자 <span className="muted">· Phase 3E-1</span>
          </h1>
        </div>
        <div className="topbar-actions" title={message}>
          <StatusPill status={status} text={message} />
        </div>
      </header>

      <section className="scroll">
        <div className="g3">
          <article>
            <div className="card-hd">
              <span className="card-title">모의투자 상태</span>
            </div>
            <StatRow label="활성" value={String(paperStatus?.enabled ?? "-")} tone={boolTone(paperStatus?.enabled)} />
            <StatRow label="주문 생성 가능" value={String(paperStatus?.can_create ?? "-")} tone={boolTone(paperStatus?.can_create)} />
            <StatRow label="미리보기 전용" value={String(paperStatus?.preview_only ?? "-")} tone={boolTone(paperStatus?.preview_only)} />
            <StatRow label="체결 시뮬레이션 가능" value={String(paperStatus?.can_simulate_fills ?? "-")} tone={boolTone(paperStatus?.can_simulate_fills)} />
          </article>

          <article>
            <div className="card-hd">
              <span className="card-title">안전 플래그</span>
            </div>
            <StatRow label="실주문 생성됨" value={String(paperStatus?.live_order_created ?? "-")} tone={boolTone(paperStatus?.live_order_created, false)} />
            <StatRow label="브로커 주문 생성됨" value={String(paperStatus?.broker_order_created ?? "-")} tone={boolTone(paperStatus?.broker_order_created, false)} />
            <StatRow label="네트워크 호출" value={String(paperStatus?.network_call_performed ?? "-")} tone={boolTone(paperStatus?.network_call_performed, false)} />
            <StatRow label="토큰 발급됨" value={String(paperStatus?.token_issued ?? "-")} tone={boolTone(paperStatus?.token_issued, false)} />
          </article>

          <article>
            <div className="card-hd">
              <span className="card-title">쓰기 건수</span>
            </div>
            <StatRow label="모의 주문" value={formatNumber(paperStatus?.counts.paper_orders_count)} />
            <StatRow label="모의 체결" value={formatNumber(paperStatus?.counts.paper_fills_count)} />
            <StatRow label="모의 포지션" value={formatNumber(paperStatus?.counts.paper_positions_count)} />
            <StatRow label="실주문" value={formatNumber(paperStatus?.counts.orders_count)} tone={paperStatus?.counts.orders_count === 0 ? "pos" : "neg"} />
          </article>
        </div>

        <article>
          <div className="card-hd">
            <span className="card-title">미리보기 요청</span>
            <button type="button" className="primary" onClick={runPreview}>
              미리보기
            </button>
          </div>
          <div className="mockFilters">
            <input value={form.symbol} onChange={(event) => updateForm("symbol", event.target.value)} />
            <select value={form.side} onChange={(event) => updateForm("side", event.target.value as "buy" | "sell")}>
              <option value="buy">매수</option>
              <option value="sell">매도</option>
            </select>
            <input min="1" type="number" value={form.qty} onChange={(event) => updateForm("qty", Number(event.target.value))} />
            <input
              min="0"
              type="number"
              value={form.limit_price ?? ""}
              onChange={(event) => updateForm("limit_price", event.target.value ? Number(event.target.value) : null)}
            />
          </div>
          <div className="previewResult">
            <StatRow label="미리보기" value={preview?.risk_gate.decision ?? paperStatus?.risk_gate.decision ?? "-"} />
            <StatRow label="모드" value={paperStatus?.mode ?? "paper"} />
            <StatRow label="사유" value={(preview?.risk_gate.reason_codes ?? paperStatus?.risk_gate.reason_codes ?? [paperStatus?.reason ?? "-"])[0] ?? "-"} />
          </div>
        </article>
      </section>
    </main>
  );
}
