"use client";

import Link from "next/link";
import { KeyboardEvent, useCallback, useEffect, useMemo, useState } from "react";

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

function JsonDetails({ title, data }: { title: string; data: unknown }) {
  return (
    <details onClick={(event) => event.stopPropagation()}>
      <summary>{title}</summary>
      <pre className="tinyPre">{JSON.stringify(data, null, 2)}</pre>
    </details>
  );
}

function InlineList({ items }: { items: string[] }) {
  if (items.length === 0) {
    return <span className="muted">none</span>;
  }
  return (
    <span className="inlineList">
      {items.map((item) => (
        <Badge key={item}>{item}</Badge>
      ))}
    </span>
  );
}

export default function ScreenerPage() {
  const [status, setStatus] = useState<ApiStatus>("loading");
  const [message, setMessage] = useState("조회 중");
  const [results, setResults] = useState<ScreenerResult[]>([]);
  const [strategyCatalog, setStrategyCatalog] = useState<StrategyMetadata[]>([]);
  const [selectedStrategyNames, setSelectedStrategyNames] = useState<string[]>([]);
  const [filters, setFilters] = useState<Filters>(defaultFilters);
  const [selected, setSelected] = useState<ScreenerResult | null>(null);

  const defaultStrategyNames = useMemo(
    () => strategyCatalog.filter((strategy) => strategy.is_default).map((strategy) => strategy.name),
    [strategyCatalog]
  );
  const strategyOptions = useMemo(() => {
    const names = new Set(strategyCatalog.map((strategy) => strategy.name));
    results.forEach((result) => names.add(result.strategy_name));
    return Array.from(names);
  }, [results, strategyCatalog]);
  const selectedStrategy = useMemo(
    () => strategyCatalog.find((strategy) => strategy.name === selected?.strategy_name),
    [selected, strategyCatalog]
  );

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
        setSelected(data[0] ?? null);
        setStatus("ok");
        setMessage(`조회 완료: ${data.length}건`);
      } catch (error) {
        setStatus("error");
        setMessage(error instanceof Error ? error.message : "조회 실패");
        setResults([]);
        setSelected(null);
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

  function handleRowKeyDown(event: KeyboardEvent<HTMLTableRowElement>, row: ScreenerResult) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      setSelected(row);
    }
  }

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Phase 2</p>
          <h1>Screener</h1>
        </div>
        <nav className="nav">
          <Link href="/dashboard">Dashboard</Link>
          <Link href="/data">Data</Link>
          <Link href="/reports">Reports</Link>
          <Link href="/backtest">Backtest</Link>
          <Link href="/portfolio">Portfolio</Link>
          <Link href="/paper">Paper</Link>
          <Link href="/settings">Settings</Link>
        </nav>
        <span className={`status ${status}`}>{message}</span>
      </header>

      <section className="panel">
        <div className="sectionHeader strategyHeader">
          <div>
            <h2>Strategy Selection</h2>
            <p className="muted">{selectedStrategyNames.length} selected</p>
          </div>
          <div className="toolbar compactToolbar strategyActions">
            <button type="button" className="secondary" onClick={selectDefaultStrategies} disabled={defaultStrategyNames.length === 0}>
              Defaults
            </button>
            <button type="button" className="secondary" onClick={selectAllStrategies} disabled={strategyCatalog.length === 0}>
              All
            </button>
            <button type="button" onClick={runScreener} disabled={selectedStrategyNames.length === 0}>
              Run Screener
            </button>
          </div>
        </div>
        <StrategySelector selected={selectedStrategyNames} strategies={strategyCatalog} onChange={setSelectedStrategyNames} />

        <div className="filters">
          <label>
            strategy_name
            <select value={filters.strategyName} onChange={(event) => updateFilter("strategyName", event.target.value)}>
              <option value="">전체</option>
              {strategyOptions.map((strategy) => (
                <option key={strategy} value={strategy}>
                  {strategy}
                </option>
              ))}
            </select>
          </label>
          <label>
            passed
            <select value={filters.passed} onChange={(event) => updateFilter("passed", event.target.value)}>
              <option value="">전체</option>
              <option value="true">pass</option>
              <option value="false">fail</option>
            </select>
          </label>
          <label>
            grade
            <select value={filters.grade} onChange={(event) => updateFilter("grade", event.target.value)}>
              <option value="">전체</option>
              <option value="A">A</option>
              <option value="B">B</option>
              <option value="C">C</option>
              <option value="D">D</option>
            </select>
          </label>
          <label>
            검색
            <input value={filters.q} onChange={(event) => updateFilter("q", event.target.value)} placeholder="symbol 또는 name" />
          </label>
          <label>
            sort_by
            <select value={filters.sortBy} onChange={(event) => updateFilter("sortBy", event.target.value)}>
              <option value="total_score">total_score</option>
              <option value="reward_risk_ratio">reward_risk_ratio</option>
            </select>
          </label>
          <label>
            sort_dir
            <select value={filters.sortDir} onChange={(event) => updateFilter("sortDir", event.target.value)}>
              <option value="desc">desc</option>
              <option value="asc">asc</option>
            </select>
          </label>
          <button type="button" onClick={() => loadResults()}>
            Apply
          </button>
        </div>
      </section>

      <section className="grid wideLeft">
        <div className="tableWrap">
          <table>
            <thead>
              <tr>
                <th>trade_date</th>
                <th>symbol</th>
                <th>name</th>
                <th>strategy_name</th>
                <th>passed</th>
                <th>grade</th>
                <th>total_score</th>
                <th>entry</th>
                <th>stop</th>
                <th>target</th>
                <th>R/R</th>
                <th>qty</th>
                <th>reason</th>
                <th>details</th>
              </tr>
            </thead>
            <tbody>
              {results.map((result) => (
                <tr
                  key={`${result.trade_date}-${result.symbol}-${result.strategy_name}`}
                  className={selected === result ? "selectedRow" : ""}
                  role="button"
                  tabIndex={0}
                  onClick={() => setSelected(result)}
                  onKeyDown={(event) => handleRowKeyDown(event, result)}
                >
                  <td>{result.trade_date}</td>
                  <td>{result.symbol}</td>
                  <td>{result.name}</td>
                  <td>{result.strategy_name}</td>
                  <td>
                    <Badge tone={result.passed ? "pass" : "fail"}>{result.passed ? "pass" : "fail"}</Badge>
                  </td>
                  <td>
                    <Badge tone={`grade${result.grade}`}>{result.grade}</Badge>
                  </td>
                  <td>{formatNumber(result.total_score, 4)}</td>
                  <td>{formatNumber(result.entry_price, 2)}</td>
                  <td>{formatNumber(result.stop_price, 2)}</td>
                  <td>{formatNumber(result.target_price, 2)}</td>
                  <td>{formatNumber(result.reward_risk_ratio, 2)}</td>
                  <td>{formatNumber(result.position_size)}</td>
                  <td className="summaryCell">{result.reason_summary}</td>
                  <td>
                    <JsonDetails title="pass_flags" data={result.pass_flags_json} />
                    <JsonDetails title="failed_conditions" data={result.failed_conditions_json} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <aside className="detailPanel">
          <h2>Result Detail</h2>
          {selected ? (
            <>
              <div className="metricGrid">
                <div className="metric">
                  <span>symbol</span>
                  <strong>{selected.symbol}</strong>
                </div>
                <div className="metric">
                  <span>strategy</span>
                  <strong>{selected.strategy_name}</strong>
                </div>
                <div className="metric">
                  <span>grade</span>
                  <strong>{selected.grade}</strong>
                </div>
                <div className="metric">
                  <span>passed</span>
                  <strong>{selected.passed ? "pass" : "fail"}</strong>
                </div>
              </div>
              <p className="strongLine">{selected.reason_summary}</p>
              {selectedStrategy ? (
                <>
                  <h3>Strategy Metadata</h3>
                  <p className="muted">{selectedStrategy.description}</p>
                  <div className="metadataRows">
                    <div>
                      <span>required_fields</span>
                      <InlineList items={selectedStrategy.required_fields} />
                    </div>
                    <div>
                      <span>limitations</span>
                      <InlineList items={selectedStrategy.limitations} />
                    </div>
                  </div>
                </>
              ) : null}
              <h3>triggered_conditions</h3>
              <InlineList items={selected.triggered_conditions} />
              <h3>data_quality_flags</h3>
              <pre className="tinyPre">{JSON.stringify(selected.data_quality_flags, null, 2)}</pre>
              <h3>risk_metadata</h3>
              <pre className="tinyPre">{JSON.stringify(selected.risk_metadata, null, 2)}</pre>
              <h3>Risk Values</h3>
              <pre className="tinyPre">{JSON.stringify(selected.risk_details_json, null, 2)}</pre>
              <h3>Score Values</h3>
              <pre className="tinyPre">{JSON.stringify(selected.score_breakdown, null, 2)}</pre>
              <h3>pass_flags_json</h3>
              <pre className="tinyPre">{JSON.stringify(selected.pass_flags_json, null, 2)}</pre>
              <h3>failed_conditions_json</h3>
              <pre className="tinyPre">{JSON.stringify(selected.failed_conditions_json, null, 2)}</pre>
            </>
          ) : (
            <p className="muted">선택된 행이 없습니다.</p>
          )}
        </aside>
      </section>
    </main>
  );
}
