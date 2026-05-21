"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import {
  callApi,
  formatNumber,
  type ApiStatus,
  type PaperPreviewRequest,
  type PaperPreviewResponse,
  type PaperStatus
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

export default function PaperPage() {
  const [status, setStatus] = useState<ApiStatus>("loading");
  const [message, setMessage] = useState("Paper status loading");
  const [paperStatus, setPaperStatus] = useState<PaperStatus | null>(null);
  const [preview, setPreview] = useState<PaperPreviewResponse | null>(null);
  const [form, setForm] = useState<PaperPreviewRequest>({
    symbol: "KR009",
    side: "buy",
    qty: 10,
    limit_price: 100,
    stop_price: 90,
    strategy_tag: "paper_preview"
  });

  const loadStatus = useCallback(async (showLoading = true) => {
    if (showLoading) {
      setStatus("loading");
      setMessage("Paper status loading");
    }
    try {
      const data = await callApi<PaperStatus>("/api/paper/status");
      setPaperStatus(data);
      setStatus("ok");
      setMessage("Paper status loaded");
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "Paper status failed");
      setPaperStatus(null);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadStatus(false);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadStatus]);

  function updateForm<Key extends keyof PaperPreviewRequest>(key: Key, value: PaperPreviewRequest[Key]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function runPreview() {
    setStatus("loading");
    setMessage("Paper preview running");
    try {
      const data = await callApi<PaperPreviewResponse>("/api/paper/orders/preview", {
        method: "POST",
        body: JSON.stringify(form)
      });
      setPreview(data);
      setPaperStatus(data);
      setStatus("ok");
      setMessage(`Paper preview ${data.risk_gate.decision}`);
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "Paper preview failed");
      setPreview(null);
    }
  }

  const reasonCodes = preview?.risk_gate.reason_codes ?? paperStatus?.risk_gate.reason_codes ?? [];

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Phase 3E-1</p>
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

      <section className="cardGrid">
        <article>
          <h2>Paper Status</h2>
          <div className="metricGrid">
            <Metric label="enabled" value={paperStatus?.enabled} />
            <Metric label="can_create" value={paperStatus?.can_create} />
            <Metric label="can_simulate_fills" value={paperStatus?.can_simulate_fills} />
            <Metric label="preview_only" value={paperStatus?.preview_only} />
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
          <h2>Write Counts</h2>
          <div className="metricGrid">
            <Metric label="paper_orders" value={formatNumber(paperStatus?.counts.paper_orders_count)} />
            <Metric label="paper_fills" value={formatNumber(paperStatus?.counts.paper_fills_count)} />
            <Metric label="paper_positions" value={formatNumber(paperStatus?.counts.paper_positions_count)} />
            <Metric label="real_orders" value={formatNumber(paperStatus?.counts.orders_count)} />
          </div>
        </article>
      </section>

      <section className="grid">
        <article>
          <h2>Preview Request</h2>
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
            <button type="button" onClick={runPreview}>
              Preview
            </button>
          </div>
        </article>
        <article>
          <h2>Preview Decision</h2>
          <div className="metricGrid">
            <Metric label="decision" value={preview?.risk_gate.decision ?? paperStatus?.risk_gate.decision} />
            <Metric label="paper_order_created" value={preview?.paper_order_created ?? paperStatus?.paper_order_created} />
            <Metric label="kill_switch" value={preview?.kill_switch.blocking ?? paperStatus?.kill_switch.blocking} />
            <Metric label="reason_count" value={formatNumber(reasonCodes.length)} />
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
          <h2>Status Payload</h2>
          <JsonBlock data={paperStatus} />
        </article>
        <article>
          <h2>Preview Payload</h2>
          <JsonBlock data={preview} />
        </article>
      </section>
    </main>
  );
}
