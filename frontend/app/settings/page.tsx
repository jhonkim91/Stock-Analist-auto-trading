"use client";

import { useCallback, useEffect, useState } from "react";

import {
  callApi,
  type ApiStatus,
  type NotificationStatus,
  type NotificationTestResponse,
  type PaperBotStatus,
  type PaperStatus,
  type RuntimeEnvPreset,
  type RuntimeEnvPresetResponse,
  type RuntimeEnvStatus,
  type RuntimeEnvToggle,
  type RuntimeEnvToggleResponse,
  type SettingsPayload
} from "../../lib/api";
import { getNotificationStatus, sendNotificationTest } from "../../lib/notificationApi";
import { getBotStatus, getPaperStatus } from "../../lib/paperApi";

const sections = ["strategies", "risk", "backtest", "app"] as const;
const envCategoryOrder = ["paper", "bot", "broker", "kis", "telegram", "reports", "notifications", "locked"] as const;

function categoryTitle(category: string) {
  const labels: Record<string, string> = {
    paper: "Paper",
    bot: "Bot",
    broker: "Broker",
    kis: "KIS",
    telegram: "Telegram",
    reports: "Reports",
    notifications: "Notifications",
    locked: "Locked"
  };
  return labels[category] ?? category;
}

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

function runtimeToggleTooltip(toggle: RuntimeEnvToggle, nextEnabled: boolean) {
  if (toggle.false_locked) {
    return `${toggle.description} 클릭하면 현재 backend 프로세스에서 ${toggle.name}=false를 다시 적용합니다. 실계좌 주문은 이 화면에서 켤 수 없습니다.`;
  }
  const nextLabel = nextEnabled ? "켜짐" : "꺼짐";
  const impact = toggle.high_impact ? "주문, 토큰, 네트워크 호출 가능성에 영향을 줄 수 있으므로 관련 gate를 함께 확인해야 합니다." : "현재 프로세스에만 반영됩니다.";
  return `${toggle.description} 클릭하면 ${toggle.name} 값이 ${nextLabel} 상태로 바뀝니다. ${impact} 서버를 재시작하면 초기 설정으로 돌아갈 수 있습니다.`;
}

function runtimePresetTooltip(preset: RuntimeEnvPreset) {
  const changes = preset.changes.map((change) => `${change.name}=${change.value}`).join(", ");
  return `${preset.description} 클릭하면 현재 backend 프로세스에 즉시 반영됩니다. 적용값: ${changes}. 서버를 재시작하면 .env 또는 실행 환경 값으로 돌아갈 수 있습니다.`;
}

function settledValue<T>(result: PromiseSettledResult<T>): T | null {
  return result.status === "fulfilled" ? result.value : null;
}

function rejectedMessage(result: PromiseSettledResult<unknown>) {
  if (result.status !== "rejected") {
    return null;
  }
  return result.reason instanceof Error ? result.reason.message : "조회 실패";
}

