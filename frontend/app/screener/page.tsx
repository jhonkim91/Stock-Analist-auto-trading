"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { StrategySelector } from "../../components/strategy-selector";
import { callApi, formatNumber, type ApiStatus, type ScreenerResult, type StrategyMetadata } from "../../lib/api";

type Filters = {
  strategyName: string;
  passed: string;
  grade: string;
  q: string;
  sortBy: string;
  sortDir: string;
};

const defaultFilters: Filters = {
  strategyName: "",
  passed: "",
  grade: "",
  q: "",
  sortBy: "total_score",
  sortDir: "desc"
};

function Badge({ children, tone }: { children: React.ReactNode; tone?: string }) {
  return <span className={`badge ${tone ?? ""}`}>{children}</span>;
}

function PageIcon() {
  return (
    <svg className="pageTitleIcon" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 6h16" />
      <path d="M7 12h10" />
      <path d="M10 18h4" />
    </svg>
  );
}

export default function ScreenerPage() {
  const [status, setStatus] = useState<ApiStatus>("loading");
  const [message, setMessage] = useState("조회 중");
  const [results, setResults] = useState<ScreenerResult[]>([]);
  const [strategyCatalog, setStrategyCatalog] = useState<StrategyMetadata[]>([]);
  const [selectedStrategyNames, setSelectedStrategyNames] = useState<string[]>([]);
  const [filters, setFilters] = useState<Filters>(defaultFilters);

  const defaultStrategyNames = useMemo(
    () => strategyCatalog.filter((strategy) => strategy.is_default).map((strategy) => strategy.name),
    [strategyCatalog]
  );
  const strategyOptions = useMemo(() => {
    const names = new Set(strategyCatalog.map((strategy) => strategy.name));
    results.forEach((result) => names.add(result.strategy_name));
    return Array.from(names);
  }, [results, strategyCatalog]);
  const passedCount = useMemo(() => results.filter((result) => result.passed).length, [results]);

  const buildPath = useCallback(() => {
    const params = new URLSearchParams({ limit: "100" });
    if (filters.strategyName) {
      params.set("strategy_name", filters.strategyName);
    }
    if (filters.passed) {
      params.set("passed", filters.passed);
    }
    if (filters.grade) {
      params.set("grade", filters.grade);
    }
    if (filters.q) {
      params.set("q", filters.q);
    }
    if (filters.sortBy) {
      params.set("sort_by", filters.sortBy);
    }
    if (filters.sortDir) {
      params.set("sort_dir", filters.sortDir);
    }
    return `/api/screener/results?${params.toString()}`;
  }, [filters]);

  const loadResults = useCallback(
    async (showLoading = true) => {
      if (showLoading) {
        setStatus("loading");
        setMessage("조회 중");
      }
      try {
        const data = await callApi<ScreenerResult[]>(buildPath());
        setResults(data);
        setStatus("ok");
        setMessage(`조회 완료: ${data.length}건`);
      } catch (error) {
        setStatus("error");
        setMessage(error instanceof Error ? error.message : "조회 실패");
        setResults([]);
      }
    },
    [buildPath]
  );

  const loadStrategies = useCallback(async () => {
    try {
      const data = await callApi<StrategyMetadata[]>("/api/screener/strategies");
      const defaultNames = data.filter((strategy) => strategy.is_default).map((strategy) => strategy.name);
      const validNames = new Set(data.map((strategy) => strategy.name));
      setStrategyCatalog(data);
      setSelectedStrategyNames((prev) => {
        const stillValid = prev.filter((name) => validNames.has(name));
        return stillValid.length > 0 ? stillValid : defaultNames;
      });
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "strategy metadata load failed");
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadResults(false);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadResults]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadStrategies();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadStrategies]);

  function updateFilter(key: keyof Filters, value: string) {
    setFilters((prev) => ({ ...prev, [key]: value }));
  }

  function selectDefaultStrategies() {
    setSelectedStrategyNames(defaultStrategyNames);
  }

  function selectAllStrategies() {
    setSelectedStrategyNames(strategyCatalog.map((strategy) => strategy.name));
  }

  async function runScreener() {
    if (selectedStrategyNames.length === 0) {
      setStatus("error");
      setMessage("select at least one strategy");
      return;
    }
    setStatus("loading");
    setMessage("screener run in progress");
    try {
      const data = await callApi<{ rows: number; passed: number; strategies: string[] }>("/api/screener/run", {
        method: "POST",
        body: JSON.stringify({ strategies: selectedStrategyNames })
      });
      await loadResults(false);
      setStatus("ok");
      setMessage(`run complete: ${data.rows} rows / ${data.strategies.length} strategies`);
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "screener run failed");
    }
  }

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <PageIcon />
          <h1>Screener</h1>
        </div>
        <div className="topbar-actions" title={message}>
          <button type="button" className="secondary" onClick={selectDefaultStrategies} disabled={defaultStrategyNames.length === 0}>
            Defaults
          </button>
          <button type="button" className="secondary" onClick={selectAllStrategies} disabled={strategyCatalog.length === 0}>
            All
          </button>
          <button type="button" className="primary" onClick={runScreener} disabled={selectedStrategyNames.length === 0}>
            Run Screener
          </button>
        </div>
      </header>

      <section className="scroll">
        <div className="sec-lbl">
          Strategy selection <span className="muted">— {selectedStrategyNames.length} selected</span>
        </div>
        <StrategySelector selected={selectedStrategyNames} strategies={strategyCatalog} onChange={setSelectedStrategyNames} />

        <div className="filter-row mockFilters">
            <select value={filters.strategyName} onChange={(event) => updateFilter("strategyName", event.target.value)}>
              <option value="">전체 전략</option>
              {strategyOptions.map((strategy) => (
                <option key={strategy} value={strategy}>
                  {strategy}
                </option>
              ))}
            </select>
            <select value={filters.passed} onChange={(event) => updateFilter("passed", event.target.value)}>
              <option value="">pass/fail 전체</option>
              <option value="true">pass</option>
              <option value="false">fail</option>
            </select>
            <select value={filters.grade} onChange={(event) => updateFilter("grade", event.target.value)}>
              <option value="">grade 전체</option>
              <option value="A">A</option>
              <option value="B">B</option>
              <option value="C">C</option>
              <option value="D">D</option>
            </select>
            <input value={filters.q} onChange={(event) => updateFilter("q", event.target.value)} placeholder="symbol 검색" />
            <select value={filters.sortBy} onChange={(event) => updateFilter("sortBy", event.target.value)}>
              <option value="total_score">total_score desc</option>
              <option value="reward_risk_ratio">reward_risk_ratio desc</option>
            </select>
            <select value={filters.sortDir} onChange={(event) => updateFilter("sortDir", event.target.value)}>
              <option value="desc">desc</option>
              <option value="asc">asc</option>
            </select>
          <button type="button" onClick={() => loadResults()}>
            Apply
          </button>
        </div>

        <article className="mockTableCard">
          <div className="sectionHeader">
            <h2>
              결과 — {results.length} evaluated · {passedCount} passed
            </h2>
            <span className="muted">{results[0]?.trade_date ?? "-"}</span>
          </div>
          <div className="tableWrap">
          <table className="tbl">
            <thead>
              <tr>
                <th style={{ width: "12%" }}>종목</th>
                <th style={{ width: "24%" }}>전략</th>
                <th style={{ width: "9%" }}>grade</th>
                <th style={{ width: "10%" }}>score</th>
                <th style={{ width: "9%" }}>R/R</th>
                <th style={{ width: "21%" }}>triggered</th>
                <th style={{ width: "8%" }}>data</th>
                <th style={{ width: "7%" }}>상태</th>
              </tr>
            </thead>
            <tbody>
              {results.map((result) => (
                <tr key={`${result.trade_date}-${result.symbol}-${result.strategy_name}`} className={result.passed ? "selectedRow" : ""}>
                  <td>{result.symbol}</td>
                  <td>{result.strategy_name}</td>
                  <td>
                    <Badge tone={`grade${result.grade}`}>{result.grade}</Badge>
                  </td>
                  <td>{formatNumber(result.total_score, 2)}</td>
                  <td>{formatNumber(result.reward_risk_ratio, 2)}</td>
                  <td className="summaryCell">{result.triggered_conditions.join(", ") || result.reason_summary}</td>
                  <td>
                    <Badge tone={Object.keys(result.data_quality_flags ?? {}).length ? "gradeC" : "pass"}>
                      {Object.keys(result.data_quality_flags ?? {}).length ? "check" : "OK"}
                    </Badge>
                  </td>
                  <td>
                    <Badge tone={result.passed ? "pass" : "fail"}>{result.passed ? "pass" : "fail"}</Badge>
                  </td>
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
