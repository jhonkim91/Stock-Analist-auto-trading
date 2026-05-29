"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { callApi, formatNumber, formatPercent, type ApiStatus } from "../../lib/api";

type SearchRow = {
  symbol: string;
  name: string;
  sector: string;
  market: string;
  exchange: string;
  latest_close: number | null;
  latest_score: number | null;
  latest_grade: string | null;
  latest_passed: boolean | null;
};

type SearchResponse = {
  results: SearchRow[];
  network_call_performed: boolean;
};

type MarketQuote = {
  available: boolean;
  trade_date?: string;
  close?: number;
  change?: number | null;
  change_pct?: number | null;
  volume?: number;
  turnover_value?: number;
};

type SymbolDetail = {
  symbol: {
    symbol: string;
    name: string;
    sector: string;
    industry: string;
    exchange: string;
  };
  quote: MarketQuote;
  indicator: {
    sma20?: number | null;
    sma50?: number | null;
    relative_strength_score?: number | null;
    atr20_pct?: number | null;
  } | null;
  screener: Array<{
    strategy_name: string;
    passed: boolean;
    grade: string;
    total_score: number;
    reward_risk_ratio: number | null;
    reason_summary: string;
  }>;
};

type ChartBar = {
  trade_date: string;
  close: number;
  volume: number;
  sma20?: number | null;
  sma50?: number | null;
};

type ChartResponse = {
  symbol: string;
  name: string;
  bars: ChartBar[];
  network_call_performed: boolean;
};

type RankingRow = {
  rank: number;
  symbol: string;
  name: string;
  metric_value: number | null;
  strategy_name?: string;
  passed?: boolean;
  grade?: string;
  reason_summary?: string;
};

type RankingResponse = {
  metric: string;
  trade_date: string | null;
  items: RankingRow[];
  network_call_performed: boolean;
};

