"use client";

import { formatNumber, type PaperHolding } from "../lib/api";

const PALETTE = [
  "#2563eb",
  "#16a34a",
  "#d97706",
  "#7c3aed",
  "#dc2626",
  "#0891b2",
  "#db2777",
  "#65a30d"
];

function Track({ pct, color }: { pct: number; color: string }) {
  const width = Math.max(0, Math.min(100, pct));
  return (
    <div
      style={{
        height: 8,
        borderRadius: 4,
        background: "rgba(148,163,184,0.25)",
        overflow: "hidden"
      }}
    >
      <div style={{ width: `${width}%`, height: "100%", background: color }} />
    </div>
  );
}

/**
 * 보유 종목 비중을 막대로 시각화. 평가금액 기준 비중 + 손익률 색상.
 * API 계약을 바꾸지 않고 기존 holdings 데이터만 사용한다.
 */
export function AllocationBars({ holdings }: { holdings: PaperHolding[] }) {
  const positive = holdings.filter((h) => (h.evaluation_amount ?? 0) > 0);
  const total = positive.reduce((sum, h) => sum + (h.evaluation_amount ?? 0), 0);

  if (!positive.length || total <= 0) {
    return <p className="muted">보유 종목 없음</p>;
  }

  const rows = [...positive].sort(
    (a, b) => (b.evaluation_amount ?? 0) - (a.evaluation_amount ?? 0)
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {rows.map((holding, index) => {
        const value = holding.evaluation_amount ?? 0;
        const pct = (value / total) * 100;
        const pnl = holding.profit_loss_rate ?? 0;
        const tone = pnl > 0 ? "pos" : pnl < 0 ? "neg" : "muted";
        return (
          <div key={holding.symbol} style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12 }}>
              <span>
                {holding.name || holding.symbol}
                <span className="muted"> ({holding.symbol})</span>
              </span>
              <span className={tone}>
                {pct.toFixed(1)}% · ₩{formatNumber(value)} · {pnl >= 0 ? "+" : ""}
                {pnl.toFixed(2)}%
              </span>
            </div>
            <Track pct={pct} color={PALETTE[index % PALETTE.length]} />
          </div>
        );
      })}
    </div>
  );
}
