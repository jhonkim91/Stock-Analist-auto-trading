"use client";

import { useCallback, useEffect, useState } from "react";

import {
  callApi,
  type ApiStatus,
  type NotificationStatus,
  type NotificationTestResponse,
  type PaperBotStatus,
  type PaperStatus,
  type SettingsPayload
} from "../../lib/api";
import { getNotificationStatus, sendNotificationTest } from "../../lib/notificationApi";
import { getBotStatus, getPaperStatus } from "../../lib/paperApi";

const sections = ["strategies", "risk", "backtest", "app"] as const;

function PageIcon() {
  return (
    <svg className="pageTitleIcon" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z" />
      <path d="M4 12h2m12 0h2M12 4v2m0 12v2M6.3 6.3l1.4 1.4m8.6 8.6 1.4 1.4M17.7 6.3l-1.4 1.4m-8.6 8.6-1.4 1.4" />
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

function boolTone(value: boolean | null | undefined, positiveWhenTrue = true): "pos" | "neg" | "muted" {
  if (value === null || value === undefined) {
    return "muted";
  }
  return value === positiveWhenTrue ? "pos" : "neg";
}

function configSnippet(value: unknown) {
  if (value === null || value === undefined) {
    return "{}";
  }
  return JSON.stringify(value, null, 2);
}

export default function SettingsPage() {
  const [status, setStatus] = useState<ApiStatus>("loading");
  const [message, setMessage] = useState("조회 중");
  const [settings, setSettings] = useState<SettingsPayload | null>(null);
  const [notifications, setNotifications] = useState<NotificationStatus | null>(null);
  const [paperStatus, setPaperStatus] = useState<PaperStatus | null>(null);
  const [botStatus, setBotStatus] = useState<PaperBotStatus | null>(null);
  const [notificationTest, setNotificationTest] = useState<NotificationTestResponse | null>(null);
  const [notificationTestStatus, setNotificationTestStatus] = useState<ApiStatus>("idle");

  const loadSettings = useCallback(async (showLoading = true) => {
    if (showLoading) {
      setStatus("loading");
      setMessage("조회 중");
    }
    try {
      const [data, notificationStatus, paperRuntimeStatus, botRuntimeStatus] = await Promise.all([
        callApi<SettingsPayload>("/api/settings"),
        getNotificationStatus(),
        getPaperStatus(),
        getBotStatus()
      ]);
      setSettings(data);
      setNotifications(notificationStatus);
      setPaperStatus(paperRuntimeStatus);
      setBotStatus(botRuntimeStatus);
      setStatus("ok");
      setMessage("조회 완료");
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "조회 실패");
      setSettings(null);
      setNotifications(null);
      setPaperStatus(null);
      setBotStatus(null);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadSettings(false);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadSettings]);

  async function runNotificationTest() {
    setNotificationTestStatus("loading");
    try {
      const result = await sendNotificationTest({
        channel_alias: null,
        message: "paper notification dry-run",
        dry_run: true
      });
      setNotificationTest(result);
      setNotificationTestStatus(result.ok ? "ok" : "error");
    } catch (error) {
      setNotificationTest({
        ok: false,
        status: error instanceof Error ? error.message : "notification test failed",
        attempted: false,
        delivered: false,
        dry_run: true,
        reason_codes: ["FRONTEND_NOTIFICATION_TEST_FAILED"]
      });
      setNotificationTestStatus("error");
    }
  }

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <PageIcon />
          <h1>Settings</h1>
        </div>
        <div className="topbar-actions" title={message}>
          <span className={`status ${status}`}>{message}</span>
        </div>
      </header>

      <section className="scroll">
        <div className="warn-box info">
          <span aria-hidden="true">i</span>
          backend/config/*.yaml 읽기 전용 요약 — 웹 수정 기능 없음
        </div>

        <div className="g3">
          <article>
            <div className="card-hd">
              <span className="card-title">Paper summary</span>
            </div>
            <StatRow label="mode" value={paperStatus?.mode ?? "disabled"} />
            <StatRow label="enabled" value={String(paperStatus?.enabled ?? "-")} tone={boolTone(paperStatus?.enabled)} />
            <StatRow label="preview_only" value={String(paperStatus?.preview_only ?? "-")} tone={boolTone(paperStatus?.preview_only)} />
            <StatRow label="kill_switch" value={String(paperStatus?.kill_switch.blocking ?? "-")} tone={boolTone(paperStatus?.kill_switch.blocking, false)} />
          </article>

          <article>
            <div className="card-hd">
              <span className="card-title">Notification summary</span>
              <button type="button" onClick={runNotificationTest}>
                dry-run
              </button>
            </div>
            <StatRow label="enabled" value={String(notifications?.enabled ?? "-")} tone={boolTone(notifications?.enabled)} />
            <StatRow label="dry_run" value={String(notifications?.default_dry_run ?? "-")} tone={boolTone(notifications?.default_dry_run)} />
            <StatRow label="redacted" value={String(notifications?.secrets_redacted ?? "-")} tone={boolTone(notifications?.secrets_redacted)} />
            <StatRow label="test_status" value={notificationTest?.status ?? notificationTestStatus} />
          </article>

          <article>
            <div className="card-hd">
              <span className="card-title">Bot summary</span>
            </div>
            <StatRow label="runtime_enabled" value={String(botStatus?.enabled ?? "-")} tone={boolTone(botStatus?.enabled)} />
            <StatRow label="kill_switch" value={String(botStatus?.kill_switch_enabled ?? "-")} tone={boolTone(botStatus?.kill_switch_enabled, false)} />
            <StatRow label="auto_submit_allowed" value={String(botStatus?.auto_submit_allowed ?? "-")} tone={boolTone(botStatus?.auto_submit_allowed)} />
            <StatRow label="paper only" value="실거래 아님" tone="pos" />
          </article>
        </div>

        <div className="g2">
          {sections.map((section) => (
            <article key={section}>
              <div className="card-hd">
                <span className="card-title">{section}.yaml</span>
              </div>
              <pre className="tinyPre configPreview">{configSnippet(settings?.[section])}</pre>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}