function PageIcon() {
  return (
    <svg className="pageTitleIcon" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 18 10 9l4 5 6-8" />
      <path d="M4 20h16" />
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

function Kpi({ label, tone, value }: { label: string; tone?: "pos" | "neg" | "muted"; value: string }) {
  return (
    <div className="kpi">
      <div className="kpi-lbl">{label}</div>
      <div className={`kpi-val ${tone ?? ""}`}>{value}</div>
    </div>
  );
}

function LineChart({ bars }: { bars: ChartBar[] }) {
  const points = useMemo(() => {
    if (bars.length === 0) {
      return "";
    }
    const closes = bars.map((bar) => bar.close);
    const min = Math.min(...closes);
    const max = Math.max(...closes);
    const span = max - min || 1;
    return bars
      .map((bar, index) => {
        const x = bars.length === 1 ? 0 : (index / (bars.length - 1)) * 100;
        const y = 100 - ((bar.close - min) / span) * 86 - 7;
        return `${x},${y}`;
      })
      .join(" ");
  }, [bars]);
  const maxVolume = Math.max(...bars.map((bar) => bar.volume), 1);

  return (
    <svg viewBox="0 0 100 122" role="img" aria-label="종가와 거래량 차트" style={{ width: "100%", height: 260 }}>
      <rect x="0" y="0" width="100" height="122" fill="var(--color-background-secondary)" rx="2" />
      <polyline fill="none" points={points} stroke="#1d9e75" strokeWidth="1.4" vectorEffect="non-scaling-stroke" />
      {bars.map((bar, index) => {
        const x = bars.length === 1 ? 0 : (index / (bars.length - 1)) * 98;
        const height = Math.max((bar.volume / maxVolume) * 17, 1);
        return <rect fill="#b9c6bd" height={height} key={`${bar.trade_date}-${index}`} width="0.55" x={x} y={118 - height} />;
      })}
    </svg>
  );
}

export default function MarketPage() {
  const [status, setStatus] = useState<ApiStatus>("loading");
  const [message, setMessage] = useState("조회 중");
  const [query, setQuery] = useState("KR009");
  const [symbol, setSymbol] = useState("KR009");
  const [searchRows, setSearchRows] = useState<SearchRow[]>([]);
  const [detail, setDetail] = useState<SymbolDetail | null>(null);
  const [chart, setChart] = useState<ChartResponse | null>(null);
  const [rankings, setRankings] = useState<RankingResponse | null>(null);

  const loadMarket = useCallback(
    async (nextSymbol = symbol, nextQuery = query, showLoading = true) => {
      if (showLoading) {
        setStatus("loading");
        setMessage("조회 중");
      }
      try {
        const [search, detailData, chartData, rankingData] = await Promise.all([
          callApi<SearchResponse>(`/api/market-realtime/search?q=${encodeURIComponent(nextQuery)}&limit=20`),
          callApi<SymbolDetail>(`/api/market-realtime/symbols/${encodeURIComponent(nextSymbol)}`),
          callApi<ChartResponse>(`/api/market-realtime/symbols/${encodeURIComponent(nextSymbol)}/chart?limit=120`),
          callApi<RankingResponse>("/api/market-realtime/rankings?metric=total_score&limit=20")
        ]);
        setSearchRows(search.results);
        setDetail(detailData);
        setChart(chartData);
        setRankings(rankingData);
        setStatus("ok");
        setMessage("조회 완료");
      } catch (error) {
        setStatus("error");
        setMessage(error instanceof Error ? error.message : "조회 실패");
      }
    },
    [query, symbol]
  );

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadMarket(symbol, query, false);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadMarket, query, symbol]);

  function selectSymbol(nextSymbol: string) {
    setSymbol(nextSymbol);
    setQuery(nextSymbol);
    void loadMarket(nextSymbol, nextSymbol);
  }

  const quote = detail?.quote;
  const changeTone = (quote?.change ?? 0) >= 0 ? "pos" : "neg";

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <PageIcon />
          <h1>Market</h1>
        </div>
        <div className="topbar-actions" title={message}>
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="symbol / name" />
          <button type="button" className="primary" onClick={() => loadMarket(symbol, query)}>
            Search
          </button>
          <span className={`status ${status}`}>{message}</span>
        </div>
      </header>

      <section className="scroll">
        <div className="g4">
          <Kpi label="close" value={formatNumber(quote?.close)} tone={changeTone} />
          <Kpi label="change" value={formatNumber(quote?.change, 2)} tone={changeTone} />
          <Kpi label="change_pct" value={formatPercent(quote?.change_pct)} tone={changeTone} />
          <Kpi label="volume" value={formatNumber(quote?.volume)} />
        </div>

        <div className="g2">
          <article>
            <div className="card-hd">
              <span className="card-title">{detail?.symbol.name ?? symbol}</span>
              <span className="bdg bdg-info">{detail?.symbol.symbol ?? symbol}</span>
            </div>
            <StatRow label="sector" value={detail?.symbol.sector ?? "-"} />
            <StatRow label="industry" value={detail?.symbol.industry ?? "-"} />
            <StatRow label="exchange" value={detail?.symbol.exchange ?? "-"} />
            <StatRow label="trade_date" value={quote?.trade_date ?? "-"} />
            <StatRow label="sma20" value={formatNumber(detail?.indicator?.sma20)} />
            <StatRow label="rs_score" value={formatNumber(detail?.indicator?.relative_strength_score, 2)} />
          </article>

          <article>
            <div className="card-hd">
              <span className="card-title">chart</span>
              <span className="muted">{chart?.bars.at(-1)?.trade_date ?? "-"}</span>
            </div>
            <LineChart bars={chart?.bars ?? []} />
          </article>
        </div>

        <div className="g2">
          <article className="mockTableCard">
            <div className="sectionHeader">
              <h2>검색 결과</h2>
              <span className="muted">{searchRows.length} rows</span>
            </div>
            <div className="tableWrap">
              <table className="tbl">
                <thead>
                  <tr>
                    <th>symbol</th>
                    <th>name</th>
                    <th>sector</th>
                    <th>score</th>
                    <th>grade</th>
                  </tr>
                </thead>
                <tbody>
                  {searchRows.map((row) => (
                    <tr key={row.symbol} className={row.symbol === symbol ? "selectedRow" : ""}>
                      <td>
                        <button type="button" className="secondary" onClick={() => selectSymbol(row.symbol)}>
                          {row.symbol}
                        </button>
                      </td>
                      <td>{row.name}</td>
                      <td>{row.sector}</td>
                      <td>{formatNumber(row.latest_score, 2)}</td>
                      <td>{row.latest_grade ?? "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </article>

          <article className="mockTableCard">
            <div className="sectionHeader">
              <h2>랭킹</h2>
              <span className="muted">{rankings?.trade_date ?? "-"}</span>
            </div>
            <div className="tableWrap">
              <table className="tbl">
                <thead>
                  <tr>
                    <th>rank</th>
                    <th>symbol</th>
                    <th>strategy</th>
                    <th>metric</th>
                    <th>state</th>
                  </tr>
                </thead>
                <tbody>
                  {(rankings?.items ?? []).map((row) => (
                    <tr key={`${row.rank}-${row.symbol}-${row.strategy_name ?? ""}`}>
                      <td>{row.rank}</td>
                      <td>
                        <button type="button" className="secondary" onClick={() => selectSymbol(row.symbol)}>
                          {row.symbol}
                        </button>
                      </td>
                      <td>{row.strategy_name ?? "-"}</td>
                      <td>{formatNumber(row.metric_value, 2)}</td>
                      <td>
                        <span className={`bdg ${row.passed ? "bdg-ok" : "bdg-warn"}`}>{row.grade ?? "-"}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </article>
        </div>

        <article>
          <div className="sectionHeader">
            <h2>strategy signals</h2>
            <span className="bdg bdg-fail">실거래 아님</span>
          </div>
          <div className="tableWrap">
            <table className="tbl">
              <thead>
                <tr>
                  <th>strategy</th>
                  <th>grade</th>
                  <th>score</th>
                  <th>R/R</th>
                  <th>reason</th>
                </tr>
              </thead>
              <tbody>
                {(detail?.screener ?? []).map((row) => (
                  <tr key={row.strategy_name}>
                    <td>{row.strategy_name}</td>
                    <td>{row.grade}</td>
                    <td>{formatNumber(row.total_score, 2)}</td>
                    <td>{formatNumber(row.reward_risk_ratio, 2)}</td>
                    <td>{row.reason_summary}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>
      </section>
    </main>
  );
}