export default function SettingsPage() {
  const [status, setStatus] = useState<ApiStatus>("loading");
  const [message, setMessage] = useState("조회 중");
  const [settings, setSettings] = useState<SettingsPayload | null>(null);
  const [notifications, setNotifications] = useState<NotificationStatus | null>(null);
  const [paperStatus, setPaperStatus] = useState<PaperStatus | null>(null);
  const [botStatus, setBotStatus] = useState<PaperBotStatus | null>(null);
  const [runtimeEnv, setRuntimeEnv] = useState<RuntimeEnvStatus | null>(null);
  const [notificationTest, setNotificationTest] = useState<NotificationTestResponse | null>(null);
  const [notificationTestStatus, setNotificationTestStatus] = useState<ApiStatus>("idle");
  const [envUpdating, setEnvUpdating] = useState<string | null>(null);
  const [presetUpdating, setPresetUpdating] = useState<string | null>(null);
  const [envMessage, setEnvMessage] = useState("process env");

  const loadSettings = useCallback(async (showLoading = true) => {
    if (showLoading) {
      setStatus("loading");
      setMessage("조회 중");
    }
    try {
      const [dataResult, notificationResult, paperResult, botResult, runtimeEnvResult] = await Promise.allSettled([
        callApi<SettingsPayload>("/api/settings"),
        getNotificationStatus(),
        getPaperStatus(),
        getBotStatus(),
        callApi<RuntimeEnvStatus>("/api/settings/runtime-env")
      ]);

      const failures = [dataResult, notificationResult, paperResult, botResult, runtimeEnvResult]
        .map(rejectedMessage)
        .filter(Boolean);
      setSettings(settledValue(dataResult));
      setNotifications(settledValue(notificationResult));
      setPaperStatus(settledValue(paperResult));
      setBotStatus(settledValue(botResult));
      setRuntimeEnv(settledValue(runtimeEnvResult));
      setStatus(dataResult.status === "fulfilled" || runtimeEnvResult.status === "fulfilled" ? "ok" : "error");
      setMessage(failures.length > 0 ? `일부 조회 실패 ${failures.length}건` : "조회 완료");
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "조회 실패");
      setSettings(null);
      setNotifications(null);
      setPaperStatus(null);
      setBotStatus(null);
      setRuntimeEnv(null);
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

  async function toggleRuntimeEnv(toggle: RuntimeEnvToggle) {
    const nextEnabled = toggle.false_locked ? false : !toggle.enabled;
    setEnvUpdating(toggle.name);
    setEnvMessage(`${toggle.name} 변경 중`);
    try {
      const result = await callApi<RuntimeEnvToggleResponse>("/api/settings/runtime-env/toggle", {
        method: "POST",
        body: JSON.stringify({
          name: toggle.name,
          enabled: nextEnabled,
          confirm: true
        })
      });
      if (!result.ok) {
        setEnvMessage(`${toggle.name}: ${result.reason_codes.join(", ") || "blocked"}`);
        return;
      }
      setEnvMessage(`${toggle.name}=${result.enabled ? "true" : "false"}`);
      await loadSettings(false);
    } catch (error) {
      setEnvMessage(error instanceof Error ? error.message : "env toggle failed");
    } finally {
      setEnvUpdating(null);
    }
  }

  async function applyRuntimePreset(preset: RuntimeEnvPreset) {
    setPresetUpdating(preset.name);
    setEnvMessage(`${preset.label} 적용 중`);
    try {
      const result = await callApi<RuntimeEnvPresetResponse>("/api/settings/runtime-env/preset", {
        method: "POST",
        body: JSON.stringify({
          name: preset.name,
          confirm: true
        })
      });
      if (!result.ok) {
        setEnvMessage(`${preset.label}: ${result.reason_codes.join(", ") || "blocked"}`);
        return;
      }
      setEnvMessage(`${preset.label} 적용 완료 (${result.applied.length}개 값)`);
      await loadSettings(false);
    } catch (error) {
      setEnvMessage(error instanceof Error ? error.message : "preset apply failed");
    } finally {
      setPresetUpdating(null);
    }
  }

  const groupedEnv = envCategoryOrder
    .map((category) => ({
      category,
      toggles: runtimeEnv?.toggles.filter((toggle) => toggle.category === category) ?? []
    }))
    .filter((group) => group.toggles.length > 0);

  const envPresets = runtimeEnv?.presets ?? [];

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
          backend/config/*.yaml 읽기 전용 요약 · env 버튼은 현재 backend 프로세스에만 반영
        </div>

        <article className="envPanel">
          <div className="card-hd">
            <span className="card-title">Runtime env</span>
            <span className="status ok" title={envMessage}>
              {runtimeEnv?.persistence ?? "process_only"}
            </span>
          </div>
          <div className="envPresetBar">
            {envPresets.map((preset) => {
              const tooltip = runtimePresetTooltip(preset);
              return (
                <button
                  className="presetButton"
                  data-tooltip={tooltip}
                  disabled={presetUpdating === preset.name}
                  key={preset.name}
                  onClick={() => void applyRuntimePreset(preset)}
                  title={tooltip}
                  type="button"
                >
                  {presetUpdating === preset.name ? "적용 중" : preset.label}
                </button>
              );
            })}
          </div>
          <div className="envGrid">
            {groupedEnv.map((group) => (
              <section className="envGroup" key={group.category}>
                <div className="envGroupTitle">{categoryTitle(group.category)}</div>
                {group.toggles.map((toggle) => {
                  const nextEnabled = toggle.false_locked ? false : !toggle.enabled;
                  const tooltip = runtimeToggleTooltip(toggle, nextEnabled);
                  const disabled = envUpdating === toggle.name;
                  return (
                    <div className="envToggleRow" key={toggle.name} title={tooltip}>
                      <div className="envToggleMeta">
                        <span className="envToggleLabel">{toggle.label}</span>
                        <span className="envToggleName">{toggle.name}</span>
                      </div>
                      <div className="envToggleControls">
                        {toggle.high_impact ? <span className="badge gradeC">gate</span> : null}
                        {toggle.false_locked ? <span className="badge fail">locked</span> : null}
                        <button
                          className={`envSwitch ${toggle.enabled ? "on" : "off"}`}
                          disabled={disabled}
                          data-tooltip={tooltip}
                          onClick={() => void toggleRuntimeEnv(toggle)}
                          title={tooltip}
                          type="button"
                        >
                          {envUpdating === toggle.name ? "..." : toggle.false_locked ? "LOCK" : toggle.enabled ? "ON" : "OFF"}
                        </button>
                      </div>
                    </div>
                  );
                })}
              </section>
            ))}
          </div>
          <div className="envMessage">{envMessage}</div>
        </article>

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
