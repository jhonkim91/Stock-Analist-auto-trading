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
import { EnvironmentSettings } from "../../components/environment-settings";

const sections = ["strategies", "risk", "backtest", "app"] as const;
const envCategoryOrder = ["paper", "bot", "broker", "kis", "telegram", "reports", "notifications", "live", "locked"] as const;
const fallbackEnvPresets: RuntimeEnvPreset[] = [
  {
    name: "paper_kis_ready",
    label: "모의 주문 준비",
    category: "paper",
    description: "KIS 모의투자 주문/취소/조회에 필요한 paper_kis gate를 한 번에 켭니다. 실계좌 주문은 계속 false로 잠급니다.",
    high_impact: true,
    scope: "process",
    changes: []
  },
  {
    name: "paper_bot_auto_on",
    label: "자동매매 ON",
    category: "bot",
    description: "모의 자동매매봇을 paper_kis 기준으로 켜고 auto-submit gate까지 켭니다. live 주문은 계속 차단됩니다.",
    high_impact: true,
    scope: "process",
    changes: []
  },
  {
    name: "telegram_report_ready",
    label: "텔레그램 리포트 ON",
    category: "telegram",
    description: "Telegram bot/report scheduler와 장전/장후/주간 리포트 gate를 켭니다. 토큰과 chat_id 값은 현재 로그인 사용자 설정 또는 .env에서 읽습니다.",
    high_impact: true,
    scope: "process",
    changes: []
  },
  {
    name: "paper_bot_safe_stop",
    label: "봇/주문 정지",
    category: "locked",
    description: "모의 자동매매와 신규 모의 주문을 즉시 막는 process-only 정지 preset입니다. live 주문은 계속 false입니다.",
    high_impact: true,
    scope: "process",
    changes: []
  }
];
const notificationDryRunTooltip = "Telegram/Discord 알림 설정을 실제 전송 없이 dry-run으로 검증합니다. 토큰, chat_id, webhook 원문은 화면에 표시하지 않습니다.";

function fallbackToggle(
  name: string,
  label: string,
  category: string,
  description: string,
  options: { falseLocked?: boolean; highImpact?: boolean } = {}
): RuntimeEnvToggle {
  return {
    name,
    label,
    category,
    description,
    enabled: false,
    configured: false,
    value: "false",
    can_toggle: true,
    false_locked: options.falseLocked ?? false,
    high_impact: options.highImpact ?? false,
    scope: "process",
    reason_codes: options.falseLocked ? ["LIVE_ENV_TOGGLE_LOCKED_FALSE"] : []
  };
}

const fallbackEnvToggles: RuntimeEnvToggle[] = [
  fallbackToggle("PAPER_TRADING_ENABLED", "Paper trading", "paper", "모의투자 기능 전체를 현재 backend 프로세스에서 켜거나 끕니다."),
  fallbackToggle("PAPER_TRADING_CAN_CREATE", "Paper create", "paper", "paper_orders에 모의 주문을 생성할 수 있는지 제어합니다."),
  fallbackToggle("PAPER_TRADING_NETWORK_ENABLED", "Paper network", "paper", "KIS 모의투자 API 호출 허용 게이트입니다. 버튼 클릭만으로 주문이 즉시 전송되지는 않습니다.", { highImpact: true }),
  fallbackToggle("PAPER_TRADING_KILL_SWITCH", "Paper kill switch", "paper", "켜져 있으면 신규 모의 주문 생성을 차단합니다.", { highImpact: true }),
  fallbackToggle("PAPER_BOT_ENABLED", "Bot enabled", "bot", "모의 자동매매봇 실행 자체를 현재 backend 프로세스에서 켜거나 끕니다."),
  fallbackToggle("PAPER_BOT_AUTO_SUBMIT", "Bot auto-submit", "bot", "봇 실행 결과가 조건을 통과했을 때 모의 주문 제출까지 허용할지 제어합니다.", { highImpact: true }),
  fallbackToggle("PAPER_BOT_SCHEDULER_ENABLED", "Bot scheduler", "bot", "모의 자동매매봇 반복 실행 scheduler gate입니다.", { highImpact: true }),
  fallbackToggle("PAPER_BOT_KILL_SWITCH", "Bot kill switch", "bot", "켜져 있으면 봇의 모의 주문 제출을 차단합니다.", { highImpact: true }),
  fallbackToggle("PAPER_BOT_CONFIRM", "Bot confirm", "bot", "봇과 모의 주문 제출에 필요한 최종 확인 게이트입니다."),
  fallbackToggle("PAPER_ORDER_SUBMIT_ENABLED", "Paper order submit", "broker", "KIS 모의투자 주문 adapter 제출 게이트입니다.", { highImpact: true }),
  fallbackToggle("PAPER_SYNC_WORKER_ENABLED", "Paper sync worker", "broker", "모의투자 미체결/체결/잔고 동기화 worker 실행 게이트입니다.", { highImpact: true }),
  fallbackToggle("KIS_TOKEN_ISSUE_ENABLED", "Token issue", "kis", "KIS 모의투자 access token 발급 API 호출 게이트입니다.", { highImpact: true }),
  fallbackToggle("KIS_TOKEN_CACHE_ENABLED", "Token cache", "kis", "KIS 모의투자 access token을 로컬 cache 파일에 저장할지 제어합니다.", { highImpact: true }),
  fallbackToggle("KIS_MARKET_QUOTE_ENABLED", "KIS quote", "kis", "종목 상세 조회에서 KIS 현재가 API를 우선 사용할지 제어합니다.", { highImpact: true }),
  fallbackToggle("TELEGRAM_BOT_ENABLED", "Telegram bot", "telegram", "Telegram 명령 dispatcher를 현재 backend 프로세스에서 켜거나 끕니다."),
  fallbackToggle("TELEGRAM_REPORT_SCHEDULER_ENABLED", "Report scheduler", "telegram", "Telegram 장전/장후/주간 리포트 scheduler 실행 게이트입니다."),
  fallbackToggle("TELEGRAM_PRE_MARKET_REPORT_ENABLED", "Pre-market report", "telegram", "장 시작 전 Telegram 리포트 slot을 켜거나 끕니다."),
  fallbackToggle("TELEGRAM_POST_MARKET_REPORT_ENABLED", "Post-market report", "telegram", "장 종료 후 Telegram 리포트 slot을 켜거나 끕니다."),
  fallbackToggle("TELEGRAM_WEEKLY_REPORT_ENABLED", "Weekly report", "telegram", "주간 Telegram 리포트 slot을 켜거나 끕니다."),
  fallbackToggle("ENABLE_REAL_ORDER", "Live order lock", "locked", "실계좌 주문 잠금입니다. 버튼을 눌러도 false로만 강제 적용됩니다.", { falseLocked: true, highImpact: true })
];

