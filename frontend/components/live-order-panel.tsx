"use client";

import { useCallback, useEffect, useState } from "react";

import { callApi } from "../lib/api";

type LiveGate = {
  live_trading_enabled: boolean;
  live_order_submit_enabled: boolean;
  real_order_enabled: boolean;
  kill_switch: boolean;
  confirm_required: boolean;
  credentials_present: boolean;
  base_url_host: string;
  max_order_notional: number | null;
  can_submit: boolean;
  reason_codes: string[];
};

type OrderResult = {
  ok: boolean;
  status: string;
  reason_codes?: string[];
  broker_order_id?: string;
  broker_message?: string;
  tr_id?: string;
};

const REASON_TEXT: Record<string, string> = {
  LIVE_TRADING_DISABLED: "라이브 트레이딩이 꺼져 있음 (설정 → 라이브)",
  LIVE_ORDER_SUBMIT_DISABLED: "라이브 주문 제출이 꺼져 있음",
  ENABLE_REAL_ORDER_REQUIRED: "ENABLE_REAL_ORDER 토글이 꺼져 있음",
  LIVE_KILL_SWITCH_ACTIVE: "라이브 킬 스위치가 켜져 있음",
  KIS_LIVE_CREDENTIALS_MISSING: "KIS 자격증명 미설정 (설정 → 자격증명)",
  KIS_LIVE_BASE_URL_REQUIRED: "라이브 베이스 URL이 아님 (설정에서 라이브 URL 입력)",
  LIVE_ORDER_CONFIRM_REQUIRED: "주문 확인(confirm)이 필요함",
  LIVE_CANCEL_CONFIRM_REQUIRED: "취소 확인(confirm)이 필요함",
  LIVE_CANCEL_BROKER_ORDER_ID_REQUIRED: "취소할 주문 ID가 필요함",
  LIVE_MAX_ORDER_NOTIONAL_EXCEEDED: "주문 금액이 1회 한도를 초과함",
  KIS_LIVE_OVERSEAS_ORDER_UNSUPPORTED: "라이브는 현재 국내(KRX) 주문만 지원",
  KIS_LIVE_RESPONSE_ERROR: "KIS 응답 오류"
};

function reasonText(code: string): string {
  return REASON_TEXT[code] ?? code;
}

