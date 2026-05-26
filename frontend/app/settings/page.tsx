"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { PaperModeBanner } from "../../components/paper-mode-banner";
import { callApi, type ApiStatus, type NotificationStatus, type PaperStatus, type SettingsPayload } from "../../lib/api";

const sections = ["strategies", "risk", "backtest", "app", "data_sources", "notifications", "bot"] as const;

function asRecord(value: unknown): Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function Metric({ label, value }: { label: string; value: string | number | boolean | null | undefined }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value === undefined || value === null ? "-" : String(value)}</strong>
    </div>
  );
}

export default function SettingsPage() {
  const [status, setStatus] = useState<ApiStatus>("loading");
  const [message, setMessage] = useState("조회 중");
  const [settings, setSettings] = useState<SettingsPayload | null>(null);
  const [notifications, setNotifications] = useState<NotificationStatus | null>(null);
  const [paperStatus, setPaperStatus] = useState<PaperStatus | null>(null);

  const loadSettings = useCallback(async (showLoading = true) => {
    if (showLoading) {
      setStatus("loading");
      setMessage("조회 중");
    }
    try {
      const [data, notificationStatus, paperRuntimeStatus] = await Promise.all([
        callApi<SettingsPayload>("/api/settings"),
        callApi<NotificationStatus>("/api/notifications/status"),
        callApi<PaperStatus>("/api/paper/status")
      ]);
      setSettings(data);
      setNotifications(notificationStatus);
      setPaperStatus(paperRuntimeStatus);
      setStatus("ok");
      setMessage("조회 완료");
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "조회 실패");
      setSettings(null);
      setNotifications(null);
      setPaperStatus(null);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadSettings(false);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadSettings]);

  const botSettings = asRecord(settings?.bot);
  const botConfig = asRecord(botSettings.bot);

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Phase 8 · Settings</p>
          <h1>Settings</h1>
        </div>
        <nav className="nav">
          <Link href="/dashboard">Dashboard</Link>
          <Link href="/data">Data</Link>
          <Link href="/screener">Screener</Link>
          <Link href="/reports">Reports</Link>
          <Link href="/backtest">Backtest</Link>
          <Link href="/portfolio">Portfolio</Link>
          <Link href="/paper">Paper</Link>
        </nav>
        <span className={`status ${status}`}>{message}</span>
      </header>

      <PaperModeBanner title="모의투자 설정 요약 · redacted" />

      <section className="panel">
        <h2>Read-only config summary</h2>
        <p className="muted">backend/config/*.yaml 값만 표시한다. 웹 config 수정 기능은 제공하지 않는다.</p>
      </section>

      <section className="cardGrid">
        <article>
          <h2>Paper summary</h2>
          <div className="metricGrid">
            <Metric label="mode" value={paperStatus?.mode ?? "disabled"} />
            <Metric label="enabled" value={paperStatus?.enabled} />
            <Metric label="preview_only" value={paperStatus?.preview_only} />
            <Metric label="kill_switch" value={paperStatus?.kill_switch.blocking} />
          </div>
        </article>
        <article>
          <h2>Notification summary</h2>
          <div className="metricGrid">
            <Metric label="enabled" value={notifications?.enabled} />
            <Metric label="dry_run" value={notifications?.default_dry_run} />
            <Metric label="redacted" value={notifications?.secrets_redacted} />
            <Metric label="channels" value={notifications?.channels.length} />
          </div>
        </article>
        <article>
          <h2>Bot summary</h2>
          <div className="metricGrid">
            <Metric label="enabled" value={String(botConfig.enabled ?? false)} />
            <Metric label="scheduler" value={String(botConfig.scheduler_enabled ?? false)} />
            <Metric label="auto_submit" value={String(botConfig.auto_submit ?? false)} />
            <Metric label="paper only" value="실거래 아님" />
          </div>
        </article>
      </section>

      {notifications ? (
        <>
          <section className="panel">
            <h2>Notification status</h2>
            <p className="muted">
              {notifications.enabled ? "enabled" : "disabled"} · {notifications.default_dry_run ? "dry-run" : "direct"} ·
              {notifications.secrets_redacted ? " redacted" : " unredacted"}
            </p>
          </section>

          <section className="cardGrid">
            {notifications.channels.map((channel) => (
              <article key={channel.alias}>
                <h2>{channel.alias}</h2>
                <p className="muted">
                  {channel.type} · {channel.mode} · {channel.configured ? "configured" : "not configured"}
                </p>
                <pre className="tinyPre">{JSON.stringify(channel.credential_fields, null, 2)}</pre>
              </article>
            ))}
          </section>
        </>
      ) : null}

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