function categoryTitle(category: string) {
  const labels: Record<string, string> = {
    paper: "모의투자",
    bot: "자동매매봇",
    broker: "브로커",
    kis: "KIS",
    telegram: "텔레그램",
    reports: "리포트",
    notifications: "알림",
    live: "라이브 (실거래·고위험)",
    locked: "잠금"
  };
  return labels[category] ?? category;
}

// 토글 라벨(영문)을 ENV 이름 기준으로 한글로 표시한다. API/폴백 라벨과 무관하게 일관 표기.
const ENV_LABELS_KO: Record<string, string> = {
  PAPER_TRADING_ENABLED: "모의투자 사용",
  PAPER_TRADING_CAN_CREATE: "모의 주문 생성",
  PAPER_TRADING_NETWORK_ENABLED: "모의 네트워크 호출",
  PAPER_TRADING_KILL_SWITCH: "모의 킬 스위치",
  PAPER_BOT_ENABLED: "봇 사용",
  PAPER_BOT_AUTO_SUBMIT: "봇 자동 제출",
  PAPER_BOT_SCHEDULER_ENABLED: "봇 스케줄러",
  PAPER_BOT_KILL_SWITCH: "봇 킬 스위치",
  PAPER_BOT_CONFIRM: "봇 최종 확인",
  PAPER_ORDER_SUBMIT_ENABLED: "모의 주문 제출",
  PAPER_SYNC_WORKER_ENABLED: "모의 동기화 워커",
  KIS_TOKEN_ISSUE_ENABLED: "KIS 토큰 발급",
  KIS_TOKEN_CACHE_ENABLED: "KIS 토큰 캐시",
  KIS_MARKET_QUOTE_ENABLED: "KIS 현재가 사용",
  KIS_WEBSOCKET_APPROVAL_ENABLED: "KIS 웹소켓 승인",
  PAPER_WEBSOCKET_ENABLED: "모의 웹소켓",
  PAPER_WEBSOCKET_CONNECT_ENABLED: "모의 웹소켓 연결",
  TELEGRAM_BOT_ENABLED: "텔레그램 봇",
  TELEGRAM_POLLING_ENABLED: "텔레그램 폴링",
  TELEGRAM_POLLING_SEND_REPLIES: "텔레그램 응답 전송",
  TELEGRAM_REPORT_SCHEDULER_ENABLED: "리포트 스케줄러",
  TELEGRAM_PRE_MARKET_REPORT_ENABLED: "장 시작 전 리포트",
  TELEGRAM_POST_MARKET_REPORT_ENABLED: "장 종료 후 리포트",
  TELEGRAM_WEEKLY_REPORT_ENABLED: "주간 리포트",
  TELEGRAM_REPORT_DRY_RUN: "텔레그램 리포트 드라이런",
  REPORT_AUTOMATION_ENABLED: "리포트 자동화",
  REPORT_AUTOMATION_DRY_RUN: "리포트 드라이런",
  REPORT_AUTOMATION_NOTIFY: "리포트 알림 전송",
  NOTIFICATIONS_ENABLED: "알림 사용",
  NOTIFICATIONS_DEFAULT_DRY_RUN: "알림 드라이런",
  ENABLE_REAL_ORDER: "실계좌 주문 잠금"
};

