"use client";

import { useCallback, useEffect, useState } from "react";

import { callApi, formatNumber, type BrokerStatus, type MarketRegime, type MarketSession } from "../lib/api";

type GlobalStatus = {
  regime: MarketRegime | null;
  session: MarketSession | null;
  broker: BrokerStatus | null;
  message: string;
};

const emptyStatus: GlobalStatus = {
  regime: null,
  session: null,
  broker: null,
  message: "status loading"
};

function regimeTone(regime: string | undefined) {
  if (regime === "bull") {
    return "ok";
  }
  if (regime === "bear") {
    return "err";
  }
  return "warn";
}

function formatRatio(value: number | null | undefined) {
  return value === null || value === undefined ? "-" : formatNumber(value, 2);
}

function TrendIcon() {
  return (
    <svg aria-hidden="true" className="gbarIcon" viewBox="0 0 24 24">
      <path d="M5 16 10 11l4 4 5-7" />
      <path d="M15 8h4v4" />
    </svg>
  );
}

function LockIcon() {
  return (
    <svg aria-hidden="true" className="gbarIcon" viewBox="0 0 24 24">
      <rect height="10" rx="2" width="14" x="5" y="10" />
      <path d="M8 10V8a4 4 0 0 1 8 0v2" />
    </svg>
  );
}

/** 전역 상단에서 시장 국면, breadth, 세션, preview-only 안전 상태를 한 줄로 보여준다. */
export function GlobalStatusBar() {
  const [status, setStatus] = useState<GlobalStatus>(emptyStatus);

  const loadStatus = useCallback(async () => {
    const [regimeResult, sessionResult, brokerResult] = await Promise.allSettled([
      callApi<MarketRegime>("/api/market/regime"),
      callApi<MarketSession>("/api/market/session?venue=KRX"),
      callApi<BrokerStatus>("/api/broker/status")
    ]);

    setStatus({
      regime: regimeResult.status === "fulfilled" ? regimeResult.value : null,
      session: sessionResult.status === "fulfilled" ? sessionResult.value : null,
      broker: brokerResult.status === "fulfilled" ? brokerResult.value : null,
      message:
        regimeResult.status === "fulfilled" || sessionResult.status === "fulfilled" || brokerResult.status === "fulfilled"
          ? "status ready"
          : "status unavailable"
    });
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadStatus();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadStatus]);

  const regime = status.regime?.regime ?? "neutral";
  const sessionName = status.session?.session ?? "unknown";
  const benchmark = status.regime?.benchmark ?? "KOSPI";
  const tradeDate = status.regime?.trade_date ?? status.session?.trade_date ?? "-";
  const previewOnly = status.broker?.preview_only ?? true;
  const canSubmit = status.broker?.can_submit ?? false;

  return (
    <div className="gbar" aria-label="Global market and safety status" role="status">
      <span className={`gbar-pill gbar-${regimeTone(regime)}`}>
        <TrendIcon />
        {regime}
      </span>
      <div className="gbar-sep" />
      <span className="gbar-txt">
        regime score <strong>{formatRatio(status.regime?.market_score)}</strong>
      </span>
      <div className="gbar-sep" />
      <span className="gbar-txt">
        KRX <strong className={sessionName === "regular" ? "pos" : "warn"}>●</strong> {sessionName}
      </span>
      <div className="gbar-sep" />
      <span className="gbar-txt">
        {benchmark} <strong>benchmark</strong>
      </span>
      <div className="gbar-sep" />
      <span className="gbar-txt">{tradeDate}</span>
      <span className={canSubmit && !previewOnly ? "gbar-pill gbar-err" : "gbar-pill gbar-err gbar-lock"}>
        <LockIcon />
        {previewOnly || !canSubmit ? "no real orders" : "submit gate open"}
      </span>
      <span className="gbar-txt compactOnly">{status.message}</span>
    </div>
  );
}
