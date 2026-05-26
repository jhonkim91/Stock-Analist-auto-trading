"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { PaperModeBanner } from "../../components/paper-mode-banner";
import {
  callApi,
  formatNumber,
  type ApiStatus,
  type PaperCancelResponse,
  type PaperFill,
  type PaperFillsResponse,
  type PaperOrder,
  type PaperOrderListResponse,
  type PaperPortfolioResponse,
  type PaperPreviewRequest,
  type PaperPreviewResponse,
  type PaperStatus,
  type PaperSubmitResponse,
  type PaperSyncResponse
} from "../../lib/api";

function StatusPill({ status, text }: { status: ApiStatus; text: string }) {
  return <span className={`status ${status}`}>{text}</span>;
}

function Metric({ label, value }: { label: string; value: string | number | boolean | null | undefined }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value === undefined || value === null ? "-" : String(value)}</strong>
    </div>
  );
}

function JsonBlock({ data }: { data: unknown }) {
  return <pre className="compactPre">{JSON.stringify(data ?? {}, null, 2)}</pre>;
}

function PaperOrderRows({ orders }: { orders: PaperOrder[] }) {
  return (
    <tbody>
      {orders.slice(0, 8).map((order) => (
        <tr key={order.paper_order_id}>
          <td>{order.paper_order_id}</td>
          <td>{order.symbol}</td>
          <td>{order.side}</td>
          <td>{formatNumber(order.qty)}</td>
          <td>{formatNumber(order.remaining_qty)}</td>
          <td>{order.status}</td>
          <td>{order.live_order_created ? "true" : "false"}</td>
        </tr>
      ))}
    </tbody>
  );
}

function PaperFillRows({ fills }: { fills: PaperFill[] }) {
  return (
    <tbody>
      {fills.slice(0, 8).map((fill) => (
        <tr key={fill.paper_fill_id}>
          <td>{fill.paper_fill_id}</td>
          <td>{fill.symbol}</td>
          <td>{fill.side}</td>
          <td>{formatNumber(fill.qty)}</td>
          <td>{formatNumber(fill.price, 2)}</td>
          <td>{fill.fill_source}</td>
          <td>{fill.live_order_created ? "true" : "false"}</td>
        </tr>
      ))}
    </tbody>
  );
}

