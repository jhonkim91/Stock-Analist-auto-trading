"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { callApi, type ApiStatus, type SettingsPayload } from "../../lib/api";

const sections = ["strategies", "risk", "backtest", "app", "data_sources"] as const;

export default function SettingsPage() {
  const [status, setStatus] = useState<ApiStatus>("loading");
  const [message, setMessage] = useState("조회 중");
  const [settings, setSettings] = useState<SettingsPayload | null>(null);

  const loadSettings = useCallback(async (showLoading = true) => {
    if (showLoading) {
      setStatus("loading");
      setMessage("조회 중");
    }
    try {
      const data = await callApi<SettingsPayload>("/api/settings");
      setSettings(data);
      setStatus("ok");
      setMessage("조회 완료");
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "조회 실패");
      setSettings(null);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadSettings(false);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadSettings]);

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Phase 2</p>
          <h1>Settings</h1>
        </div>
        <nav className="nav">
          <Link href="/dashboard">Dashboard</Link>
          <Link href="/data">Data</Link>
          <Link href="/screener">Screener</Link>
          <Link href="/reports">Reports</Link>
          <Link href="/backtest">Backtest</Link>
          <Link href="/portfolio">Portfolio</Link>
        </nav>
        <span className={`status ${status}`}>{message}</span>
      </header>

      <section className="panel">
        <h2>Read-only config summary</h2>
        <p className="muted">backend/config/*.yaml 값만 표시한다. 웹 config 수정 기능은 제공하지 않는다.</p>
      </section>

      <section className="cardGrid">
        {sections.map((section) => (
          <article key={section}>
            <h2>{section}.yaml</h2>
            <pre className="tinyPre">{JSON.stringify(settings?.[section] ?? {}, null, 2)}</pre>
          </article>
        ))}
      </section>
    </main>
  );
}