export function LiveOrderPanel() {
  const [gate, setGate] = useState<LiveGate | null>(null);
  const [symbol, setSymbol] = useState("");
  const [side, setSide] = useState<"buy" | "sell">("buy");
  const [qty, setQty] = useState("1");
  const [price, setPrice] = useState("");
  const [confirm, setConfirm] = useState(false);
  const [result, setResult] = useState<OrderResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [cancelId, setCancelId] = useState("");
  const [cancelConfirm, setCancelConfirm] = useState(false);

  const loadGate = useCallback(async () => {
    try {
      const data = await callApi<LiveGate>("/api/kis/orders/status");
      setGate(data);
    } catch {
      setGate(null);
    }
  }, []);

  useEffect(() => {
    void loadGate();
  }, [loadGate]);

  const submit = async () => {
    setBusy(true);
    setResult(null);
    try {
      const body = {
        symbol: symbol.trim(),
        side,
        qty: Number(qty) || 0,
        limit_price: price.trim() === "" ? null : Number(price),
        confirm
      };
      const res = await callApi<OrderResult>("/api/kis/orders/submit", { method: "POST", body: JSON.stringify(body) });
      setResult(res);
      await loadGate();
    } catch (error) {
      setResult({ ok: false, status: "error", reason_codes: [error instanceof Error ? error.message : "오류"] });
    } finally {
      setBusy(false);
    }
  };

  const cancel = async () => {
    setBusy(true);
    setResult(null);
    try {
      const res = await callApi<OrderResult>("/api/kis/orders/cancel", {
        method: "POST",
        body: JSON.stringify({ broker_order_id: cancelId.trim(), confirm: cancelConfirm })
      });
      setResult(res);
    } catch (error) {
      setResult({ ok: false, status: "error", reason_codes: [error instanceof Error ? error.message : "오류"] });
    } finally {
      setBusy(false);
    }
  };

  const canSubmit = Boolean(gate?.can_submit) && symbol.trim() !== "" && (Number(qty) || 0) > 0 && (!gate?.confirm_required || confirm);

  return (
    <>
      <div className="warn-box" style={{ background: "var(--color-background-danger)", color: "var(--color-text-danger)" }}>
        <span aria-hidden="true">⚠</span>
        실거래(라이브) 주문입니다. 제출 시 KIS 실계좌에 진짜 주문이 전송되어 실제 금전 손실이 발생할 수 있습니다. 처음에는 반드시 최소 수량으로 확인하세요.
      </div>

      <article className="noMargin" style={{ marginBottom: 12 }}>
        <div className="card-hd">
          <span className="card-title">라이브 게이트 상태</span>
          <button type="button" onClick={() => void loadGate()}>새로고침</button>
        </div>
        {gate ? (
          <>
            <div className="g4">
              <div className="kpi">
                <div className="kpi-lbl">제출 가능</div>
                <div className={`kpi-val ${gate.can_submit ? "pos" : "neg"}`}>{gate.can_submit ? "예" : "아니오"}</div>
              </div>
              <div className="kpi">
                <div className="kpi-lbl">라이브/실주문</div>
                <div className="kpi-val">{gate.live_trading_enabled ? "ON" : "off"} / {gate.real_order_enabled ? "ON" : "off"}</div>
              </div>
              <div className="kpi">
                <div className="kpi-lbl">자격증명 / 호스트</div>
                <div className="kpi-val">{gate.credentials_present ? "OK" : "없음"} · {gate.base_url_host === "non_live" ? "비라이브" : "라이브"}</div>
              </div>
              <div className="kpi">
                <div className="kpi-lbl">킬 스위치 / 한도</div>
                <div className="kpi-val">{gate.kill_switch ? "ON" : "off"} · {gate.max_order_notional ?? "-"}</div>
              </div>
            </div>
            {gate.reason_codes.length ? (
              <div className="mockStack" style={{ marginTop: 8 }}>
                {gate.reason_codes.map((code) => (
                  <div className="mockNotice warn" key={code}>{reasonText(code)}</div>
                ))}
              </div>
            ) : (
              <div className="mockNotice" style={{ marginTop: 8 }}>모든 게이트 통과 — 실주문 제출이 가능합니다.</div>
            )}
          </>
        ) : (
          <p className="muted">게이트 상태 조회 중…</p>
        )}
      </article>

      <article className="noMargin" style={{ marginBottom: 12 }}>
        <div className="card-hd">
          <span className="card-title">라이브 주문 (국내 KRX)</span>
        </div>
        <div className="mockFilters">
          <input placeholder="종목코드 (예: 005930)" value={symbol} onChange={(e) => setSymbol(e.target.value)} />
          <select value={side} onChange={(e) => setSide(e.target.value as "buy" | "sell")}>
            <option value="buy">매수</option>
            <option value="sell">매도</option>
          </select>
          <input placeholder="수량" value={qty} onChange={(e) => setQty(e.target.value)} />
          <input placeholder="지정가 (비우면 시장가)" value={price} onChange={(e) => setPrice(e.target.value)} />
        </div>
        <div className="mockButtonRow">
          <label style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
            <input type="checkbox" checked={confirm} onChange={(e) => setConfirm(e.target.checked)} />
            <span>실주문 확인 (confirm)</span>
          </label>
          <button type="button" className="primary" disabled={busy || !canSubmit} onClick={() => void submit()}>
            {busy ? "처리 중…" : "실주문 제출"}
          </button>
        </div>
      </article>

      <article className="noMargin" style={{ marginBottom: 12 }}>
        <div className="card-hd">
          <span className="card-title">라이브 주문 취소</span>
        </div>
        <div className="mockFilters">
          <input placeholder="broker_order_id" value={cancelId} onChange={(e) => setCancelId(e.target.value)} />
          <label style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
            <input type="checkbox" checked={cancelConfirm} onChange={(e) => setCancelConfirm(e.target.checked)} />
            <span>취소 확인</span>
          </label>
          <button type="button" disabled={busy || !cancelId.trim()} onClick={() => void cancel()}>취소 제출</button>
        </div>
      </article>

      {result ? (
        <article className="noMargin">
          <div className="card-hd">
            <span className="card-title">결과</span>
            <span className={`status ${result.ok ? "ok" : "error"}`}>{result.status}</span>
          </div>
          {result.broker_order_id ? <div className="stat-row"><span className="stat-k">broker_order_id</span><span>{result.broker_order_id}</span></div> : null}
          {result.tr_id ? <div className="stat-row"><span className="stat-k">tr_id</span><span>{result.tr_id}</span></div> : null}
          {result.broker_message ? <div className="stat-row"><span className="stat-k">메시지</span><span>{result.broker_message}</span></div> : null}
          {result.reason_codes?.length ? (
            <div className="mockStack" style={{ marginTop: 8 }}>
              {result.reason_codes.map((code) => (
                <div className="mockNotice warn" key={code}>{reasonText(code)}</div>
              ))}
            </div>
          ) : null}
        </article>
      ) : null}
    </>
  );
}