export default function PaperPage() {
  const [status, setStatus] = useState<ApiStatus>("loading");
  const [message, setMessage] = useState("모의투자 상태 조회 중");
  const [paperStatus, setPaperStatus] = useState<PaperStatus | null>(null);
  const [preview, setPreview] = useState<PaperPreviewResponse | null>(null);
  const [submitResult, setSubmitResult] = useState<PaperSubmitResponse | null>(null);
  const [cancelResult, setCancelResult] = useState<PaperCancelResponse | null>(null);
  const [syncResult, setSyncResult] = useState<PaperSyncResponse | null>(null);
  const [orders, setOrders] = useState<PaperOrder[]>([]);
  const [fills, setFills] = useState<PaperFill[]>([]);
  const [paperPortfolio, setPaperPortfolio] = useState<PaperPortfolioResponse | null>(null);
  const [submitConfirm, setSubmitConfirm] = useState(false);
  const [cancelConfirm, setCancelConfirm] = useState(false);
  const [submitIdempotencyKey, setSubmitIdempotencyKey] = useState("paper-ui-submit-1");
  const [cancelIdempotencyKey, setCancelIdempotencyKey] = useState("paper-ui-cancel-1");
  const [cancelOrderId, setCancelOrderId] = useState("");
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
      const [statusData, orderData, fillData, portfolioData] = await Promise.all([
        callApi<PaperStatus>("/api/paper/status"),
        callApi<PaperOrderListResponse>("/api/paper/orders"),
        callApi<PaperFillsResponse>("/api/paper/fills"),
        callApi<PaperPortfolioResponse>("/api/paper/portfolio")
      ]);
      setPaperStatus(statusData);
      setOrders(orderData.orders);
      setFills(fillData.fills);
      setPaperPortfolio(portfolioData);
      setStatus("ok");
      setMessage("모의투자 상태 조회 완료");
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "모의투자 상태 조회 실패");
      setPaperStatus(null);
      setOrders([]);
      setFills([]);
      setPaperPortfolio(null);
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
    setMessage("모의투자 preview 실행 중");
    try {
      const data = await callApi<PaperPreviewResponse>("/api/paper/orders/preview", {
        method: "POST",
        body: JSON.stringify(form)
      });
      setPreview(data);
      setPaperStatus(data);
      setStatus("ok");
      setMessage(`모의투자 preview: ${data.risk_gate.decision}`);
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "모의투자 preview 실패");
      setPreview(null);
    }
  }

  async function runSubmit() {
    setStatus("loading");
    setMessage("모의투자 submit 요청 중");
    const idempotencyKey = submitIdempotencyKey.trim() || `paper-ui-submit-${Date.now()}`;
    setSubmitIdempotencyKey(idempotencyKey);
    try {
      const data = await callApi<PaperSubmitResponse>("/api/paper/orders/submit", {
        method: "POST",
        body: JSON.stringify({
          ...form,
          confirm: submitConfirm,
          idempotency_key: idempotencyKey
        })
      });
      setSubmitResult(data);
      setStatus("ok");
      setMessage(data.ok ? "모의투자 submit 완료" : `모의투자 submit 차단: ${data.reason}`);
      await loadPaperState(false);
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "모의투자 submit 실패");
      setSubmitResult(null);
    }
  }

  async function runCancel() {
    setStatus("loading");
    setMessage("모의투자 cancel 요청 중");
    const idempotencyKey = cancelIdempotencyKey.trim() || `paper-ui-cancel-${Date.now()}`;
    setCancelIdempotencyKey(idempotencyKey);
    try {
      const data = await callApi<PaperCancelResponse>("/api/paper/orders/cancel", {
        method: "POST",
        body: JSON.stringify({
          paper_order_id: cancelOrderId,
          confirm: cancelConfirm,
          idempotency_key: idempotencyKey
        })
      });
      setCancelResult(data);
      setStatus("ok");
      setMessage(data.ok ? "모의투자 cancel 완료" : `모의투자 cancel 차단: ${data.reason}`);
      await loadPaperState(false);
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "모의투자 cancel 실패");
      setCancelResult(null);
    }
  }

  async function runSync() {
    setStatus("loading");
    setMessage("모의투자 sync 요청 중");
    try {
      const data = await callApi<PaperSyncResponse>("/api/paper/sync", {
        method: "POST",
        body: JSON.stringify({ scope: "all" })
      });
      setSyncResult(data);
      setStatus("ok");
      setMessage(data.sync_performed ? "모의투자 sync 완료" : `모의투자 sync 차단: ${data.reason}`);
      await loadPaperState(false);
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "모의투자 sync 실패");
      setSyncResult(null);
    }
  }

  const reasonCodes = [
    ...(preview?.risk_gate.reason_codes ?? paperStatus?.risk_gate.reason_codes ?? []),
    ...(submitResult?.reason_codes ?? []),
    ...(cancelResult?.reason_codes ?? []),
    ...(syncResult?.reason_codes ?? [])
  ];
  const snapshot = paperPortfolio?.snapshot ?? null;

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Phase 8 · 모의투자</p>
          <h1>Paper Trading</h1>
        </div>
        <nav className="nav">
          <Link href="/dashboard">Dashboard</Link>
          <Link href="/data">Data</Link>
          <Link href="/screener">Screener</Link>
          <Link href="/reports">Reports</Link>
          <Link href="/backtest">Backtest</Link>
          <Link href="/portfolio">Portfolio</Link>
          <Link href="/paper">Paper</Link>
          <Link href="/settings">Settings</Link>
        </nav>
        <StatusPill status={status} text={message} />
      </header>

      <PaperModeBanner title="모의투자 주문 제어 · 실거래 아님" />

      <section className="cardGrid">
        <article>
          <h2>Paper Status</h2>
          <div className="metricGrid">
            <Metric label="enabled" value={paperStatus?.enabled} />
            <Metric label="can_create" value={paperStatus?.can_create} />
            <Metric label="preview_only" value={paperStatus?.preview_only} />
            <Metric label="paper only" value={paperStatus?.mode ?? "paper"} />
          </div>
        </article>
        <article>
          <h2>Safety Flags</h2>
          <div className="metricGrid">
            <Metric label="live_order_created" value={paperStatus?.live_order_created} />
            <Metric label="broker_order_created" value={paperStatus?.broker_order_created} />
            <Metric label="network_call" value={paperStatus?.network_call_performed} />
            <Metric label="token_issued" value={paperStatus?.token_issued} />
          </div>
        </article>
        <article>
          <h2>Paper Counts</h2>
          <div className="metricGrid">
            <Metric label="paper_orders" value={formatNumber(paperStatus?.counts.paper_orders_count)} />
            <Metric label="paper_fills" value={formatNumber(paperStatus?.counts.paper_fills_count)} />
            <Metric label="paper_positions" value={formatNumber(paperStatus?.counts.paper_positions_count)} />
            <Metric label="orders table" value={formatNumber(paperStatus?.counts.orders_count)} />
          </div>
        </article>
      </section>

      <section className="grid">
        <article>
          <h2>Preview / Submit Request</h2>
          <div className="formRow">
            <label>
              symbol
              <input value={form.symbol} onChange={(event) => updateForm("symbol", event.target.value)} />
            </label>
            <label>
              side
              <select value={form.side} onChange={(event) => updateForm("side", event.target.value as "buy" | "sell")}>
                <option value="buy">buy</option>
                <option value="sell">sell</option>
              </select>
            </label>
            <label>
              qty
              <input
                min="1"
                type="number"
                value={form.qty}
                onChange={(event) => updateForm("qty", Number(event.target.value))}
              />
            </label>
            <label>
              limit_price
              <input
                min="0"
                type="number"
                value={form.limit_price ?? ""}
                onChange={(event) => updateForm("limit_price", event.target.value ? Number(event.target.value) : null)}
              />
            </label>
            <label>
              stop_price
              <input
                min="0"
                type="number"
                value={form.stop_price ?? ""}
                onChange={(event) => updateForm("stop_price", event.target.value ? Number(event.target.value) : null)}
              />
            </label>
            <label>
              strategy_tag
              <input
                value={form.strategy_tag ?? ""}
                onChange={(event) => updateForm("strategy_tag", event.target.value || null)}
              />
            </label>
            <button type="button" onClick={runPreview}>
              Preview
            </button>
            <button type="button" className="secondary" onClick={runSubmit}>
              Paper submit
            </button>
          </div>
          <div className="formRow compactToolbar">
            <label>
              confirm paper submit
              <input checked={submitConfirm} type="checkbox" onChange={(event) => setSubmitConfirm(event.target.checked)} />
            </label>
            <label>
              idempotency_key
              <input value={submitIdempotencyKey} onChange={(event) => setSubmitIdempotencyKey(event.target.value)} />
            </label>
          </div>
        </article>
        <article>
          <h2>Cancel / Sync</h2>
          <div className="formRow">
            <label>
              paper_order_id
              <input value={cancelOrderId} onChange={(event) => setCancelOrderId(event.target.value)} />
            </label>
            <label>
              confirm paper cancel
              <input checked={cancelConfirm} type="checkbox" onChange={(event) => setCancelConfirm(event.target.checked)} />
            </label>
            <label>
              cancel idempotency_key
              <input value={cancelIdempotencyKey} onChange={(event) => setCancelIdempotencyKey(event.target.value)} />
            </label>
            <button type="button" className="secondary" onClick={runCancel}>
              Paper cancel
            </button>
            <button type="button" onClick={runSync}>
              Sync paper snapshot
            </button>
          </div>
          <div className="metricGrid">
            <Metric label="preview" value={preview?.risk_gate.decision ?? paperStatus?.risk_gate.decision} />
            <Metric label="submit" value={submitResult?.status} />
            <Metric label="cancel" value={cancelResult?.status} />
            <Metric label="sync" value={syncResult?.status} />
          </div>
          <ul className="plainList">
            {reasonCodes.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        </article>
      </section>

      <section className="cardGrid">
        <article>
          <h2>Paper Portfolio Snapshot</h2>
          <div className="metricGrid">
            <Metric label="snapshot_id" value={snapshot?.snapshot_id} />
            <Metric label="total_equity" value={formatNumber(snapshot?.total_equity)} />
            <Metric label="market_value" value={formatNumber(snapshot?.market_value)} />
            <Metric label="source" value={paperPortfolio?.source} />
          </div>
        </article>
        <article>
          <h2>Paper Positions Summary</h2>
          <div className="metricGrid">
            <Metric label="count" value={formatNumber(paperPortfolio?.positions_summary.count)} />
            <Metric label="total_qty" value={formatNumber(paperPortfolio?.positions_summary.total_qty)} />
            <Metric label="market_value" value={formatNumber(paperPortfolio?.positions_summary.market_value)} />
            <Metric label="unrealized_pnl" value={formatNumber(paperPortfolio?.positions_summary.unrealized_pnl)} />
          </div>
        </article>
        <article>
          <h2>Separation Check</h2>
          <div className="metricGrid">
            <Metric label="paper_source" value={String(paperPortfolio?.separation_contract.paper_positions_table ?? "-")} />
            <Metric label="snapshot_source" value={String(paperPortfolio?.separation_contract.paper_snapshots_table ?? "-")} />
            <Metric label="mixed" value={String(paperPortfolio?.separation_contract.mixed ?? false)} />
            <Metric label="reason" value={paperPortfolio?.reason ?? "ok"} />
          </div>
        </article>
      </section>

      <section className="grid">
        <article>
          <h2>Recent Paper Orders</h2>
          <div className="tableWrap compactTable">
            <table className="miniTable">
              <thead>
                <tr>
                  <th>paper_order_id</th>
                  <th>symbol</th>
                  <th>side</th>
                  <th>qty</th>
                  <th>remaining</th>
                  <th>status</th>
                  <th>live</th>
                </tr>
              </thead>
              <PaperOrderRows orders={orders} />
            </table>
          </div>
        </article>
        <article>
          <h2>Recent Paper Fills</h2>
          <div className="tableWrap compactTable">
            <table className="miniTable">
              <thead>
                <tr>
                  <th>paper_fill_id</th>
                  <th>symbol</th>
                  <th>side</th>
                  <th>qty</th>
                  <th>price</th>
                  <th>source</th>
                  <th>live</th>
                </tr>
              </thead>
              <PaperFillRows fills={fills} />
            </table>
          </div>
        </article>
      </section>

      <section className="grid">
        <article>
          <h2>Action Result</h2>
          <JsonBlock data={submitResult ?? cancelResult ?? syncResult ?? preview} />
        </article>
        <article>
          <h2>Paper Portfolio Payload</h2>
          <JsonBlock data={paperPortfolio} />
        </article>
      </section>
    </main>
  );
}
