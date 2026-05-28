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
    return "error";
  }
  return "loading";
}

function formatRatio(value: number | null | undefined) {
  return value === null || value === undefined ? "-" : formatNumber(value, 2);
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
  const breadthRegime = status.regime?.breadth_regime ?? "not_available";
  const sessionName = status.session?.session ?? "unknown";
  const previewOnly = status.broker?.preview_only ?? true;
  const canSubmit = status.broker?.can_submit ?? false;

  return (
    <div className="globalStatusBar" aria-label="Global market and safety status">
      <span className={`status ${regimeTone(regime)}`}>Regime: {regime}</span>
      <span className="globalStatusText">
        Breadth {formatRatio(status.regime?.breadth_score)} · {breadthRegime}
      </span>
      <span className="globalStatusText">KRX: {sessionName}</span>
      <span className={canSubmit ? "globalSafetyBadge danger" : "globalSafetyBadge"}>
        {previewOnly || !canSubmit ? "preview-only · no real orders" : "submit gate open"}
      </span>
      <span className="globalStatusText compactOnly">{status.message}</span>
    </div>
  );
}