function envLabelKo(toggle: RuntimeEnvToggle): string {
  return ENV_LABELS_KO[toggle.name] ?? toggle.label;
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
  const changeText = changes ? `적용값: ${changes}.` : "적용값은 서버 allowlist 기준으로 적용됩니다.";
  return `${preset.description} 클릭하면 현재 backend 프로세스에 즉시 반영됩니다. ${changeText} 서버를 재시작하면 .env 또는 실행 환경 값으로 돌아갈 수 있습니다.`;
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

  const envToggles = runtimeEnv?.toggles?.length ? runtimeEnv.toggles : fallbackEnvToggles;
  const groupedEnv = envCategoryOrder
    .map((category) => ({
      category,
      toggles: envToggles.filter((toggle) => toggle.category === category)
    }))
    .filter((group) => group.toggles.length > 0);

  const envPresets = runtimeEnv?.presets?.length ? runtimeEnv.presets : fallbackEnvPresets;

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <PageIcon />
          <h1>설정</h1>
        </div>
        <div className="topbar-actions" title={message}>
          <span className={`status ${status}`}>{message}</span>
        </div>
      </header>

      <section className="scroll">
        <div className="warn-box info">
          <span aria-hidden="true">i</span>
          backend/config/*.yaml 읽기 전용 요약 · env 버튼은 현재 로그인 사용자 설정으로 분리 저장
        </div>

        <article className="envPanel">
          <div className="card-hd">
            <span className="card-title">런타임 환경</span>
            <span className="status ok" title={envMessage}>
              {runtimeEnv?.scope === "user" ? `user · ${runtimeEnv.user_id ?? ""}` : (runtimeEnv?.persistence ?? "global")}
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
                      <div className="envToggleMeta" data-tooltip={tooltip} tabIndex={0}>
                        <span className="envToggleLabel">{envLabelKo(toggle)}</span>
                        <span className="envToggleName">{toggle.name}</span>
                      </div>
                      <div className="envToggleControls">
                        {toggle.high_impact ? <span className="badge gradeC">게이트</span> : null}
                        {toggle.false_locked ? <span className="badge fail">잠금</span> : null}
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

        <EnvironmentSettings />

        <div className="g3">
          <article>
            <div className="card-hd">
              <span className="card-title">모의투자 요약</span>
            </div>
            <StatRow label="모드" value={paperStatus?.mode ?? "disabled"} />
            <StatRow label="활성" value={String(paperStatus?.enabled ?? "-")} tone={boolTone(paperStatus?.enabled)} />
            <StatRow label="미리보기 전용" value={String(paperStatus?.preview_only ?? "-")} tone={boolTone(paperStatus?.preview_only)} />
            <StatRow label="킬 스위치" value={String(paperStatus?.kill_switch.blocking ?? "-")} tone={boolTone(paperStatus?.kill_switch.blocking, false)} />
          </article>

          <article>
            <div className="card-hd">
              <span className="card-title">알림 요약</span>
              <button data-tooltip={notificationDryRunTooltip} title={notificationDryRunTooltip} type="button" onClick={runNotificationTest}>
                드라이런
              </button>
            </div>
            <StatRow label="활성" value={String(notifications?.enabled ?? "-")} tone={boolTone(notifications?.enabled)} />
            <StatRow label="드라이런" value={String(notifications?.default_dry_run ?? "-")} tone={boolTone(notifications?.default_dry_run)} />
            <StatRow label="비밀값 마스킹" value={String(notifications?.secrets_redacted ?? "-")} tone={boolTone(notifications?.secrets_redacted)} />
            <StatRow label="테스트 상태" value={notificationTest?.status ?? notificationTestStatus} />
          </article>

          <article>
            <div className="card-hd">
              <span className="card-title">봇 요약</span>
            </div>
            <StatRow label="실행 활성" value={String(botStatus?.enabled ?? "-")} tone={boolTone(botStatus?.enabled)} />
            <StatRow label="킬 스위치" value={String(botStatus?.kill_switch_enabled ?? "-")} tone={boolTone(botStatus?.kill_switch_enabled, false)} />
            <StatRow label="자동 제출 허용" value={String(botStatus?.auto_submit_allowed ?? "-")} tone={boolTone(botStatus?.auto_submit_allowed)} />
            <StatRow label="실거래 아님" value="실거래 아님" tone="pos" />
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
